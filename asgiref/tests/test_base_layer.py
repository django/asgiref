from __future__ import unicode_literals

import unittest

from asgiref.base_layer import BaseChannelLayer


class BaseLayerTests(unittest.TestCase):
   
    def test_get_capacity(self):
        """
        Tests that the capacity selection code works
        """
        layer = BaseChannelLayer(
            capacity=42,
            channel_capacity={
                "http.response!*": 10,
                "http.request": 100,
            }
        )
        self.assertEqual(layer.get_capacity("http.disconnect"), 42)
        self.assertEqual(layer.get_capacity("http.request"), 100)
        self.assertEqual(layer.get_capacity("http.response!abcdefgh"), 10)
