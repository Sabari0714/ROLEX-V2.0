"""Safe math expression evaluator — AST based, NO eval() ever."""
from __future__ import annotations

import ast
import math
from typing import Any

from ..errors import MathError

_ALLOWED_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "log": math.log10, "ln": math.log, "log2": math.log2,
    "sqrt": math.sqrt, "cbrt": lambda x: math.copysign(abs(x) ** (1 / 3), x),
    "exp": math.exp, "abs": abs, "fabs": math.fabs,
    "round": round, "floor": math.floor, "ceil": math.ceil,
    "factorial": math.factorial, "fact": math.factorial,
    "degrees": math.degrees, "radians": math.radians,
    "pi": math.pi, "e": math.e, "tau": math.tau,
}

_ALLOWED_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
}

_ALLOWED_UNARY = {ast.UAdd: lambda a: +a, ast.USub: lambda a: -a}


def safe_eval(expr: str) -> Any:
    """Evaluate a pure math expression string safely.
    Raises MathError on anything non-math (names, calls, etc.)."""
    expr = (expr or "").strip().rstrip("=?").strip()
    expr = expr.replace("×", "*").replace("÷", "/").replace("^", "**")
    expr = expr.replace("−", "-").replace(",", "")
    if not expr:
        raise MathError("empty expression")
    if not all(c in "0123456789+-*/%(). eE" or c.isalpha() for c in expr):
        raise MathError(f"unsafe characters in: {expr!r}")

    try:
        tree = ast.parse(expr, mode="eval")
        return _eval_node(tree.body)
    except MathError:
        raise
    except ZeroDivisionError:
        raise MathError("division by zero")
    except Exception as e:  # noqa: BLE001
        raise MathError(f"cannot evaluate {expr!r} ({e})")


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise MathError(f"constant not allowed: {node.value!r}")

    if isinstance(node, ast.BinOp):
        fn = _ALLOWED_BINOPS.get(type(node.op))
        if fn is None:
            raise MathError("operator not allowed")
        return fn(_eval_node(node.left), _eval_node(node.right))

    if isinstance(node, ast.UnaryOp):
        fn = _ALLOWED_UNARY.get(type(node.op))
        if fn is None:
            raise MathError("unary operator not allowed")
        return fn(_eval_node(node.operand))

    if isinstance(node, ast.Name):
        name = node.id.lower()
        if name in _ALLOWED_FUNCS:
            return _ALLOWED_FUNCS[name]
        raise MathError(f"unknown symbol: {node.id}")

    if isinstance(node, ast.Call):
        fn = _eval_node(node.func)
        args = [_eval_node(a) for a in node.args]
        if not callable(fn):
            raise MathError("not a function call")
        try:
            return fn(*args)
        except Exception as e:  # noqa: BLE001
            raise MathError(f"function error: {e}")

    raise MathError(f"node not allowed: {type(node).__name__}")


def format_number(value: Any) -> str:
    """Pretty-print a numeric result (int-like, or trimmed float)."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if value == int(value) and abs(value) < 1e15:
            return f"{int(value):,}"
        return f"{value:,.6g}"
    return str(value)
