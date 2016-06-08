from __future__ import unicode_literals

import six
from unittest import TestCase
from ..inmemory import ChannelLayer
from ..wsgi import WsgiToAsgiAdapter


class TestWsgiToAsgiAdapter(WsgiToAsgiAdapter):
    """
    Testing subclass with a fixed reply channel
    """

    def get_reply_channel(self):
        return "http.response!testtest"


class WsgiToAsgiTests(TestCase):
    """
    Tests the WSGI-to-ASGI adapter.
    """

    def setUp(self):
        """
        Make an in memory channel layer for testing
        """
        self.channel_layer = ChannelLayer()
        self.reply_channel = "http.response!testtest"
        self.start_response_value = None
        self.application = TestWsgiToAsgiAdapter(self.channel_layer)

    def native_string(self, value):
        """
        Makes sure that the passed in string value comes out as a PEP3333
        "native string".
        """
        if six.PY2:
            if isinstance(value, unicode):
                return value.encode("latin1")
            else:
                return value
        else:
            if isinstance(value, bytes):
                return value.decode("latin1")
            else:
                return value

    def start_response(self, status, headers, exc_info=None):
        self.start_response_value = [status, headers, exc_info]

    def test_basic(self):
        # Example request
        ns = self.native_string
        environ = {
            "PATH_INFO": ns("/"),
            "CONTENT_TYPE": ns("text/html; charset=utf-8"),
            "REQUEST_METHOD": ns("GET"),
        }
        # Inject the response ahead of time
        self.channel_layer.send(self.reply_channel, {
            "status": 200,
            "content": b"Hi there!",
        })
        # Run WSGI adapter
        response = list(self.application(environ, self.start_response))
        # Make sure response looks fine
        self.assertEqual(response[0], b"Hi there!")
        self.assertEqual(self.start_response_value[0], b"200 OK")
