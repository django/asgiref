import importlib

import pytest


@pytest.mark.parametrize(
    "deprecated_type",
    (
        "WebsocketConnectEvent",
        "WebsocketAcceptEvent",
        "WebsocketReceiveEvent",
        "WebsocketSendEvent",
        "WebsocketResponseStartEvent",
        "WebsocketResponseBodyEvent",
        "WebsocketDisconnectEvent",
        "WebsocketCloseEvent",
    ),
)
def test_deprecated_types(deprecated_type: str) -> None:
    with pytest.deprecated_call() as warnings:
        getattr(importlib.import_module("asgiref.typing"), deprecated_type)
        assert len(warnings.list) == 1
        assert deprecated_type in str(warnings.list[0])
