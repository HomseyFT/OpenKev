"""Built-in function registry for Kevcel formulas.

Each function receives a list of argument spans. A span is a list of Values:

* a single-element list if the caller passed a scalar expression (e.g. ``3``,
  ``A1``, ``1+2``)
* a multi-element list if the caller passed a range (already flattened from
  2D grid order by the evaluator)

Functions are expected to return a concrete :class:`Value`. They should never
raise — invalid input is returned as an :class:`ErrorValue`.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Callable, Iterable

from apps.Kevcel.core.values import (
    BoolValue, DateTimeValue, EmptyValue, ErrorCode, ErrorValue, NumberValue,
    TextValue, Value,
)


FunctionImpl = Callable[[list[list[Value]]], Value]
REGISTRY: dict[str, FunctionImpl] = {}


def _register(name: str) -> Callable[[FunctionImpl], FunctionImpl]:
    def decorator(fn: FunctionImpl) -> FunctionImpl:
        REGISTRY[name] = fn
        return fn

    return decorator


# ---- Helpers --------------------------------------------------------------


def _flatten(args: list[list[Value]]) -> list[Value]:
    out: list[Value] = []
    for span in args:
        out.extend(span)
    return out


def _iter_numbers(values: Iterable[Value]) -> Iterable[float]:
    """Yield numeric coercions, silently skipping blanks/text (SUM-style)."""
    for v in values:
        if isinstance(v, EmptyValue):
            continue
        if isinstance(v, NumberValue):
            yield v.number
            continue
        if isinstance(v, BoolValue):
            yield 1.0 if v.value else 0.0
            continue
        # Text / dates / errors are skipped; errors propagate via _first_error
        if isinstance(v, TextValue):
            continue


def _first_error(values: Iterable[Value]) -> Value | None:
    for v in values:
        if v.is_error:
            return v
    return None


def _require_args(args: list[list[Value]], minimum: int, maximum: int | None = None) -> Value | None:
    n = len(args)
    if n < minimum or (maximum is not None and n > maximum):
        return ErrorValue(
            ErrorCode.VALUE,
            f"Expected {minimum}{'+' if maximum is None else f'..{maximum}'} args, got {n}",
        )
    return None


def _scalar(args: list[list[Value]], index: int) -> Value:
    span = args[index]
    if len(span) != 1:
        return ErrorValue(ErrorCode.VALUE, f"Expected scalar for arg #{index + 1}")
    return span[0]


def _as_float(v: Value) -> float | Value:
    n = v.as_number()
    if n.is_error:
        return n
    assert isinstance(n, NumberValue)
    return n.number


def _as_text(v: Value) -> str:
    if isinstance(v, EmptyValue):
        return ""
    return v.display()


# ---- Math -----------------------------------------------------------------


@_register("SUM")
def _sum(args: list[list[Value]]) -> Value:
    flat = _flatten(args)
    err = _first_error(flat)
    if err is not None:
        return err
    return NumberValue(sum(_iter_numbers(flat)))


@_register("AVERAGE")
def _avg(args: list[list[Value]]) -> Value:
    flat = _flatten(args)
    err = _first_error(flat)
    if err is not None:
        return err
    nums = list(_iter_numbers(flat))
    if not nums:
        return ErrorValue(ErrorCode.DIV_ZERO)
    return NumberValue(sum(nums) / len(nums))


@_register("MIN")
def _min(args: list[list[Value]]) -> Value:
    flat = _flatten(args)
    err = _first_error(flat)
    if err is not None:
        return err
    nums = list(_iter_numbers(flat))
    if not nums:
        return NumberValue(0.0)
    return NumberValue(min(nums))


@_register("MAX")
def _max(args: list[list[Value]]) -> Value:
    flat = _flatten(args)
    err = _first_error(flat)
    if err is not None:
        return err
    nums = list(_iter_numbers(flat))
    if not nums:
        return NumberValue(0.0)
    return NumberValue(max(nums))


@_register("COUNT")
def _count(args: list[list[Value]]) -> Value:
    """Count numeric values only (matches Excel/Sheets COUNT)."""
    flat = _flatten(args)
    return NumberValue(float(sum(1 for v in flat if isinstance(v, NumberValue))))


@_register("COUNTA")
def _counta(args: list[list[Value]]) -> Value:
    """Count non-empty values (matches Excel COUNTA)."""
    flat = _flatten(args)
    return NumberValue(float(sum(1 for v in flat if not isinstance(v, EmptyValue))))


@_register("ABS")
def _abs(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 1, 1)) is not None:
        return err
    n = _as_float(_scalar(args, 0))
    if isinstance(n, Value):
        return n
    return NumberValue(abs(n))


@_register("ROUND")
def _round(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 1, 2)) is not None:
        return err
    n = _as_float(_scalar(args, 0))
    if isinstance(n, Value):
        return n
    digits = 0
    if len(args) == 2:
        d = _as_float(_scalar(args, 1))
        if isinstance(d, Value):
            return d
        digits = int(d)
    return NumberValue(round(n, digits))


@_register("SQRT")
def _sqrt(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 1, 1)) is not None:
        return err
    n = _as_float(_scalar(args, 0))
    if isinstance(n, Value):
        return n
    if n < 0:
        return ErrorValue(ErrorCode.NUM)
    return NumberValue(math.sqrt(n))


@_register("POW")
def _pow(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 2, 2)) is not None:
        return err
    base = _as_float(_scalar(args, 0))
    exp = _as_float(_scalar(args, 1))
    if isinstance(base, Value):
        return base
    if isinstance(exp, Value):
        return exp
    try:
        return NumberValue(math.pow(base, exp))
    except (ValueError, OverflowError):
        return ErrorValue(ErrorCode.NUM)


@_register("MOD")
def _mod(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 2, 2)) is not None:
        return err
    a = _as_float(_scalar(args, 0))
    b = _as_float(_scalar(args, 1))
    if isinstance(a, Value):
        return a
    if isinstance(b, Value):
        return b
    if b == 0:
        return ErrorValue(ErrorCode.DIV_ZERO)
    return NumberValue(math.fmod(a, b))


@_register("INT")
def _int(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 1, 1)) is not None:
        return err
    n = _as_float(_scalar(args, 0))
    if isinstance(n, Value):
        return n
    return NumberValue(float(math.floor(n)))


# ---- Logical --------------------------------------------------------------


def _to_bool(v: Value) -> bool | Value:
    if isinstance(v, BoolValue):
        return v.value
    if isinstance(v, NumberValue):
        return v.number != 0
    if isinstance(v, EmptyValue):
        return False
    if isinstance(v, TextValue):
        if v.text.upper() == "TRUE":
            return True
        if v.text.upper() == "FALSE":
            return False
        return ErrorValue(ErrorCode.VALUE)
    if v.is_error:
        return v
    return ErrorValue(ErrorCode.VALUE)


@_register("IF")
def _if(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 2, 3)) is not None:
        return err
    cond = _to_bool(_scalar(args, 0))
    if isinstance(cond, Value):
        return cond
    if cond:
        return _scalar(args, 1)
    if len(args) == 3:
        return _scalar(args, 2)
    return BoolValue(False)


@_register("AND")
def _and(args: list[list[Value]]) -> Value:
    flat = _flatten(args)
    err = _first_error(flat)
    if err is not None:
        return err
    for v in flat:
        b = _to_bool(v)
        if isinstance(b, Value):
            return b
        if not b:
            return BoolValue(False)
    return BoolValue(True)


@_register("OR")
def _or(args: list[list[Value]]) -> Value:
    flat = _flatten(args)
    err = _first_error(flat)
    if err is not None:
        return err
    for v in flat:
        b = _to_bool(v)
        if isinstance(b, Value):
            return b
        if b:
            return BoolValue(True)
    return BoolValue(False)


@_register("NOT")
def _not(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 1, 1)) is not None:
        return err
    b = _to_bool(_scalar(args, 0))
    if isinstance(b, Value):
        return b
    return BoolValue(not b)


# ---- Text -----------------------------------------------------------------


@_register("CONCAT")
def _concat(args: list[list[Value]]) -> Value:
    flat = _flatten(args)
    err = _first_error(flat)
    if err is not None:
        return err
    return TextValue("".join(_as_text(v) for v in flat))


@_register("LEN")
def _len(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 1, 1)) is not None:
        return err
    return NumberValue(float(len(_as_text(_scalar(args, 0)))))


@_register("UPPER")
def _upper(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 1, 1)) is not None:
        return err
    return TextValue(_as_text(_scalar(args, 0)).upper())


@_register("LOWER")
def _lower(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 1, 1)) is not None:
        return err
    return TextValue(_as_text(_scalar(args, 0)).lower())


@_register("TRIM")
def _trim(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 1, 1)) is not None:
        return err
    return TextValue(_as_text(_scalar(args, 0)).strip())


@_register("LEFT")
def _left(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 1, 2)) is not None:
        return err
    s = _as_text(_scalar(args, 0))
    n = 1
    if len(args) == 2:
        nv = _as_float(_scalar(args, 1))
        if isinstance(nv, Value):
            return nv
        n = max(0, int(nv))
    return TextValue(s[:n])


@_register("RIGHT")
def _right(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 1, 2)) is not None:
        return err
    s = _as_text(_scalar(args, 0))
    n = 1
    if len(args) == 2:
        nv = _as_float(_scalar(args, 1))
        if isinstance(nv, Value):
            return nv
        n = max(0, int(nv))
    return TextValue(s[-n:] if n else "")


@_register("MID")
def _mid(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 3, 3)) is not None:
        return err
    s = _as_text(_scalar(args, 0))
    start = _as_float(_scalar(args, 1))
    length = _as_float(_scalar(args, 2))
    if isinstance(start, Value):
        return start
    if isinstance(length, Value):
        return length
    start_i = max(1, int(start)) - 1  # spreadsheet indexes are 1-based
    length_i = max(0, int(length))
    return TextValue(s[start_i : start_i + length_i])


# ---- Date/time ------------------------------------------------------------


@_register("TODAY")
def _today(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 0, 0)) is not None:
        return err
    now = datetime.now()
    return DateTimeValue(datetime(now.year, now.month, now.day))


@_register("NOW")
def _now(args: list[list[Value]]) -> Value:
    if (err := _require_args(args, 0, 0)) is not None:
        return err
    return DateTimeValue(datetime.now())
