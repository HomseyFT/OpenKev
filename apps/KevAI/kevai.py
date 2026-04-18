"""KevPilot — the AI chat module for OpenKev.

Talks to a local Ollama server. The UI is composed of:

* :class:`ChatWindow` — scrollable chat transcript
* :class:`ChatBar`    — input row + Send button

``KevPilot`` satisfies the :class:`KevModule` contract. It has no on-disk
documents, so ``open_files`` is always empty and ``focus_file`` is a no-op.
"""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from apps.KevAI.chatbar import ChatBar, DEFAULT_OLLAMA_MODEL
from apps.KevAI.chatwindow import ChatWindow
from apps.kev_module import KevModule


class KevPilot(KevModule):
    """Ollama-backed chat module."""

    app_name = "KevPilot"

    def __init__(
        self,
        model: str = DEFAULT_OLLAMA_MODEL,
        parent: QWidget | None = None,
        
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.chat_window = ChatWindow(self)
        self.chat_bar = ChatBar(self.chat_window, model=model, parent=self)

        layout.addWidget(self.chat_window, stretch=1)
        layout.addWidget(self.chat_bar)

    # ----- KevModule interface ------------------------------------------

    @property
    def open_files(self) -> list[str]:
        return []

    def focus_file(self, filepath: str) -> None:  # noqa: ARG002 — no-op by design
        return None
