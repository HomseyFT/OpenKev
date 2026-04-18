"""A1-style references and ranges.

Everything is stored internally as zero-indexed ``(row, col)`` tuples; this
module handles translation to/from the human-facing A1 notation (including
``$``-prefixed absolute markers and optional ``Sheet!`` qualifiers).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Regex for a single A1 reference with optional absolute markers and sheet
# qualifier. The sheet qualifier is captured but not validated here.
_CELL_RE = re.compile(
    r"""
    ^
    (?:(?P<sheet>[A-Za-z_][A-Za-z0-9_ ]*)!)?   # optional "Sheet!" prefix
    (?P<col_abs>\$?)(?P<col>[A-Za-z]+)
    (?P<row_abs>\$?)(?P<row>[0-9]+)
    $
    """,
    re.VERBOSE,
)

_RANGE_RE = re.compile(r"^(?P<start>[^:]+):(?P<end>[^:]+)$")


def column_letters_to_index(letters: str) -> int:
    """Convert a column label like ``A``/``Z``/``AA`` to a zero-based index."""
    letters = letters.upper()
    if not letters or not letters.isalpha():
        raise ValueError(f"Invalid column letters: {letters!r}")
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def index_to_column_letters(index: int) -> str:
    """Convert a zero-based column index to an uppercase A1 letter label."""
    if index < 0:
        raise ValueError(f"Column index must be non-negative: {index}")
    result = ""
    n = index + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


@dataclass(frozen=True)
class CellRef:
    """Immutable reference to a single cell.

    ``sheet`` is None for unqualified refs. ``row``/``col`` are zero-based.
    ``row_absolute``/``col_absolute`` reflect the ``$`` markers from the source.
    """

    row: int
    col: int
    row_absolute: bool = False
    col_absolute: bool = False
    sheet: str | None = None

    def __post_init__(self) -> None:
        if self.row < 0 or self.col < 0:
            raise ValueError(f"CellRef requires non-negative row/col: {self!r}")

    @classmethod
    def parse(cls, text: str) -> "CellRef":
        """Parse an A1-style cell reference string."""
        m = _CELL_RE.match(text.strip())
        if not m:
            raise ValueError(f"Not a valid cell reference: {text!r}")
        return cls(
            row=int(m.group("row")) - 1,
            col=column_letters_to_index(m.group("col")),
            row_absolute=bool(m.group("row_abs")),
            col_absolute=bool(m.group("col_abs")),
            sheet=m.group("sheet"),
        )

    def to_a1(self, *, include_sheet: bool = True) -> str:
        """Render back to A1 string form (preserves absolute markers)."""
        col = ("$" if self.col_absolute else "") + index_to_column_letters(self.col)
        row = ("$" if self.row_absolute else "") + str(self.row + 1)
        base = f"{col}{row}"
        if include_sheet and self.sheet:
            return f"{self.sheet}!{base}"
        return base

    def without_absolutes(self) -> "CellRef":
        """Return an equivalent ref with absolute markers stripped."""
        return CellRef(row=self.row, col=self.col, sheet=self.sheet)


@dataclass(frozen=True)
class RangeRef:
    """Rectangular range with inclusive start/end cell refs."""

    start: CellRef
    end: CellRef

    def __post_init__(self) -> None:
        if (self.start.sheet or None) != (self.end.sheet or None):
            raise ValueError("Range endpoints must share a sheet qualifier")

    @classmethod
    def parse(cls, text: str) -> "RangeRef":
        m = _RANGE_RE.match(text.strip())
        if not m:
            raise ValueError(f"Not a valid range: {text!r}")
        start = CellRef.parse(m.group("start"))
        end = CellRef.parse(m.group("end"))
        # If the end doesn't carry its own sheet prefix but the start does,
        # propagate the sheet so callers see a consistent range.
        if start.sheet and not end.sheet:
            end = CellRef(
                row=end.row,
                col=end.col,
                row_absolute=end.row_absolute,
                col_absolute=end.col_absolute,
                sheet=start.sheet,
            )
        return cls(start=start, end=end)

    @property
    def sheet(self) -> str | None:
        return self.start.sheet

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        """Return ``(top, left, bottom, right)`` as zero-based indices."""
        top = min(self.start.row, self.end.row)
        bottom = max(self.start.row, self.end.row)
        left = min(self.start.col, self.end.col)
        right = max(self.start.col, self.end.col)
        return top, left, bottom, right

    def iter_cells(self) -> list[CellRef]:
        """Yield all concrete (row, col) cell refs inside the range."""
        top, left, bottom, right = self.bounds
        return [
            CellRef(row=r, col=c, sheet=self.sheet)
            for r in range(top, bottom + 1)
            for c in range(left, right + 1)
        ]

    def to_a1(self, *, include_sheet: bool = True) -> str:
        s = self.start.to_a1(include_sheet=include_sheet)
        e = self.end.to_a1(include_sheet=False)
        return f"{s}:{e}"
