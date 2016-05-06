asgiref
=======

.. image:: https://api.travis-ci.org/andrewgodwin/asgiref.svg
    :target: https://travis-ci.org/andrewgodwin/asgiref

Contains various reference ASGI implementations, including:

* An in-memory channel layer, ``asgiref.inmemory``
* WSGI-to-ASGI and ASGI-to-WSGI adapters, in ``asgiref.wsgi``


In-memory Channel Layer
-----------------------

Simply instantiate ``asgiref.inmemory.ChannelLayer``, or use the pre-made
``asgiref.inmemory.channel_layer`` for easy use. Implements the ``group``
extension, and is designed to support running multiple ASGI programs
in separate threads within one process (the channel layer is threadsafe).


WSGI-ASGI Adapters
------------------

These are not yet complete and should not be used.
