====================================
HTTP & WebSocket ASGI Message Format
====================================

**Version**: 2.1 (2019-03-20)

The HTTP+WebSocket ASGI sub-specification outlines how to transport HTTP/1.1,
HTTP/2 and WebSocket connections within ASGI.

It is deliberately intended and designed to be a superset of the WSGI format
and specifies how to translate between the two for the set of requests that
are able to be handled by WSGI.


Spec Versions
-------------

This spec has had two versions:

* ``2.0``: The first version of the spec, released with ASGI 2.0
* ``2.1``: Added the ``headers`` key to the WebSocket Accept response.

Spec versions let you understand what the server you are using understands -
if a server tells you it only supports version ``2.0`` of this spec, then
sending ``headers`` with a WebSocket Accept message is an error, for example.

They are separate from the HTTP version or the ASGI version.


HTTP
----

The HTTP format covers HTTP/1.0, HTTP/1.1 and HTTP/2, as the changes in
HTTP/2 are largely on the transport level. A protocol server should give
different requests on the same HTTP/2 connection different scopes, and
correctly multiplex the responses back into the same stream as they come in.
The HTTP version is available as a string in the scope.

Multiple header fields with the same name are complex in HTTP. RFC 7230
states that for any header field that can appear multiple times, it is exactly
equivalent to sending that header field only once with all the values joined by
commas.

However, RFC 7230 and RFC 6265 make it clear that this rule does not apply to
the various headers used by HTTP cookies (``Cookie`` and ``Set-Cookie``). The
``Cookie`` header must only be sent once by a user-agent, but the
``Set-Cookie`` header may appear repeatedly and cannot be joined by commas.
The ASGI design decision is to transport both request and response headers as
lists of 2-element ``[name, value]`` lists and preserve headers exactly as they
were provided.

The HTTP protocol should be signified to ASGI applications with a ``type``
value of ``http``.


Connection Scope
''''''''''''''''

HTTP connections have a single-request connection scope - that is, your
applications will be instantiated at the start of the request, and destroyed
at the end, even if the underlying socket is still open and serving multiple
requests.

If you hold a response open for long-polling or similar, the scope will
persist until the response closes from either the client or server side.

The connection scope contains:

* ``type``: ``http``

* ``asgi["version"]``: The version of the ASGI spec, as a string.

* ``asgi['spec_version']``: Version of the ASGI HTTP spec this server understands
   as a string; one of ``2.0`` or ``2.1``. Optional, if missing assume ``2.0``.

* ``http_version``: Unicode string, one of ``1.0``, ``1.1`` or ``2``.

* ``method``: Unicode string HTTP method name, uppercased.

* ``scheme``: Unicode string URL scheme portion (likely ``http`` or ``https``).
  Optional (but must not be empty), default is ``"http"``.

* ``path``: Unicode string HTTP request target excluding any query
  string, with percent escapes decoded and UTF-8 byte sequences
  decoded into characters.

* ``query_string``: Byte string URL portion after the ``?``, not url-decoded.

* ``root_path``: Unicode string that indicates the root path this application
  is mounted at; same as ``SCRIPT_NAME`` in WSGI. Optional, defaults
  to ``""``.

* ``headers``: An iterable of ``[name, value]`` two-item iterables, where
  ``name`` is the byte string header name, and ``value`` is the byte string
  header value. Order of header values must be preserved from the original HTTP
  request; order of header names is not important. Duplicates are possible and
  must be preserved in the message as received.
  Header names must be lowercased.

* ``client``: A two-item iterable of ``[host, port]``, where ``host``
  is a unicode string of the remote host's IPv4 or IPv6 address, and
  ``port`` is the remote port as an integer. Optional, defaults to ``None``.

* ``server``: A two-item iterable of ``[host, port]``, where ``host``
  is the listening address for this server as a unicode string, and ``port``
  is the integer listening port. Optional, defaults to ``None``.


Request
'''''''

Sent to indicate an incoming request. Most of the request information is in
the connection scope; the body message serves as a way to stream large incoming
HTTP bodies in chunks, and as a trigger to actually run request code (as you
should not trigger on a connection opening alone).

Keys:

* ``type``: ``http.request``

* ``body``: Body of the request, as a byte string. Optional, defaults to ``b""``.
  If ``more_body`` is set, treat as start of body and concatenate
  on further chunks.

* ``more_body``: Boolean value signifying if there is additional content
  to come (as part of a Request message). If ``True``, the consuming
  application should wait until it gets a chunk with this set to ``False``. If
  ``False``, the request is complete and should be processed. Optional, defaults
  to ``False``.


Response Start
''''''''''''''

Starts sending a response to the client. Needs to be followed by at least
one response content message. The protocol server must not start sending the
response to the client until it has received at least one *Response Body* event.

Keys:

* ``type``: ``http.response.start``

* ``status``: Integer HTTP status code.

* ``headers``: A list of ``[name, value]`` lists, where ``name`` is the
  byte string header name, and ``value`` is the byte string
  header value. Order must be preserved in the HTTP response. Header names
  must be lowercased. Optional, defaults to an empty list.


Response Body
'''''''''''''

Continues sending a response to the client. Protocol servers must
flush any data passed to them into the send buffer before returning from a
send call. If ``more_body`` is set to ``False`` this will
close the connection.

Keys:

* ``type``: ``http.response.body``

* ``body``: Byte string of HTTP body content. Concatenated onto any previous
  ``body`` values sent in this connection scope. Optional, defaults to
  ``b""``.

* ``more_body``: Boolean value signifying if there is additional content
  to come (as part of a Response Body message). If ``False``, response will
  be taken as complete and closed off, and any further messages on the channel
  will be ignored. Optional, defaults to ``False``.


Disconnect
''''''''''

