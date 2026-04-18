"""Per-workbook UI — formatting toolbar + formula bar + sheet tabs.

A workbook view hosts exactly ONE workbook. Multiple workbook views live as
sibling tabs inside the outer :class:`Kevcel` module (see ``kevcel.py``).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QInputDialog, QMessageBox, QStackedWidget, QTableView, QTabBar, QTabWidget,
    QVBoxLayout, QWidget,
)

from apps.Kevcel.core.styles import CellStyle
from apps.Kevcel.core.workbook import Workbook, WorkbookEvent
from apps.Kevcel.ui.formula_bar import FormulaBar
from apps.Kevcel.ui.table_model import SheetModel
from apps.Kevcel.ui.toolbar import FormattingToolbar


class WorkbookView(QWidget):
    """Interactive UI for a single :class:`Workbook`."""

    #: Emitted whenever the workbook contents change and the title/dirty-state
    #: bookkeeping in the outer Kevcel module needs to refresh.
    dirtied = Signal()

    def __init__(
        self,
        workbook: Workbook,
        filepath: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._wb = workbook
        self._filepath = filepath
        self._saved = filepath is not None
        self._sheet_models: list[SheetModel] = []

        self._build_ui()
        self._rebuild_sheet_tabs()

        # Structural changes (add/remove/rename sheet) rebuild the tab bar.
        self._unsub = workbook.subscribe(self._on_workbook_event)

    # ---- public ---------------------------------------------------------

    @property
    def workbook(self) -> Workbook:
        return self._wb

    @property
    def filepath(self) -> str | None:
        return self._filepath

    @filepath.setter
    def filepath(self, value: str | None) -> None:
        self._filepath = value

    @property
    def display_name(self) -> str:
        return Path(self._filepath).name if self._filepath else "Untitled"

    @property
    def is_saved(self) -> bool:
        return self._saved

    def mark_saved(self) -> None:
        self._saved = True
        self.dirtied.emit()

    def dispose(self) -> None:
        for model in self._sheet_models:
            model.dispose()
        self._unsub()

    # ---- sheet-tab management -------------------------------------------

    def add_sheet(self) -> None:
        self._wb.add_sheet()

    def remove_current_sheet(self) -> None:
        idx = self._sheet_tabs.currentIndex()
        if idx < 0:
            return
        try:
            self._wb.remove_sheet(idx)
        except ValueError as exc:
            QMessageBox.warning(self, "Can't remove sheet", str(exc))

    def rename_current_sheet(self) -> None:
        idx = self._sheet_tabs.currentIndex()
        if idx < 0:
            return
        current = self._wb.sheets[idx].name
        new_name, ok = QInputDialog.getText(
            self, "Rename sheet", "Sheet name:", text=current
        )
        if not ok or not new_name:
            return
        try:
            self._wb.rename_sheet(idx, new_name)
        except ValueError as exc:
            QMessageBox.warning(self, "Rename failed", str(exc))

    # ---- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = FormattingToolbar(self)
        self.toolbar.style_action.connect(self._apply_style_to_selection)
        layout.addWidget(self.toolbar)

        self.formula_bar = FormulaBar(self)
        self.formula_bar.submitted.connect(self._on_formula_submitted)
        layout.addWidget(self.formula_bar)

        self._sheet_stack = QStackedWidget(self)
        layout.addWidget(self._sheet_stack, 1)

        self._sheet_tabs = QTabBar(self)
        self._sheet_tabs.setDrawBase(True)
        self._sheet_tabs.setShape(QTabBar.Shape.RoundedSouth)
        self._sheet_tabs.currentChanged.connect(self._on_sheet_changed)
        self._sheet_tabs.tabBarDoubleClicked.connect(lambda _i: self.rename_current_sheet())
        layout.addWidget(self._sheet_tabs)

    # ---- sheet-tab machinery --------------------------------------------

    def _rebuild_sheet_tabs(self) -> None:
        """Rebuild sheet tabs + views to match the current workbook."""
        # Detach old models
        for model in self._sheet_models:
            model.dispose()
        self._sheet_models = []

        # Clear stacked widget
        while self._sheet_stack.count() > 0:
            w = self._sheet_stack.widget(0)
            self._sheet_stack.removeWidget(w)
            w.deleteLater()

        # Clear tab bar
        self._sheet_tabs.blockSignals(True)
        while self._sheet_tabs.count() > 0:
            self._sheet_tabs.removeTab(0)

        for i, sheet in enumerate(self._wb.sheets):
            view = QTableView()
            view.setAlternatingRowColors(True)
            model = SheetModel(self._wb, i, parent=view)
            view.setModel(model)
            view.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
            view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
            view.selectionModel().currentChanged.connect(self._on_current_cell_changed)
            self._sheet_models.append(model)
            self._sheet_stack.addWidget(view)
            self._sheet_tabs.addTab(sheet.name)

        # Restore active sheet if still valid
        active = min(self._wb.active_index, self._wb.sheets.__len__() - 1)
        self._sheet_tabs.setCurrentIndex(active)
        self._sheet_stack.setCurrentIndex(active)
        self._sheet_tabs.blockSignals(False)

    def _on_sheet_changed(self, index: int) -> None:
        if index < 0:
            return
        self._wb.set_active(index)
        self._sheet_stack.setCurrentIndex(index)
        # Re-sync formula bar for the newly-active sheet's current cell.
        view = self._current_view()
        if view is not None:
            current = view.currentIndex()
            if current.isValid():
                self._on_current_cell_changed(current, current)

    def _current_view(self) -> QTableView | None:
        w = self._sheet_stack.currentWidget()
        return w if isinstance(w, QTableView) else None

    def _current_model(self) -> SheetModel | None:
        if not self._sheet_models:
            return None
        return self._sheet_models[self._sheet_tabs.currentIndex()]

    # ---- selection / formula-bar / toolbar sync --------------------------

    def _on_current_cell_changed(self, current, _previous) -> None:
        model = self._current_model()
        if model is None or not current.isValid():
            return
        source = model.cell_source(current.row(), current.column())
        self.formula_bar.set_active_cell(current.row(), current.column(), source)
        self.toolbar.sync_from_style(model.cell_style(current.row(), current.column()))

    def _on_formula_submitted(self, text: str) -> None:
        view = self._current_view()
        if view is None:
            return
        idx = view.currentIndex()
        if not idx.isValid():
            return
        self._wb.set_cell_source(
            self._sheet_tabs.currentIndex(), idx.row(), idx.column(), text
        )
        self._saved = False
        self.dirtied.emit()

    def _apply_style_to_selection(self, mutate: Callable[[CellStyle], CellStyle]) -> None:
        view = self._current_view()
        if view is None:
            return
        sel = view.selectionModel().selectedIndexes()
        if not sel:
            current = view.currentIndex()
            if current.isValid():
                sel = [current]
            else:
                return
        sheet_idx = self._sheet_tabs.currentIndex()
        for idx in sel:
            self._wb.update_cell_style(sheet_idx, idx.row(), idx.column(), mutate)
        self._saved = False
        self.dirtied.emit()

    # ---- workbook -> UI --------------------------------------------------

    def _on_workbook_event(self, event: WorkbookEvent) -> None:
        if event.kind == "structure":
            self._rebuild_sheet_tabs()
        elif event.kind == "sheet_renamed":
            if event.sheet_idx is not None:
                self._sheet_tabs.setTabText(
                    event.sheet_idx, self._wb.sheets[event.sheet_idx].name
                )
        elif event.kind == "cell":
            self._saved = False
            self.dirtied.emit()
