import pytest

from asgiref.wsgi import WsgiToAsgi


@pytest.mark.asyncio
async def test_basic_wsgi():
    """
    Makes sure the WSGI wrapper has basic functionality.
    """
    # Define WSGI app
    def wsgi_application(environ, start_response):
        assert environ["HTTP_TEST_HEADER"] == "test value"
        start_response("200 OK", [["X-Colour", "Blue"]])
        yield b"first chunk "
        yield b"second chunk"
    # Wrap it
    application = WsgiToAsgi(wsgi_application)
    # Feed it a scope
    instance = application({
        "type": "http",
        "http_version": "1.0",
        "method": "GET",
        "path": "/foo/",
        "query_string": b"bar=baz",
        "headers": [[b"test-header", b"test value"]],
    })
    # Feed it send/receive awaitables
    sent = []

    async def receive():
        return {
            "type": "http.request",
        }

    async def send(message):
        sent.append(message)

    # Run coroutine (the WSGI one exits after the request ends)
    await instance(receive, send)
    # Check they send stuff
    assert len(sent) == 4
    assert sent[0] == {
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"X-Colour", b"Blue")],
    }
    assert sent[1] == {
        "type": "http.response.content",
        "content": b"first chunk ",
        "more_content": True,
    }
    assert sent[2] == {
        "type": "http.response.content",
        "content": b"second chunk",
        "more_content": True,
    }
    assert sent[3] == {
        "type": "http.response.content",
    }
