from asgiref.inmemory import ChannelLayer
from asgiref.conformance import ConformanceTestCase


class InMemorylAYERTests(ConformanceTestCase):
    channel_layer = ChannelLayer(expiry=1, group_expiry=2)
    expiry_delay = 1.1
