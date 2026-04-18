"""CSV import/export for a single sheet in a Kevcel workbook.

CSV is a lossy format — styles and formulas are flattened to displayed text
on export, and imports always come in as plain literals.
"""

from __future__ import annotations

import csv
from pathlib import Path

from apps.Kevcel.core.workbook import Sheet, Workbook


def import_csv(path: str | Path) -> Workbook:
    """Create a fresh workbook with one sheet populated from a CSV file."""
    wb = Workbook(["Sheet1"])
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for r, row in enumerate(reader):
            for c, cell_text in enumerate(row):
                if cell_text == "":
                    continue
                wb.set_cell_source(0, r, c, cell_text)
    return wb


def export_csv(sheet: Sheet, path: str | Path) -> None:
    """Dump a sheet's *displayed* values to a CSV file."""
    if not sheet.cells:
        # Still write an empty file rather than failing silently.
        open(path, "w").close()
        return
    max_row = max(r for r, _ in sheet.cells)
    max_col = max(c for _, c in sheet.cells)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for r in range(max_row + 1):
            row_out: list[str] = []
            for c in range(max_col + 1):
                cell = sheet.cells.get((r, c))
                row_out.append(cell.value.display() if cell else "")
            writer.writerow(row_out)
