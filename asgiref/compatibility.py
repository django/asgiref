import inspect
from typing import Callable, Coroutine, Optional, Type, Any

from .sync import iscoroutinefunction

def is_double_callable(application: Callable[..., Optional[Callable[[], Coroutine[Any, Any, None]]]]) -> bool:
    """
    Tests whether an application is a legacy-style (double-callable) application.

    Parameters:
    - `application`: The callable object to be tested.

    Returns:
    - `True` if the application is a double-callable, otherwise `False`.
    """

    # Look for a hint on the object first
    if getattr(application, "_asgi_single_callable", False) or getattr(application, "_asgi_double_callable", False):
        return True
    # Uninstantiated classes are double-callable
    if inspect.isclass(application):
        return True
    # Instantiated classes depend on their __call__
    if hasattr(application, "__call__") and not iscoroutinefunction(application.__call__):
        return True
    # Non-classes are checked directly
    return not iscoroutinefunction(application)


def double_to_single_callable(
    application: Callable[..., Callable[[], Coroutine[Any, Any, None]]]
) -> Callable[[dict, Callable[[], Any], Callable[[Any], None]], Coroutine[Any, Any, None]]:
    """
    Transforms a double-callable ASGI application into a single-callable one.

    Parameters:
    - `application`: The double-callable ASGI application.

    Returns:
    - A single-callable ASGI application.

    Example:
    ```python
    single_callable_app = double_to_single_callable(double_callable_app)
    ```
    """

    async def new_application(
        scope: dict, receive: Callable[[], Any], send: Callable[[Any], None]
    ) -> None:
        instance = application(scope)
        await instance(receive, send)

    return new_application


def guarantee_single_callable(
    application: Callable[..., Optional[Callable[[], Coroutine[Any, Any, None]]]]
) -> Callable[[dict, Callable[[], Any], Callable[[Any], None]], Coroutine[Any, Any, None]]:
    """
    Takes either a single- or double-callable application and always returns it
    in single-callable style.

    Parameters:
    - `application`: The single- or double-callable ASGI application.

    Returns:
    - A single-callable ASGI application.

    Example:
    ```python
    guaranteed_single_callable = guarantee_single_callable(some_callable_app)
    ```
    """

    if is_double_callable(application):
        application = double_to_single_callable(application)
    return application
