from __future__ import annotations

import ast
import operator
from typing import Callable

# Map AST operator nodes to safe Python operator callables.
# This gives us explicit control over what syntax is allowed.
_ALLOWED_BINOPS: dict[type[ast.AST], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

_ALLOWED_UNARYOPS: dict[type[ast.AST], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class CalculatorError(ValueError):
    pass


def maybe_calculate(expression: str) -> float | None:
    """Return a numeric result for simple math expressions, otherwise None.

    We intentionally parse with ``ast`` and manually evaluate allowed nodes,
    instead of using ``eval``. This keeps calculator handling safe.
    """

    cleaned = expression.strip()
    if not cleaned:
        return None

    # Basic fast filters: avoid trying to parse non-math free-text queries.
    if not any(ch.isdigit() for ch in cleaned):
        return None
    if any(ch.isalpha() for ch in cleaned):
        return None

    try:
        parsed = ast.parse(cleaned, mode="eval")
        return _eval_ast(parsed.body)
    except Exception:
        return None


def _eval_ast(node: ast.AST) -> float:
    """Recursively evaluate an AST node if it is in our allow-list."""

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)

    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _eval_ast(node.left)
        right = _eval_ast(node.right)
        return _ALLOWED_BINOPS[type(node.op)](left, right)

    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_eval_ast(node.operand))

    raise CalculatorError("Unsupported calculator expression")
