=================
Lifespan Protocol
=================

**Version**: 1.0 (2018-07-01)

The Lifespan ASGI sub-specification outlines how to communicate
lifespan events such as startup and cleanup within ASGI. The lifespan
being referred to is that of main event loop. In a multi-process
environment there will be lifespan events in each process.


Scope
'''''

The lifespan scope exists for the duration of the event loop. The
scope itself contains basic metadata,

* ``type``: ``lifespan``


Startup
'''''''

Sent when the server is ready to startup and recieve connections, but
before it has started to do so.

Keys:

* ``type``: ``lifespan.startup``


Cleanup
'''''''

Sent when the server has stopped accepting connections and closed all
active connections.

Keys:

* ``type``:  ``lifespan.cleanup``


Version History
===============

* 1.0 (2018-07-01): Updated ASGI spec with a lifespan protocol.


Copyright
=========

This document has been placed in the public domain.
