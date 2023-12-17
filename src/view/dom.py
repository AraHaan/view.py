from __future__ import annotations

import inspect
from typing import Any, Callable, TypeVar

from typing_extensions import ParamSpec, Self, TypeAlias

__view_js = Any
__view_JsProxy: TypeAlias = __view_js.JsProxy


VIEW_BROWSER: bool = False


class _ImplDefined:
    ...


_ImplDefinedType = type(_ImplDefined)


class _JavaScriptObject:
    def __init__(self, obj: __view_JsProxy) -> None:
        if not VIEW_BROWSER:
            raise RuntimeError("this object can only be used from the browser!")

        self._object = obj

    @classmethod
    def _from_obj(cls, obj: __view_JsProxy) -> Self:
        instance = cls.__new__(cls)
        instance._object = obj
        return instance

    def _mirror_call(
        self, name: str, *args: Any, **kwargs: Any | _ImplDefinedType
    ) -> Any:
        new_args = [
            (i._object if isinstance(i, _JavaScriptObject) else i) for i in args
        ]
        new_kwargs = {
            k: v
            for k, v in kwargs.items()
            if not isinstance(v, _ImplDefinedType)
        }
        return self._object.as_object_map()[name](*new_args, {**new_kwargs})

    @staticmethod
    def _new_obj(obj_name: str, *args: Any, **kwargs: Any) -> __view_JsProxy:
        return getattr(__view_js, obj_name).new(*args, {**kwargs})

    @classmethod
    def _construct(
        cls, obj_name: str, *args: Any, **kwargs: Any
    ) -> _JavaScriptObject:
        return _JavaScriptObject(cls._new_obj(obj_name, *args, **kwargs))


ListenerFor = Callable[[T], Any] | Callable[[], Any]


class EventTarget(_JavaScriptObject):
    def __init__(self):
        super().__init__(self._new_obj("EventTarget"))

    def add_event_listener(
        self,
        type: str,
        listener: ListenerFor[T],
        *,
        capture: bool | _ImplDefinedType = _ImplDefined,
        once: bool | _ImplDefinedType = _ImplDefined,
        passive: bool | _ImplDefinedType = _ImplDefined,
        use_capture: bool | _ImplDefinedType = _ImplDefined,
    ) -> None:
        return self._mirror_call(
            "addEventListener",
            type,
            listener,
            capture=capture,
            once=once,
            passive=passive,
            use_capture=use_capture,
        )

    def remove_event_listener(
        self,
        type: str,
        listener: ListenerFor[T],
        *,
        capture: bool | _ImplDefinedType = _ImplDefined,
    ) -> None:
        return self._mirror_call(
            "removeEventListener", type, listener, capture=capture
        )

    def dispatch_event(self, event: Event) -> bool:
        return self._mirror_call("dispatch_event", event)


class Event(_JavaScriptObject):
    def __init__(
        self,
        type: str,
        *,
        bubbles: bool | _ImplDefinedType = _ImplDefined,
        cancelable: bool | _ImplDefinedType = _ImplDefined,
        composed: bool | _ImplDefinedType = _ImplDefined,
    ) -> None:
        super().__init__(
            self._new_obj(
                "Event",
                type,
                bubbles=bubbles,
                cancelable=cancelable,
                composed=composed,
            ),
        )

    @property
    def bubbles(self) -> bool:
        return self._object.bubbles

    @property
    def cancelable(self) -> bool:
        return self._object.cancelable

    @property
    def composed(self) -> bool:
        return self._object.composed

    @property
    def current_target(self) -> EventTarget:
        return EventTarget._from_obj(self._object.currentTarget)

    @property
    def default_prevented(self) -> bool:
        return self._object.defaultPrevented

    @property
    def event_phase(self) -> int:
        return self._object.eventPhase

    @property
    def is_trusted(self) -> bool:
        return self._object.isTrusted

    @property
    def target(self) -> EventTarget:
        return EventTarget._from_obj(self._object.target)

    @property
    def time_stamp(self) -> float:
        return self._object.timeStamp

    @property
    def type(self) -> str:
        return self._object.type

    def composed_path(self) -> list[EventTarget]:
        return [EventTarget._from_obj(i) for i in self._object.composedPath()]

    def prevent_default(self) -> None:
        self._object.preventDefault()

    def stop_immediate_propagation(self) -> None:
        self._object.stopImmediatePropagation()

    def stop_propagation(self) -> None:
        self._object.stopPropagation()


T = TypeVar("T")
P = ParamSpec("P")


class HTMLElement(EventTarget, _JavaScriptObject):
    def __init__(self) -> None:
        self._object = self._new_obj("HTMLElement")


DOM = str | HTMLElement


def render(content: DOM) -> None:
    raise TypeError("this can only be called from the browser")


def browser_supported(func: T) -> T:
    setattr(func, "_view_browser_ok", True)
    return func


def browser_mirror(target: Callable):
    def inner(func: Callable):
        setattr(target, "_view_browser_mirror", func)
        return func

    return inner


_ESSENTIALS = []


def browser_essential(target: Callable) -> Callable:
    src = inspect.getsource(target).split("\n")
    src.pop(0)
    _ESSENTIALS.append("\n".join(src))

    def _transport(*args, **kwargs):
        raise TypeError("this can only be called from the browser")

    return _transport


B_OPEN = "{"
B_CLOSE = "}"


@browser_essential
def __view_find(id: str):
    __view_ele = __view_js.document.getElementById(id)
    if __view_ele is None:
        raise TypeError("could not find view.py element")
    return __view_ele


@browser_essential
def __view_named_node_map(map: __view_JsProxy) -> dict:
    res = {}

    for i in range(map.length):
        item = map.item(i)
        res[item.name] = item.value

    return res


@browser_essential
def __view_node_init(id: str) -> Element:
    __view_ele = __view_find(id)
    return Element(
        __view_ele.innerHTML,
        __view_ele.tagName,
        __view_named_node_map(__view_ele.attributes),
    )


Callback = Callable[[], Any]
