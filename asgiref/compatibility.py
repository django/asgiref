from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable

from typing_extensions import TypeAlias

from .sync import iscoroutinefunction


Scope: TypeAlias = dict[str, Any]
Receive: TypeAlias = Callable[[], Awaitable[Any]]
Send: TypeAlias = Callable[[dict[str, Any]], Awaitable[None]]

# ASGI 3.0 style: async callable(scope, receive, send)
ASGISingleCallable: TypeAlias = Callable[[Scope, Receive, Send], Awaitable[Any]]

# ASGI 2.0 legacy style: callable(scope) -> awaitable callable(receive, send)
ASGIDoubleCallableInstance: TypeAlias = Callable[[Receive, Send], Awaitable[Any]]
ASGIDoubleCallable: TypeAlias = Callable[[Scope], ASGIDoubleCallableInstance]


def is_double_callable(application: Any) -> bool:
    """
    Tests to see if an application is a legacy-style (double-callable) application.
    """
    # Look for a hint on the object first
    if getattr(application, "_asgi_single_callable", False):
        return False
    if getattr(application, "_asgi_double_callable", False):
        return True
    # Uninstanted classes are double-callable
    if inspect.isclass(application):
        return True
    # Instanted classes depend on their __call__
    if hasattr(application, "__call__"):
        # We only check to see if its __call__ is a coroutine function -
        # if it's not, it still might be a coroutine function itself.
        if iscoroutinefunction(application.__call__):
            return False
    # Non-classes we just check directly
    return not iscoroutinefunction(application)


def double_to_single_callable(application: ASGIDoubleCallable) -> ASGISingleCallable:
    """
    Transforms a double-callable ASGI application into a single-callable one.
    """

    async def new_application(scope: Scope, receive: Receive, send: Send) -> Any:
        instance = application(scope)
        return await instance(receive, send)

    return new_application


def guarantee_single_callable(application: Any) -> ASGISingleCallable:
    """
    Takes either a single- or double-callable application and always returns it
    in single-callable style. Use this to add backwards compatibility for ASGI
    2.0 applications to your server/test harness/etc.
    """
    if is_double_callable(application):
        application = double_to_single_callable(application)
    return application
