from __future__ import annotations

import httpx
import ollama
import os
import re
import uuid
from PySide6.QtCore import QThread, QObject, Signal, Slot


class AIWorker(QThread):
    """Ollama streaming + soul.md"""

    token_received = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        model: str,
        messages: list[dict],
        host: str = "http://127.0.0.1:11434",
        soul_path: str | None = os.path.join(os.path.dirname(__file__), "soul.md"),
        parent=None,
    ) -> None:
        super().__init__(parent)

        # LLM config
        self.model = model
        self.messages = messages
        self.host = host

        # Soul prompt
        self.soul_path = soul_path
        self._soul_cache = None
        self._soul_mtime = 0

    # ---------------- SOUL ----------------
    def _load_soul(self):
        if not self.soul_path:
            return None

        try:
            mtime = os.path.getmtime(self.soul_path)
            if self._soul_cache is None or mtime != self._soul_mtime:
                with open(self.soul_path, "r", encoding="utf-8") as f:
                    self._soul_cache = f.read()
                self._soul_mtime = mtime
            return self._soul_cache
        except Exception:
            return None

    # ---------------- MAIN ----------------
    def run(self):
        try:
            client = ollama.Client(host=self.host)

            # 👇 Build message list safely
            final_messages = []

            soul = self._load_soul()
            if soul:
                final_messages.append({
                    "role": "system",
                    "content": soul
                })

            # Avoid mutating original messages
            final_messages.extend(self.messages)

            full_parts: list[str] = []

            for chunk in client.chat(
                model=self.model,
                messages=final_messages,
                stream=True,
            ):
                message = chunk.get("message") if isinstance(chunk, dict) else getattr(chunk, "message", None)
                if message is None:
                    continue

                content = message.get("content") if isinstance(message, dict) else getattr(message, "content", "")
                if content:
                    full_parts.append(content)
                    self.token_received.emit(content)

            self.finished.emit("".join(full_parts))

        except (httpx.ConnectError, ConnectionError) as exc:
            self.error.emit(f"Cannot reach Ollama: {exc}")

        except Exception as exc:
            self.error.emit(f"Unexpected error: {exc!r}")
