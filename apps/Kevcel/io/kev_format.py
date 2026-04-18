"""Kevcel ``.kev`` spreadsheet format.

On-disk layout::

    <!-- kev-sheet:1.0 -->
    { "version": "1.0", "active": 0, "sheets": [ ... ] }

The payload is canonical UTF-8 JSON. We deliberately do NOT persist evaluated
values — on load we re-parse and re-evaluate every formula, which guarantees
disk state never goes stale relative to the engine's behavior.

The shared ``.kev`` extension distinguishes itself from WeiWord documents by
the first-line sentinel, so a single loader can sniff the file and dispatch.
"""

from __future__ import annotations

import json
from pathlib import Path

from apps.Kevcel.core.styles import CellStyle
from apps.Kevcel.core.workbook import Cell, Sheet, Workbook


SHEET_VERSION_HEADER = "<!-- kev-sheet:1.0 -->\n"
WEIWORD_VERSION_HEADER = "<!-- kev:1.0 -->"


# ---- Sniffing -------------------------------------------------------------


def sniff_kev_file(path: str | Path) -> str:
    """Return ``"sheet"``, ``"document"``, or ``"unknown"`` from the header."""
    with open(path, "r", encoding="utf-8") as f:
        first_line = f.readline().rstrip("\r\n")
    if first_line == SHEET_VERSION_HEADER.rstrip("\r\n"):
        return "sheet"
    if first_line.startswith(WEIWORD_VERSION_HEADER):
        return "document"
    return "unknown"


# ---- Serialization --------------------------------------------------------


def save_workbook(workbook: Workbook, path: str | Path) -> None:
    """Write the workbook as a ``.kev`` spreadsheet."""
    payload = _workbook_to_dict(workbook)
    text = SHEET_VERSION_HEADER + json.dumps(payload, indent=2, ensure_ascii=False)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def load_workbook(path: str | Path) -> Workbook:
    """Load a ``.kev`` spreadsheet and return a fully-recalculated workbook."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    if not raw.startswith(SHEET_VERSION_HEADER):
        raise ValueError(f"Not a Kevcel spreadsheet (missing header): {path}")
    body = raw[len(SHEET_VERSION_HEADER):]
    data = json.loads(body)
    wb = _workbook_from_dict(data)
    wb.recalculate_all()
    return wb


# ---- Internal conversion --------------------------------------------------


def _workbook_to_dict(wb: Workbook) -> dict:
    return {
        "version": "1.0",
        "active": wb.active_index,
        "sheets": [_sheet_to_dict(s) for s in wb.sheets],
    }


def _sheet_to_dict(sheet: Sheet) -> dict:
    cells_payload: list[dict] = []
    # Sorted for deterministic output (helps diffs / tests).
    for (row, col) in sorted(sheet.cells):
        cell = sheet.cells[(row, col)]
        entry: dict = {"r": row, "c": col, "src": cell.source}
        style_dict = cell.style.to_dict()
        if style_dict:
            entry["style"] = style_dict
        cells_payload.append(entry)
    return {
        "name": sheet.name,
        "logical_rows": sheet.logical_rows,
        "logical_cols": sheet.logical_cols,
        "row_heights": {str(k): v for k, v in sheet.row_heights.items()},
        "col_widths": {str(k): v for k, v in sheet.col_widths.items()},
        "cells": cells_payload,
    }


def _workbook_from_dict(data: dict) -> Workbook:
    names = [s["name"] for s in data.get("sheets", [])] or ["Sheet1"]
    wb = Workbook(sheet_names=names)
    wb.active_index = int(data.get("active", 0))
    for idx, sheet_data in enumerate(data.get("sheets", [])):
        sheet = wb.sheets[idx]
        sheet.logical_rows = int(sheet_data.get("logical_rows", sheet.logical_rows))
        sheet.logical_cols = int(sheet_data.get("logical_cols", sheet.logical_cols))
        sheet.row_heights = {int(k): int(v) for k, v in sheet_data.get("row_heights", {}).items()}
        sheet.col_widths = {int(k): int(v) for k, v in sheet_data.get("col_widths", {}).items()}
        for entry in sheet_data.get("cells", []):
            row = int(entry["r"])
            col = int(entry["c"])
            source = entry.get("src", "")
            style = CellStyle.from_dict(entry.get("style", {}))
            # Value is intentionally left empty; recalculate_all fills it in.
            sheet.cells[(row, col)] = Cell(source=source, style=style)
            sheet.ensure_bounds(row, col)
    return wb
