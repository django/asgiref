import contextvars
import threading
from typing import Any, Union


class _CVar:
    """Storage utility for Local."""

    def __init__(self) -> None:
        self._thread_lock = threading.RLock()
        self._data: dict[str, contextvars.ContextVar[Any]] = {}

    def __getattr__(self, key: str) -> Any:
        with self._thread_lock:
            try:
                var = self._data[key]
            except KeyError:
                raise AttributeError(f"{self!r} object has no attribute {key!r}")

        try:
            return var.get()
        except LookupError:
            raise AttributeError(f"{self!r} object has no attribute {key!r}")

    def __setattr__(self, key: str, value: Any) -> None:
        if key in ("_data", "_thread_lock"):
            return super().__setattr__(key, value)

        with self._thread_lock:
            var = self._data.get(key)
            if var is None:
                self._data[key] = var = contextvars.ContextVar(key)
        var.set(value)

    def __delattr__(self, key: str) -> None:
        with self._thread_lock:
            if key in self._data:
                del self._data[key]
            else:
                raise AttributeError(f"{self!r} object has no attribute {key!r}")


def Local(thread_critical: bool = False) -> Union[threading.local, _CVar]:
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
    if thread_critical:
        return threading.local()
    else:
        return _CVar()
