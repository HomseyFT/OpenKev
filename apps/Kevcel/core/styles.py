"""Cell-level styling.

Styles are **immutable** (`frozen=True`) so they can be shared safely between
cells without worrying about mutation. The UI updates a cell's style by
replacing the :class:`CellStyle` instance wholesale via helpers like
:meth:`CellStyle.with_bold`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from datetime import datetime
from enum import Enum


class HAlign(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    DEFAULT = "default"  # numbers right, text left, bools center


class VAlign(str, Enum):
    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


class NumberFormat(str, Enum):
    GENERAL = "general"      # no forced formatting
    INTEGER = "integer"      # 1234
    DECIMAL_2 = "decimal_2"  # 1234.56
    PERCENT = "percent"      # 12.3%
    CURRENCY = "currency"    # $1,234.56
    DATE = "date"            # 2025-04-18
    DATETIME = "datetime"    # 2025-04-18 12:34:56
    TEXT = "text"            # force as text (no coercion)


@dataclass(frozen=True)
class CellStyle:
    """Immutable per-cell style.

    Fields are deliberately primitive to make serialization trivial. The UI
    layer converts to QFont/QColor on demand.
    """

    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_family: str | None = None
    font_size: int | None = None
    font_color: str | None = None       # CSS-style, e.g. "#rrggbb"
    fill_color: str | None = None       # CSS-style, e.g. "#rrggbb"
    h_align: HAlign = HAlign.DEFAULT
    v_align: VAlign = VAlign.MIDDLE
    number_format: NumberFormat = NumberFormat.GENERAL

    # ---- Mutation helpers (return a new style) ----------------------------

    def with_bold(self, on: bool) -> "CellStyle":
        return replace(self, bold=on)

    def with_italic(self, on: bool) -> "CellStyle":
        return replace(self, italic=on)

    def with_underline(self, on: bool) -> "CellStyle":
        return replace(self, underline=on)

    def with_font(self, *, family: str | None = None, size: int | None = None) -> "CellStyle":
        kwargs = {}
        if family is not None:
            kwargs["font_family"] = family
        if size is not None:
            kwargs["font_size"] = size
        return replace(self, **kwargs)

    def with_colors(
        self,
        *,
        font_color: str | None = ...,  # sentinel: keep existing
        fill_color: str | None = ...,
    ) -> "CellStyle":
        kwargs = {}
        if font_color is not ...:
            kwargs["font_color"] = font_color
        if fill_color is not ...:
            kwargs["fill_color"] = fill_color
        return replace(self, **kwargs)

    def with_alignment(self, *, h: HAlign | None = None, v: VAlign | None = None) -> "CellStyle":
        kwargs = {}
        if h is not None:
            kwargs["h_align"] = h
        if v is not None:
            kwargs["v_align"] = v
        return replace(self, **kwargs)

    def with_number_format(self, nf: NumberFormat) -> "CellStyle":
        return replace(self, number_format=nf)

    # ---- Serialization ----------------------------------------------------

    def to_dict(self) -> dict:
        """Dict representation with enums rendered as their string values."""
        out: dict = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if v == f.default:
                continue  # keep serialized form minimal
            if isinstance(v, Enum):
                v = v.value
            out[f.name] = v
        return out

    @classmethod
    def from_dict(cls, data: dict) -> "CellStyle":
        if not data:
            return cls()
        payload = dict(data)
        if "h_align" in payload:
            payload["h_align"] = HAlign(payload["h_align"])
        if "v_align" in payload:
            payload["v_align"] = VAlign(payload["v_align"])
        if "number_format" in payload:
            payload["number_format"] = NumberFormat(payload["number_format"])
        return cls(**payload)


# Module-level default so we don't keep allocating fresh blanks.
DEFAULT_STYLE: CellStyle = CellStyle()


# ---- Number formatting ----------------------------------------------------


def format_number(n: float, fmt: NumberFormat) -> str:
    """Render a number according to a :class:`NumberFormat`."""
    if fmt is NumberFormat.GENERAL:
        if n == int(n) and abs(n) < 1e16:
            return str(int(n))
        return repr(n)
    if fmt is NumberFormat.INTEGER:
        return f"{int(round(n))}"
    if fmt is NumberFormat.DECIMAL_2:
        return f"{n:,.2f}"
    if fmt is NumberFormat.PERCENT:
        return f"{n * 100:.2f}%"
    if fmt is NumberFormat.CURRENCY:
        return f"${n:,.2f}"
    # Dates/datetimes/text are not applicable to pure numbers; fall back.
    return str(n)


def format_datetime(dt: datetime, fmt: NumberFormat) -> str:
    if fmt is NumberFormat.DATETIME:
        return dt.isoformat(sep=" ", timespec="seconds")
    # DATE and anything else default to date-only ISO
    return dt.date().isoformat()
