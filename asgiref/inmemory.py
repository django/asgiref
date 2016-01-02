from __future__ import unicode_literals

import random
import six
import string
import time
from collections import deque


# TODO: Ensure thread safety

class ChannelLayer(object):
    """
    In memory channel layer object; a single one is instantiated as
    "channel_layer" for easy shared use.
    """

    # Message expiry time, in seconds
    message_expiry = 60

    # Storage for state
    _channels = {}
    _groups = {}

    ### ASGI API ###

    extensions = ["groups"]

    class MessageTooLarge(Exception):
        pass

    def send(self, channel, message):
        # Make sure the message is a dict at least (no deep inspection)
        assert isinstance(message, dict), "message is not a dict"
        # Channel name should be bytes
        assert isinstance(channel, six.binary_type), "%s is not bytes" % channel
        # Add it to a deque for the appropriate channel name
        self._channels.setdefault(channel, deque()).append((time.time(), message))

    def receive_many(self, channels, block=False):
        # Shuffle channel names to ensure approximate global ordering
        channels = list(channels)
        random.shuffle(channels)
        # Go through channels and see if a message is available:
        for channel in channels:
            assert isinstance(channel, six.binary_type), "%s is not bytes" % channel
            # Loop through messages until one isn't expired or there are none
            while True:
                try:
                    created, message = self._channels[channel].popleft()
                    # Did it expire?
                    if (time.time() - created) > self.message_expiry:
                        continue
                    # Is the channel now empty and needs deleting?
                    if not self._channels[channel]:
                        del self._channels[channel]
                    # Return retrieved message
                    return channel, message
                except (IndexError, KeyError):
                    break
        # No message available
        return None, None

    def new_channel(self, pattern):
        assert isinstance(pattern, six.binary_type)
        # Keep making channel names till one isn't present.
        while True:
            random_string = b"".join(random.choice(string.ascii_letters.encode("ascii")) for i in range(8))
            new_name = pattern.replace(b"?", random_string)
            # Basic check for existence
            if new_name not in self._channels:
                return new_name

    ### ASGI Group API ###

    group_expiry = 120

    def group_add(self, group, channel):
        raise NotImplementedError()

    def group_discard(self, group, channel):
        raise NotImplementedError()

    def send_group(self, group, message):
        raise NotImplementedError()


# Global single instance for easy use
channel_layer = ChannelLayer()
