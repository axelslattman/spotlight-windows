# calculator.py – safely evaluate simple math expressions typed by the user.
#
# WHY NOT eval()?
# Python's built-in eval() executes *any* Python code, so eval("__import__('os').system('del /f /s /q C:\\')")
# would run that command. Never use eval() on untrusted input.
#
# Instead we parse the expression into an Abstract Syntax Tree (AST) –
# a tree structure that represents the code's meaning – and then walk the
# tree ourselves, only allowing the specific node types we consider safe
# (numbers and basic arithmetic operators).

import ast      # Python's built-in parser; produces an AST from source code
import operator  # Standard math functions as callable objects (e.g. operator.add)
from typing import Optional  # For type hints: Optional[str] means "str or None"

# Map each AST operator node type to the corresponding Python operator function.
# For example, ast.Add (the + token in the AST) maps to operator.add (the
# Python function that adds two numbers).
_SAFE_BINARY_OPS: dict = {
    ast.Add:  operator.add,   # a + b
    ast.Sub:  operator.sub,   # a - b
    ast.Mult: operator.mul,   # a * b
    ast.Div:  operator.truediv,  # a / b  (always returns float)
    ast.Pow:  operator.pow,   # a ** b (exponentiation)
    ast.Mod:  operator.mod,   # a % b  (remainder)
}

_SAFE_UNARY_OPS: dict = {
    ast.UAdd: operator.pos,  # +a  (unary plus, rarely used)
    ast.USub: operator.neg,  # -a  (unary minus, e.g. -5)
}


def _eval_node(node: ast.AST) -> float:
    """Recursively evaluate a single AST node.

    Raises ValueError for any node type we don't explicitly allow,
    which prevents injection of arbitrary Python code.
    """

    # ast.Constant represents a literal value like 42, 3.14, etc.
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)  # always work in floats to avoid int/float quirks
        raise ValueError(f"Unsupported constant type: {type(node.value)}")

    # ast.BinOp represents a binary operation: left OP right
    # e.g. "3 + 4" → BinOp(left=Constant(3), op=Add(), right=Constant(4))
    if isinstance(node, ast.BinOp):
        op_func = _SAFE_BINARY_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        # Recursively evaluate both sides of the expression, then apply the op.
        return op_func(_eval_node(node.left), _eval_node(node.right))

    # ast.UnaryOp represents a unary operation: OP operand
    # e.g. "-5" → UnaryOp(op=USub(), operand=Constant(5))
    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_UNARY_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_func(_eval_node(node.operand))

    # If we reach here, the AST contains something we didn't allow (e.g.
    # a function call, a variable name, an import, etc.). Reject it.
    raise ValueError(f"Unsupported AST node: {type(node).__name__}")


def _format_result(value: float) -> str:
    """Format a float cleanly: 6.0 → '6', 3.14159 → '3.14159'."""
    # If the result is a whole number, show it without the decimal point.
    if value == int(value):
        return str(int(value))
    # Otherwise show the float, but strip unnecessary trailing zeros.
    return f"{value:.10g}"  # 'g' format removes trailing zeros automatically


def evaluate(expression: str) -> Optional[str]:
    """Try to evaluate `expression` as a math expression.

    Returns the result as a string, or None if the expression is not valid math.
    Never raises an exception – all errors are caught and return None.
    """
    # Quick pre-filter: if the query has no digits at all, it can't be math.
    # This avoids the overhead of parsing text like "hello world".
    if not any(ch.isdigit() for ch in expression):
        return None

    # Also require at least one operator character to avoid showing the
    # calculator result for bare numbers like "42" typed as a search query.
    if not any(ch in expression for ch in "+-*/%^("):
        return None

    try:
        # ast.parse turns the string into a tree. mode="eval" means we expect
        # a single expression (not statements like assignments or imports).
        tree = ast.parse(expression.strip(), mode="eval")

        # tree.body is the root expression node.
        result = _eval_node(tree.body)

        return _format_result(result)

    except ZeroDivisionError:
        return "Division by zero"
    except Exception:
        # Anything that goes wrong (syntax error, unsupported node, etc.)
        # just means "this isn't a math expression" – return None quietly.
        return None
