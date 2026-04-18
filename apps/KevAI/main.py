"""Standalone entry point for KevPilot.

Run with::

    python -m apps.KevAI.main

This mirrors the structure of ``apps/WeiWord/main.py`` so every module can be
launched in isolation for development, while still being embeddable inside the
top-level OpenKev navigator when that arrives.
"""

from __future__ import annotations

import sys
sys.path.append("../..")

from PySide6.QtWidgets import QApplication, QMainWindow

from apps.KevAI.kevai import KevPilot


class KevPilotWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KevPilot")
        self.resize(900, 700)
        self.module = KevPilot()
        self.setCentralWidget(self.module)
        self.setWindowIcon("static/kev.png")


def main() -> int:
    app = QApplication(sys.argv)
    window = KevPilotWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
