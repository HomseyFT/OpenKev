"""Qt adapter that exposes a :class:`Sheet` through :class:`QAbstractTableModel`.

Design notes:

* The model NEVER mutates the underlying workbook directly — all edits go
  through ``workbook.set_cell_source`` so the dependency graph recalc path is
  always exercised.
* The model subscribes to the workbook's :class:`WorkbookEvent` stream and
  emits targeted ``dataChanged`` for only the cells the recalc touched,
  avoiding full grid repaints.
* Headers are ``A``/``B``/``...`` horizontally and 1-based integers vertically
  to match spreadsheet conventions.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont

from apps.Kevcel.core.refs import index_to_column_letters
from apps.Kevcel.core.styles import (
    CellStyle, HAlign, NumberFormat, VAlign, format_datetime, format_number,
)
from apps.Kevcel.core.values import (
    DateTimeValue, ErrorValue, NumberValue, TextValue, Value,
)
from apps.Kevcel.core.workbook import Workbook, WorkbookEvent


class SheetModel(QAbstractTableModel):
    """Table model bound to a specific sheet of a :class:`Workbook`."""

    def __init__(self, workbook: Workbook, sheet_idx: int, parent=None) -> None:
        super().__init__(parent)
        self._wb = workbook
        self._sheet_idx = sheet_idx
        self._unsubscribe = workbook.subscribe(self._on_workbook_event)

    # ---- Lifecycle ------------------------------------------------------

    def dispose(self) -> None:
        self._unsubscribe()

    def sheet_idx(self) -> int:
        return self._sheet_idx

    # ---- Dimensions -----------------------------------------------------

    def _sheet(self):
        return self._wb.sheets[self._sheet_idx]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return self._sheet().logical_rows

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return self._sheet().logical_cols

    # ---- Headers --------------------------------------------------------

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return index_to_column_letters(section)
        return str(section + 1)

    # ---- Cell data ------------------------------------------------------

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return (
            Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsEnabled
        )

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        cell = self._sheet().get(row, col)
        if cell is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return _formatted_display(cell.value, cell.style)
        if role == Qt.ItemDataRole.EditRole:
            return cell.source
        if role == Qt.ItemDataRole.ToolTipRole:
            if isinstance(cell.value, ErrorValue) and cell.value.detail:
                return f"{cell.value.display()}: {cell.value.detail}"
            return None
        if role == Qt.ItemDataRole.FontRole:
            return _font_from_style(cell.style)
        if role == Qt.ItemDataRole.ForegroundRole:
            if isinstance(cell.value, ErrorValue):
                return QBrush(QColor("#c62828"))
            if cell.style.font_color:
                return QBrush(QColor(cell.style.font_color))
            return None
        if role == Qt.ItemDataRole.BackgroundRole:
            if cell.style.fill_color:
                return QBrush(QColor(cell.style.fill_color))
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return _qt_alignment(cell.style, cell.value)
        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        self._wb.set_cell_source(self._sheet_idx, index.row(), index.column(), str(value))
        return True

    # ---- Helpers for external callers (formula bar, toolbar) -----------

    def cell_source(self, row: int, col: int) -> str:
        cell = self._sheet().get(row, col)
        return cell.source if cell else ""

    def cell_style(self, row: int, col: int) -> CellStyle:
        cell = self._sheet().get(row, col)
        from apps.Kevcel.core.styles import DEFAULT_STYLE
        return cell.style if cell else DEFAULT_STYLE

    # ---- Workbook event handling ---------------------------------------

    def _on_workbook_event(self, event: WorkbookEvent) -> None:
        if event.kind == "structure":
            # Something big changed (sheet add/remove/recalc-all).
            self.beginResetModel()
            self.endResetModel()
            return
        if event.kind == "sheet_renamed":
            return  # handled at the tab-bar level
        if event.kind != "cell":
            return
        if event.sheet_idx is not None and event.sheet_idx != self._sheet_idx:
            return
        if not event.cells:
            return
        # Emit a single dataChanged per affected cell. Each cell is a point so
        # the bounding box is trivial.
        for r, c in event.cells:
            idx = self.index(r, c)
            self.dataChanged.emit(idx, idx)


# ---- Helpers --------------------------------------------------------------


def _font_from_style(style: CellStyle) -> QFont | None:
    if not (style.bold or style.italic or style.underline or style.font_family or style.font_size):
        return None
    font = QFont()
    if style.font_family:
        font.setFamilies([style.font_family])
    if style.font_size:
        font.setPointSize(style.font_size)
    font.setBold(style.bold)
    font.setItalic(style.italic)
    font.setUnderline(style.underline)
    return font


def _qt_alignment(style: CellStyle, value: Value) -> int:
    h_map = {
        HAlign.LEFT: Qt.AlignmentFlag.AlignLeft,
        HAlign.CENTER: Qt.AlignmentFlag.AlignHCenter,
        HAlign.RIGHT: Qt.AlignmentFlag.AlignRight,
    }
    v_map = {
        VAlign.TOP: Qt.AlignmentFlag.AlignTop,
        VAlign.MIDDLE: Qt.AlignmentFlag.AlignVCenter,
        VAlign.BOTTOM: Qt.AlignmentFlag.AlignBottom,
    }
    if style.h_align is HAlign.DEFAULT:
        h = (
            Qt.AlignmentFlag.AlignRight
            if isinstance(value, NumberValue) else Qt.AlignmentFlag.AlignLeft
        )
    else:
        h = h_map[style.h_align]
    v = v_map.get(style.v_align, Qt.AlignmentFlag.AlignVCenter)
    return h | v


def _formatted_display(value: Value, style: CellStyle) -> str:
    fmt = style.number_format
    if fmt is NumberFormat.GENERAL or fmt is NumberFormat.TEXT:
        return value.display()
    if isinstance(value, NumberValue):
        return format_number(value.number, fmt)
    if isinstance(value, DateTimeValue):
        return format_datetime(value.when, fmt)
    if isinstance(value, TextValue):
        return value.text
    return value.display()
