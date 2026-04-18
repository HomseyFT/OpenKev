"""Standalone entry point for Kevcel.

Run with::

    python -m apps.Kevcel.main
"""

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from apps.Kevcel.kevcel import Kevcel  # noqa: E402


class KevcelWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Kevcel")
        self.resize(1200, 800)
        self.module = Kevcel()
        self.setCentralWidget(self.module)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if self.module.close_all():
            event.accept()
        else:
            event.ignore()


def main() -> int:
    app = QApplication(sys.argv)
    window = KevcelWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
