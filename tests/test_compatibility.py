"""
Module for testing ASGI compatibility functions and classes.
"""

import pytest
from asgiref.compatibility import double_to_single_callable, is_double_callable
from asgiref.testing import ApplicationCommunicator


@pytest.mark.asyncio
async def test_is_double_callable():
    """Test the behavior of is_double_callable function."""
    assert is_double_callable(double_application_function)
    assert is_double_callable(DoubleApplicationClass)
    assert is_double_callable(DoubleApplicationClassNestedFunction())
    assert not is_double_callable(single_application_function)
    assert not is_double_callable(SingleApplicationClass())


@pytest.mark.asyncio
async def test_double_to_single_callable():
    """Test the behavior of double_to_single_callable function."""
    new_app = double_to_single_callable(double_application_function)
    assert not is_double_callable(new_app)


@pytest.mark.asyncio
async def test_double_to_single_communicator():
    """Test the behavior of the new application using ApplicationCommunicator."""
    new_app = double_to_single_callable(double_application_function)
    instance = ApplicationCommunicator(new_app, {"value": "woohoo"})
    await instance.send_input({"value": 42})
    output = await instance.receive_output()
    assert output == {"scope": "woohoo", "message": 42}


# Additional functions and classes for testing
def double_application_function(scope):
    """A nested function-based double-callable application."""

    async def inner(receive, send):
        message = await receive()
        await send({"scope": scope["value"], "message": message["value"]})

    return inner


class DoubleApplicationClass:
    """A classic class-based double-callable application."""

    def __init__(self):
        pass

    async def __call__(self):
        pass


class DoubleApplicationClassNestedFunction:
    """A function closure inside a class."""

    def __init__(self):
        pass

    def __call__(self):
        async def inner():
            pass

        return inner


async def single_application_function():
    """A single-function single-callable application."""


class SingleApplicationClass:
    """A single-callable class."""

    def __init__(self):
        pass

    async def __call__(self):
        pass

