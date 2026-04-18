"""Scrollable chat surface that hosts MessageWidget bubbles."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget


class ChatWindow(QWidget):
    """A vertically scrolling chat container.

    Messages are appended at the bottom and a trailing stretch keeps early
    messages pinned to the top until the container fills.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.container = QWidget()
        self.chat_layout = QVBoxLayout(self.container)
        self.chat_layout.setSpacing(5)
        self.chat_layout.addStretch()  # trailing stretch keeps messages top-aligned

        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)

    def add_message(self, message_widget: QWidget) -> None:
        """Append a message bubble above the trailing stretch."""
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, message_widget)
        self.scroll_to_bottom()

    def scroll_to_bottom(self) -> None:
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
