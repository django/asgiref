"""
ASGI spec conformance test suite.

Calling the functions with an ASGI channel layer instance will return you a
single TestCase instance that checks for conformity on that instance.

You MUST also pass along an expiry value to the sets of tests, to allow the
suite to wait correctly for expiry. It's suggested you configure the layer
for 1-second expiry during tests, and use a 1.1 second expiry delay.

The channel layers should be empty to start with, and discarded after use,
as they'll be full of test data. If a layer supports the "flush" extension,
it'll be flushed before every test.
"""

from __future__ import unicode_literals
import six
import time
import unittest


def make_tests(channel_layer, expiry_delay):

    class LayerTestCase(unittest.TestCase):
        """
        Tests that core ASGI functionality is maintained.
        """

        def setUp(self):
            if "flush" in channel_layer.extensions:
                channel_layer.flush()

        def test_send_recv(self):
            """
            Tests that channels can send and receive messages right.
            """
            channel_layer.send("sr_test", {"value": "blue"})
            channel_layer.send("sr_test", {"value": "green"})
            channel_layer.send("sr_test2", {"value": "red"})
            # Get just one first
            channel, message = channel_layer.receive_many(["sr_test"])
            self.assertEqual(channel, "sr_test")
            self.assertEqual(message, {"value": "blue"})
            # And the second
            channel, message = channel_layer.receive_many(["sr_test"])
            self.assertEqual(channel, "sr_test")
            self.assertEqual(message, {"value": "green"})
            # And the other channel with multi select
            channel, message = channel_layer.receive_many(["sr_test", "sr_test2"])
            self.assertEqual(channel, "sr_test2")
            self.assertEqual(message, {"value": "red"})

        def test_unicode_channel_name(self):
            """
            Makes sure channel names can handle unicode
            """
            channel_layer.send("\u00a3_test", {"value": "blue"})
            # Get just one first
            channel, message = channel_layer.receive_many(["\u00a3_test"])
            self.assertEqual(channel, "\u00a3_test")
            self.assertEqual(message, {"value": "blue"})

        def test_message_expiry(self):
            """
            Tests that messages expire correctly.
            """
            channel_layer.send("me_test", {"value": "blue"})
            time.sleep(expiry_delay)
            channel, message = channel_layer.receive_many(["me_test"])
            self.assertIs(channel, None)
            self.assertIs(message, None)

        def test_new_channel(self):
            """
            Tests that new channel names are made correctly.
            """
            pattern = "test.?.foo.?"
            name1 = channel_layer.new_channel(pattern)
            self.assertIsInstance(name1, six.text_type)
            # Send a message and make sure new_channel on second pass changes
            channel_layer.send(name1, {"value": "blue"})
            name2 = channel_layer.new_channel(pattern)
            # Make sure the two ?s are replaced by the same string
            bits = name2.split(".")
            self.assertEqual(bits[1], bits[3], "New channel random strings don't match")
            # Make sure we can consume off of that new channel
            channel, message = channel_layer.receive_many([name1, name2])
            self.assertEqual(channel, name1)
            self.assertEqual(message, {"value": "blue"})

        def test_strings(self):
            """
            Ensures byte strings and unicode strings both make it through
            serialization properly.
            """
            # Message. Double-nested to ensure serializers are recursing properly.
            message = {
                "values": {
                    # UTF-8 sequence for british pound, but we want it not interpreted into that.
                    "utf-bytes": b"\xc2\xa3",
                    # Actual unicode for british pound, should come back as 1 char
                    "unicode": "\u00a3",
                    # Emoji, in case someone is using 3-byte-wide unicode storage
                    "emoji": "\u1F612",
                    # Random control characters and null
                    "control": b"\x01\x00\x03\x21",
                }
            }
            # Send it and receive it
            channel_layer.send("str_test", message)
            _, received = channel_layer.receive_many(["str_test"])
            # Compare
            self.assertIsInstance(received["values"]["utf-bytes"], six.binary_type)
            self.assertIsInstance(received["values"]["unicode"], six.text_type)
            self.assertIsInstance(received["values"]["emoji"], six.text_type)
            self.assertIsInstance(received["values"]["control"], six.binary_type)
            self.assertEqual(received["values"]["utf-bytes"], message["values"]["utf-bytes"])
            self.assertEqual(received["values"]["unicode"], message["values"]["unicode"])
            self.assertEqual(received["values"]["emoji"], message["values"]["emoji"])
            self.assertEqual(received["values"]["control"], message["values"]["control"])

        @unittest.skipIf("groups" not in channel_layer.extensions, "No groups extension")
        def test_groups(self):
            """
            Tests that basic group addition and send works
            """
            # Make a group and send to it
            channel_layer.group_add("tgroup", "tg_test")
            channel_layer.group_add("tgroup", "tg_test2")
            channel_layer.group_add("tgroup", "tg_test3")
            channel_layer.group_discard("tgroup", "tg_test3")
            channel_layer.send_group("tgroup", {"value": "orange"})
            # Receive from the two channels in the group and ensure messages
            channel, message = channel_layer.receive_many(["tg_test"])
            self.assertEqual(channel, "tg_test")
            self.assertEqual(message, {"value": "orange"})
            channel, message = channel_layer.receive_many(["tg_test2"])
            self.assertEqual(channel, "tg_test2")
            self.assertEqual(message, {"value": "orange"})
            # Make sure another channel does not get a message
            channel, message = channel_layer.receive_many(["tg_test3"])
            self.assertIs(channel, None)
            self.assertIs(message, None)

        @unittest.skipIf("flush" not in channel_layer.extensions, "No flush extension")
        def test_flush(self):
            """
            Tests that messages go away after a flush.
            """
            channel_layer.send("fl_test", {"value": "blue"})
            channel_layer.flush()
            channel, message = channel_layer.receive_many(["fl_test"])
            self.assertIs(channel, None)
            self.assertIs(message, None)

        @unittest.skipIf("flush" not in channel_layer.extensions, "No flush extension")
        @unittest.skipIf("groups" not in channel_layer.extensions, "No groups extension")
        def test_flush_groups(self):
            """
            Tests that groups go away after a flush.
            """
            channel_layer.send("fl_test", {"value": "blue"})
            channel_layer.flush()
            channel, message = channel_layer.receive_many(["fl_test"])
            self.assertIs(channel, None)
            self.assertIs(message, None)

    return LayerTestCase
