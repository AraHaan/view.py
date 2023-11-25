from __future__ import annotations
import abc
import ast
from typing import Any
from ast_decompiler import decompile
import inspect
import textwrap

__all__ = "Compiler", "PyodideCompiler", "compile", "compile_pyodide"

class Compiler(abc.ABC):
    @abc.abstractmethod
    def compile(self, module: ast.Module) -> str:
        ...


class PyodideCompiler(Compiler):
    def __init__(self, rerender: ast.Call) -> None:
        self.rerender = rerender

    def place_stmts(self, body: list[ast.stmt]) -> None:
        for index, i in enumerate(body):
            if hasattr(i, "body"):
                bd = getattr(i, "body")
                self.place_stmts(bd)

            if isinstance(i, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
                body.insert(
                    index + 1,
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Name(id="render"),
                            args=[self.rerender],
                            keywords=[]
                        )
                    ),
                )

    def compile(self, module: ast.Module) -> str:
        self.place_stmts(module.body)
        return decompile(module)

def compile(text: str, render: ast.Call) -> str:
    compiler = PyodideCompiler(render)
    return compiler.compile(ast.parse(text))

def format_pyodide(data: Any | str) -> str:
    data = data.replace("`", "\\`").replace("\\n", "\\\\n")
    return data

def dedent(data: str):
    if data[0] not in {" ", "\t"}:
        return data

    length = 0

    for i in data:
        if i in {" ", "\t"}:
            length += 1
        else:
            break

    res = ""

    current = 0
    next_line = True

    for i in data:
        if (i in {" ", "\t"}) and next_line:
            current += 1
            if current == length:
                next_line = False
                current = 0
        elif i == "\n":
            next_line = True
            res += i
        else:
            res += i

    return res

def get_indent_style(data: str) -> str:
    for line in data.split("\n"):
        if line.startswith((" ", "\t")):
            amount = 0

            for i in line:
                if i == "\t":
                    return "\t"
                elif i == " ":
                    amount += 1
                else:
                    return " " * 4
    return "    "



def compile_pyodide(data: type[Any]) -> str:
    src = f"class {data.__name__}:"

    for i in dir(data):
        value = getattr(data, i)

        mirror = getattr(value, "_view_browser_mirror", None)
        if mirror:
            mirror_source = ast.parse(dedent(inspect.getsource(mirror)))
            fdef = mirror_source.body[0]
            assert isinstance(fdef, ast.FunctionDef)
            fdef.decorator_list = []
            fdef.name = i
            final = decompile(mirror_source)
            src += f"\n{textwrap.indent(final, get_indent_style(final))}"
            continue
        
        if getattr(value, "_view_browser_ok", False):
            src += f"\n{inspect.getsource(value)}"
        else:
            if (not callable(value)) or i.startswith("_"):
                 continue
            src += f"\n    def {i}{inspect.signature(value)}: raise ValueError('{i} is unsupported in the browser')"
    
    return format_pyodide(src)
