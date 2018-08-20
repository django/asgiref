==============================
Startup and Cleanup (Lifespan)
==============================

**Version**: 1.0 (2018-08-20)

The startup and cleanup ASGI sub-specification outlines how to
communicate the lifespan events startup and cleanup within ASGI. The
lifespan being referred to is that of main event loop. In a
multi-process environment there will be lifespan events in each
process.

These sub-specifications allow an application to complete startup or
cleanup whilst the server waits. They differ from the WWW
sub-specifications in that no events are sent, with the
application_instance callable awaited by the server till completion.

In order to be backwards compatible a server should continue if an
application errors when receiving these scopes.

Startup
-------

The startup sub-specification is simply a scope with the following,

* ``type``: ``lifespan``

the callable returned by the application will then be awaited by the
server. On completion of the callable the server will start accepting
connections.

Cleanup
-------

The cleanup sub-specification is simply a scope with the following,

* ``type``: ``cleanup``

the callable returned by the application will then be awaited by the
server. The server will only send this scope after it has stopped
accepting connections and finalised any existing.


Version History
===============

* 1.0 (2018-07-01): Updated ASGI spec with a lifespan protocol.


Copyright
=========

This document has been placed in the public domain.
