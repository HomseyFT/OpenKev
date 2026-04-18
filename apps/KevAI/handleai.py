"""Background worker that streams Ollama chat responses off the UI thread.

Uses the official ``ollama`` Python SDK which wraps the HTTP streaming API and
yields incremental message deltas. Each delta is emitted as a ``token_received``
signal so the UI can render tokens as they arrive; a final ``finished`` signal
carries the fully assembled response.

Connection-level problems (Ollama not running, host unreachable) are
distinguished from generation-level errors and reported through the ``error``
signal with a human-friendly message.
"""

from __future__ import annotations

import httpx
import ollama
from PySide6.QtCore import QThread, Signal


class AIWorker(QThread):
    """Streams a chat completion from a local Ollama server on a worker thread."""

    token_received = Signal(str)   # emitted for each streamed delta
    finished = Signal(str)         # emitted once with the fully assembled response
    error = Signal(str)            # emitted with a user-friendly error message

    def __init__(
        self,
        model: str,
        messages: list[dict],
        host: str = "http://127.0.0.1:11434",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.messages = messages
        self.host = host

    def run(self) -> None:  # noqa: D401 — QThread override
        try:
            client = ollama.Client(host=self.host)
            full_parts: list[str] = []
            for chunk in client.chat(
                model=self.model,
                messages=self.messages,
                stream=True,
            ):
                # Each chunk is a ChatResponse-like dict with a 'message' payload.
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
            # e.g. model not pulled, invalid request, etc.
            self.error.emit(f"Ollama error: {exc}")
        except Exception as exc:  # pragma: no cover — defensive catch-all
            self.error.emit(f"Unexpected error: {exc!r}")
