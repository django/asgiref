import asyncio
import contextvars
import threading
from typing import Any


class _Storage:
    """Thread-tagged storage for a non-thread-critical ``Local``.

    The data is tagged with the identity of the thread that owns it. This lets
    ``_CVar`` ignore data that leaked into an unrelated thread.

    Python 3.14 added ``sys.flags.thread_inherit_context``, which is enabled by
    default on free-threaded builds. When set, a new thread starts with a copy
    of the spawning thread's context instead of an empty one, so the contextvar
    backing a ``Local`` would otherwise be visible in any thread spawned from
    one that had set it -- breaking the documented "thread-local in sync
    threads" behaviour. asgiref re-homes the storage to the current thread at
    the points where it *intentionally* moves work between threads (see
    ``asgiref.sync._restore_context``); data merely inherited by an unrelated
    thread is never re-homed and so stays isolated.
    """

    __slots__ = ("thread_id", "data")

    def __init__(self, thread_id: int, data: dict[str, Any]) -> None:
        self.thread_id = thread_id
        self.data = data


def _rehome(storage: "_Storage") -> "_Storage":
    """Return a copy of *storage* owned by the current thread."""
    return _Storage(threading.get_ident(), storage.data)


_object_setattr = object.__setattr__


class _CVar:
    """Storage utility for Local."""

    _data: "contextvars.ContextVar[_Storage]"

    def __init__(self) -> None:
        _object_setattr(self, "_data", contextvars.ContextVar("asgiref.local"))

    def _storage(self) -> "_Storage":
        # Only return storage that belongs to the current thread. Storage with
        # a different thread id was inherited by this thread (rather than
        # intentionally moved here by asgiref) and must not be visible.
        storage = self._data.get(None)
        if storage is None or storage.thread_id != threading.get_ident():
            return _Storage(threading.get_ident(), {})
        return storage

    def __getattr__(self, key):
        try:
            return self._storage().data[key]
        except KeyError:
            raise AttributeError(f"{self!r} object has no attribute {key!r}")

    def __setattr__(self, key: str, value: Any) -> None:
        if key == "_data":
            raise AttributeError("Cannot set attribute '_data' on Local")

        data = self._storage().data.copy()
        data[key] = value
        self._data.set(_Storage(threading.get_ident(), data))

    def __delattr__(self, key: str) -> None:
        data = self._storage().data.copy()
        if key in data:
            del data[key]
            self._data.set(_Storage(threading.get_ident(), data))
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


_object_setattr = object.__setattr__


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
    code (such as DB handles) to be kept strictly to their initial thread and
    disable the sharing across `sync_to_async` and `async_to_sync` wrapped calls.

    Unlike plain `contextvars` objects, this utility is threadsafe.
    """

    def __new__(cls, thread_critical: bool = False) -> "Local":
        # Make `Local(...)` actually instantiate either of the specialized subclasses.
        if thread_critical:
            return object.__new__(_ThreadCriticalLocal)
        return object.__new__(_DefaultLocal)

    def __init__(self, thread_critical: bool = False) -> None:
        # `thread_critical` is not really used here;
        # this just marks the __init__ interface for
        # the concrete specialized subclasses.
        pass

    # These mark this class as magical to Mypy; the real implementations
    # are in the concrete subclasses below.

    def __getattr__(self, key: str) -> Any: ...

    def __setattr__(self, key: str, value: Any) -> Any: ...

    def __delattr__(self, key: str) -> Any: ...


class _DefaultLocal(Local):
    """Local with thread_critical=False: CVar storage protected by a lock."""

    def __init__(self, thread_critical: bool = False) -> None:
        super().__init__(thread_critical)
        storage = _CVar()
        lock = threading.RLock()
        _object_setattr(self, "_storage", storage)
        _object_setattr(self, "_lock_context", _LockContext(lock, storage))

    def __getattr__(self, key):
        with self._lock_context as storage:
            return getattr(storage, key)

    def __setattr__(self, key, value):
        with self._lock_context as storage:
            setattr(storage, key, value)

    def __delattr__(self, key):
        with self._lock_context as storage:
            delattr(storage, key)


class _ThreadCriticalLocal(Local):
    """Local with thread_critical=True: thread-local storage, CVar in async."""

    def __init__(self, thread_critical: bool = False) -> None:
        super().__init__(thread_critical)
        _object_setattr(self, "_storage", threading.local())

    def _get_storage(self):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # We are in a sync thread, the storage is
            # just the plain thread local (i.e, "global within
            # this thread" - it doesn't matter where you are
            # in a call stack you see the same storage)
            return self._storage

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
        return self._storage.cvar

    def __getattr__(self, key):
        return getattr(self._get_storage(), key)

    def __setattr__(self, key, value):
        setattr(self._get_storage(), key, value)

    def __delattr__(self, key):
        delattr(self._get_storage(), key)
