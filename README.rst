asgiref
=======

.. image:: https://api.travis-ci.org/andrewgodwin/asgiref.svg
    :target: https://travis-ci.org/andrewgodwin/asgiref
    
.. image:: https://img.shields.io/pypi/v/asgiref.svg
    :target: https://pypi.python.org/pypi/asgiref

Contains various reference ASGI implementations, including:

* A base channel layer, ``asgiref.base_layer``
* An in-memory channel layer, ``asgiref.inmemory``
* WSGI-to-ASGI and ASGI-to-WSGI adapters, in ``asgiref.wsgi``


Base Channel Layer
------------------

Provides an optional template to start ASGI channel layers from with the two
exceptions you need provided and all API functions stubbed out.

Also comes with logic for doing per-channel capacities using channel names and
globbing; use ``self.get_capacity`` and pass the arguments through to the base
``__init__`` if you want to use it.


In-memory Channel Layer
-----------------------

Simply instantiate ``asgiref.inmemory.ChannelLayer``, or use the pre-made
``asgiref.inmemory.channel_layer`` for easy use. Implements the ``group``
extension, and is designed to support running multiple ASGI programs
in separate threads within one process (the channel layer is threadsafe).


WSGI-ASGI Adapters
------------------

These are not yet complete and should not be used.
