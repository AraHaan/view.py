import abc
import ast
from ast_decompiler import decompile

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
                            func=ast.Name(id="__view_update"),
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
