====================================
HTTP & WebSocket ASGI Message Format
====================================

**Version**: 2.5 (2024-06-05)

The HTTP+WebSocket ASGI sub-specification outlines how to transport HTTP/1.1,
HTTP/2 and WebSocket connections within ASGI.

It is deliberately intended and designed to be a superset of the WSGI format
and specifies how to translate between the two for the set of requests that
are able to be handled by WSGI.


Spec Versions
-------------

This spec has had the following versions:

* ``2.0``: The first version of the spec, released with ASGI 2.0
* ``2.1``: Added the ``headers`` key to the WebSocket Accept response
* ``2.2``: Allow ``None`` in the second item of ``server`` scope value.
* ``2.3``: Added the ``reason`` key to the WebSocket close event.
* ``2.4``: Calling ``send()`` on a closed connection should raise an error
* ``2.5``: Added the ``reason`` key to the WebSocket disconnect event.

Spec versions let you understand what the server you are using understands. If
a server tells you it only supports version ``2.0`` of this spec, then
sending ``headers`` with a WebSocket Accept message is an error, for example.

They are separate from the HTTP version or the ASGI version.


HTTP
----

The HTTP format covers HTTP/1.0, HTTP/1.1 and HTTP/2, as the changes in
HTTP/2 are largely on the transport level. A protocol server should give
different scopes to different requests on the same HTTP/2 connection, and
correctly multiplex the responses back to the same stream in which they came.
The HTTP version is available as a string in the scope.

Multiple header fields with the same name are complex in HTTP. RFC 7230
states that for any header field that can appear multiple times, it is exactly
equivalent to sending that header field only once with all the values joined by
commas.

However, for HTTP cookies (``Cookie`` and ``Set-Cookie``) the allowed behaviour
does not follow the above rule, and also varies slightly based on the HTTP
protocol version:

* For the ``Set-Cookie`` header in HTTP/1.0, HTTP/1.1 and HTTP2.0, it may appear
  repeatedly, but cannot be concatenated by commas (or anything else) into a
  single header field.

* For the ``Cookie`` header, in HTTP/1.0 and HTTP/1.1, RFC 7230 and RFC 6265
  make it clear that the ``Cookie`` header must only be sent once by a
  user-agent, and must be concatenated into a single octet string using the
  two-octet delimiter of 0x3b, 0x20 (the ASCII string "; "). However in HTTP/2,
  RFC 9113 states that ``Cookie`` headers MAY appear repeatedly, OR be
  concatenated using the two-octet delimiter of 0x3b, 0x20
  (the ASCII string "; ").

The ASGI design decision is to transport both request and response headers as
lists of 2-element ``[name, value]`` lists and preserve headers exactly as they
were provided.

For ASGI applications that support HTTP/2, care should be taken to handle the
special case for ``Cookie`` noted above.

The HTTP protocol should be signified to ASGI applications with a ``type``
value of ``http``.


