import asyncio
import sys
from collections.abc import Callable, Generator
from typing import Any, Protocol

import pytest

from asgiref.local import Local


class BenchmarkFixture(Protocol):
    def __call__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None: ...


# Installed-but-inactive is not enough. PYTEST_DISABLE_PLUGIN_AUTOLOAD leaves the
# package importable while the benchmark fixture is unregistered, and collection
# then errors instead of skipping.
if "pytest_benchmark" not in sys.modules and "pytest_codspeed" not in sys.modules:
    pytest.skip(
        "pytest-benchmark or pytest-codspeed plugin must be active",
        allow_module_level=True,
    )


# -- Sync, thread_critical=False (lock + CVar path) --


@pytest.fixture
def local_default() -> Local:
    return Local(thread_critical=False)


@pytest.fixture
def local_thread_critical() -> Local:
    return Local(thread_critical=True)


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def test_getattr_default(benchmark: BenchmarkFixture, local_default: Local) -> None:
    local_default.x = 1
    benchmark(getattr, local_default, "x")


def test_setattr_default(benchmark: BenchmarkFixture, local_default: Local) -> None:
    benchmark(setattr, local_default, "x", 1)


def test_delattr_default(benchmark: BenchmarkFixture, local_default: Local) -> None:
    def del_cycle() -> None:
        local_default.x = 1
        del local_default.x

    benchmark(del_cycle)


def test_getattr_missing_default(
    benchmark: BenchmarkFixture, local_default: Local
) -> None:
    def get_missing() -> None:
        try:
            local_default.x
        except AttributeError:
            pass

    benchmark(get_missing)


# -- Sync, thread_critical=True (thread-local path, no async loop) --


def test_getattr_thread_critical(
    benchmark: BenchmarkFixture, local_thread_critical: Local
) -> None:
    local_thread_critical.x = 1
    benchmark(getattr, local_thread_critical, "x")


def test_setattr_thread_critical(
    benchmark: BenchmarkFixture, local_thread_critical: Local
) -> None:
    benchmark(setattr, local_thread_critical, "x", 1)


def test_delattr_thread_critical(
    benchmark: BenchmarkFixture, local_thread_critical: Local
) -> None:
    def del_cycle() -> None:
        local_thread_critical.x = 1
        del local_thread_critical.x

    benchmark(del_cycle)


# -- Async paths --
#
# Call benchmark inside coroutine to avoid capturing loop setup/teardown.


def test_getattr_thread_critical_async(
    benchmark: BenchmarkFixture, event_loop: asyncio.AbstractEventLoop
) -> None:
    local = Local(thread_critical=True)

    async def run() -> None:
        local.x = 1
        benchmark(getattr, local, "x")

    event_loop.run_until_complete(run())


def test_setattr_thread_critical_async(
    benchmark: BenchmarkFixture, event_loop: asyncio.AbstractEventLoop
) -> None:
    local = Local(thread_critical=True)

    async def run() -> None:
        benchmark(setattr, local, "x", 1)

    event_loop.run_until_complete(run())


def test_delattr_thread_critical_async(
    benchmark: BenchmarkFixture, event_loop: asyncio.AbstractEventLoop
) -> None:
    local = Local(thread_critical=True)

    def del_cycle() -> None:
        local.x = 1
        del local.x

    async def run() -> None:
        benchmark(del_cycle)

    event_loop.run_until_complete(run())


def test_getattr_default_async(
    benchmark: BenchmarkFixture, event_loop: asyncio.AbstractEventLoop
) -> None:
    local = Local(thread_critical=False)

    async def run() -> None:
        local.x = 1
        benchmark(getattr, local, "x")

    event_loop.run_until_complete(run())
