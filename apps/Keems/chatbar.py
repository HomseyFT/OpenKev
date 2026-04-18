"""Input bar for KevPilot that submits prompts to an Ollama-backed worker."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

from chatwindow import ChatWindow
from message import MessageWidget
from sendMessage import sendMessage

class ChatBar(QWidget):
    """Chat input row: QLineEdit + Send button."""

    def __init__(
        self,
        chat_window: ChatWindow,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.chat_window = chat_window
        self.setFixedHeight(80)

        # Conversation history for multi-turn context
        self._history: list[dict] = []
        self._pending_widget: MessageWidget | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a message…")
        self.input.setStyleSheet(
            """
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 20px;
                padding: 10px;
                font-size: 14px;
            }
            """
        )

        self.send_button = QPushButton("Send")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setFixedWidth(80)
        self.send_button.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 20px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #9ccba0;
            }
            """
        )

        self.send_button.clicked.connect(self.send_message)
        self.input.returnPressed.connect(self.send_message)

        layout.addWidget(self.input)
        layout.addWidget(self.send_button)

    # ----- slots --------------------------------------------------------

    def send_message(self) -> None:
        text = self.input.text().strip()
        sendMessage(text, self.chat_window)
        # self.chat_window.add_message(MessageWidget("You", text, parent=self.chat_window, is_self=True))

        self.input.clear()
        self.send_button.setEnabled(False)

        