HTTP Connection Scope
'''''''''''''''''''''

HTTP connections have a single-request *connection scope* - that is, your
application will be called at the start of the request, and will last until
the end of that specific request, even if the underlying socket is still open
and serving multiple requests.

If you hold a response open for long-polling or similar, the *connection scope*
will persist until the response closes from either the client or server side.

The *connection scope* information passed in ``scope`` contains:

* ``type`` (*Unicode string*) -- ``"http"``.

* ``asgi["version"]`` (*Unicode string*) -- Version of the ASGI spec.

* ``asgi["spec_version"]`` (*Unicode string*) -- Version of the ASGI
  HTTP spec this server understands; for example: ``"2.0"``, ``"2.1"``, ``"2.2"``,
  etc. Optional; if missing assume ``"2.0"``.

* ``http_version`` (*Unicode string*) -- One of ``"1.0"``, ``"1.1"`` or ``"2"``.

* ``method`` (*Unicode string*) -- The HTTP method name, uppercased.

* ``scheme`` (*Unicode string*) -- URL scheme portion (likely ``"http"`` or
  ``"https"``). Optional (but must not be empty); default is ``"http"``.

* ``path`` (*Unicode string*) -- HTTP request target excluding any query
  string, with percent-encoded sequences and UTF-8 byte sequences
  decoded into characters.

* ``raw_path`` (*byte string*) -- The original HTTP path component,
  excluding any query string, unmodified from the bytes that were
  received by the web server. Some web server implementations may
  be unable to provide this. Optional; if missing defaults to ``None``.

* ``query_string`` (*byte string*) -- URL portion after the ``?``,
  percent-encoded.

* ``root_path`` (*Unicode string*) -- The root path this application
  is mounted at; same as ``SCRIPT_NAME`` in WSGI. Optional; if missing
  defaults to ``""``.

* ``headers`` (*Iterable[[byte string, byte string]]*) -- An iterable of
  ``[name, value]`` two-item iterables, where ``name`` is the header name, and
  ``value`` is the header value. Order of header values must be preserved from
  the original HTTP request; order of header names is not important. Duplicates
  are possible and must be preserved in the message as received. Header names
  should be lowercased, but it is not required; servers should preserve header case
  on a best-effort basis. Pseudo headers (present in HTTP/2 and HTTP/3) must be
  removed; if ``:authority`` is present its value must be added to the start of
  the iterable with ``host`` as the header name or replace any existing host
  header already present.

* ``client`` (*Iterable[Unicode string, int]*) -- A two-item iterable
  of ``[host, port]``, where ``host`` is the remote host's IPv4 or
  IPv6 address, and ``port`` is the remote port as an
  integer. Optional; if missing defaults to ``None``.

* ``server`` (*Iterable[Unicode string, Optional[int]]*) -- Either a
  two-item iterable of ``[host, port]``, where ``host`` is the
  listening address for this server, and ``port`` is the integer
  listening port, or ``[path, None]`` where ``path`` is that of the
  unix socket. Optional; if missing defaults to ``None``.

* ``state`` Optional(*dict[Unicode string, Any]*) -- A copy of the
  namespace passed into the lifespan corresponding to this request. (See :doc:`lifespan`).
  Optional; if missing the server does not support this feature.

Servers are responsible for handling inbound and outbound chunked transfer
encodings. A request with a ``chunked`` encoded body should be automatically
de-chunked by the server and presented to the application as plain body bytes;
a response that is given to the server with no ``Content-Length`` may be chunked
as the server sees fit.


Request - ``receive`` event
'''''''''''''''''''''''''''

Sent to the application to indicate an incoming request. Most of the request
information is in the connection ``scope``; the body message serves as a way to
stream large incoming HTTP bodies in chunks, and as a trigger to actually run
request code (as you should not trigger on a connection opening alone).

Note that if the request is being sent using ``Transfer-Encoding: chunked``,
the server is responsible for handling this encoding. The ``http.request``
messages should contain just the decoded contents of each chunk.

Keys:

* ``type`` (*Unicode string*) -- ``"http.request"``.

* ``body`` (*byte string*) -- Body of the request. Optional; if
  missing defaults to ``b""``. If ``more_body`` is set, treat as start
  of body and concatenate on further chunks.

* ``more_body`` (*bool*) -- Signifies if there is additional content
  to come (as part of a Request message). If ``True``, the consuming
  application should wait until it gets a chunk with this set to
  ``False``. If ``False``, the request is complete and should be
  processed. Optional; if missing defaults to ``False``.


Response Start - ``send`` event
'''''''''''''''''''''''''''''''

Sent by the application to start sending a response to the client. Needs to be
followed by at least one response content message.

Protocol servers *need not* flush the data generated by this event to the
send buffer until the first *Response Body* event is processed.
This may give them more leeway to replace the response with an error response
in case internal errors occur while handling the request.

You may send a ``Transfer-Encoding`` header in this message, but the server
must ignore it. Servers handle ``Transfer-Encoding`` themselves, and may opt
to use ``Transfer-Encoding: chunked`` if the application presents a response
that has no ``Content-Length`` set.

Note that this is not the same as ``Content-Encoding``, which the application
still controls, and which is the appropriate place to set ``gzip`` or other
compression flags.

Keys:

* ``type`` (*Unicode string*) -- ``"http.response.start"``.

* ``status`` (*int*) -- HTTP status code.

* ``headers`` (*Iterable[[byte string, byte string]]*) -- An iterable
  of ``[name, value]`` two-item iterables, where ``name`` is the
  header name, and ``value`` is the header value. Order must be
  preserved in the HTTP response.  Header names must be
  lowercased. Optional; if missing defaults to an empty list. Pseudo
  headers (present in HTTP/2 and HTTP/3) must not be present.

* ``trailers`` (*bool*) -- Signifies if the application will send
  trailers. If ``True``, the server must wait until it receives a
  ``"http.response.trailers"`` message after the *Response Body* event.
  Optional; if missing defaults to ``False``.


