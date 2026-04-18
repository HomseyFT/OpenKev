"""AST evaluator.

The evaluator is intentionally decoupled from workbook storage via a small
:class:`EvalContext` protocol. This keeps the engine unit-testable in
isolation (tests just supply a dict-backed mock context).
"""

from __future__ import annotations

from typing import Protocol

from apps.Kevcel.core.parser import (
    BinOp, BoolLit, Expr, FunctionCall, NumberLit, RangeNode, RefNode,
    StringLit, UnaryOp,
)
from apps.Kevcel.core.refs import CellRef, RangeRef
from apps.Kevcel.core.values import (
    BoolValue, EmptyValue, ErrorCode, ErrorValue, NumberValue, TextValue, Value,
)


class EvalContext(Protocol):
    """Minimum interface required for formula evaluation."""

    def get_cell_value(self, ref: CellRef) -> Value: ...

    def get_range_values(self, rng: RangeRef) -> list[list[Value]]: ...


def evaluate(node: Expr, ctx: EvalContext) -> Value:
    """Evaluate an AST node against a context, returning a concrete :class:`Value`."""
    return _eval(node, ctx)


# ---- Dispatch -------------------------------------------------------------


def _eval(node: Expr, ctx: EvalContext) -> Value:
    if isinstance(node, NumberLit):
        return NumberValue(node.value)
    if isinstance(node, StringLit):
        return TextValue(node.value)
    if isinstance(node, BoolLit):
        return BoolValue(node.value)
    if isinstance(node, RefNode):
        if node.ref.sheet:
            # v1 policy: sheet-qualified references are not yet evaluated.
            return ErrorValue(ErrorCode.REF, "Cross-sheet refs not supported yet")
        return ctx.get_cell_value(node.ref.without_absolutes())
    if isinstance(node, RangeNode):
        # Ranges are only meaningful as function arguments (SUM, AVG…). A bare
        # range expression evaluates to a #VALUE! error to match Excel.
        return ErrorValue(ErrorCode.VALUE, "Bare range outside function call")
    if isinstance(node, UnaryOp):
        return _eval_unary(node, ctx)
    if isinstance(node, BinOp):
        return _eval_binop(node, ctx)
    if isinstance(node, FunctionCall):
        return _eval_call(node, ctx)
    return ErrorValue(ErrorCode.VALUE, f"Unknown node type: {type(node).__name__}")


# ---- Unary / binary operator helpers --------------------------------------


def _eval_unary(node: UnaryOp, ctx: EvalContext) -> Value:
    operand = _eval(node.operand, ctx)
    if operand.is_error:
        return operand
    if node.op == "+":
        return operand.as_number()
    if node.op == "-":
        n = operand.as_number()
        if isinstance(n, NumberValue):
            return NumberValue(-n.number)
        return n  # error propagates
    if node.op == "%":
        n = operand.as_number()
        if isinstance(n, NumberValue):
            return NumberValue(n.number / 100.0)
        return n
    return ErrorValue(ErrorCode.VALUE, f"Unknown unary op: {node.op}")


_ARITH_OPS = {"+", "-", "*", "/", "^"}
_COMPARE_OPS = {"=", "<>", "<", ">", "<=", ">="}


def _eval_binop(node: BinOp, ctx: EvalContext) -> Value:
    left = _eval(node.left, ctx)
    right = _eval(node.right, ctx)
    if left.is_error:
        return left
    if right.is_error:
        return right

    if node.op == "&":
        return TextValue(_coerce_text(left) + _coerce_text(right))

    if node.op in _ARITH_OPS:
        ln, rn = left.as_number(), right.as_number()
        if ln.is_error:
            return ln
        if rn.is_error:
            return rn
        assert isinstance(ln, NumberValue) and isinstance(rn, NumberValue)
        try:
            if node.op == "+":
                return NumberValue(ln.number + rn.number)
            if node.op == "-":
                return NumberValue(ln.number - rn.number)
            if node.op == "*":
                return NumberValue(ln.number * rn.number)
            if node.op == "/":
                if rn.number == 0:
                    return ErrorValue(ErrorCode.DIV_ZERO)
                return NumberValue(ln.number / rn.number)
            if node.op == "^":
                return NumberValue(ln.number ** rn.number)
        except (OverflowError, ValueError):
            return ErrorValue(ErrorCode.NUM)

    if node.op in _COMPARE_OPS:
        return _compare(node.op, left, right)

    return ErrorValue(ErrorCode.VALUE, f"Unknown binary op: {node.op}")


def _compare(op: str, left: Value, right: Value) -> Value:
    # Try numeric comparison first; if either side can't coerce, fall back to
    # lexicographic comparison of display strings. Empty is treated as 0.
    ln, rn = left.as_number(), right.as_number()
    if not ln.is_error and not rn.is_error:
        assert isinstance(ln, NumberValue) and isinstance(rn, NumberValue)
        lv, rv = ln.number, rn.number
    else:
        lv, rv = left.display(), right.display()
    result = {
        "=": lv == rv,
        "<>": lv != rv,
        "<": lv < rv,
        ">": lv > rv,
        "<=": lv <= rv,
        ">=": lv >= rv,
    }[op]
    return BoolValue(result)


def _coerce_text(v: Value) -> str:
    if isinstance(v, EmptyValue):
        return ""
    return v.display()


# ---- Function calls -------------------------------------------------------


def _eval_call(node: FunctionCall, ctx: EvalContext) -> Value:
    from apps.Kevcel.core.functions import REGISTRY

    fn = REGISTRY.get(node.name)
    if fn is None:
        return ErrorValue(ErrorCode.NAME, f"Unknown function: {node.name}")

    # Functions receive a list of *argument spans*. Each span is either a
    # flat list of values (from a scalar expr) or the expanded 2D grid of a
    # range. The function decides how to interpret each span.
    arg_values: list[list[Value]] = []
    for a in node.args:
        if isinstance(a, RangeNode):
            grid = ctx.get_range_values(a.range)
            flat = [v for row in grid for v in row]
            arg_values.append(flat)
        else:
            arg_values.append([_eval(a, ctx)])
    try:
        return fn(arg_values)
    except Exception as exc:  # pragma: no cover — defensive
        return ErrorValue(ErrorCode.VALUE, f"{node.name}: {exc!r}")
