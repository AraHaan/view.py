from __future__ import annotations

import ast
import inspect
import textwrap
import uuid
from pathlib import Path
from types import FrameType as Frame
from typing import Any, Callable, ClassVar, Dict, Literal, TypeVar

from ast_decompiler import decompile
from typing_extensions import NotRequired, ParamSpec, TypedDict, Unpack

from .__about__ import __version__
from .compiler import compile, compile_pyodide
from .compiler import dedent as _dedent
from .compiler import get_indent_style as _get_indent_style
from .response import HTML

T = TypeVar("T")
P = ParamSpec("P")


class Mutable:
    def __init__(self, value: str, name: str, frame: Frame) -> None:
        self.value = value
        self.name = name
        self.frame = frame

    def __str__(self) -> str:
        return self.value


Script = Callable
NEWLINE = "\n"


class DOMNode:
    def __init__(
        self,
        data: tuple[str | DOMNode],
        tag: str,
        attrs: dict[str, Any],
        *,
        is_head: bool = False,
        skip_script: bool = False,
        is_body: bool = False,
    ) -> None:
        self.data: list[DOMNode | str] = list(data)
        self.needs_script = False
        self.tag = tag
        self.attrs = attrs
        self.mutables: dict[str, Mutable] = {}
        self.funcs: list[Script] = []
        self.heads = [self] if is_head else []
        self.bodies = [self] if is_body else []
        self.script_setup = False
        self.events: dict[str, Script] = {}
        self.is_head = is_head

        if not skip_script:
            f = inspect.currentframe()
            assert f
            while f.f_back:
                if f.f_code.co_filename != __file__:
                    break

                f = f.f_back
                assert f

            caller_frame = f
            path = caller_frame.f_code.co_filename
            lineno = caller_frame.f_lineno
            self.caller_frame = caller_frame

            lines = Path(path).read_text(encoding="utf-8").split("\n")
            code = "\n".join(lines[lineno - 1 : len(lines)])
            parsed = ast.parse(_dedent(code), filename=path)

            for node in parsed.body:
                self._set_muts(node)

            call = parsed.body[0]

            while hasattr(call, "value"):
                call = getattr(call, "value")

            values = getattr(call, "values", None)
            if values:
                for value in values:
                    if isinstance(value, ast.Call):
                        call = value

            while hasattr(call, "value"):
                call = getattr(call, "value")

            if not isinstance(call, ast.Call):
                raise TypeError(f"{ast.dump(call)} is not an ast.Call")

            self.call = call

            for i in data:
                if isinstance(i, DOMNode):
                    self.mutables.update(i.mutables)
                    self.funcs.extend(i.funcs)
                    self.heads.extend(i.heads)
                    self.bodies.extend(i.bodies)
                    self.events.update(i.events)

                    if i.needs_script:
                        self.needs_script = True

        cls = attrs.get("cls")
        if cls:
            attrs["class"] = cls
            attrs.pop("cls")
            attrs.pop("cls")

        for k, v in attrs.items():
            if isinstance(v, bool):
                attrs[k] = "true" if v else "false"

        for k, v in (attrs.get("data") or {}).items():
            attrs[f"data-{k}"] = v

        self.attrs = attrs
        id = self.attrs.get("id")
        self.id = id or uuid.uuid4().hex

        if not id:
            self.attrs["id"] = self.id

    @browser_mirror(__init__)
    def _mirror__init__(
        self,
        data: tuple[str | DOMNode],
        tag: str,
        attrs: dict[str, Any],
        *,
        is_head: bool = False,
        skip_script: bool = False,
        is_body: bool = False,
    ) -> None:
        self.data = list(data)
        self.tag = tag
        self.attrs = attrs
        self.id = attrs.get("id") or ""

    def add_node(self, *nodes: DOMNode):
        for node in nodes:
            self.data.append(node)

    @browser_mirror(add_node)
    def _mirror_add_node(self, *nodes: DOMNode):
        for node in nodes:
            ...

    append = add_node

    def _set_muts(self, node: ast.stmt) -> None:
        if hasattr(node, "body"):
            self._set_muts(getattr(node, "body"))

        if isinstance(node, (ast.Assign, ast.NamedExpr)):
            for target in node.targets:
                self._add_mutable(target, node.value)

    def _add_mutable(self, name: ast.expr, value: ast.expr) -> None:
        assert isinstance(
            name, ast.Name
        ), f"{ast.dump(name)} is not an ast.Name"
        self.mutables[name.id] = Mutable(
            decompile(value), name.id, self.caller_frame
        )

    @browser_supported
    def _make_attr_string(self):
        attr_str = ""

        for k, v in self.attrs.items():
            if v is None:
                continue

            k = k.replace("_", "-")
            if v:
                attr_str += f' {k}="{v}"'
            else:
                attr_str += f" {k}"

        return attr_str

    def script(self, func: Script):
        self.needs_script = True
        self.funcs.append(func)

    def event(self, name: str):
        self.needs_script = True

        def inner(func: Callable[P, T]) -> Callable[P, T]:
            self.events[name] = func
            return func

        return inner

    @browser_mirror(event)
    def _mirror_event(self, name: str):
        def inner(f):
            return f

        return inner

    def _handle_value(self, value: Any) -> Any:
        if isinstance(value, DOMNode):
            return f"__view_node_init('{self.id}')"

        return value

    def _compile_event(self, event_name: str) -> str:
        current_vars = {}

        for i in self.mutables.values():
            scope = {**i.frame.f_globals, **i.frame.f_locals}
            current_vars[i.name] = scope[i.name]

        mutable_script = [
            f"{x} = {self._handle_value(y)}" for x, y in current_vars.items()
        ]
        # func_script = [compile(_dedent(inspect.getsource(i)), self.call) for i in self.funcs]
        py = "\n".join(mutable_script) + compile(
            _dedent(inspect.getsource(self.events[event_name])), self.call
        )
        return py

    def _compile(self) -> str:
        source = ["from pyodide.ffi import create_proxy as __view_create_proxy"]
        for i, func in self.events.items():
            compiled = self._compile_event(i)
            name = f"__view_{self.id}_{i}"
            source.append(
                f"""
def {name}():
{textwrap.indent(compiled, _get_indent_style(compiled))}
    return {func.__name__}
__view_find('{self.id}').addEventListener('{i}', __view_create_proxy({name}()))
                          """
            )

        return "\n".join(source)

    @browser_supported
    def __repr__(self) -> str:
        return f"DOMNode({self.data!r}, {self.tag!r}, {self.attrs!r})"

    @browser_supported
    def content(self) -> str:
        return "\n".join([str(i) for i in self.data])

    def _gen_update(self) -> str:
        return f"""
def render(content: DOMNode | str) -> None:
    __view_this_element = __view_find('{self.id}')
    __view_this_element.innerHTML = str(content)"""

    def __str__(self) -> str:
        if self.needs_script:
            if not self.script_setup:
                for head in self.heads:
                    if not head.script_setup:
                        head.append(
                            DOMNode(
                                tuple(),
                                "script",
                                {
                                    "src": "https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js"
                                },
                                skip_script=True,
                            ),
                        )
                        head.script_setup = True
                self.script_setup = True

            compiled = self._compile()
            for body in self.bodies:
                body.append(
                    DOMNode(
                        (
                            f"""const __view_pyodide = await loadPyodide();
__view_pyodide.runPython(`{self._comp_prefix}\n{self._gen_update()}\n{compiled}`);""",
                        ),
                        "script",
                        {"type": "module"},
                        skip_script=True,
                    )
                )
                body.script_setup = True

        return f"<{self.tag}{self._make_attr_string()}>{self.content()}</{self.tag}>"

    @browser_mirror(__str__)
    def _mirror__str__(self):
        return f"<{self.tag}{self._make_attr_string()}>{self.content()}</{self.tag}>"

    def __view_result__(self):
        return HTML(self.__str__()).__view_result__()


AutoCapitalizeType = Literal[
    "off", "none", "on", "sentences", "words", "characters"
]
DirType = Literal["ltr", "rtl", "auto"]


class GlobalAttributes(TypedDict):
    accesskey: NotRequired[str]
    autocapitalize: NotRequired[AutoCapitalizeType]
    autofocus: NotRequired[bool]
    cls: NotRequired[str]
    contenteditable: NotRequired[bool]
    contextmenu: NotRequired[str]
    data: NotRequired[Dict[str, Any]]
    dir: NotRequired[DirType]
    draggable: NotRequired[bool]
    enterkeyhint: NotRequired[str]
    exportparts: NotRequired[str]
