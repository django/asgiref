===============
Implementations
===============

Complete or upcoming implementations of ASGI - servers, frameworks, and other
useful pieces.

Servers
=======

Daphne
------

*Stable* / http://github.com/django/daphne

The current ASGI reference server, written in Twisted and maintained as part
of the Django Channels project. Supports HTTP/1, HTTP/2, and WebSockets.


Uvicorn
-------

*Stable* / https://www.uvicorn.org/

A fast ASGI server based on uvloop and httptools.
Supports HTTP/1 and WebSockets.


Hypercorn
---------

*Beta* / https://pgjones.gitlab.io/hypercorn/index.html

An ASGI server based on the sans-io hyper, h11, h2, and wsproto libraries.
Supports HTTP/1, HTTP/2, and WebSockets.


Application Frameworks
======================

Django/Channels
---------------

*Stable* / http://channels.readthedocs.io

Channels is the Django project to add asynchronous support to Django and is the
original driving force behind the ASGI project. Supports HTTP and WebSockets
with Django integration, and any protocol with ASGI-native code.


Quart
-----

*Beta* / https://github.com/pgjones/quart

Quart is a Python ASGI web microframework. It is intended to provide the easiest
way to use asyncio functionality in a web context, especially with existing Flask apps.
Supports HTTP.


Starlette
---------

*Beta* / https://github.com/encode/starlette

Starlette is a minimalist ASGI library for writing against basic but powerful
``Request`` and ``Response`` classes. Supports HTTP.
