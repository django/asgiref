
ASGI Documentation
==================

ASGI (*Asynchronous Server Gateway Interface*) is a spiritual successor to
WSGI, intended to provide a standard interface between async-capable Python
web servers, frameworks, and applications.

Where WSGI provided a standard for synchronous Python apps, ASGI provides one
for both asynchronous and synchronous apps, with a WSGI backwards-compatibility
implementation and multiple servers and application frameworks.

You can read more in the :doc:`introduction <introduction>` to ASGI, look
through the :doc:`specifications <specs/index>`, and see what
:doc:`implementations <implementations>` there already are or that are upcoming.

Contribution and discussion about ASGI is welcome, and mostly happens on
the `asgiref GitHub repository <https://github.com/django/asgiref>`_.

.. toctree::
   :maxdepth: 1

   introduction
   specs/index
   extensions
   implementations
