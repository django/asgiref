import asyncio

import async_timeout


class ApplicationCommunicator:
    """
    Runs an ASGI application in a test mode, allowing sending of messages to
    it and retrieval of messages it sends.
    """

    def __init__(self, instance):
        self.instance = instance
        self.input_queue = asyncio.Queue()
        self.output_queue = asyncio.Queue()
        self.future = asyncio.ensure_future(
            self.instance(self.input_queue.get, self.output_queue.put)
        )

    def __del__(self):
        # Clean up on deletion
        if not self.future.done():
            self.future.cancel()

    async def send_input(self, message):
        """
        Sends a single message to the application
        """
        await self.input_queue.put(message)

    async def receive_output(self, timeout=None):
        """
        Receives a single message from the application, with optional timeout.
        """
        async with async_timeout.timeout(timeout):
            return await self.output_queue.get()