Sent to the application when a HTTP connection is closed or if receive
is called after a response has been sent. This is mainly useful for
long-polling, where you may want to trigger cleanup code if the
connection closes early.

Keys:

* ``type``: ``http.disconnect``


WebSocket
---------

WebSockets share some HTTP details - they have a path and headers - but also
have more state. Again, most of that state is in the scope, which will live
as long as the socket does.

WebSocket protocol servers should handle PING/PONG messages themselves, and
send PING messages as necessary to ensure the connection is alive.

WebSocket protocol servers should handle message fragmentation themselves,
and deliver complete messages to the application.

The WebSocket protocol should be signified to ASGI applications with
a ``type`` value of ``websocket``.


Connection Scope
''''''''''''''''

WebSocket connections' scope lives as long as the socket itself - if the
application dies the socket should be closed, and vice-versa. The scope
contains the initial connection metadata (mostly from the HTTP handshake):

* ``type``: ``websocket``

* ``asgi["version"]``: The version of the ASGI spec, as a string.

* ``asgi['spec_version']``: Version of the ASGI HTTP spec this server understands
   as a string; one of ``2.0`` or ``2.1``. Optional, if missing assume ``2.0``.

* ``http_version``: Unicode string, one of ``1.1`` or ``2``. Optional,
  default is ``1.1``.

* ``scheme``: Unicode string URL scheme portion (likely ``ws`` or ``wss``).
  Optional (but must not be empty), default is ``ws``.

* ``path``: Unicode string HTTP request target excluding any query
  string, with percent escapes decoded and UTF-8 byte sequences
  decoded into characters.

* ``query_string``: Byte string URL portion after the ``?``. Optional, default
  is empty string.

* ``root_path``: Byte string that indicates the root path this application
  is mounted at; same as ``SCRIPT_NAME`` in WSGI. Optional, defaults
  to empty string.

* ``headers``: An iterable of ``[name, value]`` two-item iterables, where
  ``name`` is the header name as byte string and ``value`` is the header value
  as a byte string. Order should be preserved from the original HTTP request;
  duplicates are possible and must be preserved in the message as received.
  Header names must be lowercased.

* ``client``: A two-item iterable of ``[host, port]``, where ``host``
  is a unicode string of the remote host's IPv4 or IPv6 address, and
  ``port`` is the remote port as an integer. Optional, defaults to ``None``.

* ``server``: A two-item iterable of ``[host, port]``, where ``host``
  is the listening address for this server as a unicode string, and ``port``
  is the integer listening port. Optional, defaults to ``None``.

* ``subprotocols``: List of subprotocols the client advertised as unicode
  strings. Optional, defaults to empty list.


Connection
''''''''''

Sent when the client initially opens a connection and is about to finish the
WebSocket handshake.

This message must be responded to with either an *Accept* message
or a *Close* message before the socket will pass ``websocket.receive``
messages. The protocol server must send this message
during the handshake phase of the WebSocket and not complete the handshake
until it gets a reply, returning HTTP status code ``403`` if the connection is
denied.

