from __future__ import unicode_literals, division

import argparse
import os
import time
import sys
import importlib
import string
import random


class Benchmarker(object):
    """
    Class that does standard-ish benchmarking of channel layers
    (rather than on a protocol that runs over a channel layer).

    Uses two processes to measure the throughput, using the
    local computer time to detect latency.
    """

    def __init__(self, channel_layer, warmup=100, n=1000, cooldown=3, channel_name="benchmark"):
        self.channel_layer = channel_layer
        self.channel_name = channel_name
        self.warmup = warmup
        self.n = n
        self.cooldown = cooldown
        self.tag = "".join(random.choice(string.ascii_letters) for i in range(10))

    @classmethod
    def cli(cls):
        parser = argparse.ArgumentParser(
            description="Channel layer benchmark tool",
        )
        parser.add_argument(
            'channel_layer',
            help='The ASGI channel layer instance to use as path.to.module:instance.path',
        )
        parser.add_argument(
            '-c',
            '--channel',
            type=str,
            help='Name of the channel to benchmark on',
            default="benchmark",
        )
        parser.add_argument(
            '-n',
            '--number',
            type=int,
            help='Number of messages to send',
            default=1000,
        )
        args = parser.parse_args()

        # Import channel layer
        sys.path.insert(0, ".")
        module_path, object_path = args.channel_layer.split(":", 1)
        channel_layer = importlib.import_module(module_path)
        for bit in object_path.split("."):
            channel_layer = getattr(channel_layer, bit)

        self = cls(channel_layer, n=args.number, channel_name=args.channel)
        self.run()

    def run(self):
        """
        Runs the benchmarker. Splits into two processes; one that does
        run_sender, which continuously sends as many messages as possible
        down a channel, and the other which does run_receiver, which receives
        messages and calculates stats.
        """
        self.child_pid = os.fork()
        if self.child_pid:
            # We are the parent.
            print("Running receiver...")
            self.run_receiver()
        else:
            # We are the child
            print("Running sender...")
            self.run_sender()
            print("Sender complete.")
            sys.exit(0)

    def run_sender(self):
        """
        Continuously tries to send information down the channel layer
        """
        for _ in range(self.warmup):
            self.wait_send({"warmup": True})
        for i in range(self.n):
            if not (i % 100):
                print("Sent %s" % i)
            self.wait_send({"sent": time.time(), "number": i, "tag": self.tag})

    def wait_send(self, message):
        """
        Sends a message onto our test channel, waiting if ChannelFull is raised.
        """
        while True:
            try:
                self.channel_layer.send(self.channel_name, message)
            except self.channel_layer.ChannelFull:
                continue
            else:
                break

    def run_receiver(self):
        """
        Receives the messages and does timing. Stops every so often to see if
        the sender process has exited.
        """
        self.received = []
        self.stop_time = None
        while True:
            # Check to see if we need to stop
            if self.stop_time:
                if self.stop_time < time.time():
                    break
            else:
                if os.waitpid(self.child_pid, os.WNOHANG)[0]:
                    print("Sender exited, scheduling receiver shutdown")
                    self.stop_time = time.time() + self.cooldown
            # Receive and re-loop
            channel, message = self.channel_layer.receive([self.channel_name], block=False)
            if channel is None:
                continue
            # Drop any warmups
            if "warmup" in message:
                continue
            # Check the tag to make sure it's us
            if message["tag"] != self.tag:
                raise RuntimeError("Tag mismatch on receive - make sure the channel layer is clean (%s != %s)" % (
                    self.tag,
                    message["tag"],
                ))
            self.received.append((message["number"], message["sent"], time.time()))
            if len(self.received) % 100 == 0 and len(self.received):
                print("Received %s" % len(self.received))
        # Calculate what's missing
        print("Receiver complete. Calculating stats...")
        self.seen_numbers = set()
        self.latencies = []
        self.sent_times = []
        self.received_times = []
        for number, sent, received in self.received:
            if number in self.seen_numbers:
                raise ValueError("Multiple receive detected! Got number %s more than once" % number)
            else:
                self.seen_numbers.add(number)
            self.latencies.append(received - sent)
            self.received_times.append(received)
            self.sent_times.append(sent)
        self.first_send = min(self.sent_times)
        self.last_send = max(self.sent_times)
        self.first_receive = min(self.received_times)
        self.last_receive = max(self.received_times)
        # Final stats
        print()
        print("Received: %s/%s (%.1f%%)" % (
            len(self.seen_numbers),
            self.n,
            (len(self.seen_numbers) / self.n) * 100,
        ))
        print("Latency mean: %.4f  median: %.4f  10%%: %.4f  90%%: %.4f" % (
            self.mean(self.latencies),
            self.percentile(self.latencies, 0.5),
            self.percentile(self.latencies, 0.1),
            self.percentile(self.latencies, 0.9),
        ))
        print("Send throughput: %.1f/s" % (len(self.seen_numbers) / (self.last_send - self.first_send)))
        print("Receive throughput: %.1f/s" % (len(self.seen_numbers) / (self.last_receive - self.first_receive)))

    def mean(self, values):
        """
        Returns the mean of a list.
        """
        return sum(values) / len(values)

    def percentile(self, values, cutoff):
        """
        Returns the cutoff-percentile, with cutoff as a float. E.g. 0.75 means
        75th percentile. Not super accurate but quite close.
        """
        index = int(len(values) * cutoff)
        return sorted(values)[index]