Response Body - ``send`` event
''''''''''''''''''''''''''''''

Continues sending a response to the client. Protocol servers must
flush any data passed to them into the send buffer before returning from a
send call. If ``more_body`` is set to ``False``, and the server is not
expecting *Response Trailers* this will complete the response.

Keys:

* ``type`` (*Unicode string*) -- ``"http.response.body"``.

* ``body`` (*byte string*) -- HTTP body content. Concatenated onto any
  previous ``body`` values sent in this connection scope. Optional; if
  missing defaults to ``b""``.

* ``more_body`` (*bool*) -- Signifies if there is additional content
  to come (as part of a *Response Body* message). If ``False``, and the
  server is not expecting *Response Trailers* response will be taken as
  complete and closed, and any further messages on the channel will be
  ignored. Optional; if missing defaults to ``False``.


Disconnected Client - ``send`` exception
''''''''''''''''''''''''''''''''''''''''

If ``send()`` is called on a closed connection the server should raise
a server-specific subclass of ``OSError``. This is not guaranteed, however,
especially on older ASGI server implementations (it was introduced in spec
version 2.4).

Applications may catch this exception and do cleanup work before
re-raising it or returning with no exception.

Servers must be prepared to catch this exception if they raised it and
should not log it as an error in their server logs.


Disconnect - ``receive`` event
''''''''''''''''''''''''''''''

Sent to the application if receive is called after a response has been
sent or after the HTTP connection has been closed. This is mainly useful
for long-polling, where you may want to trigger cleanup code if the
connection closes early.

Once you have received this event, you should expect future calls to ``send()``
to raise an exception, as described above. However, if you have highly
concurrent code, you may find calls to ``send()`` erroring slightly before you
receive this event.

Keys:

* ``type`` (*Unicode string*) -- ``"http.disconnect"``.


WebSocket
---------

WebSockets share some HTTP details - they have a path and headers - but also
have more state. Again, most of that state is in the ``scope``, which will live
as long as the socket does.

WebSocket protocol servers should handle PING/PONG messages themselves, and
send PING messages as necessary to ensure the connection is alive.

WebSocket protocol servers should handle message fragmentation themselves,
and deliver complete messages to the application.

The WebSocket protocol should be signified to ASGI applications with
a ``type`` value of ``websocket``.


Websocket Connection Scope
''''''''''''''''''''''''''

WebSocket connections' scope lives as long as the socket itself - if the
application dies the socket should be closed, and vice-versa.

The *connection scope* information passed in ``scope`` contains initial connection
metadata (mostly from the HTTP request line and headers):

* ``type`` (*Unicode string*) -- ``"websocket"``.

* ``asgi["version"]`` (*Unicode string*) -- The version of the ASGI spec.

* ``asgi["spec_version"]`` (*Unicode string*) -- Version of the ASGI
  HTTP spec this server understands; one of ``"2.0"``, ``"2.1"``, ``"2.2"`` or
  ``"2.3"``. Optional; if missing assume ``"2.0"``.

* ``http_version`` (*Unicode string*) -- One of ``"1.1"`` or
  ``"2"``. Optional; if missing default is ``"1.1"``.

* ``scheme`` (*Unicode string*) -- URL scheme portion (likely ``"ws"`` or
  ``"wss"``). Optional (but must not be empty); default is ``"ws"``.

* ``path`` (*Unicode string*) -- HTTP request target excluding any query
  string, with percent-encoded sequences and UTF-8 byte sequences
  decoded into characters.

* ``raw_path`` (*byte string*) -- The original HTTP path component,
  excluding any query string, unmodified from the bytes that were
  received by the web server. Some web server implementations may
  be unable to provide this. Optional; if missing defaults to ``None``.

* ``query_string`` (*byte string*) -- URL portion after the
  ``?``. Optional; if missing or ``None`` default is empty string.

* ``root_path`` (*Unicode string*) -- The root path this application is
  mounted at; same as ``SCRIPT_NAME`` in WSGI. Optional; if missing
  defaults to empty string.

* ``headers`` (*Iterable[[byte string, byte string]]*) -- An iterable of
  ``[name, value]`` two-item iterables, where ``name`` is the header name and
  ``value`` is the header value. Order should be preserved from the original
  HTTP request; duplicates are possible and must be preserved in the message
  as received. Header names should be lowercased, but it is not required;
  servers should preserve header case on a best-effort basis.
  Pseudo headers (present in HTTP/2 and HTTP/3) must be removed;
  if ``:authority`` is present its value must be added to the
  start of the iterable with ``host`` as the header name
  or replace any existing host header already present.

* ``client`` (*Iterable[Unicode string, int]*) -- A two-item iterable
  of ``[host, port]``, where ``host`` is the remote host's IPv4 or
  IPv6 address, and ``port`` is the remote port. Optional; if missing
  defaults to ``None``.

* ``server`` (*Iterable[Unicode string, Optional[int]]*) -- Either a
  two-item iterable of ``[host, port]``, where ``host`` is the
  listening address for this server, and ``port`` is the integer
  listening port, or ``[path, None]`` where ``path`` is that of the
  unix socket. Optional; if missing defaults to ``None``.

* ``subprotocols`` (*Iterable[Unicode string]*) -- Subprotocols the
  client advertised. Optional; if missing defaults to empty list.

* ``state`` Optional(*dict[Unicode string, Any]*) -- A copy of the
  namespace passed into the lifespan corresponding to this request. (See :doc:`lifespan`).
  Optional; if missing the server does not support this feature.


Connect - ``receive`` event
'''''''''''''''''''''''''''

