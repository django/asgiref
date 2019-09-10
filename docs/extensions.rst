Extensions
==========

The ASGI specification provides for server-specific extensions to be
used outside of the core ASGI specification. This document specifies
some common extensions.


Websocket Denial Response
-------------------------

Websocket connections start with the client sending a HTTP request
containing the appropriate upgrade headers. On receipt of this request
a server can choose to either upgrade the connection or respond with an
HTTP response (denying the upgrade). The core ASGI specification does
not allow for any control over the denial response, instead specifying
that the HTTP status code ``403`` should be returned, whereas this
extension allows an ASGI framework to control the
denial response. Rather than being a core part of
ASGI, this is an extension for what is considered a niche feature as most
clients do not utilise the denial response.

ASGI Servers that implement this extension will provide
``websocket.http.response`` in the extensions part of the scope::

    "scope": {
        ...
        "extensions": {
            "websocket.http.response": {},
        },
    }

This will allow the ASGI Framework to send HTTP response messages
after the ``websocket.connect`` message. These messages cannot be
followed by any other websocket messages as the server should send a
HTTP response and then close the connection.

The messages themselves should be ``websocket.http.response.start``
and ``websocket.http.response.body`` with a structure that matches the
``http.response.start`` and ``http.response.body`` messages defined in
the HTTP part of the core ASGI specification.

HTTP/2 Server Push
------------------

HTTP/2 allows for a server to push a resource to a client by sending a
push promise. ASGI servers that implement this extension will provide
``http.response.push`` in the extensions part of the scope::

    "scope": {
        ...
        "extensions": {
            "http.response.push": {},
        },
    }

An ASGI framework can initiate a server push by sending a message with
the following keys. This message can be sent at any time after the
*Response Start* message but before the final *Response Body* message.

Keys:

* ``type`` (*Unicode string*): ``"http.response.push"``

* ``path`` (*Unicode string*): HTTP path from URL, with percent-encoded
  sequences and UTF-8 byte sequences decoded into characters.

* ``headers`` (*Iterable[[byte string, byte string]]*): An iterable of
  ``[name, value]`` two-item iterables, where ``name`` is the header name, and
  ``value`` is the header value. Header names must be lowercased. Pseudo
  headers (present in HTTP/2 and HTTP/3) must not be present.

The ASGI server should then attempt to send a server push (or push
promise) to the client. If the client supports server push, the server
should create a new connection to a new instance of the application
and treat it as if the client had made a request.

The ASGI server should set the pseudo ``:authority`` header value to
be the same value as the request that triggered the push promise.
