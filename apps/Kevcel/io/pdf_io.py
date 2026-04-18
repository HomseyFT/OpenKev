"""PDF export for a single Kevcel sheet.

We reuse the HTML renderer and hand the result to Qt's built-in PDF pipeline
so styling remains consistent between HTML embedding and PDF output.
"""

from __future__ import annotations

import os
from pathlib import Path

from apps.Kevcel.core.workbook import Sheet
from apps.Kevcel.io.html_io import sheet_to_html


def export_sheet_pdf(sheet: Sheet, path: str | Path) -> bool:
    """Render ``sheet`` to a PDF at ``path``. Returns True on success."""
    # Local imports so this module can still be imported in headless tests
    # without pulling in Qt if PDF export isn't exercised.
    from PySide6.QtGui import QTextDocument
    from PySide6.QtPrintSupport import QPrinter

    html = sheet_to_html(sheet, include_headers=True)
    doc = QTextDocument()
    doc.setHtml(html)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    try:
        doc.print_(printer)
    except Exception:
        return False
    try:
        return os.path.exists(path) and os.path.getsize(path) > 0
    except OSError:
        return False
