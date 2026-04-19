"""Input bar for KevPilot that submits prompts to an Ollama-backed worker."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget, QLabel

from chatwindow import ChatWindow
from message import MessageWidget
from sendMessage import sendMessage

class IpBar(QWidget):
    """Chat input row: QLineEdit + Send button."""

    def __init__(
        self,
        chat_window: ChatWindow,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.chat_window = chat_window
        self.setFixedHeight(80)
        self.setFixedWidth(300)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Recipient")
        self.input.setStyleSheet(
            """
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 20px;
                padding: 10px;
                font-size: 14px;
            }
            """)
        
        self.label = QLabel("IP: ")
        layout.addWidget(self.label)
        layout.addWidget(self.input)
        self.setLayout(layout)

    @property
    def getText(self):
        return self.input.text()
    
    def clearText(self):
        self.input.clear()

        