Keys:

* ``type``: ``websocket.connect``


Accept
''''''

Sent by the application when it wishes to accept an incoming connection.

* ``type``: ``websocket.accept``

* ``subprotocol``: The subprotocol the server wishes to accept, as a unicode
  string. Optional, defaults to ``None``.

* ``headers``: A list of ``[name, value]`` lists, where ``name`` is
  the byte string header name, and ``value`` is the byte string header
  value. Order must be preserved in the HTTP response. Header names
  must be lowercased. Must not include a ``sec-websocket-protocol``
  named header, use the ``subprotocol`` key instead.  Optional,
  defaults to an empty list. *Added in spec version 2.1*


Receive
'''''''

Sent when a data message is received from the client.

Keys:

* ``type``: ``websocket.receive``

* ``bytes``: Byte string of the message content, if it was binary mode, or
  ``None``. Optional; if missing, it is equivalent to ``None``.

* ``text``: Unicode string of the message content, if it was text mode, or
  ``None``. Optional; if missing, it is equivalent to ``None``.

Exactly one of ``bytes`` or ``text`` must be non-``None``. One or both
keys may be present, however.


Send
''''

Sends a data message to the client.

Keys:

* ``type``: ``websocket.send``

* ``bytes``: Byte string of binary message content, or ``None``.
   Optional; if missing, it is equivalent to ``None``.

* ``text``: Unicode string of text message content, or ``None``.
   Optional; if missing, it is equivalent to ``None``.

Exactly one of ``bytes`` or ``text`` must be non-``None``. One or both
keys may be present, however.


Disconnection
'''''''''''''

Sent when either connection to the client is lost, either from the client
closing the connection, the server closing the connection, or loss of the
socket.

Keys:

* ``type``: ``websocket.disconnect``

* ``code``: The WebSocket close code (integer), as per the WebSocket spec.


Close
'''''

Tells the server to close the connection.

If this is sent before the socket is accepted, the server
must close the connection with a HTTP 403 error code
(Forbidden), and not complete the WebSocket handshake; this may present on some
browsers as a different WebSocket error code (such as 1006, Abnormal Closure).

If this is sent after the socket is accepted, the server must close the socket
with the close code passed in the message (or 1000 if none is specified).

* ``type``: ``websocket.close``

* ``code``: The WebSocket close code (integer), as per the WebSocket spec.
  Optional, defaults to ``1000``.


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

* ``REQUEST_METHOD`` is the ``method`` key
* ``SCRIPT_NAME`` is ``root_path``
* ``PATH_INFO`` can be derived from ``path`` and ``root_path``
* ``QUERY_STRING`` is ``query_string``
* ``CONTENT_TYPE`` can be extracted from ``headers``
* ``CONTENT_LENGTH`` can be extracted from ``headers``
* ``SERVER_NAME`` and ``SERVER_PORT`` are in ``server``
* ``REMOTE_HOST``/``REMOTE_ADDR`` and ``REMOTE_PORT`` are in ``client``
* ``SERVER_PROTOCOL`` is encoded in ``http_version``
* ``wsgi.url_scheme`` is ``scheme``
* ``wsgi.input`` is a StringIO based around the ``http.request`` messages
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
``scope`` dict as either a bytestring or a unicode string. HTTP, being an older
protocol, is sometimes imperfect at specifying encoding, so some decisions
of what is unicode versus bytes may not be obvious.

* ``path``: URLs can have both percent-encoded and UTF-8 encoded sections.
  Because decoding these is often done by the underlying server (or sometimes
  even proxies in the path), this is a unicode string, fully decoded from both
  UTF-8 encoding and percent encodings.

* ``headers``: These are bytestrings of the exact byte sequences sent by the
  client/to be sent by the server. While modern HTTP standards say that headers
  should be ASCII, older ones did not and allowed a wider range of characters.
  Frameworks/applications should decode headers as they deem appropriate.

* ``query_string``: Unlike the ``path``, this is not as subject to server
  interference and so is presented as its raw bytestring version, undecoded.

* ``root_path``: Unicode to match ``path``.


Version History
===============

* 2.0 (2017-11-28): Initial non-channel-layer based ASGI spec


Copyright
=========

This document has been placed in the public domain.
