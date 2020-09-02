==================================
TLS Connection Information in ASGI
==================================

**Version**: 0.1 (2020-09-02)

**Status: This is a draft specification.**

This TLS ASGI sub-specification outlines how to transport TLS (or SSL)
connection information in the ASGI *connection scope* object.

The Inner Protocol
------------------

TLS is not usable on its own, it always wraps another protocol.
So this ASGI sub-specification is not designed to be usable on its own,
it must be used as an addon to another ASGI sub-specification.
That other ASGI sub-specification is referred to as the *inner protocol
specification*.

For HTTP-over-TLS (HTTPS), use this TLS sub-specification and the
ASGI HTTP sub-specification.  The *inner protocol specification* is the
ASGI HTTP sub-specification.

For WebSockets-over-TLS (wss:// protocol), use this TLS sub-specification
and the ASGI WebSockets sub-specification.  The *inner protocol specification*
is the ASGI WebSockets sub-specification.

When to use this specification
------------------------------

This specification, and the connection scope keys defined here, must only be
used for TLS connections.

For non-TLS connections, the ASGI server is forbidden from providing any of
the connection scope keys defined here.

So an ASGI application can check for the presence of the ``tls_used`` key in
the connection scope.  If present, the server supports this specification and
the connection is over TLS.  If not present, either the server does not support
this specification or the connection is not over TLS.

TLS Connection Scope
--------------------

The lifetime of the *connection scope* is defined in the *inner protocol
specification*.  However, the *inner protocol specification* must define the 
*connection scope* in a way that ensures it covers at most one TLS connection.

The *connection scope* information passed in ``scope`` contains the following
extra values, as well as the ones defined in the *inner protocol
specification*:

* ``tls_used`` (*bool*) -- Must be ``True`` to indicate that this connection is
  over TLS.  Mandatory.

* ``tls_server_cert`` (*Optional[Unicode string]*) -- The PEM-encoded conversion
  of the x509 certificate sent by the server when establishing the TLS
  connection.  Some web server implementations may be unable to provide this
  (e.g. if TLS is terminated by a separate proxy or load balancer); in that
  case this shall be ``None``.  Optional; defaults to ``None``.

* ``tls_client_cert_chain`` (*Iterable[Unicode string]*) -- An iterable of
  Unicode strings, where each string is a PEM-encoded x509 certificate.
  The first certificate is the client certificate.  Any subsequent certificates
  are part of the certificate chain sent by the client, with each certificate
  signing the preceeding one.  Only applicable if the connection was over TLS;
  for non-TLS connections or if the client did not provide a client certificate
  then it will be an empty iterable.  Some web server implementations may be
  unable to provide this (e.g. if TLS is terminated by a separate proxy or
  load balancer); in that case this shall be an empty list. Optional; defaults
  to empty list.

* ``tls_client_cert_name`` (*Optional[Unicode string]*) -- The x509 Distinguished
  Name of the Subject of the client certificate, as a single string encoded as
  defined in RFC4514.  If the client did not provide a client certificate then
  it will be ``None``. Some web server implementations may be unable to provide
  this (e.g. if TLS is terminated by a separate proxy or load balancer); in that
  case this shall be ``None``. If ``tls_client_cert_chain`` is provided and
  non-empty then this field must be provided and must contain information that
  is consistent with ``tls_client_cert_chain[0]``.  Note that under some setups,
  (e.g. where TLS is terminated by a separate proxy or load balancer and that
  device forwards the client certificate name to the web server), this field
  may be set even where ``tls_client_cert_chain`` is not set.  Optional; defaults
  to ``None``.

* ``tls_client_cert_error`` (*Optional[Unicode string]*) -- ``None`` if a client
  certificate was provided and successfully verified, or was not provided.
  If a client certificate was provided but verification failed, this is a
  non-empty string containing an error message or error code indicating why
  validation failed; the details are web server specific. Most web server
  implementations will reject the connection if the client certificate
  verification failed, instead of setting this value.  However, some may be
  configured to allow the connection anyway.  This is especially useful when
  testing that client certificates are supported properly by the client - it
  allows a response containing an error message that can be presented to a
  human, instead of just refusing the connection. Optional; defaults to ``None``.

* ``tls_version`` (*Optional[int]*) -- The TLS version in use.  This is one of
  the version numbers as defined in the TLS specifications, which is an
  unsigned integer.  Common values include ``0x0303`` for TLS 1.2 or ``0x0304``
  for TLS 1.3.  If TLS is not in use, set to ``None``.  Some web server
  implementations may be unable to provide this (e.g. if TLS is terminated by a
  separate proxy or load balancer); in that case set to ``None``. Optional;
  defaults to ``None``.

* ``tls_cipher_suite`` (*Optional[int]*) -- The TLS cipher suite that is being
  used.  This is a 16-bit unsigned integer that encodes the pair of 8-bit
  integers specified in the relevant RFC, in network byte order.  For example
  RFC8446 defines that the cipher suite ``TLS_AES_128_GCM_SHA256`` is
  ``{0x13, 0x01}``; that is encoded as a ``tls_cipher_suite`` value of
  ``0x1301`` (equal to 4865).  If TLS is not in use, set to ``None``.  Some web
  server implementations may be unable to provide this (e.g. if TLS is
  terminated by a separate proxy or load balancer); in that case set to
  ``None``. Optional; defaults to ``None``.

Events
------

All events are as defined in the *inner protocol specification*.

Rationale (Informative)
-----------------------

This section explains the choices that led to this specification.

Providing the entire TLS certificates in ``tls_client_cert_chain``, rather than a
parsed subset:

* makes it easier for webservers to implement, as they do not have to
  include a parser for the entirity of the x509 certificate specifications
  (which are huge and complicated).  They just have to convert the binary
  DER format certificate from the wire, to the text PEM format.  That is
  supported by many off-the-shelf libraries.
* makes it easier for webservers to maintain, as they do not have to update
  their parser when new certificate fields are defined.
* makes it easier for clients as there are plenty of existing x509 libraries
  available that they can use to parse the certificate; they don't need to
  do some special ASGI-specific thing.
* improves interoperability as this is a simple, well-defined encoding, that
  clients and servers are unlikely to get wrong.
* makes it much easier to write this specification.  There is no standard
  documented format for a parsed certificate in Python, and we would need to
  write one.
* makes it much easier to maintain this specification.  There is no need
  to update a parsed certificate specification when new certificate fields
  are defined.
* allows the client to support new certificate fields without requiring
  any server changes, so long as the fields are marked as "non-critical" in
  the certificate.  (A x509 parser is allowed to ignore non-critical fields
  it does not understand.  Critical fields that are not understood cause
  certificate parsing to fail).
* allows the client to do wierd and wonderful things with the raw certificate,
  instead of placing arbitrary limits on it.

Specifying ``tls_version`` as an integer, not a string or float:

* avoids maintenance effort in this specification. If a new version of TLS is
  defined, then no changes are needed in this specification.
* does not significantly affect servers.  Whatever format we specified, servers
  would likely need a lookup table from what their TLS library reports to what
  this API needs.  (Unless their TLS library provides access to the raw value,
  in which case it can be reported via this API directly).
* does not significantly affect clients.  Whatever format we specified, clients
  would likely need a lookup table from what this API reports to the values
  they support and wish to use internally.

Specifying ``tls_cipher_suite`` as an integer, not a string:

* avoids significant effort to compile a list of cipher suites in this
  specification.  There are a huge number of existing TLS cipher suites, many
  of which are not widely used, even listing them all would be a huge effort.
* avoids maintenance effort in this specification. If a new cipher suite is
  defined, then no changes are needed in this specification.
* avoids dependencies on nonstandard TLS-library-specific names.  E.g. the
  cipher names used by OpenSSL are different from the cipher names used by the
  RFCs.
* does not significantly affect servers.  Whatever format we specified, (unless
  it was a nonstandard library-specific name and the server happened to use
  that library), servers would likely need a lookup table from what their
  TLS library reports to what this API needs.  (Unless their TLS library
  provides access to the raw value, in  which case it can be reported via this
  API directly).
* does not significantly affect clients.  Whatever format we specified, clients
  would likely need a lookup table from what this API reports to the values
  they support and wish to use internally.
* Using a single integer, rather than a pair of integers, makes handling this
  value simpler and faster.

``tls_client_cert_name`` duplicates information that is also available in
``tls_client_cert_chain``.  However, many ASGI applications will probably find
that information is sufficient for their application - it provides a simple
string that identifies the user.  It is simpler to use than parsing the x509
certificate.  For the server, this information is readily available.

There are theoretical interoperability problems with ``tls_client_cert_name``,
since it depends on a list of object ID names that is maintained by IANA and
theoretically can change.  In practise, this is not a real problem, since the
object IDs that are actually used in certificates have not changed in many
years.  So in practise it will be fine.


Copyright
---------

This document has been placed in the public domain.
