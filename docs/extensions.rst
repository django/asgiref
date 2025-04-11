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

Zero Copy Send
--------------

Zero Copy Send allows you to send the contents of a file descriptor to the
HTTP client with zero copy (where the underlying OS directly handles the data
transfer from a source file or socket without loading it into Python and
writing it out again).

ASGI servers that implement this extension will provide
``http.response.zerocopysend`` in the extensions part of the scope::

    "scope": {
        ...
        "extensions": {
            "http.response.zerocopysend": {},
        },
    }

The ASGI framework can initiate a zero-copy send by sending a message with
the following keys. This message can be sent at any time after the
*Response Start* message but before the final *Response Body* message,
and can be mixed with ``http.response.body``. It can also be called
multiple times in one response. Except for the characteristics of
zero-copy, it should behave the same as ordinary ``http.response.body``.

Keys:

* ``type`` (*Unicode string*): ``"http.response.zerocopysend"``

* ``file`` (*file descriptor object*): An opened file descriptor object
  with an underlying OS file descriptor that can be used to call
  ``os.sendfile``. (e.g. not BytesIO)

* ``offset`` (*int*): Optional. If this value exists, it will specify
  the offset at which sendfile starts to read data from ``file``.
  Otherwise, it will be read from the current position of ``file``.

* ``count`` (*int*): Optional. ``count`` is the number of bytes to
  copy between the file descriptors. If omitted, the file will be read until
  its end.

* ``more_body`` (*bool*): Signifies if there is additional content
  to come (as part of a Response Body message). If ``False``, response
  will be taken as complete and closed, and any further messages on
  the channel will be ignored. Optional; if missing defaults to
  ``False``.

After calling this extension to respond, the ASGI application itself should
actively close the used file descriptor - ASGI servers are not responsible for
closing descriptors.

Path Send
---------

Path Send allows you to send the contents of a file path to the
HTTP client without handling file descriptors, offloading the operation
directly to the server.

ASGI servers that implement this extension will provide
``http.response.pathsend`` in the extensions part of the scope::

    "scope": {
        ...
        "extensions": {
            "http.response.pathsend": {},
        },
    }

The ASGI framework can initiate a path-send by sending a message with
the following keys. This message can be sent at any time after the
*Response Start* message, and cannot be mixed with ``http.response.body``.
It can be called just one time in one response.
Except for the characteristics of path-send, it should behave the same
as ordinary ``http.response.body``.

Keys:

* ``type`` (*Unicode string*): ``"http.response.pathsend"``

* ``path`` (*Unicode string*): The string representation of the absolute
  file path to be sent by the server, platform specific.

The ASGI application itself is responsible to send the relevant headers
in the *Response Start* message, like the ``Content-Type`` and
``Content-Length`` headers for the file to be sent.

TLS
---

See :doc:`specs/tls`.

Early Hints
-----------

An informational response with the status code 103 is an Early Hint,
indicating to the client that resources are associated with the
subsequent response, see ``RFC 8297``. ASGI servers that implement
this extension will allow early hints to be sent. These servers will
provide ``http.response.early_hint`` in the extensions part of the
scope::

    "scope": {
        ...
        "extensions": {
            "http.response.early_hint": {},
        },
    }

An ASGI framework can send an early hint by sending a message with the
following keys. This message can be sent at any time (and multiple
times) after the *Response Start* message but before the final
*Response Body* message.

Keys:

* ``type`` (*Unicode string*): ``"http.response.early_hint"``

* ``links`` (*Iterable[byte string]*): An iterable of link header field
  values, see ``RFC 8288``.

The ASGI server should then attempt to send an informational response
to the client with the provided links as ``Link`` headers. The server
may decide to ignore this message, for example if the HTTP/1.1
protocol is used and the server has security concerns.

HTTP Trailers
-------------

The Trailer response header allows the sender to include additional fields at the
end of chunked messages in order to supply metadata that might be dynamically
generated while the message body is sent, such as a message integrity check,
digital signature, or post-processing status.

ASGI servers that implement this extension will provide
``http.response.trailers`` in the extensions part of the scope::

    "scope": {
        ...
        "extensions": {
            "http.response.trailers": {},
        },
    }

An ASGI framework interested in sending trailing headers to the client, must set the
field ``trailers`` in *Response Start* as ``True``. That will allow the ASGI server
to know that after the last ``http.response.body`` message (``more_body`` being ``False``),
the ASGI framework will send a ``http.response.trailers`` message.

The ASGI framework is in charge of sending the ``Trailers`` headers to let the client know
which trailing headers the server will send. The ASGI server is not responsible for validating
the ``Trailers`` headers provided.

Keys:

* ``type`` (*Unicode string*): ``"http.response.trailers"``

* ``headers`` (*Iterable[[byte string, byte string]]*): An iterable of
  ``[name, value]`` two-item iterables, where ``name`` is the header name, and
  ``value`` is the header value. Header names must be lowercased. Pseudo
  headers (present in HTTP/2 and HTTP/3) must not be present.

* ``more_trailers`` (*bool*): Signifies if there is additional content
  to come (as part of a *HTTP Trailers* message). If ``False``, response
  will be taken as complete and closed, and any further messages on
  the channel will be ignored. Optional; if missing defaults to
  ``False``.


The ASGI server will only send the trailing headers in case the client has sent the
``TE: trailers`` header in the request.

Debug
-----

The debug extension allows a way to send debug information from an ASGI framework in
its responses. This extension is not meant to be used in production, only for testing purposes,
and ASGI servers should not implement it.

The ASGI context sent to the framework will provide ``http.response.debug`` in the extensions
part of the scope::

    "scope": {
        ...
        "extensions": {
            "http.response.debug": {},
        },
    }

The ASGI framework can send debug information by sending a message with the following
keys. This message must be sent once, before the *Response Start* message.

Keys:

* ``type`` (*Unicode string*): ``"http.response.debug"``

* ``info`` (*Dict[Unicode string, Any]*): A dictionary containing the debug information.
  The keys and values of this dictionary are not defined by the ASGI specification, and
  are left to the ASGI framework to define.
