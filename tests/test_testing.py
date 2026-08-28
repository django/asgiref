import asyncio

import pytest

from asgiref.testing import ApplicationCommunicator
from asgiref.wsgi import WsgiToAsgi


@pytest.mark.asyncio
async def test_receive_nothing():
    """
    Tests ApplicationCommunicator.receive_nothing to return the correct value.
    """

    # Get an ApplicationCommunicator instance
    def wsgi_application(environ, start_response):
        start_response("200 OK", [])
        yield b"content"

    application = WsgiToAsgi(wsgi_application)
    instance = ApplicationCommunicator(
        application,
        {
            "type": "http",
            "http_version": "1.0",
            "method": "GET",
            "path": "/foo/",
            "query_string": b"bar=baz",
            "headers": [],
        },
    )

    # No event
    assert await instance.receive_nothing() is True

    # Produce 3 events to receive
    await instance.send_input({"type": "http.request"})
    # Start event of the response
    assert await instance.receive_nothing() is False
    await instance.receive_output()
    # First body event of the response announcing further body event
    assert await instance.receive_nothing() is False
    await instance.receive_output()
    # Last body event of the response
    assert await instance.receive_nothing() is False
    await instance.receive_output()
    # Response received completely
    assert await instance.receive_nothing(0.01) is True


@pytest.mark.asyncio
async def test_receive_output_timeout_restores_cancellation_count():
    """A handled timeout must not leave its task in a cancelling state."""
    if not hasattr(asyncio, "timeout"):
        pytest.skip("Task cancellation counts were added in Python 3.11")

    async def application(scope, receive, send):
        await asyncio.Event().wait()

    instance = ApplicationCommunicator(application, {})
    task = asyncio.current_task()
    assert task is not None
    cancelling = getattr(task, "cancelling")
    uncancel = getattr(task, "uncancel")
    before = cancelling()

    try:
        with pytest.raises(asyncio.TimeoutError):
            await instance.receive_output(timeout=0)

        assert cancelling() == before
    finally:
        while cancelling() > before:
            uncancel()


def test_receive_nothing_lazy_loop():
    """
    Tests ApplicationCommunicator.receive_nothing to return the correct value.
    """

    # Get an ApplicationCommunicator instance
    def wsgi_application(environ, start_response):
        start_response("200 OK", [])
        yield b"content"

    application = WsgiToAsgi(wsgi_application)
    instance = ApplicationCommunicator(
        application,
        {
            "type": "http",
            "http_version": "1.0",
            "method": "GET",
            "path": "/foo/",
            "query_string": b"bar=baz",
            "headers": [],
        },
    )

    async def test():
        # No event
        assert await instance.receive_nothing() is True

        # Produce 3 events to receive
        await instance.send_input({"type": "http.request"})
        # Start event of the response
        assert await instance.receive_nothing() is False
        await instance.receive_output()
        # First body event of the response announcing further body event
        assert await instance.receive_nothing() is False
        await instance.receive_output()
        # Last body event of the response
        assert await instance.receive_nothing() is False
        await instance.receive_output()
        # Response received completely
        assert await instance.receive_nothing(0.01) is True

    asyncio.run(test())
