from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QScrollArea
)
from PySide6.QtCore import Qt
import sys


class ChatWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Scrollable Chat")
        self.resize(400, 600)

        main_layout = QVBoxLayout(self)

        # --- Scroll Area ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # --- Container inside scroll ---
        self.container = QWidget()
        self.chat_layout = QVBoxLayout(self.container)
        self.chat_layout.setSpacing(5)
        self.chat_layout.addStretch()  # keeps messages at top

        self.scroll_area.setWidget(self.container)

        main_layout.addWidget(self.scroll_area)

    def add_message(self, message_widget):
        # Insert above the stretch so it stays at the bottom
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, message_widget)

        # Auto-scroll to bottom
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())