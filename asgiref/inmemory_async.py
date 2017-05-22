import asyncio

@asyncio.coroutine
def receive_async(self, channels):
    """
    Asynchronous-compatible receive method.
    Right now is actually very dumb and sleep-polls; can likely be improved
    considerably.
    """
    while True:
        channel, message = self.receive(channels, block=False)
        if channel is not None:
            return channel, message
        yield from asyncio.sleep(0.001)
