from __future__ import unicode_literals
import time
from asgiref.inmemory import ChannelLayer
from asgiref.conformance import ConformanceTestCase


class InMemoryLayerTests(ConformanceTestCase):
    channel_layer = ChannelLayer(expiry=1, group_expiry=2, capacity=5)
    expiry_delay = 1.1
    capacity_limit = 5

    def test_group_message_eviction(self):
        """
        Tests that when messages expire, group expiry also occurs.
        """
        # Add things to a group and send a message that should expire
        self.channel_layer.group_add("tgme_group", "tgme_test")
        self.channel_layer.send_group("tgme_group", {"value": "blue"})
        # Wait message expiry plus a tiny bit (must sum to less than group expiry)
        time.sleep(1.2)
        # Send new message to group, ensure message never arrives
        self.channel_layer.send_group("tgme_group", {"value": "blue"})
        channel, message = self.channel_layer.receive(["tgme_test"])
        self.assertIs(channel, None)
        self.assertIs(message, None)
