from __future__ import annotations

import httpx
import ollama
import os
from PySide6.QtCore import QThread, Signal


class AIWorker(QThread):
    """Streams a chat completion from a local Ollama server on a worker thread."""

    token_received = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        model: str,
        messages: list[dict],
        host: str = "http://127.0.0.1:11434",
        soul_path: str | None = "soul.md",   # 👈 NEW
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.messages = messages
        self.host = host
        self.soul_path = soul_path
        self._soul_cache: str | None = None
        self._soul_mtime: float = 0

    # ---------- NEW: Soul loader ----------
    def _load_soul(self) -> str | None:
        if not self.soul_path:
            return None

        try:
            mtime = os.path.getmtime(self.soul_path)
            if self._soul_cache is None or mtime != self._soul_mtime:
                with open(self.soul_path, "r", encoding="utf-8") as f:
                    self._soul_cache = f.read()
                self._soul_mtime = mtime
            return self._soul_cache
        except FileNotFoundError:
            return None
        except Exception as e:
            # Don't crash worker for soul issues
            self.error.emit(f"Failed to load soul.md: {e}")
            return None

    # ---------- MODIFIED RUN ----------
    def run(self) -> None:
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
            self.error.emit(
                f"Cannot reach Ollama at {self.host}. Is `ollama serve` running? ({exc})"
            )
        except ollama.ResponseError as exc:
            self.error.emit(f"Ollama error: {exc}")
        except Exception as exc:
            self.error.emit(f"Unexpected error: {exc!r}")