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

    def __init__(self, expiry=60):
        self.expiry = expiry
        # Storage for state
        self._channels = {}
        self._groups = {}

    ### ASGI API ###

    extensions = ["groups", "flush"]

    class MessageTooLarge(Exception):
        pass

    def send(self, channel, message):
        # Make sure the message is a dict at least (no deep inspection)
        assert isinstance(message, dict), "message is not a dict"
        # Channel name should be text
        assert isinstance(channel, six.text_type), "%s is not text" % channel
        # Add it to a deque for the appropriate channel name
        self._channels.setdefault(channel, deque()).append((
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
        for channel in channels:
            if self._channels.get(channel, None):
                _, message = self._channels[channel].popleft()
                return channel, message
        # No message available
        return None, None

    def new_channel(self, pattern):
        assert isinstance(pattern, six.text_type)
        # Keep making channel names till one isn't present.
        while True:
            random_string = "".join(random.choice(string.ascii_letters) for i in range(8))
            new_name = pattern.replace("?", random_string)
            # Basic check for existence
            if new_name not in self._channels:
                return new_name

    ### ASGI Group API ###

    def group_add(self, group, channel):
        # Both should be text
        assert isinstance(group, six.text_type), "%s is not text" % group
        assert isinstance(channel, six.text_type), "%s is not text" % channel
        # Add to group set
        self._groups[group] = self._groups.get(group, set()).union({channel})

    def group_discard(self, group, channel):
        # Both should be text
        assert isinstance(group, six.text_type), "%s is not text" % group
        assert isinstance(channel, six.text_type), "%s is not text" % channel
        # Remove from group set
        if group in self._groups:
            self._groups[group].discard(channel)
            if not self._groups[group]:
                del self._groups[group]

    def send_group(self, group, message):
        # Check types
        assert isinstance(message, dict), "message is not a dict"
        assert isinstance(group, six.text_type), "%s is not text" % group
        # Send to each channel
        for channel in self._groups.get(group, set()):
            self.send(channel, message)

    ### ASGI Flush API ###

    def flush(self):
        self._channels = {}
        self._groups = {}

    ### Expire cleanup ###

    def _clean_expired(self):
        """
        Goes through all messages and removes those that are expired.
        Any channel with an expired message is removed from all groups.
        """
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

    def _remove_from_groups(self, channel):
        """
        Removes a channel from all groups. Used when a message on it expires.
        """
        for  channels in self._groups.values():
            channels.discard(channel)

# Global single instance for easy use
channel_layer = ChannelLayer()
