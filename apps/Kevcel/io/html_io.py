"""HTML table rendering for a Kevcel sheet.

Produces a self-contained ``<table>`` fragment with all styles inlined. The
output is suitable for:

* embedding inside a WeiWord ``.kev`` document (the "spreadsheets from Kevcel
  imported as static embedded HTML tables" contract)
* feeding into ``QTextDocument.setHtml`` for the PDF pipeline
"""

from __future__ import annotations

from html import escape

from apps.Kevcel.core.styles import CellStyle, HAlign, NumberFormat, format_number
from apps.Kevcel.core.values import (
    DateTimeValue, EmptyValue, NumberValue, Value,
)
from apps.Kevcel.core.workbook import Sheet


def sheet_to_html(sheet: Sheet, *, include_headers: bool = False) -> str:
    """Render a sheet to a styled ``<table>`` fragment.

    ``include_headers`` adds A/B/C column headers and 1/2/3 row labels (useful
    for a print-like PDF export; usually unwanted when embedding in WeiWord).
    """
    if not sheet.cells:
        return '<table class="kevcel-sheet"></table>'
    max_row = max(r for r, _ in sheet.cells)
    max_col = max(c for _, c in sheet.cells)

    parts: list[str] = [
        '<table class="kevcel-sheet" '
        'style="border-collapse: collapse; font-family: sans-serif;">'
    ]

    if include_headers:
        parts.append("<thead><tr>")
        parts.append('<th style="border:1px solid #ccc;background:#eee;"></th>')
        for c in range(max_col + 1):
            parts.append(
                '<th style="border:1px solid #ccc;background:#eee;'
                'padding:2px 6px;">'
                f"{_column_label(c)}</th>"
            )
        parts.append("</tr></thead>")

    parts.append("<tbody>")
    for r in range(max_row + 1):
        parts.append("<tr>")
        if include_headers:
            parts.append(
                '<th style="border:1px solid #ccc;background:#eee;'
                'padding:2px 6px;">'
                f"{r + 1}</th>"
            )
        for c in range(max_col + 1):
            cell = sheet.cells.get((r, c))
            if cell is None:
                parts.append('<td style="border:1px solid #ddd;">&nbsp;</td>')
            else:
                style_attr = _render_cell_style(cell.style, cell.value)
                text = escape(_format_display(cell.value, cell.style))
                parts.append(f'<td style="{style_attr}">{text}</td>')
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _column_label(col: int) -> str:
    # Matches core.refs.index_to_column_letters but avoids circular import.
    result = ""
    n = col + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


def _render_cell_style(style: CellStyle, value: Value) -> str:
    bits = ["border:1px solid #ddd;", "padding:2px 6px;"]
    if style.bold:
        bits.append("font-weight:bold;")
    if style.italic:
        bits.append("font-style:italic;")
    if style.underline:
        bits.append("text-decoration:underline;")
    if style.font_family:
        bits.append(f"font-family:{style.font_family};")
    if style.font_size:
        bits.append(f"font-size:{style.font_size}pt;")
    if style.font_color:
        bits.append(f"color:{style.font_color};")
    if style.fill_color:
        bits.append(f"background-color:{style.fill_color};")
    align = style.h_align
    if align is HAlign.DEFAULT:
        # Default: numbers/bools align right, text left.
        if isinstance(value, NumberValue):
            align = HAlign.RIGHT
        else:
            align = HAlign.LEFT
    if align is not HAlign.DEFAULT:
        bits.append(f"text-align:{align.value};")
    return "".join(bits)


def _format_display(value: Value, style: CellStyle) -> str:
    """Apply the cell's number format (if any) and fall back to .display()."""
    fmt = style.number_format
    if fmt is NumberFormat.GENERAL or fmt is NumberFormat.TEXT:
        return value.display()
    if isinstance(value, NumberValue):
        return format_number(value.number, fmt)
    if isinstance(value, DateTimeValue):
        from apps.Kevcel.core.styles import format_datetime
        return format_datetime(value.when, fmt)
    return value.display()
