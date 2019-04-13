import asyncio
import threading
import time

from .sync import SyncToAsync


class Local:
    """
    A drop-in replacement for threading.locals that also works with asyncio
    Tasks (via the current_task asyncio method), and correctly passes locals
    in and out of threads made with sync_to_async.

    This doesn't use contextvars as it needs to support 3.6. Once it can support
    3.7 only, we can then reimplement the storage much more nicely.
    """

    CLEANUP_INTERVAL = 60  # seconds

    def __init__(self):
        self._storage = {}
        self._last_cleanup = time.time()
        self._clean_lock = threading.Lock()

    @staticmethod
    def _get_context_id():
        """
        Get the ID we should use for looking up variables
        """
        # First, pull the current task if we can
        context_id = SyncToAsync.get_current_task()
        # If that fails, then try and pull the proxy ID from a threadlocal
        if context_id is None:
            try:
                context_id = SyncToAsync.threadlocal.current_task
            except AttributeError:
                pass
        # OK, let's try for a thread ID
        if context_id is None:
            context_id = threading.current_thread()
        # If that fails, error
        if context_id is None:
            raise RuntimeError("Cannot find task context for Local storage")
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
        if key in ("_storage", "_last_cleanup", "_clean_lock"):
            return super().__setattr__(key, value)
        self._maybe_cleanup()
        self._storage.setdefault(self._get_context_id(), {})[key] = value

    def __delattr__(self, key):
        context_id = self._get_context_id()
        if key in self._storage.get(context_id, {}):
            del self._storage[context_id][key]
        else:
            raise AttributeError("%r object has no attribute %r" % (self, key))
