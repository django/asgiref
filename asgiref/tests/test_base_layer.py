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

    def test_valid_channel_name(self):
        """
        Tests the channel name validator
        """
        layer = BaseChannelLayer()
        self.assertTrue(layer.valid_channel_name("http.request"))
        self.assertTrue(layer.valid_channel_name("http.response!ab0def"))
        self.assertTrue(layer.valid_channel_name("http.request.body?ab0def"))
        self.assertTrue(layer.valid_channel_name("0.a_b-c?d_e-f.1"))

        with self.assertRaises(TypeError):
            layer.valid_channel_name("http.request\u00a3")

        with self.assertRaises(TypeError):
            layer.valid_channel_name("way.too.long" * 10)

        with self.assertRaises(TypeError):
            layer.valid_channel_name("one?two?three")

        with self.assertRaises(TypeError):
            layer.valid_channel_name("four!five!six")

        with self.assertRaises(TypeError):
            layer.valid_channel_name("some+other!thing")

    def test_valid_group_name(self):
        """
        Tests the group name validator
        """
        layer = BaseChannelLayer()
        self.assertTrue(layer.valid_group_name("foo.bar"))
        self.assertTrue(layer.valid_group_name("0.a_b-c"))

        with self.assertRaises(TypeError):
            layer.valid_group_name("foo.bar?baz")
        with self.assertRaises(TypeError):
            layer.valid_group_name("foo.bar!baz")
        with self.assertRaises(TypeError):
            layer.valid_group_name("foo.bar\u00a3")
        with self.assertRaises(TypeError):
            layer.valid_group_name("way.too.long" * 10)
        with self.assertRaises(TypeError):
            layer.valid_group_name("some+other=thing")
