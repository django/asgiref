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
    instance = ApplicationCommunicator(application, {
        "type": "http",
        "http_version": "1.0",
        "method": "GET",
        "path": "/foo/",
        "query_string": b"bar=baz",
        "headers": [],
    })

    # No event
    assert await instance.receive_nothing() is True

    # Events
    await instance.send_input({
        "type": "http.request",
    })
    assert await instance.receive_nothing() is False
    await instance.receive_output()
    assert await instance.receive_nothing() is False
    await instance.receive_output()
    assert await instance.receive_nothing() is False
    await instance.receive_output()
    assert await instance.receive_nothing(0.01) is True
