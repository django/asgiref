asgiref
=======

.. image:: https://api.travis-ci.org/django/asgiref.svg
    :target: https://travis-ci.org/django/asgiref

.. image:: https://img.shields.io/pypi/v/asgiref.svg
    :target: https://pypi.python.org/pypi/asgiref

ASGI is a standard for Python asynchronous web apps and servers to communicate
with each other, and positioned as an asynchronous successor to WSGI. You can
read more at https://asgi.readthedocs.io/en/latest/

This package includes ASGI base libraries, such as:

* Sync-to-async and async-to-sync function wrappers, ``asgiref.sync``
* Server base classes, ``asgiref.server``
* A WSGI-to-ASGI adapter, in ``asgiref.wsgi``


Function wrappers
-----------------

These allow you to wrap or decorate async or sync functions to call them from
the other style (so you can call async functions from a synchronous thread,
or vice-versa).

In particular:

* AsyncToSync lets a synchronous subthread stop and wait while the async
  function is called on the main thread's event loop, and then control is
  returned to the thread when the async function is finished.

* SyncToAsync lets async code call a synchronous function, which is run in
  a threadpool and control returned to the async coroutine when the synchronous
  function completes.

The idea is to make it easier to call synchronous APIs from async code and
asynchronous APIs from synchronous code so it's easier to transition code from
one style to the other. In the case of Channels, we wrap the (synchronous)
Django view system with SyncToAsync to allow it to run inside the (asynchronous)
ASGI server.


Threadlocal replacement
-----------------------

This is a drop-in replacement for ``threading.local`` that works with both
threads and asyncio Tasks. Even better, it will proxy values through from a
task-local context to a thread-local context when you use ``sync_to_async``
to run things in a threadpool, and vice-versa for ``async_to_sync``.

If you instead want true thread- and task-safety, you can set
``thread_critical`` on the Local object to ensure this instead.


Server base classes
-------------------

Includes a ``StatelessServer`` class which provides all the hard work of
writing a stateless server (as in, does not handle direct incoming sockets
but instead consumes external streams or sockets to work out what is happening).

An example of such a server would be a chatbot server that connects out to
a central chat server and provides a "connection scope" per user chatting to
it. There's only one actual connection, but the server has to separate things
into several scopes for easier writing of the code.

You can see an example of this being used in `frequensgi <https://github.com/andrewgodwin/frequensgi>`_.


WSGI-to-ASGI adapter
--------------------

Allows you to wrap a WSGI application so it appears as a valid ASGI application.

Simply wrap it around your WSGI application like so::

    asgi_application = WsgiToAsgi(wsgi_application)

The WSGI application will be run in a synchronous threadpool, and the wrapped
ASGI application will be one that accepts ``http`` class messages.

Please note that not all extended features of WSGI may be supported (such as
file handles for incoming POST bodies).


Dependencies
------------

``asgiref`` requires Python 3.5 or higher.


Contributing
------------

Please refer to the
`main Channels contributing docs <https://github.com/django/channels/blob/master/CONTRIBUTING.rst>`_.


Testing
'''''''

To run tests, make sure you have installed the ``tests`` extra with the package::

    cd asgiref/
    pip install -e .[tests]
    pytest


Building the documentation
''''''''''''''''''''''''''

The documentation uses `Sphinx <http://www.sphinx-doc.org>`_::

    cd asgiref/docs/
    pip install sphinx

To build the docs, you can use the default tools::

    sphinx-build -b html . _build/html  # or `make html`, if you've got make set up
    cd _build/html
    python -m http.server

...or you can use ``sphinx-autobuild`` to run a server and rebuild/reload
your documentation changes automatically::

    pip install sphinx-autobuild
    sphinx-autobuild . _build/html


Maintenance and Security
------------------------

To report security issues, please contact security@djangoproject.com. For GPG
signatures and more security process information, see
https://docs.djangoproject.com/en/dev/internals/security/.

To report bugs or request new features, please open a new GitHub issue.

This repository is part of the Channels project. For the shepherd and maintenance team, please see the
`main Channels readme <https://github.com/django/channels/blob/master/README.rst>`_.
