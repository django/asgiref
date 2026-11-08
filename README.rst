asgiref
=======

.. image:: https://github.com/django/asgiref/actions/workflows/tests.yml/badge.svg
    :target: https://github.com/django/asgiref/actions/workflows/tests.yml

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

Note that exactly what threads things run in is very specific, and aimed to
keep maximum compatibility with old synchronous code. See
"Synchronous code & Threads" below for a full explanation. By default,
``sync_to_async`` will run all synchronous code in the program in the same
thread for safety reasons; you can disable this for more performance with
``@sync_to_async(thread_sensitive=False)``, but make sure that your code does
not rely on anything bound to threads (like database connections) when you do.


Thread-sensitive contexts
-------------------------

``ThreadSensitiveContext`` gives thread-sensitive ``sync_to_async`` calls a
shared, single-worker executor for an async block. This allows you to group
thread-sensitive calls, for example, per-request in a web application,
rather than per-process::

    class ASGIHandler(...):
        ...

        async def __call__(...):
            ...

            async with ThreadSensitiveContext():
                await self.handle(...)

By default, only the outermost ``ThreadSensitiveContext`` sets the
context. Nested calls are a no-op and reuse it.

Nested contexts can be created by passing the explicit ``executor`` keyword
argument.

* The executor must run one call at a time on one thread, such as
  ``ThreadPoolExecutor(max_workers=1)``. Recall, it is used for
  ``sync_to_async(…, thread_sensitive=True)`` calls.

* The calling code is responsible for the executor lifetime:
  the context does not shut it down. You may use it again for a later block,
  for example in a pool.

* Do not use one executor for two blocks at the same time.

By providing an executor, nested work can be run on a separate thread from the
parent context's, including when the block is reached through ``async_to_sync``::

    from concurrent.futures import ThreadPoolExecutor

    from asgiref.sync import ThreadSensitiveContext, sync_to_async

    worker = ThreadPoolExecutor(max_workers=1)

    async with ThreadSensitiveContext():
        await sync_to_async(parent_work)()
        async with ThreadSensitiveContext(executor=worker):
            await sync_to_async(child_work)()
            await sync_to_async(more_child_work)()
        await sync_to_async(parent_work)()

Both child calls run on the worker's thread. After the child block exits, calls
use the parent thread again. Nested ``sync_to_async`` / ``async_to_sync`` calls
within the child block also retain its thread affinity.

Tasks created inside a block inherit its context. Wait for those tasks before
leaving the context. A thread-sensitive call made by such a task after the
context has exited raises ``RuntimeError``. To isolate concurrent tasks, each
must enter its own context with its own executor.

A context with an executor can be entered only once: create a new one for each
block.

Executor contexts separate thread-critical ``Local`` storage but do not change
``ContextVar`` or plain ``Local`` propagation. ``thread_sensitive=False`` calls
are not affected.

Threadlocal replacement
-----------------------

``asgiref.local.Local`` provides a namespace for data local to the current
thread or async task, with attribute access like ``threading.local``. Import
and create an instance, then set, read, and delete attributes as usual::

    from asgiref.local import Local

    local = Local()
    local.user = "alice"
    assert local.user == "alice"
    del local.user
    assert not hasattr(local, "user")

Reading or deleting an attribute that has not been set in the current context
raises ``AttributeError``. You can use ``getattr(local, "user", None)`` to
provide a default when reading an unset attribute.

In a synchronous thread (one without a running event loop), attributes are
local to that thread. In async code, they follow ``contextvars`` semantics:
code you directly ``await`` sees the same values, and a new task inherits the
context at the time it is created. Setting or deleting attributes in that
task does not change the attributes in the parent task::

    import asyncio

    from asgiref.local import Local

    local = Local()

    async def child():
        assert local.user == "alice"
        local.user = "bob"

    async def main():
        local.user = "alice"
        await asyncio.create_task(child())
        assert local.user == "alice"

    asyncio.run(main())

Attribute values are not deep-copied: if an attribute holds a mutable object,
such as a list, an inheriting task can still mutate that same object.

