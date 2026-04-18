"""Formula bar: cell reference label + QLineEdit for editing the active cell."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget

from apps.Kevcel.core.refs import index_to_column_letters


class FormulaBar(QWidget):
    """A minimal formula bar. Emits :attr:`submitted` when the user presses Enter."""

    submitted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self._ref_label = QLabel("A1")
        self._ref_label.setFixedWidth(60)
        self._ref_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ref_label.setStyleSheet(
            "QLabel { border: 1px solid #ccc; padding: 2px 4px; background: #fafafa; }"
        )

        fx_label = QLabel(" fx ")
        fx_label.setStyleSheet("QLabel { font-style: italic; color: #888; }")

        self._edit = QLineEdit()
        self._edit.returnPressed.connect(self._on_return)

        layout.addWidget(self._ref_label)
        layout.addWidget(fx_label)
        layout.addWidget(self._edit, 1)

    # ---- external setters ------------------------------------------------

    def set_active_cell(self, row: int, col: int, source: str) -> None:
        self._ref_label.setText(f"{index_to_column_letters(col)}{row + 1}")
        self._edit.blockSignals(True)
        self._edit.setText(source)
        self._edit.blockSignals(False)

    def focus_edit(self) -> None:
        self._edit.setFocus(Qt.FocusReason.ShortcutFocusReason)

    # ---- internal --------------------------------------------------------

    def _on_return(self) -> None:
        self.submitted.emit(self._edit.text())
