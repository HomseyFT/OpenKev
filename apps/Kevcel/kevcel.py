"""Kevcel — spreadsheet module for OpenKev.

Owns the outer UI chrome (top menu bar of actions, open-workbook tabs) and
coordinates file-level operations (new/open/save/export/import).
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog, QMessageBox, QTabWidget, QToolBar, QVBoxLayout, QWidget,
)

from apps.kev_module import KevModule
from apps.Kevcel.core.workbook import Workbook
from apps.Kevcel.io.csv_io import export_csv, import_csv
from apps.Kevcel.io.html_io import sheet_to_html
from apps.Kevcel.io.kev_format import (
    SHEET_VERSION_HEADER, load_workbook, save_workbook, sniff_kev_file,
)
from apps.Kevcel.io.pdf_io import export_sheet_pdf
from apps.Kevcel.io.xlsx_io import export_xlsx, import_xlsx
from apps.Kevcel.ui.workbook_view import WorkbookView


KEV_FILTER = "Kev Spreadsheet (*.kev)"
CSV_FILTER = "CSV (*.csv)"
XLSX_FILTER = "Excel Workbook (*.xlsx)"
PDF_FILTER = "PDF (*.pdf)"
HTML_FILTER = "HTML Table (*.html)"


class Kevcel(KevModule):
    """Excel-ish spreadsheet app with multiple open workbooks as inner tabs."""

    app_name = "Kevcel"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.new_workbook()

    # ---- KevModule interface --------------------------------------------

    @property
    def open_files(self) -> list[str]:
        files: list[str] = []
        for i in range(self.tab_bar.count()):
            view = self.tab_bar.widget(i)
            if isinstance(view, WorkbookView) and view.filepath:
                files.append(os.path.abspath(view.filepath))
        return files

    def focus_file(self, filepath: str) -> None:
        abs_path = os.path.abspath(filepath)
        for i in range(self.tab_bar.count()):
            view = self.tab_bar.widget(i)
            if isinstance(view, WorkbookView) and view.filepath:
                if os.path.abspath(view.filepath) == abs_path:
                    self.tab_bar.setCurrentIndex(i)
                    return

    # ---- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_file_toolbar())

        self.tab_bar = QTabWidget()
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.tabCloseRequested.connect(self._close_tab)
        layout.addWidget(self.tab_bar, 1)

    def _build_file_toolbar(self) -> QToolBar:
        tb = QToolBar()
        tb.setIconSize(QSize(16, 16))
        tb.setMovable(False)

        def add(name: str, shortcut: QKeySequence | str | None, slot) -> None:
            act = QAction(name, self)
            if shortcut is not None:
                act.setShortcut(shortcut)
            act.triggered.connect(slot)
            tb.addAction(act)

        add("New", QKeySequence.StandardKey.New, self.new_workbook)
        add("Open…", QKeySequence.StandardKey.Open, self.open_workbook)
        add("Save", QKeySequence.StandardKey.Save, self.save_workbook)
        add("Save As…", QKeySequence("Ctrl+Shift+S"), self._save_as)
        tb.addSeparator()
        add("Import CSV", None, lambda: self._import(CSV_FILTER))
        add("Import XLSX", None, lambda: self._import(XLSX_FILTER))
        tb.addSeparator()
        add("Export…", None, self._export)
        tb.addSeparator()
        add("+ Sheet", None, self._current_view_do("add_sheet"))
        add("Rename Sheet", None, self._current_view_do("rename_current_sheet"))
        add("- Sheet", None, self._current_view_do("remove_current_sheet"))
        return tb

    def _current_view_do(self, method_name: str):
        def _invoke() -> None:
            view = self._current_view()
            if view is not None:
                getattr(view, method_name)()
        return _invoke

    def _current_view(self) -> WorkbookView | None:
        w = self.tab_bar.currentWidget()
        return w if isinstance(w, WorkbookView) else None

    # ---- File operations -------------------------------------------------

    def new_workbook(self) -> None:
        self._add_view(WorkbookView(Workbook()))

    def open_workbook(self, filepath: str | None = None) -> None:
        if not filepath:
            filepath, _ = QFileDialog.getOpenFileName(
                self, "Open Spreadsheet", "", f"{KEV_FILTER};;All Files (*)"
            )
        if not filepath:
            return
        abs_path = os.path.abspath(filepath)
        if abs_path in self.open_files:
            self.focus_file(abs_path)
            return
        try:
            kind = sniff_kev_file(abs_path)
            if kind == "document":
                QMessageBox.warning(
                    self, "Wrong file type",
                    "That .kev file is a WeiWord document, not a spreadsheet.",
                )
                return
            wb = load_workbook(abs_path)
        except Exception as exc:
            QMessageBox.warning(self, "Open failed", f"Could not open file: {exc}")
            return
        self._add_view(WorkbookView(wb, filepath=abs_path))

    def save_workbook(self) -> None:
        view = self._current_view()
        if view is None:
            return
        if not view.filepath:
            self._save_as()
            return
        try:
            save_workbook(view.workbook, view.filepath)
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", f"Could not save: {exc}")
            return
        view.mark_saved()
        self._refresh_tab_title(self.tab_bar.currentIndex())

    def _save_as(self) -> bool:
        view = self._current_view()
        if view is None:
            return False
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Spreadsheet", "", f"{KEV_FILTER};;All Files (*)"
        )
        if not filepath:
            return False
        if not filepath.endswith(".kev"):
            filepath += ".kev"
        try:
            save_workbook(view.workbook, filepath)
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", f"Could not save: {exc}")
            return False
        view.filepath = filepath
        view.mark_saved()
        self._refresh_tab_title(self.tab_bar.currentIndex())
        return True

    # ---- Import / Export -------------------------------------------------

    def _import(self, filter_str: str) -> None:
        filepath, _ = QFileDialog.getOpenFileName(self, "Import", "", filter_str)
        if not filepath:
            return
        try:
            if filter_str == CSV_FILTER:
                wb = import_csv(filepath)
            else:
                wb = import_xlsx(filepath)
        except Exception as exc:
            QMessageBox.warning(self, "Import failed", f"{exc}")
            return
        self._add_view(WorkbookView(wb))  # imported workbooks arrive untitled

    def _export(self) -> None:
        view = self._current_view()
        if view is None:
            return
        filters = ";;".join([PDF_FILTER, CSV_FILTER, XLSX_FILTER, HTML_FILTER])
        filepath, selected = QFileDialog.getSaveFileName(
            self, "Export Spreadsheet", "", filters
        )
        if not filepath:
            return
        wb = view.workbook
        sheet = wb.active_sheet
        lower = filepath.lower()
        try:
            if "pdf" in selected.lower() or lower.endswith(".pdf"):
                if not export_sheet_pdf(sheet, filepath):
                    QMessageBox.warning(self, "Export failed", "PDF export produced no output.")
            elif "csv" in selected.lower() or lower.endswith(".csv"):
                export_csv(sheet, filepath)
            elif "xlsx" in selected.lower() or lower.endswith(".xlsx"):
                export_xlsx(wb, filepath)
            else:
                # HTML: embed standalone <table> fragment in a tiny page
                html = sheet_to_html(sheet, include_headers=True)
                Path(filepath).write_text(
                    f"<!doctype html><meta charset=\"utf-8\"><body>{html}</body>",
                    encoding="utf-8",
                )
        except Exception as exc:
            QMessageBox.warning(self, "Export failed", f"{exc}")

    # ---- Tab bookkeeping -------------------------------------------------

    def _add_view(self, view: WorkbookView) -> None:
        view.dirtied.connect(lambda v=view: self._refresh_tab_title(self.tab_bar.indexOf(v)))
        index = self.tab_bar.addTab(view, view.display_name)
        self.tab_bar.setCurrentIndex(index)
        self._refresh_tab_title(index)

    def _refresh_tab_title(self, index: int) -> None:
        if index < 0:
            return
        view = self.tab_bar.widget(index)
        if not isinstance(view, WorkbookView):
            return
        marker = "" if view.is_saved else "*"
        self.tab_bar.setTabText(index, f"{view.display_name}{marker}")

    def _close_tab(self, index: int) -> None:
        view = self.tab_bar.widget(index)
        if not isinstance(view, WorkbookView):
            return
        if not view.is_saved:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"'{view.display_name}' has unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Save:
                if not view.filepath:
                    self.tab_bar.setCurrentIndex(index)
                    if not self._save_as():
                        return
                else:
                    self.save_workbook()
        view.dispose()
        self.tab_bar.removeTab(index)
        view.deleteLater()

    # ---- Utility for parent windows --------------------------------------

    def close_all(self) -> bool:
        """Try to close every open workbook, honoring save prompts.

        Returns True on success, False if the user cancelled.
        """
        while self.tab_bar.count() > 0:
            before = self.tab_bar.count()
            self._close_tab(self.tab_bar.currentIndex())
            if self.tab_bar.count() == before:
                return False
        return True