By default, ``sync_to_async`` and ``async_to_sync`` also propagate local values
across the sync/async boundary, including changes made by the wrapped call::

    import asyncio

    from asgiref.local import Local
    from asgiref.sync import sync_to_async

    local = Local()

    def update_user():
        assert local.user == "alice"
        local.user = "bob"

    async def main():
        local.user = "alice"
        await sync_to_async(update_user)()
        assert local.user == "bob"

    asyncio.run(main())

For values that must stay on their original thread, such as database handles,
use ``Local(thread_critical=True)``. This disables sharing across threads via
``sync_to_async`` and ``async_to_sync``. In a synchronous thread, this behaves
like ``threading.local``; in a thread running an event loop, values are also
local to the async context, with the task inheritance behaviour described
above. ``Local`` cannot be subclassed.


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

``asgiref`` requires Python 3.11 or higher.


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

There is also a micro-benchmark suite for ``asgiref.local`` in
``tests/test_benchmark_local.py``. It is skipped unless ``pytest-benchmark``
(or ``pytest-codspeed``) is installed, and is not part of the regular CI run.
To run it via tox::

    tox -e benchmark

Benchmark numbers are only meaningful when compared on the same machine, so
the typical workflow is to save a baseline and then compare against it::

    tox -e benchmark -- --benchmark-save=before
    # ... make changes ...
    tox -e benchmark -- --benchmark-compare


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


Releasing
'''''''''

To release, first add details to CHANGELOG.txt and update the version number in ``asgiref/__init__.py``.

Then, build and push the packages::

    python -m build
    twine upload dist/*
    rm -r asgiref.egg-info dist


Implementation Details
----------------------

Synchronous code & threads
''''''''''''''''''''''''''

The ``asgiref.sync`` module provides two wrappers that let you go between
asynchronous and synchronous code at will, while taking care of the rough edges
for you.

Unfortunately, the rough edges are numerous, and the code has to work especially
hard to keep things in the same thread as much as possible. Notably, the
restrictions we are working with are:

* All synchronous code called through ``SyncToAsync`` and marked with
  ``thread_sensitive`` should run in the same thread as each other (and if the
  outer layer of the program is synchronous, the main thread)

* If a thread already has a running async loop, ``AsyncToSync`` can't run things
  on that loop if it's blocked on synchronous code that is above you in the
  call stack.

The first compromise you get to might be that ``thread_sensitive`` code should
just run in the same thread and not spawn in a sub-thread, fulfilling the first
restriction, but that immediately runs you into the second restriction.

The only real solution is to essentially have a variant of ThreadPoolExecutor
that executes any ``thread_sensitive`` code on the outermost synchronous
thread - either the main thread, or a single spawned subthread.

This means you now have two basic states:

* If the outermost layer of your program is synchronous, then all async code
  run through ``AsyncToSync`` will run in a per-call event loop in arbitrary
  sub-threads, while all ``thread_sensitive`` code will run in the main thread.

* If the outermost layer of your program is asynchronous, then all async code
  runs on the main thread's event loop, and all ``thread_sensitive`` synchronous
  code will run in a single shared sub-thread.

Crucially, this means that in both cases there is a thread which is a shared
resource that all ``thread_sensitive`` code must run on, and there is a chance
that this thread is currently blocked on its own ``AsyncToSync`` call. Thus,
``AsyncToSync`` needs to act as an executor for thread code while it's blocking.

The ``CurrentThreadExecutor`` class provides this functionality; rather than
simply waiting on a Future, you can call its ``run_until_future`` method and
it will run submitted code until that Future is done. This means that code
inside the call can then run code on your thread.


Maintenance and Security
------------------------

To report security issues, please contact security@djangoproject.com. For GPG
signatures and more security process information, see
https://docs.djangoproject.com/en/dev/internals/security/.

To report bugs or request new features, please open a new GitHub issue.

This repository is part of the Channels project. For the shepherd and maintenance team, please see the
`main Channels readme <https://github.com/django/channels/blob/master/README.rst>`_.
