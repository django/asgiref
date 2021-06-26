import importlib

import pytest

from asgiref import typing


@pytest.mark.parametrize("deprecated_type", typing.__deprecated__.keys())
def test_deprecated_types(deprecated_type: str) -> None:
    with pytest.deprecated_call() as warnings:
        getattr(importlib.import_module("asgiref.typing"), deprecated_type)
        assert len(warnings.list) == 1
        assert deprecated_type in str(warnings.list[0])


@pytest.mark.parametrize("available_type", typing.__all__)
def test_available_types(available_type: str) -> None:
    with pytest.warns(None) as record:
        getattr(importlib.import_module("asgiref.typing"), available_type)
        assert len(record) == 0
