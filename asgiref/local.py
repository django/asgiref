import asyncio
from contextlib import nullcontext
import contextvars
import threading
from typing import Any, Dict, Union


class _CVar:
    """Storage utility for Local."""

    def __init__(self) -> None:
        self._data: "contextvars.ContextVar[Dict[str, Any]]" = contextvars.ContextVar(
            "asgiref.local"
        )

    def __getattr__(self, key):
        storage_object = self._data.get({})
        try:
            return storage_object[key]
        except KeyError:
            raise AttributeError(f"{self!r} object has no attribute {key!r}")

    def __setattr__(self, key: str, value: Any) -> None:
        if key == "_data":
            return super().__setattr__(key, value)

        storage_object = self._data.get({}).copy()
        storage_object[key] = value
        self._data.set(storage_object)

    def __delattr__(self, key: str) -> None:
        storage_object = self._data.get({}).copy()
        if key in storage_object:
            del storage_object[key]
            self._data.set(storage_object)
        else:
            raise AttributeError(f"{self!r} object has no attribute {key!r}")


class _LockContext:
    """Context manager that acquires a lock and yields a value."""

    __slots__ = ("_lock", "_value")

    def __init__(self, lock: threading.RLock, value: Any) -> None:
        self._lock = lock
        self._value = value

    def __enter__(self):
        self._lock.acquire()
        return self._value

    def __exit__(self, *exc_info):
        self._lock.release()


class Local:
    """Local storage for async tasks.

    This is a namespace object (similar to `threading.local`) where data is
    also local to the current async task (if there is one).

    In async threads, local means in the same sense as the `contextvars`
    module - i.e. a value set in an async frame will be visible:

    - to other async code `await`-ed from this frame.
    - to tasks spawned using `asyncio` utilities (`create_task`, `wait_for`,
      `gather` and probably others).
    - to code scheduled in a sync thread using `sync_to_async`

    In "sync" threads (a thread with no async event loop running), the
    data is thread-local, but additionally shared with async code executed
    via the `async_to_sync` utility, which schedules async code in a new thread
    and copies context across to that thread.

    If `thread_critical` is True, then the local will only be visible per-thread,
    behaving exactly like `threading.local` if the thread is sync, and as
    `contextvars` if the thread is async. This allows genuinely thread-sensitive
    code (such as DB handles) to be kept stricly to their initial thread and
    disable the sharing across `sync_to_async` and `async_to_sync` wrapped calls.

    Unlike plain `contextvars` objects, this utility is threadsafe.
    """

    def __init__(self, thread_critical: bool = False) -> None:
        self._thread_critical = thread_critical
        self._thread_lock = threading.RLock()

        self._storage: "Union[threading.local, _CVar]"

        if thread_critical:
            # Thread-local storage
            self._storage = threading.local()
        else:
            # Contextvar storage
            self._storage = _CVar()
            self._lock_context = _LockContext(self._thread_lock, self._storage)

    def _lock_storage(self):
        # Thread safe access to storage
        if self._thread_critical:
            is_async = True
            try:
                # this is a test for are we in a async or sync
                # thread - will raise RuntimeError if there is
                # no current loop
                asyncio.get_running_loop()
            except RuntimeError:
                is_async = False
            if not is_async:
                # We are in a sync thread, the storage is
                # just the plain thread local (i.e, "global within
                # this thread" - it doesn't matter where you are
                # in a call stack you see the same storage)
                return nullcontext(self._storage)
            else:
                # We are in an async thread - storage is still
                # local to this thread, but additionally should
                # behave like a context var (is only visible with
                # the same async call stack)

                # Ensure context exists in the current thread
                if not hasattr(self._storage, "cvar"):
                    self._storage.cvar = _CVar()

                # self._storage is a thread local, so the members
                # can't be accessed in another thread (we don't
                # need any locks)
                return nullcontext(self._storage.cvar)
        else:
            # Lock for thread_critical=False as other threads
            # can access the exact same storage object
            return self._lock_context

    def __getattr__(self, key):
        with self._lock_storage() as storage:
            return getattr(storage, key)

    def __setattr__(self, key, value):
        if key in ("_local", "_storage", "_thread_critical", "_thread_lock", "_lock_context"):
            return super().__setattr__(key, value)
        with self._lock_storage() as storage:
            setattr(storage, key, value)

    def __delattr__(self, key):
        with self._lock_storage() as storage:
            delattr(storage, key)
