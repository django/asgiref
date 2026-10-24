from typing import Any
import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[Any]) -> None:
    if not (config.pluginmanager.hasplugin("benchmark") or config.pluginmanager.hasplugin("pytest_codspeed")):
        skip_benchmark = pytest.mark.skip(reason="pytest-benchmark or pytest-codspeed plugin required")
        for item in items:
            if "benchmark" in getattr(item, "fixturenames", ()):
                item.add_marker(skip_benchmark)
