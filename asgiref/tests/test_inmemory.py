from asgiref.inmemory import ChannelLayer
from asgiref.conformance import make_tests

channel_layer = ChannelLayer(expiry=1)
InMemoryTests = make_tests(channel_layer, expiry_delay=1.1)
