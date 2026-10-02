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


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_output", [False, True])
async def test_receive_output_timeout_preserves_application(initial_output):
    started = asyncio.Event()

    async def application(scope, receive, send):
        started.set()
        while True:
            await send(await receive())

    instance = ApplicationCommunicator(application, {})
    future = instance.future
    try:
        await started.wait()
        if initial_output:
            await instance.send_input({"value": "first"})
            assert await instance.receive_output() == {"value": "first"}
        with pytest.raises(TimeoutError):
            await instance.receive_output(timeout=0)
        assert instance.future is future
        assert not future.done()
        await instance.send_input({"value": "after timeout"})
        assert await instance.receive_output() == {"value": "after timeout"}
    finally:
        instance.stop(exceptions=False)
        await asyncio.gather(future, return_exceptions=True)


@pytest.mark.asyncio
async def test_application_error_after_receive_output_timeout():
    error = ValueError("application failed")
    started = asyncio.Event()

    async def application(scope, receive, send):
        started.set()
        await receive()
        raise error

    instance = ApplicationCommunicator(application, {})
    future = instance.future
    try:
        await started.wait()
        with pytest.raises(TimeoutError):
            await instance.receive_output(timeout=0)
        await instance.send_input({})
        with pytest.raises(ValueError) as raised:
            await future
        assert raised.value is error
        with pytest.raises(ValueError) as raised:
            await instance.receive_output(timeout=0)
        assert raised.value is error
    finally:
        instance.stop(exceptions=False)
        await asyncio.gather(future, return_exceptions=True)


@pytest.mark.asyncio
async def test_receive_output_reports_application_error_on_timeout():
    error = ValueError("application failed")
    started = asyncio.Event()

    async def application(scope, receive, send):
        started.set()
        await receive()
        raise error

    instance = ApplicationCommunicator(application, {})
    future = instance.future
    try:
        await started.wait()
        await instance.send_input({})
        with pytest.raises(ValueError) as raised:
            await instance.receive_output(timeout=0)
        assert raised.value is error
    finally:
        instance.stop(exceptions=False)
        await asyncio.gather(future, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("finish", ["stop", "wait"])
async def test_application_cleanup_after_receive_output_timeout(finish):
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def application(scope, receive, send):
        try:
            started.set()
            await receive()
        finally:
            stopped.set()

    instance = ApplicationCommunicator(application, {})
    future = instance.future
    try:
        await started.wait()
        with pytest.raises(TimeoutError):
            await instance.receive_output(timeout=0)
        assert not stopped.is_set()
        if finish == "stop":
            instance.stop()
        else:
            await instance.wait(timeout=0)
        await asyncio.gather(future, return_exceptions=True)
        assert future.cancelled()
        assert stopped.is_set()
    finally:
        instance.stop(exceptions=False)
        await asyncio.gather(future, return_exceptions=True)


@pytest.mark.asyncio
async def test_receive_output_timeout_after_successful_application():
    async def application(scope, receive, send):
        return

    instance = ApplicationCommunicator(application, {})
    future = instance.future
    try:
        await future
        with pytest.raises(TimeoutError):
            await instance.receive_output(timeout=0)
        assert not future.cancelled()
        assert future.exception() is None
    finally:
        instance.stop(exceptions=False)
        await asyncio.gather(future, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancel_receive_output_preserves_application():
    started = asyncio.Event()
    receiving = asyncio.Event()

    async def application(scope, receive, send):
        started.set()
        await send(await receive())

    instance = ApplicationCommunicator(application, {})
    future = instance.future
    receiver = None

    async def receive_output():
        receiving.set()
        return await instance.receive_output(timeout=None)

    try:
        await started.wait()
        receiver = asyncio.create_task(receive_output())
        await receiving.wait()
        receiver.cancel()
        with pytest.raises(asyncio.CancelledError):
            await receiver
        assert not future.done()
        await instance.send_input({"value": "after cancellation"})
        assert await instance.receive_output() == {"value": "after cancellation"}
    finally:
        if receiver is not None:
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
        instance.stop(exceptions=False)
        await asyncio.gather(future, return_exceptions=True)
