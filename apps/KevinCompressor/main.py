"""Standalone entry point for Kevin Compressor.

Run with::

    python -m apps.KevinCompressor.main
"""

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from apps.KevinCompressor.kevin_compressor import KevinCompressor  # noqa: E402


class KevinCompressorWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Kevin Compressor")
        self.resize(1000, 720)
        self.module = KevinCompressor()
        self.setCentralWidget(self.module)


def main() -> int:
    app = QApplication(sys.argv)
    window = KevinCompressorWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