Sent to the application when the client initially opens a connection and is about
to finish the WebSocket handshake.

This message must be responded to with either an *Accept* message
or a *Close* message before the socket will pass ``websocket.receive``
messages. The protocol server must send this message
during the handshake phase of the WebSocket and not complete the handshake
until it gets a reply, returning HTTP status code ``403`` if the connection is
denied.

Keys:

* ``type`` (*Unicode string*) -- ``"websocket.connect"``.


Accept - ``send`` event
'''''''''''''''''''''''

Sent by the application when it wishes to accept an incoming connection.

* ``type`` (*Unicode string*) -- ``"websocket.accept"``.

* ``subprotocol`` (*Unicode string*) -- The subprotocol the server
  wishes to accept. Optional; if missing defaults to ``None``.

* ``headers`` (*Iterable[[byte string, byte string]]*) -- An iterable
  of ``[name, value]`` two-item iterables, where ``name`` is the
  header name, and ``value`` is the header value. Order must be
  preserved in the HTTP response.  Header names must be
  lowercased. Must not include a header named
  ``sec-websocket-protocol``; use the ``subprotocol`` key
  instead. Optional; if missing defaults to an empty list. *Added in
  spec version 2.1*. Pseudo headers (present in HTTP/2 and HTTP/3)
  must not be present.


Receive - ``receive`` event
'''''''''''''''''''''''''''

Sent to the application when a data message is received from the client.

Keys:

* ``type`` (*Unicode string*) -- ``"websocket.receive"``.

* ``bytes`` (*byte string*) -- The message content, if it was binary
  mode, or ``None``. Optional; if missing, it is equivalent to
  ``None``.

* ``text`` (*Unicode string*) -- The message content, if it was text
  mode, or ``None``. Optional; if missing, it is equivalent to
  ``None``.

Exactly one of ``bytes`` or ``text`` must be non-``None``. One or both
keys may be present, however.


Send - ``send`` event
'''''''''''''''''''''

Sent by the application to send a data message to the client.

Keys:

* ``type`` (*Unicode string*) -- ``"websocket.send"``.

* ``bytes`` (*byte string*) -- Binary message content, or ``None``.
   Optional; if missing, it is equivalent to ``None``.

* ``text`` (*Unicode string*) -- Text message content, or ``None``.
   Optional; if missing, it is equivalent to ``None``.

Exactly one of ``bytes`` or ``text`` must be non-``None``. One or both
keys may be present, however.


.. _disconnect-receive-event-ws:

Disconnect - ``receive`` event
''''''''''''''''''''''''''''''

Sent to the application when either connection to the client is lost, either from
the client closing the connection, the server closing the connection, or loss of the
socket.

Once you have received this event, you should expect future calls to ``send()``
to raise an exception, as described below. However, if you have highly
concurrent code, you may find calls to ``send()`` erroring slightly before you
receive this event.

Keys:

* ``type`` (*Unicode string*) -- ``"websocket.disconnect"``

* ``code`` (*int*) -- The WebSocket close code, as per the WebSocket spec. If no code
  was received in the frame from the client, the server should set this to ``1005``
  (the default value in the WebSocket specification).

* ``reason`` (*Unicode string*) -- A reason given for the disconnect, can
  be any string. Optional; if missing or ``None`` default is empty
  string.


Disconnected Client - ``send`` exception
''''''''''''''''''''''''''''''''''''''''

