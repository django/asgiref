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


class ConformanceTestCase(unittest.TestCase):
    """
    Tests that core ASGI functionality is maintained.
    """

    channel_layer = None
    expiry_delay = None
    capacity_limit = None

    @classmethod
    def raiseSkip(cls, message):
        """
        Picks the right skip class based on what version of unittest we're using.
        """
        try:
            import unittest2
            SkipTest = unittest2.SkipTest
        except ImportError:
            SkipTest = unittest.SkipTest
        raise SkipTest(message)

    @classmethod
    def setUpClass(cls):
        # Don't let this actual class run, it's abstract
        if cls is ConformanceTestCase:
            cls.raiseSkip("Skipping base class tests")

    def setUp(self):
        if self.channel_layer is None:
            raise ValueError("You must define 'channel_layer' when subclassing the conformance tests.")
        if self.expiry_delay is None:
            raise ValueError("You must define 'expiry_delay' when subclassing the conformance tests.")
        if "flush" in self.channel_layer.extensions:
            self.channel_layer.flush()

    def skip_if_no_extension(self, extension):
        """
        Handy function for skipping things without an extension.
        We can't use the decorators, as we need access to self.
        """
        if extension not in self.channel_layer.extensions:
            self.raiseSkip("No %s extension" % extension)

    def test_send_recv(self):
        """
        Tests that channels can send and receive messages right.
        """
        self.channel_layer.send("sr_test", {"value": "blue"})
        self.channel_layer.send("sr_test", {"value": "green"})
        self.channel_layer.send("sr_test2", {"value": "red"})
        # Get just one first
        channel, message = self.channel_layer.receive_many(["sr_test"])
        self.assertEqual(channel, "sr_test")
        self.assertEqual(message, {"value": "blue"})
        # And the second
        channel, message = self.channel_layer.receive_many(["sr_test"])
        self.assertEqual(channel, "sr_test")
        self.assertEqual(message, {"value": "green"})
        # And the other channel with multi select
        channel, message = self.channel_layer.receive_many(["sr_test", "sr_test2"])
        self.assertEqual(channel, "sr_test2")
        self.assertEqual(message, {"value": "red"})

    def test_message_expiry(self):
        """
        Tests that messages expire correctly.
        """
        self.channel_layer.send("me_test", {"value": "blue"})
        time.sleep(self.expiry_delay)
        channel, message = self.channel_layer.receive_many(["me_test"])
        self.assertIs(channel, None)
        self.assertIs(message, None)

    def test_new_channel_single_reader(self):
        """
        Tests that new channel names are made correctly.
        """
        pattern = "test.foo?"
        name1 = self.channel_layer.new_channel(pattern)
        self.assertFalse(name1.endswith("?"))
        self.assertTrue("?" in name1)
        self.assertEqual(name1.find("?"), name1.rfind("?"))
        self.assertIsInstance(name1, six.text_type)
        # Send a message and make sure new_channel on second pass changes
        self.channel_layer.send(name1, {"value": "blue"})
        name2 = self.channel_layer.new_channel(pattern)
        # Make sure we can consume off of that new channel
        channel, message = self.channel_layer.receive_many([name1, name2])
        self.assertEqual(channel, name1)
        self.assertEqual(message, {"value": "blue"})

    def test_new_channel_single_process(self):
        """
        Tests that new channel names are made correctly.
        """
        pattern = "test.foo!"
        name1 = self.channel_layer.new_channel(pattern)
        self.assertFalse(name1.endswith("!"))
        self.assertTrue("!" in name1)
        self.assertEqual(name1.find("!"), name1.rfind("!"))
        self.assertIsInstance(name1, six.text_type)
        # Send a message and make sure new_channel on second pass changes
        self.channel_layer.send(name1, {"value": "blue"})
        name2 = self.channel_layer.new_channel(pattern)
        # Make sure we can consume off of that new channel
        channel, message = self.channel_layer.receive_many([name1, name2])
        self.assertEqual(channel, name1)
        self.assertEqual(message, {"value": "blue"})

    def test_new_channel_failures(self):
        """
        Tests that we don't allow bad new channel names.
        """
        with self.assertRaises(Exception):
            self.channel_layer.new_channel("test!foo")
        with self.assertRaises(Exception):
            self.channel_layer.new_channel("test.foo")

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
        self.channel_layer.send("str_test", message)
        _, received = self.channel_layer.receive_many(["str_test"])
        # Compare
        self.assertIsInstance(received["values"]["utf-bytes"], six.binary_type)
        self.assertIsInstance(received["values"]["unicode"], six.text_type)
        self.assertIsInstance(received["values"]["emoji"], six.text_type)
        self.assertIsInstance(received["values"]["control"], six.binary_type)
        self.assertEqual(received["values"]["utf-bytes"], message["values"]["utf-bytes"])
        self.assertEqual(received["values"]["unicode"], message["values"]["unicode"])
        self.assertEqual(received["values"]["emoji"], message["values"]["emoji"])
        self.assertEqual(received["values"]["control"], message["values"]["control"])

    def test_groups(self):
        """
        Tests that basic group addition and send works
        """
        self.skip_if_no_extension("groups")
        # Make a group and send to it
        self.channel_layer.group_add("tgroup", "tg_test")
        self.channel_layer.group_add("tgroup", "tg_test2")
        self.channel_layer.group_add("tgroup", "tg_test3")
        self.assertEqual(
            set(self.channel_layer.group_channels("tgroup")),
            {"tg_test", "tg_test2", "tg_test3"},
        )
        self.channel_layer.group_discard("tgroup", "tg_test3")
        self.channel_layer.send_group("tgroup", {"value": "orange"})
        # Check group members
        self.assertEqual(
            set(self.channel_layer.group_channels("tgroup")),
            {"tg_test", "tg_test2"},
        )
        # Receive from the two channels in the group and ensure messages
        channel, message = self.channel_layer.receive_many(["tg_test"])
        self.assertEqual(channel, "tg_test")
        self.assertEqual(message, {"value": "orange"})
        channel, message = self.channel_layer.receive_many(["tg_test2"])
        self.assertEqual(channel, "tg_test2")
        self.assertEqual(message, {"value": "orange"})
        # Make sure another channel does not get a message
        channel, message = self.channel_layer.receive_many(["tg_test3"])
        self.assertIs(channel, None)
        self.assertIs(message, None)

    def test_flush(self):
        """
        Tests that messages go away after a flush.
        """
        self.skip_if_no_extension("flush")
        # Send something to flush
        self.channel_layer.send("fl_test", {"value": "blue"})
        self.channel_layer.flush()
        channel, message = self.channel_layer.receive_many(["fl_test"])
        self.assertIs(channel, None)
        self.assertIs(message, None)

    def test_flush_groups(self):
        """
        Tests that groups go away after a flush.
        """
        self.skip_if_no_extension("groups")
        self.skip_if_no_extension("flush")
        # Add things to a group and send to it
        self.channel_layer.group_add("tfg_group", "tfg_test")
        self.channel_layer.send_group("tfg_group", {"value": "blue"})
        self.channel_layer.flush()
        channel, message = self.channel_layer.receive_many(["tfg_test"])
        self.assertIs(channel, None)
        self.assertIs(message, None)

    def test_group_expiry(self):
        """
        Tests that group expiry is provided, and test it if it's less than
        20 seconds.
        """
        self.skip_if_no_extension("groups")
        # Check group expiry is provided, and see if we can continue
        expiry = getattr(self.channel_layer, "group_expiry", None)
        if expiry is None:
            self.fail("group_expiry is not defined")
        if expiry > 20:
            raise unittest.SkipTest("Expiry too long for test")
        # Add things to a group
        self.channel_layer.group_add("tge_group", "tge_test")
        # Wait group expiry plus one
        time.sleep(expiry + 1)
        # Ensure message never arrives
        self.channel_layer.send_group("tge_group", {"value": "blue"})
        channel, message = self.channel_layer.receive_many(["tge_test"])
        self.assertIs(channel, None)
        self.assertIs(message, None)

    def test_capacity(self):
        """
        Tests that the capacity limiter on send() raises ChannelFull
        after the right number of messages. Only runs if capacity_limit is set.
        """
        if self.capacity_limit is None:
            self.raiseSkip("No test capacity specified")
        for _ in range(self.capacity_limit):
            self.channel_layer.send("cap_test", {"hey": "there"})
        with self.assertRaises(self.channel_layer.ChannelFull):
            self.channel_layer.send("cap_test", {"hey": "there"})

    def test_exceptions(self):
        """
        Tests that the two exception classes exist on the channel layer
        """
        self.assertTrue(hasattr(self.channel_layer, "MessageTooLarge"))
        self.assertTrue(hasattr(self.channel_layer, "ChannelFull"))
