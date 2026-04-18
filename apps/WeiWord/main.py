"""Standalone entry point for Wei Word.

Run with::

    python -m apps.WeiWord.main
"""

from __future__ import annotations

import os
import sys

# When executed directly (``python apps/WeiWord/main.py``) Python doesn't add
# the project root to sys.path, so the ``apps.*`` imports below would fail.
# Under ``python -m apps.WeiWord.main`` this is a no-op because the path is
# already present. Guarded to avoid polluting sys.path unnecessarily.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from apps.WeiWord.weiword import WeiWord  # noqa: E402


class WeiWordWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Wei Word")
        self.resize(1000, 700)
        self.editor = WeiWord()
        self.setCentralWidget(self.editor)

    def closeEvent(self, event) -> None:
        # Attempt to close all tabs gracefully before exiting.
        tab_bar = self.editor.tab_bar
        while tab_bar.count() > 0:
            idx = tab_bar.currentIndex()
            before = tab_bar.count()
            self.editor._close_tab(idx)
            if tab_bar.count() == before:
                # User cancelled a save dialog — abort close.
                event.ignore()
                return
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    window = WeiWordWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
