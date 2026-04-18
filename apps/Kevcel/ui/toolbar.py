"""Formatting toolbar for a Kevcel workbook view.

Each action emits a pure "style mutation" callable via the
:attr:`FormattingToolbar.style_action` signal. The workbook view applies that
mutation to every cell in the current selection.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QLabel, QSpinBox, QToolBar, QWidget,
)

from apps.Kevcel.core.styles import CellStyle, HAlign, NumberFormat


StyleMutation = Callable[[CellStyle], CellStyle]


class FormattingToolbar(QToolBar):
    """Emits :attr:`style_action` with a style mutator for the current selection."""

    style_action = Signal(object)  # emits a Callable[[CellStyle], CellStyle]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setIconSize(QSize(16, 16))
        self.setMovable(False)

        self._build()

    # ---- Construction ---------------------------------------------------

    def _build(self) -> None:
        self.act_bold = QAction("B", self)
        self.act_bold.setShortcut(QKeySequence.StandardKey.Bold)
        self.act_bold.setCheckable(True)
        bold_font = self.act_bold.font()
        bold_font.setBold(True)
        self.act_bold.setFont(bold_font)
        self.act_bold.triggered.connect(self._on_bold)
        self.addAction(self.act_bold)

        self.act_italic = QAction("I", self)
        self.act_italic.setShortcut(QKeySequence.StandardKey.Italic)
        self.act_italic.setCheckable(True)
        italic_font = self.act_italic.font()
        italic_font.setItalic(True)
        self.act_italic.setFont(italic_font)
        self.act_italic.triggered.connect(self._on_italic)
        self.addAction(self.act_italic)

        self.act_underline = QAction("U", self)
        self.act_underline.setShortcut(QKeySequence.StandardKey.Underline)
        self.act_underline.setCheckable(True)
        self.act_underline.triggered.connect(self._on_underline)
        self.addAction(self.act_underline)

        self.addSeparator()

        self.font_combo = QComboBox()
        self.font_combo.setFixedWidth(160)
        self.font_combo.addItems(QFontDatabase.families())
        self.font_combo.activated.connect(self._on_font_family)
        self.addWidget(QLabel(" Font: "))
        self.addWidget(self.font_combo)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 96)
        self.size_spin.setValue(10)
        self.size_spin.setFixedWidth(50)
        self.size_spin.editingFinished.connect(self._on_font_size)
        self.addWidget(QLabel(" Size: "))
        self.addWidget(self.size_spin)

        self.addSeparator()

        act_font_color = QAction("Text Color", self)
        act_font_color.triggered.connect(self._on_font_color)
        self.addAction(act_font_color)

        act_fill_color = QAction("Fill Color", self)
        act_fill_color.triggered.connect(self._on_fill_color)
        self.addAction(act_fill_color)

        self.addSeparator()

        for label, h in (("⬅", HAlign.LEFT), ("⬌", HAlign.CENTER), ("➡", HAlign.RIGHT)):
            act = QAction(label, self)
            act.triggered.connect(self._make_align_handler(h))
            self.addAction(act)

        self.addSeparator()

        self.number_format_combo = QComboBox()
        self.number_format_combo.addItems(
            [
                "General", "Integer", "Decimal", "Percent", "Currency",
                "Date", "Date + Time", "Text",
            ]
        )
        self.number_format_combo.activated.connect(self._on_number_format)
        self.addWidget(QLabel(" Format: "))
        self.addWidget(self.number_format_combo)

    # ---- Sync active-cell style into the toolbar ------------------------

    def sync_from_style(self, style: CellStyle) -> None:
        self.act_bold.blockSignals(True)
        self.act_italic.blockSignals(True)
        self.act_underline.blockSignals(True)
        self.act_bold.setChecked(style.bold)
        self.act_italic.setChecked(style.italic)
        self.act_underline.setChecked(style.underline)
        self.act_bold.blockSignals(False)
        self.act_italic.blockSignals(False)
        self.act_underline.blockSignals(False)

        if style.font_family:
            idx = self.font_combo.findText(style.font_family)
            if idx >= 0:
                self.font_combo.blockSignals(True)
                self.font_combo.setCurrentIndex(idx)
                self.font_combo.blockSignals(False)
        if style.font_size:
            self.size_spin.blockSignals(True)
            self.size_spin.setValue(style.font_size)
            self.size_spin.blockSignals(False)

        fmt_index = _NUMBER_FORMAT_ORDER.index(style.number_format)
        self.number_format_combo.blockSignals(True)
        self.number_format_combo.setCurrentIndex(fmt_index)
        self.number_format_combo.blockSignals(False)

    # ---- Handlers --------------------------------------------------------

    def _on_bold(self, checked: bool) -> None:
        self.style_action.emit(lambda s: s.with_bold(checked))

    def _on_italic(self, checked: bool) -> None:
        self.style_action.emit(lambda s: s.with_italic(checked))

    def _on_underline(self, checked: bool) -> None:
        self.style_action.emit(lambda s: s.with_underline(checked))

    def _on_font_family(self, _index: int) -> None:
        family = self.font_combo.currentText()
        self.style_action.emit(lambda s: s.with_font(family=family))

    def _on_font_size(self) -> None:
        size = int(self.size_spin.value())
        self.style_action.emit(lambda s: s.with_font(size=size))

    def _on_font_color(self) -> None:
        color = QColorDialog.getColor(QColor("black"), self, "Text Color")
        if not color.isValid():
            return
        hex_code = color.name()
        self.style_action.emit(lambda s: s.with_colors(font_color=hex_code))

    def _on_fill_color(self) -> None:
        color = QColorDialog.getColor(QColor("yellow"), self, "Fill Color")
        if not color.isValid():
            return
        hex_code = color.name()
        self.style_action.emit(lambda s: s.with_colors(fill_color=hex_code))

    def _make_align_handler(self, h: HAlign) -> Callable[[bool], None]:
        def handler(_checked: bool) -> None:
            self.style_action.emit(lambda s: s.with_alignment(h=h))
        return handler

    def _on_number_format(self, index: int) -> None:
        fmt = _NUMBER_FORMAT_ORDER[index]
        self.style_action.emit(lambda s: s.with_number_format(fmt))


_NUMBER_FORMAT_ORDER = [
    NumberFormat.GENERAL, NumberFormat.INTEGER, NumberFormat.DECIMAL_2,
    NumberFormat.PERCENT, NumberFormat.CURRENCY, NumberFormat.DATE,
    NumberFormat.DATETIME, NumberFormat.TEXT,
]
