import math
import time

import pytest

from asgiref.testing import ApplicationCommunicator
from asgiref.wsgi import WsgiToAsgi


@pytest.mark.parametrize(
    "event, timeout, attempt, duration, tolerance, expected", [
        # No event
        # Standard values
        (False, 0.1, 0.01, 0.1, 0.03, True),
        # attempt > timeout
        (False, 0.1, 1, 0.1, 0.03, True),
        # timeout % attempt > 0
        (False, 1, 0.6, 1, 0.03, True),

        # Events
        # Standard values
        (True, 0.1, 0.01, 0.01, 0.003, False),
        # No delay
        (True, 0, 0.01, 0, 0.003, True),
        # No attempt
        (True, 0.1, 0, 0.1, 0.03, False),
        # attempt > timeout
        (True, 0.1, 1, 0.1, 0.03, False),
    ]
)
@pytest.mark.asyncio
async def test_receive_nothing(event, timeout, attempt, duration, tolerance, expected):
    """
    Tests ApplicationCommunicator.receive_nothing with different parameters.
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

    if event:
        await instance.send_input({
            "type": "http.request",
        })

    start = time.monotonic()
    result = await instance.receive_nothing(timeout=timeout, attempt=attempt)
    end = time.monotonic()
    assert result is expected
    assert math.isclose(end - start, duration, abs_tol=tolerance)

    if event:
        await instance.receive_output()
        assert await instance.receive_nothing() is False
        await instance.receive_output()
        assert await instance.receive_nothing() is False
        await instance.receive_output()
        assert await instance.receive_nothing(0.01) is True
