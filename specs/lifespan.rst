=================
Lifespan Protocol
=================

**Version**: 1.0 (2018-09-06)

The Lifespan ASGI sub-specification outlines how to communicate
lifespan events such as startup and cleanup within ASGI. The lifespan
being referred to is that of main event loop. In a multi-process
environment there will be lifespan events in each process.

The lifespan messages allow for a application to initialise and
cleanup in the context of a running event loop. An example of this
would be creating a connection pool and subsequently closing the
connection pool to release the connections.

A possible implementation of this protocol is given below::

    class App:

        def __init__(self, scope):
            self.scope = scope

        async def __call__(self, receive, send):
            if self.scope['type'] == 'lifespan':
                while True:
                    message = await receive()
                    if message['type'] == 'lifespan.startup':
                        await self.startup()
                        await send({'type': 'lifespan.startup.complete'})
                    elif message['type'] == 'lifespan.cleanup':
                        await self.cleanup()
                        await send({'type': 'lifespan.cleanup.complete'})
                        return
            else:
                pass # Handle other types

        async def startup(self):
            ...

        async def cleanup(self):
            ...


Scope
'''''

The lifespan scope exists for the duration of the event loop. The
scope itself contains basic metadata,

* ``type``: ``lifespan``

If an exception is raised when calling the application callable with a
lifespan scope the server must continue but not send any lifespan
events. This allows for compatibility with applications that do not
support the lifespan protocol.


Startup
'''''''

Sent when the server is ready to startup and recieve connections, but
before it has started to do so.

Keys:

* ``type``: ``lifespan.startup``


Startup Complete
''''''''''''''''

Sent by the application when it has completed its startup. A server
must wait for this message before it starts processing connections.

Keys:

* ``type``: ``lifespan.startup.complete``


Cleanup
'''''''

Sent when the server has stopped accepting connections and closed all
active connections.

Keys:

* ``type``:  ``lifespan.cleanup``


Cleanup Complete
''''''''''''''''

Sent by the application when it has completed its cleanup. A server
must wait for this message before terminating.

Keys:

* ``type``: ``lifespan.cleanup.complete``


Version History
===============

* 1.0 (2018-09-06): Updated ASGI spec with a lifespan protocol.


Copyright
=========

This document has been placed in the public domain.
