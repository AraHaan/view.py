from __future__ import annotations

import abc
import ast
import base64
import inspect
import io
import pickle
import tokenize
from pathlib import Path
from textwrap import dedent, indent
from types import FrameType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .dom import Component

from ast_decompiler import decompile

__all__ = "Compiler", "PyodideCompiler"

B_OPEN = "{"
B_CLOSE = "}"


class Compiler(abc.ABC):
    @abc.abstractmethod
    def compile(self, module: ast.Module) -> str:
        ...


class PyodideCompiler(Compiler, ast.NodeTransformer):
    def __init__(self, rerender: ast.AST) -> None:
        self.rerender = rerender

    def visit_Assign(self, node: ast.AST):
        return (
            node,
            ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="render"),
                    args=[self.rerender],
                    keywords=[],
                )
            ),
        )

    visit_AugAssign = visit_Assign
    visit_NamedExpr = visit_Assign
    visit_AnnAssign = visit_Assign

    def visit_Call(self, node: ast.Call):
        return node
        return (
            node,
            ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="render"),
                    args=[self.rerender],
                    keywords=[],
                )
            ),
        )

    def compile(self, module: ast.Module) -> str:
        return decompile(self.visit(module))


def _parse_function(parsed: ast.Module, uuid: str) -> ast.Module:
    assert isinstance(parsed.body[0], ast.FunctionDef)
    parsed.body[0].name = f"__view_{parsed.body[0].name}_{uuid}"
    return parsed


def _extract_name(expr: ast.expr) -> str:
    if isinstance(expr, ast.Name):
        return expr.id

    if isinstance(expr, ast.Attribute):
        return f"{_extract_name(expr.value)}.{expr.attr}"

    raise RuntimeError(f"cannot extract a name from a {expr} node")


class FindFunctionDef(ast.NodeVisitor):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.found: ast.FunctionDef | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        if node.name == self.name:
            self.found = node


class MangleNames(ast.NodeTransformer):
    def __init__(self, mapping: dict[str, str]) -> None:
        super().__init__()
        self.mapping = mapping

    def visit_Name(self, node: ast.Name) -> Any:
        new_name = self.mapping.get(node.id)

        if new_name:
            node.id = new_name

        return node


PREFIX: str = """import pickle as __pickle
import base64 as __b64"""


def _find_skips(code: str) -> list[int]:
    buffer = io.StringIO(code)
    res: list[int] = []

    for line in tokenize.generate_tokens(buffer.readline):
        if line.type == tokenize.COMMENT:
            if line.string == "# view: skip":
                res.append(line.start[0])

    return res


def _find_names(
    content: str,
    *,
    parsed: ast.Module | ast.FunctionDef | None = None,
) -> list[str]:
    parsed = parsed or ast.parse(content)
    names: list[str] = []
    skips = _find_skips(content)
    body = parsed.body

    for i in body:
        skip_outer = False

        for skip_line in skips:
            if skip_line in range(
                i.lineno,
                (i.end_lineno + 1) if i.end_lineno else (i.lineno + 1),
            ):
                skip_outer = True
                break

        if skip_outer:
            continue

        if isinstance(i, (ast.NamedExpr, ast.AnnAssign)):
            names.append(_extract_name(i.target))

        if isinstance(i, ast.Assign):
            for target in i.targets:
                if isinstance(target, ast.Tuple):
                    for e in target.elts:
                        names.append(_extract_name(e))
                else:
                    names.append(_extract_name(target))

    return names


def _get_pickle_expr(
    frame: FrameType, name: str, *, locals: bool = False
) -> str:
    scope = frame.f_globals if not locals else frame.f_locals
    try:
        pickled = base64.b64encode(pickle.dumps(scope[name]))
    except KeyError as e:
        raise RuntimeError(
            f"found global that doesn't exist: {name} (this is a bug!)"
        ) from e
    except AttributeError as e:
        raise RuntimeError(
            f"{scope[name]!r} cannot be used in the browser"
        ) from e

    return f"{name} = __pickle.loads(__b64.b64decode({pickled}))"


def compile_component(component: Component) -> str:
    compiled_list = []
    compiler = PyodideCompiler(component.rerender_call)
    global_index = 0

    assert component.hook
    for global_scope, global_scripts in component.hook.scripts.items():
        frame = component.hook.frames[global_scope]
        content = Path(frame.f_code.co_filename).read_text(encoding="utf-8")
        global_names = _find_names(content)
        compiled_list.append([f"def __view_global_{global_scope}():"])

        for name in global_names:
            compiled_list[global_index].append(
                f"    {_get_pickle_expr(frame, name)}"
            )

        for scope, scripts in global_scripts.items():
            compiled_list[global_index].append([f"    def __view_{scope}():"])
            local_frame = component.hook.local_frames[scope]

            for func, script_id in scripts.items():
                source = dedent(inspect.getsource(func))
                parsed = ast.parse(source)

                visitor = FindFunctionDef(local_frame.f_code.co_name)
                visitor.visit(ast.parse(content))
                assert visitor.found

                names = _find_names(source, parsed=visitor.found)

                for name in names:
                    compiled_list[global_index].append(
                        f"        {_get_pickle_expr(local_frame, name, locals=True)}"
                    )

                compiled_list[global_index].append(
                    indent(
                        compiler.compile(_parse_function(parsed, script_id)),
                        " " * 8,
                    )
                )

        global_index += 1

    flattened = []

    for global_scope in compiled_list:
        for local_scope in global_scope:
            if isinstance(local_scope, list):
                flattened.append("\n".join(local_scope))
            else:
                flattened.append(local_scope)

    compiled = "\n".join([i for i in flattened])
    return f"""(async () => {B_OPEN}
    let __view_pyodide = await loadPyodide();
    __view_pyodide.runPython(`# view.py compiled code
{PREFIX}
{compiled}`)
{B_CLOSE}()"""


def format_pyodide(data: Any | str) -> str:
    data = data.replace("`", "\\`").replace("\\n", "\\\\n")
    return data
