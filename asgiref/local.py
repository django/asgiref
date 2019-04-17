import asyncio
import threading
import time

from .sync import AsyncToSync, SyncToAsync


class Local:
    """
    A drop-in replacement for threading.locals that also works with asyncio
    Tasks (via the current_task asyncio method), and passes locals through
    sync_to_async and async_to_sync.

    Specifically:
     - Locals work per-coroutine on any thread not spawned using asgiref
     - Locals work per-thread on any thread not spawned using asgiref
     - Locals are shared with the parent coroutine when using sync_to_async
     - Locals are shared with the parent thread when using async_to_sync
       (and if that thread was launched using sync_to_async, with its parent
       coroutine as well, with this working for indefinite levels of nesting)

    Set thread_critical to True to not allow locals to pass from an async Task
    to a thread it spawns. This is needed for code that truly needs
    thread-safety, as opposed to things used for helpful context (e.g. sqlite
    does not like being called from a different thread to the one it is from).
    Thread-critical code will still be differentiated per-Task within a thread
    as it is expected it does not like concurrent access.

    This doesn't use contextvars as it needs to support 3.6. Once it can support
    3.7 only, we can then reimplement the storage more nicely.
    """

    CLEANUP_INTERVAL = 60  # seconds

    def __init__(self, thread_critical=False):
        self._storage = {}
        self._last_cleanup = time.time()
        self._clean_lock = threading.Lock()
        self._thread_critical = thread_critical

    def _get_context_id(self):
        """
        Get the ID we should use for looking up variables
        """
        # First, pull the current task if we can
        context_id = SyncToAsync.get_current_task()
        # OK, let's try for a thread ID
        if context_id is None:
            context_id = threading.current_thread()
        # If we're thread-critical, we stop here, as we can't share contexts.
        if self._thread_critical:
            return context_id
        # Now, take those and see if we can resolve them through the launch maps
        while True:
            try:
                if isinstance(context_id, threading.Thread):
                    # Threads have a source task in SyncToAsync
                    context_id = SyncToAsync.launch_map[context_id]
                else:
                    # Tasks have a source thread in AsyncToSync
                    context_id = AsyncToSync.launch_map[context_id]
            except KeyError:
                break
        return context_id

    def _cleanup(self):
        """
        Cleans up any references to dead threads or tasks
        """
        for key in list(self._storage.keys()):
            if isinstance(key, threading.Thread):
                if not key.is_alive():
                    del self._storage[key]
            elif isinstance(key, asyncio.Task):
                if key.done():
                    del self._storage[key]
        self._last_cleanup = time.time()

    def _maybe_cleanup(self):
        """
        Cleans up if enough time has passed
        """
        if time.time() - self._last_cleanup > self.CLEANUP_INTERVAL:
            with self._clean_lock:
                self._cleanup()

    def __getattr__(self, key):
        context_id = self._get_context_id()
        if key in self._storage.get(context_id, {}):
            return self._storage[context_id][key]
        else:
            raise AttributeError("%r object has no attribute %r" % (self, key))

    def __setattr__(self, key, value):
        if key in ("_storage", "_last_cleanup", "_clean_lock", "_thread_critical"):
            return super().__setattr__(key, value)
        self._maybe_cleanup()
        self._storage.setdefault(self._get_context_id(), {})[key] = value

    def __delattr__(self, key):
        context_id = self._get_context_id()
        if key in self._storage.get(context_id, {}):
            del self._storage[context_id][key]
        else:
            raise AttributeError("%r object has no attribute %r" % (self, key))
