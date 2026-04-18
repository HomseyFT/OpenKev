"""Typed spreadsheet values.

Every cell evaluates to exactly one :class:`Value` subclass. Errors are
first-class values so they propagate cleanly through formula evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class ErrorCode(str, Enum):
    """Spreadsheet error sentinels (string-valued for stable serialization)."""

    DIV_ZERO = "#DIV/0!"
    REF = "#REF!"
    NAME = "#NAME?"
    VALUE = "#VALUE!"
    NUM = "#NUM!"
    CIRC = "#CIRC!"
    NA = "#N/A"

    def __str__(self) -> str:  # pragma: no cover — trivial
        return self.value


class Value:
    """Base class for all evaluated cell values."""

    __slots__ = ()

    def display(self) -> str:
        """Human-readable, unformatted rendering of the value."""
        raise NotImplementedError

    def as_number(self) -> "Value":
        """Coerce to a Number or return an Error value describing the failure."""
        return ErrorValue(ErrorCode.VALUE)

    @property
    def is_error(self) -> bool:
        return isinstance(self, ErrorValue)


@dataclass(frozen=True)
class EmptyValue(Value):
    """An empty cell (distinct from the string ``""``)."""

    def display(self) -> str:
        return ""

    def as_number(self) -> Value:
        return NumberValue(0.0)


@dataclass(frozen=True)
class NumberValue(Value):
    number: float

    def display(self) -> str:
        # Integers without fractional component should render without a
        # trailing ``.0`` (matches typical spreadsheet behavior).
        if self.number == int(self.number) and abs(self.number) < 1e16:
            return str(int(self.number))
        return repr(self.number)

    def as_number(self) -> Value:
        return self


@dataclass(frozen=True)
class TextValue(Value):
    text: str

    def display(self) -> str:
        return self.text

    def as_number(self) -> Value:
        # Allow coercion of numeric-looking text (common spreadsheet behavior).
        try:
            return NumberValue(float(self.text))
        except (TypeError, ValueError):
            return ErrorValue(ErrorCode.VALUE)


@dataclass(frozen=True)
class BoolValue(Value):
    value: bool

    def display(self) -> str:
        return "TRUE" if self.value else "FALSE"

    def as_number(self) -> Value:
        return NumberValue(1.0 if self.value else 0.0)


@dataclass(frozen=True)
class DateTimeValue(Value):
    when: datetime

    def display(self) -> str:
        if self.when.time() == datetime.min.time():
            return self.when.date().isoformat()
        return self.when.isoformat(sep=" ", timespec="seconds")

    def as_number(self) -> Value:
        # Days since 1899-12-30 (Excel epoch) as a reasonable numeric fallback.
        epoch = datetime(1899, 12, 30)
        delta = self.when - epoch
        return NumberValue(delta.total_seconds() / 86400.0)


@dataclass(frozen=True)
class ErrorValue(Value):
    code: ErrorCode
    detail: str = ""

    def display(self) -> str:
        return self.code.value

    def as_number(self) -> Value:
        return self


# ---- Helpers --------------------------------------------------------------

_TRUE_STRS = {"TRUE", "true", "True"}
_FALSE_STRS = {"FALSE", "false", "False"}


def from_literal(text: str) -> Value:
    """Best-effort coercion of a user-entered literal (no ``=`` prefix) into a Value.

    Ordering mirrors Excel/Sheets: empty -> bool -> number -> date -> text.
    """
    if text == "":
        return EmptyValue()
    if text in _TRUE_STRS:
        return BoolValue(True)
    if text in _FALSE_STRS:
        return BoolValue(False)
    # Numbers
    try:
        num = float(text)
        return NumberValue(num)
    except ValueError:
        pass
    # ISO dates and timestamps
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return DateTimeValue(datetime.strptime(text, fmt))
        except ValueError:
            continue
    return TextValue(text)


def from_python(obj: object) -> Value:
    """Convert a raw Python object (e.g. from openpyxl) into a Value."""
    if obj is None:
        return EmptyValue()
    if isinstance(obj, bool):
        return BoolValue(obj)
    if isinstance(obj, (int, float)):
        return NumberValue(float(obj))
    if isinstance(obj, datetime):
        return DateTimeValue(obj)
    if isinstance(obj, date):
        return DateTimeValue(datetime(obj.year, obj.month, obj.day))
    if isinstance(obj, str):
        return TextValue(obj)
    return TextValue(str(obj))
