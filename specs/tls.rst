==================
ASGI TLS Extension
==================

**Version**: 0.3 (2026-09-15)

This specification outlines how to report TLS (or SSL) connection information
in the ASGI *connection scope* object.

The Base Protocol
-----------------

TLS is not usable on its own, it always wraps another protocol.
So this specification is not designed to be usable on its own,
it must be used as an extension to another ASGI specification.
That other ASGI specification is referred to as the *base protocol
specification*.

For HTTP-over-TLS (HTTPS), use this TLS specification and the
ASGI HTTP specification.  The *base protocol specification* is the
ASGI HTTP specification.  (See :doc:`www`)

For WebSockets-over-TLS (wss:// protocol), use this TLS specification
and the ASGI WebSockets specification.  The *base protocol specification*
is the ASGI WebSockets specification.  (See :doc:`www`)

If using this extension with other protocols (not HTTPS or WebSockets), note
that the *base protocol specification* must define the *connection scope* in a
way that ensures it covers at most one TLS connection.  If not, you cannot use
this extension.

When to use this extension
--------------------------

This extension must only be used for TLS connections.

For non-TLS connections, the ASGI server is forbidden from providing this
extension.

An ASGI application can check for the presence of the ``"tls"`` extension in
the ``extensions`` dictionary in the connection scope.  If present, the server
supports this extension and the connection is over TLS.  If not present,
either the server does not support this extension or the connection is not
over TLS.

TLS Connection Scope
--------------------

The *connection scope* information passed in ``scope`` contains an
``"extensions"`` key, which contains a dictionary of extensions.  Inside that
dictionary, the key ``"tls"`` identifies the extension specified in this
document.  The value will be a dictionary with the following entries:

* ``client_cert_chain`` (*Iterable[Unicode string]*) -- An iterable of
  Unicode strings, where each string is a PEM-encoded x509 certificate.
  The first certificate is the client certificate.  Any subsequent certificates
  are part of the certificate chain sent by the client, with each certificate
  signing the preceding one.  If the client did not provide a client
  certificate then it will be an empty iterable.  Some web server
  implementations may be unable to provide this (e.g. if TLS is terminated by a
  separate proxy or load balancer); in that case this shall be an empty
  iterable.  Optional; if missing defaults to empty iterable.

Events
------

All events are as defined in the *base protocol specification*.

Rationale (Informative)
-----------------------

This section explains the choices that led to this specification.

Providing the entire TLS certificates in ``client_cert_chain``, rather than a
parsed subset:

* Makes it easier for web servers to implement, as they do not have to
  include a parser for the entirety of the x509 certificate specifications
  (which are huge and complicated).  They just have to convert the binary
  DER format certificate from the wire, to the text PEM format.  That is
  supported by many off-the-shelf libraries.
* Makes it easier for web servers to maintain, as they do not have to update
  their parser when new certificate fields are defined.
* Makes it easier for clients as there are plenty of existing x509 libraries
  available that they can use to parse the certificate; they don't need to
  do some special ASGI-specific thing.
* Improves interoperability as this is a simple, well-defined encoding, that
  clients and servers are unlikely to get wrong.
* Makes it much easier to write this specification.  There is no standard
  documented format for a parsed certificate in Python, and we would need to
  write one.
* Makes it much easier to maintain this specification.  There is no need
  to update a parsed certificate specification when new certificate fields
  are defined.
* Allows the client to support new certificate fields without requiring
  any server changes, so long as the fields are marked as "non-critical" in
  the certificate.  (A x509 parser is allowed to ignore non-critical fields
  it does not understand.  Critical fields that are not understood cause
  certificate parsing to fail).
* Allows the client to do weird and wonderful things with the raw certificate,
  instead of placing arbitrary limits on it.

Version History
---------------

* 0.3 (2026-09-15): Removed all fields except ``client_cert_chain``.
* 0.2 (2020-10-02): Initial version.


Copyright
---------

This document has been placed in the public domain.
