from __future__ import unicode_literals

import random
import six
import string
import time
import threading
from collections import deque


# TODO: Ensure thread safety

class ChannelLayer(object):
    """
    In memory channel layer object; a single one is instantiated as
    "channel_layer" for easy shared use. Only allows global capacity config.
    """

    def __init__(self, expiry=60, group_expiry=86400, capacity=100):
        self.expiry = expiry
        self.capacity = capacity
        self.group_expiry = group_expiry
        self.thread_lock = threading.Lock()
        # Storage for state
        self._channels = {}
        self._groups = {}

    ### ASGI API ###

    extensions = ["groups", "flush"]

    class ChannelFull(Exception):
        pass

    class MessageTooLarge(Exception):
        pass

    def send(self, channel, message):
        # Make sure the message is a dict at least (no deep inspection)
        assert isinstance(message, dict), "message is not a dict"
        # Channel name should be text
        assert isinstance(channel, six.text_type), "%s is not text" % channel
        # Add it to a deque for the appropriate channel name
        with self.thread_lock:
            queue = self._channels.setdefault(channel, deque())
            if len(queue) >= self.capacity:
                raise self.ChannelFull(channel)
            queue.append((
                time.time() + self.expiry,
                message,
            ))

    def receive_many(self, channels, block=False):
        # Shuffle channel names to ensure approximate global ordering
        channels = list(channels)
        random.shuffle(channels)
        # Expire old messages
        self._clean_expired()
        # Go through channels and see if a message is available:
        with self.thread_lock:
            for channel in channels:
                if self._channels.get(channel, None):
                    _, message = self._channels[channel].popleft()
                    return channel, message
        # No message available
        return None, None

    def new_channel(self, pattern):
        assert isinstance(pattern, six.text_type)
        assert pattern.endswith("!"), "New channel pattern must end with !"
        # Keep making channel names till one isn't present.
        while True:
            random_string = "".join(random.choice(string.ascii_letters) for i in range(8))
            new_name = pattern + random_string
            # Basic check for existence
            if new_name not in self._channels:
                return new_name

    ### ASGI Group API ###

    def group_add(self, group, channel):
        # Both should be text
        assert isinstance(group, six.text_type), "%s is not text" % group
        assert isinstance(channel, six.text_type), "%s is not text" % channel
        # Add to group dict
        with self.thread_lock:
            self._groups.setdefault(group, {})
            self._groups[group][channel] = time.time()

    def group_discard(self, group, channel):
        # Both should be text
        assert isinstance(group, six.text_type), "%s is not text" % group
        assert isinstance(channel, six.text_type), "%s is not text" % channel
        # Remove from group set
        with self.thread_lock:
            if group in self._groups:
                if channel in self._groups[group]:
                    del self._groups[group][channel]
                if not self._groups[group]:
                    del self._groups[group]

    def send_group(self, group, message):
        # Check types
        assert isinstance(message, dict), "message is not a dict"
        assert isinstance(group, six.text_type), "%s is not text" % group
        # Run clean
        self._clean_expired()
        # Send to each channel
        for channel in self._groups.get(group, set()):
            try:
                self.send(channel, message)
            except self.ChannelFull:
                pass

    ### ASGI Flush API ###

    def flush(self):
        self._channels = {}
        self._groups = {}

    ### Expire cleanup ###

    def _clean_expired(self):
        """
        Goes through all messages and groups and removes those that are expired.
        Any channel with an expired message is removed from all groups.
        """
        with self.thread_lock:
            # Channel cleanup
            for channel, queue in list(self._channels.items()):
                remove = False
                # See if it's expired
                while queue and queue[0][0] < time.time():
                    queue.popleft()
                    remove = True
                # Any removal prompts group discard
                if remove:
                    self._remove_from_groups(channel)
                # Is the channel now empty and needs deleting?
                if not queue:
                    del self._channels[channel]
            # Group cleanup
            for group, channels in list(self._groups.items()):
                for channel, added in list(channels.items()):
                    if added < (time.time() - self.group_expiry):
                        del self._groups[group][channel]
                        if not self._groups[group]:
                            del self._groups[group]

    def _remove_from_groups(self, channel):
        """
        Removes a channel from all groups. Used when a message on it expires.
        """
        for channels in self._groups.values():
            if channel in channels:
                del channels[channel]

# Global single instance for easy use
channel_layer = ChannelLayer()
