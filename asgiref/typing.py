import sys
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    Literal,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypedDict,
    Union,
)

if sys.version_info >= (3, 11):
    from typing import NotRequired
else:
    from typing_extensions import NotRequired

__all__ = (
    "ASGIVersions",
    "HTTPScope",
    "WebSocketScope",
    "LifespanScope",
    "WWWScope",
    "Scope",
    "HTTPRequestEvent",
    "HTTPResponseStartEvent",
    "HTTPResponseBodyEvent",
    "HTTPResponseTrailersEvent",
    "HTTPResponsePathsendEvent",
    "HTTPServerPushEvent",
    "HTTPDisconnectEvent",
    "WebSocketConnectEvent",
    "WebSocketAcceptEvent",
    "WebSocketReceiveEvent",
    "WebSocketSendEvent",
    "WebSocketResponseStartEvent",
    "WebSocketResponseBodyEvent",
    "WebSocketDisconnectEvent",
    "WebSocketCloseEvent",
    "LifespanStartupEvent",
    "LifespanShutdownEvent",
    "LifespanStartupCompleteEvent",
    "LifespanStartupFailedEvent",
    "LifespanShutdownCompleteEvent",
    "LifespanShutdownFailedEvent",
    "ASGIReceiveEvent",
    "ASGISendEvent",
    "ASGIReceiveCallable",
    "ASGISendCallable",
    "ASGI2Protocol",
    "ASGI2Application",
    "ASGI3Application",
    "ASGIApplication",
)


class ASGIVersions(TypedDict):
    spec_version: str
    version: Union[Literal["2.0"], Literal["3.0"]]


class HTTPScope(TypedDict):
    type: Literal["http"]
    asgi: ASGIVersions
    http_version: str
    method: str
    scheme: NotRequired[str]
    path: str
    raw_path: NotRequired[Optional[bytes]]
    query_string: bytes
    root_path: NotRequired[str]
    headers: Iterable[Tuple[bytes, bytes]]
    client: NotRequired[Optional[Tuple[str, int]]]
    server: NotRequired[Optional[Tuple[str, Optional[int]]]]
    state: NotRequired[Dict[str, Any]]
    extensions: NotRequired[Optional[Dict[str, Dict[object, object]]]]


class WebSocketScope(TypedDict):
    type: Literal["websocket"]
    asgi: ASGIVersions
    http_version: NotRequired[str]
    scheme: NotRequired[str]
    path: str
    raw_path: NotRequired[Optional[bytes]]
    query_string: NotRequired[Optional[bytes]]
    root_path: NotRequired[str]
    headers: Iterable[Tuple[bytes, bytes]]
    client: NotRequired[Optional[Tuple[str, int]]]
    server: NotRequired[Optional[Tuple[str, Optional[int]]]]
    subprotocols: NotRequired[Iterable[str]]
    state: NotRequired[Dict[str, Any]]
    extensions: NotRequired[Optional[Dict[str, Dict[object, object]]]]


class LifespanScope(TypedDict):
    type: Literal["lifespan"]
    asgi: ASGIVersions
    state: NotRequired[Dict[str, Any]]
    extensions: NotRequired[Optional[Dict[str, Dict[object, object]]]]


WWWScope = Union[HTTPScope, WebSocketScope]
Scope = Union[HTTPScope, WebSocketScope, LifespanScope]


class HTTPRequestEvent(TypedDict):
    type: Literal["http.request"]
    body: NotRequired[bytes]
    more_body: NotRequired[bool]


class HTTPResponseDebugEvent(TypedDict):
    type: Literal["http.response.debug"]
    info: Dict[str, object]


class HTTPResponseStartEvent(TypedDict):
    type: Literal["http.response.start"]
    status: int
    headers: NotRequired[Iterable[Tuple[bytes, bytes]]]
    trailers: NotRequired[bool]


class HTTPResponseBodyEvent(TypedDict):
    type: Literal["http.response.body"]
    body: NotRequired[bytes]
    more_body: NotRequired[bool]


class HTTPResponseTrailersEvent(TypedDict):
    type: Literal["http.response.trailers"]
    headers: Iterable[Tuple[bytes, bytes]]
    more_trailers: NotRequired[bool]


class HTTPResponsePathsendEvent(TypedDict):
    type: Literal["http.response.pathsend"]
    path: str


