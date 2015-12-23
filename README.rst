asgi-inmemory
=============

An ASGI channel layer that works purely in memory, intended when multiple
ASGI applications or protocol servers are run in the same process in
separate threads.


Usage
-----

Simply point your ASGI code to use ``asgi_inmemory.channel_layer`` as its
channel layer. No configuration is required.
