from asgiref.inmemory import ChannelLayer
from asgiref.conformance import core_tests

channel_layer = ChannelLayer(expiry=1)
InMemoryCoreTests = core_tests(channel_layer, 1.1)
