import asyncio

def test_receive_async(self):
    """
    Tests that the asynchronous receive() method works.
    """
    # Make sure we can run asyncio code
    self.skip_if_no_extension("async")
    try:
        import asyncio
    except ImportError:
        raise unittest.SkipTest("No asyncio")
    # Test that receive works
    self.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(None)

    @asyncio.coroutine
    def test():
        self.channel_layer.send("test_async", {"is it": "working"})
        channel, message = yield from self.channel_layer.receive_async(["test_async"])
        self.assertEqual(channel, "test_async")
        self.assertEqual(message, {"is it": "working"})
    self.loop.run_until_complete(test())
