import pytest

from asgiref.testing import ApplicationCommunicator
from asgiref.wsgi import WsgiToAsgi


@pytest.fixture
def default_payload():
    return {
        "type": "http",
        "http_version": "1.0",
        "method": "GET",
        "path": "/foo/",
        "query_string": b"bar=baz",
        "headers": [],
    }


@pytest.mark.asyncio
async def test_receive_nothing(default_payload):
    """
    Tests ApplicationCommunicator.receive_nothing to return the correct value.
    """
    # Get an ApplicationCommunicator instance
    def wsgi_application(environ, start_response):
        start_response("200 OK", [])
        yield b"content"

    application = WsgiToAsgi(wsgi_application)
    communicator = ApplicationCommunicator(application, default_payload)

    # No event
    assert await communicator.receive_nothing() is True

    # Produce 3 events to receive
    await communicator.send_input({"type": "http.request"})
    # Start event of the response
    assert await communicator.receive_nothing() is False
    await communicator.receive_output()
    # First body event of the response announcing further body event
    assert await communicator.receive_nothing() is False
    await communicator.receive_output()
    # Last body event of the response
    assert await communicator.receive_nothing() is False
    await communicator.receive_output()
    # Response received completely
    assert await communicator.receive_nothing(0.01) is True


@pytest.mark.asyncio
async def test_communicator_instance(default_payload):
    """
    Tests ApplicationCommunicator.instance is exposed
    """

    class WsgiApplication:

        def __call__(self, environ, start_response):
            start_response('200 OK', [('Content-Type', 'text/plain')])
            yield "Hello World!\n"


    application = WsgiToAsgi(WsgiApplication())
    communicator = ApplicationCommunicator(application, default_payload)

    application_instance = await communicator.receive_application_instance()

    assert isinstance(application_instance, WsgiApplication)