If ``send()`` is called on a closed connection the server should raise
a server-specific subclass of ``OSError``. This is not guaranteed, however,
especially on older ASGI server implementations (it was introduced in spec
version 2.4).

Applications may catch this exception and do cleanup work before
re-raising it or returning with no exception.

Servers must be prepared to catch this exception if they raised it and
should not log it as an error in their server logs.


Close - ``send`` event
''''''''''''''''''''''

Sent by the application to tell the server to close the connection.

If this is sent before the socket is accepted, the server
must close the connection with a HTTP 403 error code
(Forbidden), and not complete the WebSocket handshake; this may present on some
browsers as a different WebSocket error code (such as 1006, Abnormal Closure).

If this is sent after the socket is accepted, the server must close the socket
with the close code passed in the message (or 1000 if none is specified).

* ``type`` (*Unicode string*) -- ``"websocket.close"``.

* ``code`` (*int*) -- The WebSocket close code, as per the WebSocket
  spec.  Optional; if missing defaults to ``1000``.

* ``reason`` (*Unicode string*) -- A reason given for the closure, can
  be any string. Optional; if missing or ``None`` default is empty
  string.


WSGI Compatibility
------------------

Part of the design of the HTTP portion of this spec is to make sure it
aligns well with the WSGI specification, to ensure easy adaptability
between both specifications and the ability to keep using WSGI
applications with ASGI servers.

WSGI applications, being synchronous, must be run in a threadpool in order
to be served, but otherwise their runtime maps onto the HTTP connection scope's
lifetime.

There is an almost direct mapping for the various special keys in
WSGI's ``environ`` variable to the ``http`` scope:

* ``REQUEST_METHOD`` is the ``method``
* ``SCRIPT_NAME`` is ``root_path``
* ``PATH_INFO`` can be derived by stripping ``root_path`` from ``path``
* ``QUERY_STRING`` is ``query_string``
* ``CONTENT_TYPE`` can be extracted from ``headers``
* ``CONTENT_LENGTH`` can be extracted from ``headers``
* ``SERVER_NAME`` and ``SERVER_PORT`` are in ``server``
* ``REMOTE_HOST``/``REMOTE_ADDR`` and ``REMOTE_PORT`` are in ``client``
* ``SERVER_PROTOCOL`` is encoded in ``http_version``
* ``wsgi.url_scheme`` is ``scheme``
* ``wsgi.input`` is a ``StringIO`` based around the ``http.request`` messages
* ``wsgi.errors`` is directed by the wrapper as needed

The ``start_response`` callable maps similarly to ``http.response.start``:

* The ``status`` argument becomes ``status``, with the reason phrase dropped.
* ``response_headers`` maps to ``headers``

Yielding content from the WSGI application maps to sending
``http.response.body`` messages.


WSGI encoding differences
-------------------------

The WSGI specification (as defined in PEP 3333) specifies that all strings
sent to or from the server must be of the ``str`` type but only contain
codepoints in the ISO-8859-1 ("latin-1") range. This was due to it originally
being designed for Python 2 and its different set of string types.

The ASGI HTTP and WebSocket specifications instead specify each entry of the
``scope`` dict as either a byte string or a Unicode string. HTTP, being an
older protocol, is sometimes imperfect at specifying encoding, so some
decisions of what is Unicode versus bytes may not be obvious.

* ``path``: URLs can have both percent-encoded and UTF-8 encoded sections.
  Because decoding these is often done by the underlying server (or sometimes
  even proxies in the path), this is a Unicode string, fully decoded from both
  UTF-8 encoding and percent encodings.

* ``headers``: These are byte strings of the exact byte sequences sent by the
  client/to be sent by the server. While modern HTTP standards say that headers
  should be ASCII, older ones did not and allowed a wider range of characters.
  Frameworks/applications should decode headers as they deem appropriate.

* ``query_string``: Unlike the ``path``, this is not as subject to server
  interference and so is presented as its raw byte string version,
  percent-encoded.

* ``root_path``: Unicode string to match ``path``.


Version History
---------------


* 2.0 (2017-11-28): Initial non-channel-layer based ASGI spec


Copyright
---------


This document has been placed in the public domain.
