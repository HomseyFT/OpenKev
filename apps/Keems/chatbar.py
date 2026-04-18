"""Input bar for KevPilot that submits prompts to an Ollama-backed worker."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

from apps.KevAI.chatwindow import ChatWindow
from apps.KevAI.handleai import AIWorker
from apps.KevAI.message import MessageWidget

# Default model — override by passing ``model`` to ChatBar.
DEFAULT_OLLAMA_MODEL = "llama3.2:latest"
PENDING_PLACEHOLDER = "…"


class ChatBar(QWidget):
    """Chat input row: QLineEdit + Send button wired to an AIWorker."""

    def __init__(
        self,
        chat_window: ChatWindow,
        model: str = DEFAULT_OLLAMA_MODEL,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.chat_window = chat_window
        self.model = model
        self.setFixedHeight(80)

        # Conversation history for multi-turn context
        self._history: list[dict] = []
        self._ai_worker: AIWorker | None = None
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
        if not text or self._ai_worker is not None:
            return  # ignore empty input or while AI is already responding

        self.input.clear()
        self.send_button.setEnabled(False)

        self.chat_window.add_message(
            MessageWidget("You", text, "static/user.png", is_self=True, parent=self.chat_window)
        )
        self._history.append({"role": "user", "content": text})

        self._pending_widget = MessageWidget(
            "KevPilot", PENDING_PLACEHOLDER, "static/kev.png",is_self=False, parent=self.chat_window
        )
        self.chat_window.add_message(self._pending_widget)

        self._ai_worker = AIWorker(self.model, list(self._history), parent=self)
        self._ai_worker.token_received.connect(self._on_token)
        self._ai_worker.finished.connect(self._on_finished)
        self._ai_worker.error.connect(self._on_error)
        self._ai_worker.start()

    def _on_token(self, token: str) -> None:
        """Append each streamed token to the pending message bubble."""
        if self._pending_widget is None:
            return
        current = self._pending_widget.message_label.text()
        if current == PENDING_PLACEHOLDER:
            current = ""
        self._pending_widget.message_label.setText(current + token)
        self.chat_window.scroll_to_bottom()

    def _on_finished(self, full_response: str) -> None:
        if self._pending_widget is not None:
            # Overwrite with the authoritative full response (handles any
            # end-of-stream whitespace normalization the model may have done).
            self._pending_widget.message_label.setText(full_response)
        self._history.append({"role": "assistant", "content": full_response})
        self._cleanup_worker()

    def _on_error(self, error_msg: str) -> None:
        if self._pending_widget is not None:
            self._pending_widget.message_label.setText(f"⚠️ {error_msg}")
        self._cleanup_worker()

    def _cleanup_worker(self) -> None:
        if self._ai_worker is not None:
            self._ai_worker.deleteLater()
            self._ai_worker = None
        self._pending_widget = None
        self.send_button.setEnabled(True)