class HTTPServerPushEvent(TypedDict):
    type: Literal["http.response.push"]
    path: str
    headers: Iterable[Tuple[bytes, bytes]]


class HTTPDisconnectEvent(TypedDict):
    type: Literal["http.disconnect"]


class WebSocketConnectEvent(TypedDict):
    type: Literal["websocket.connect"]


class WebSocketAcceptEvent(TypedDict):
    type: Literal["websocket.accept"]
    subprotocol: NotRequired[Optional[str]]
    headers: NotRequired[Iterable[Tuple[bytes, bytes]]]


class _WebSocketSendEvent_Text(TypedDict):
    type: Literal["websocket.send"]
    bytes: NotRequired[None]
    text: str


class _WebSocketSendEvent_Bytes(TypedDict):
    type: Literal["websocket.send"]
    bytes: bytes
    text: NotRequired[None]


WebSocketSendEvent = Union[
    _WebSocketSendEvent_Text,
    _WebSocketSendEvent_Bytes,
]


class _WebSocketReceiveEvent_Text(TypedDict):
    type: Literal["websocket.receive"]
    bytes: NotRequired[None]
    text: str


class _WebSocketReceiveEvent_Bytes(TypedDict):
    type: Literal["websocket.receive"]
    bytes: bytes
    text: NotRequired[None]


WebSocketReceiveEvent = Union[
    _WebSocketReceiveEvent_Text,
    _WebSocketReceiveEvent_Bytes,
]


class WebSocketResponseStartEvent(TypedDict):
    type: Literal["websocket.http.response.start"]
    status: int
    headers: NotRequired[Iterable[Tuple[bytes, bytes]]]
    trailers: NotRequired[bool]


class WebSocketResponseBodyEvent(TypedDict):
    type: Literal["websocket.http.response.body"]
    body: NotRequired[bytes]
    more_body: NotRequired[bool]


class WebSocketDisconnectEvent(TypedDict):
    type: Literal["websocket.disconnect"]
    code: int
    reason: NotRequired[Optional[str]]


class WebSocketCloseEvent(TypedDict):
    type: Literal["websocket.close"]
    code: int
    reason: NotRequired[Optional[str]]


class LifespanStartupEvent(TypedDict):
    type: Literal["lifespan.startup"]


class LifespanShutdownEvent(TypedDict):
    type: Literal["lifespan.shutdown"]


class LifespanStartupCompleteEvent(TypedDict):
    type: Literal["lifespan.startup.complete"]


class LifespanStartupFailedEvent(TypedDict):
    type: Literal["lifespan.startup.failed"]
    message: NotRequired[str]


class LifespanShutdownCompleteEvent(TypedDict):
    type: Literal["lifespan.shutdown.complete"]


class LifespanShutdownFailedEvent(TypedDict):
    type: Literal["lifespan.shutdown.failed"]
    message: NotRequired[str]


ASGIReceiveEvent = Union[
    HTTPRequestEvent,
    HTTPDisconnectEvent,
    WebSocketConnectEvent,
    WebSocketReceiveEvent,
    WebSocketDisconnectEvent,
    LifespanStartupEvent,
    LifespanShutdownEvent,
]


ASGISendEvent = Union[
    HTTPResponseStartEvent,
    HTTPResponseBodyEvent,
    HTTPResponseTrailersEvent,
    HTTPServerPushEvent,
    HTTPDisconnectEvent,
    WebSocketAcceptEvent,
    WebSocketSendEvent,
    WebSocketResponseStartEvent,
    WebSocketResponseBodyEvent,
    WebSocketCloseEvent,
    LifespanStartupCompleteEvent,
    LifespanStartupFailedEvent,
    LifespanShutdownCompleteEvent,
    LifespanShutdownFailedEvent,
]


ASGIReceiveCallable = Callable[[], Awaitable[ASGIReceiveEvent]]
ASGISendCallable = Callable[[ASGISendEvent], Awaitable[None]]


class ASGI2Protocol(Protocol):
    def __init__(self, scope: Scope) -> None:
        ...

    async def __call__(
        self, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        ...


ASGI2Application = Type[ASGI2Protocol]
ASGI3Application = Callable[
    [
        Scope,
        ASGIReceiveCallable,
        ASGISendCallable,
    ],
    Awaitable[None],
]
ASGIApplication = Union[ASGI2Application, ASGI3Application]
