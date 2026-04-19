"""OpenKev Navigator — top-level entry point.

Run with::

    python -m apps.main

Layout
------
The navigator is a QMainWindow with a QDockWidget sidebar on the left.

* When no apps are open the central area shows the Home page — logo,
  app name, and launch buttons.
* Once at least one app is open the central area switches to a
  QStackedWidget whose pages are the live module widgets. The sidebar
  lists open apps and lets the user switch between them or go Home.
* The Home button in the sidebar always returns to the Home page without
  closing any open apps.
* Opening an already-open app focuses its existing instance rather than
  creating a new one.
* Kev Teams runs its WebSocket receiver in a daemon thread, mirroring
  its standalone launcher.
"""

from __future__ import annotations

import os
import sys
import threading

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDockWidget, QLabel, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
    QVBoxLayout, QWidget,
)

from apps.kev_module import KevModule


# ---------------------------------------------------------------------------
# App registry — add new modules here
# ---------------------------------------------------------------------------

def _make_kevpilot(parent) -> KevModule:
    from apps.KevAI.kevai import KevPilot
    return KevPilot(parent=parent)

def _make_weiword(parent) -> KevModule:
    from apps.WeiWord.weiword import WeiWord
    return WeiWord(parent=parent)

def _make_kevcel(parent) -> KevModule:
    from apps.Kevcel.kevcel import Kevcel
    return Kevcel(parent=parent)

def _make_kevin_compressor(parent) -> KevModule:
    from apps.KevinCompressor.kevin_compressor import KevinCompressor
    return KevinCompressor(parent=parent)

def _make_keems(parent) -> QWidget:
    """
    Keems doesn't subclass KevModule so we extract its central widget
    from KeemsWindow and wire up the WebSocket receiver thread here.
    """
    import threading
    from apps.Keems.chatwindow import ChatWindow
    from apps.Keems.chatbar import ChatBar
    from apps.Keems.ipbar import IpBar
    from apps.Keems.message import MessageWidget
    from apps.Keems.recvMessage import MessageReceiver

    container = QWidget(parent)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    chat_window = ChatWindow(container)
    chat_bar = ChatBar(parent=container, chat_window=chat_window)
    ip_bar = IpBar(chat_window)

    layout.addWidget(ip_bar)
    layout.addWidget(chat_window, stretch=1)
    layout.addWidget(chat_bar)

    receiver = MessageReceiver()
    receiver.message_received.connect(
        lambda username, message: chat_window.add_message(
            MessageWidget(username, message, is_self=False, parent=chat_bar)
        )
    )
    # Store receiver on the widget so it isn't GC'd
    container._receiver = receiver
    ws_thread = threading.Thread(target=receiver.run, daemon=True)
    ws_thread.start()

    # Give it a display name for the sidebar
    container.app_name = "Kev Teams"
    return container


#: Registry of all launchable apps.
#: Each entry: (display_name, factory_fn)
APP_REGISTRY: list[tuple[str, callable]] = [
    ("KevPilot",          _make_kevpilot),
    ("Wei Word",          _make_weiword),
    ("Kevcel",            _make_kevcel),
    ("Kevin Compressor",  _make_kevin_compressor),
    ("Kev Teams",         _make_keems),
]


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------

LOGO_PATH = os.path.join(os.path.dirname(__file__), "static", "logo.png")


class HomePage(QWidget):
    """Shown on first launch and whenever the Home button is pressed."""

    def __init__(self, on_launch: callable, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_launch = on_launch
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.setSpacing(24)

        # Logo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        px = QPixmap(LOGO_PATH)
        if not px.isNull():
            logo_label.setPixmap(
                px.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
            )
        else:
            logo_label.setText("🗂")
            logo_label.setStyleSheet("font-size: 64px;")
        outer.addWidget(logo_label)

        # App name
        title = QLabel("OpenKev")
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        # Launch buttons
        for name, factory in APP_REGISTRY:
            btn = QPushButton(name)
            btn.setFixedWidth(220)
            btn.setFixedHeight(44)
            btn.setStyleSheet("""
                QPushButton {
                    background: #f0f0f0;
                    border: 1px solid #ccc;
                    border-radius: 8px;
                    font-size: 14px;
                }
                QPushButton:hover { background: #e0e8ff; border-color: #7aabf7; }
                QPushButton:pressed { background: #c8d8ff; }
            """)
            btn.clicked.connect(lambda checked=False, f=factory, n=name: self._on_launch(n, f))
            outer.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

class _SidebarButton(QPushButton):
    """A single entry in the sidebar app list."""

    _STYLE_NORMAL = """
        QPushButton {
            text-align: left;
            padding: 8px 12px;
            border: none;
            border-radius: 6px;
            background: transparent;
            font-size: 13px;
        }
        QPushButton:hover { background: #e0e8ff; }
    """
    _STYLE_ACTIVE = """
        QPushButton {
            text-align: left;
            padding: 8px 12px;
            border: none;
            border-radius: 6px;
            background: #c8d8ff;
            font-weight: bold;
            font-size: 13px;
        }
    """

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(label, parent)
        self.setFlat(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(36)
        self.set_active(False)

    def set_active(self, active: bool) -> None:
        self.setStyleSheet(self._STYLE_ACTIVE if active else self._STYLE_NORMAL)


class Sidebar(QWidget):
    """Left dock panel: Home button + list of open apps."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(160)
        self.setMaximumWidth(220)
        self.setStyleSheet("background: #f5f6fa;")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 12, 8, 8)
        root.setSpacing(4)

        # Home button always at top
        self._home_btn = _SidebarButton("🏠  Home")
        root.addWidget(self._home_btn)

        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #ddd;")
        root.addWidget(divider)

        # Scrollable list of open apps
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_widget)
        root.addWidget(scroll, stretch=1)

        # Map name -> button
        self._buttons: dict[str, _SidebarButton] = {}

    # Public API used by Navigator

    def connect_home(self, slot) -> None:
        self._home_btn.clicked.connect(slot)

    def add_app(self, name: str, slot) -> None:
        if name in self._buttons:
            return
        btn = _SidebarButton(name)
        btn.clicked.connect(slot)
        # Insert before the trailing stretch
        self._list_layout.insertWidget(self._list_layout.count() - 1, btn)
        self._buttons[name] = btn

    def remove_app(self, name: str) -> None:
        btn = self._buttons.pop(name, None)
        if btn:
            self._list_layout.removeWidget(btn)
            btn.deleteLater()

    def set_active(self, name: str | None) -> None:
        """Highlight the button for ``name``; clear all others."""
        self._home_btn.set_active(name is None)
        for n, btn in self._buttons.items():
            btn.set_active(n == name)


# ---------------------------------------------------------------------------
# Navigator (main window)
# ---------------------------------------------------------------------------

class Navigator(QMainWindow):
    """Top-level OpenKev window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OpenKev")
        self.resize(1280, 800)

        # name -> widget
        self._open_apps: dict[str, QWidget] = {}

        # Central stacked widget: page 0 = home, pages 1+ = modules
        self._stack = QStackedWidget()
        self._home = HomePage(on_launch=self.launch_app)
        self._stack.addWidget(self._home)
        self.setCentralWidget(self._stack)

        # Sidebar dock
        self._sidebar = Sidebar()
        self._sidebar.connect_home(self._go_home)

        dock = QDockWidget()
        dock.setWidget(self._sidebar)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        dock.setTitleBarWidget(QWidget())  # hide default title bar
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self._dock = dock

        self._go_home()

    # ------------------------------------------------------------------
    # App lifecycle
    # ------------------------------------------------------------------

    def launch_app(self, name: str, factory: callable) -> None:
        """Open an app or focus its existing instance."""
        if name in self._open_apps:
            self._focus_app(name)
            return

        widget = factory(self._stack)
        self._open_apps[name] = widget
        self._stack.addWidget(widget)
        self._sidebar.add_app(name, lambda checked=False, n=name: self._focus_app(n))
        self._focus_app(name)

    def _focus_app(self, name: str) -> None:
        widget = self._open_apps.get(name)
        if widget is None:
            return
        self._stack.setCurrentWidget(widget)
        self._sidebar.set_active(name)
        self._dock.show()

    def _go_home(self) -> None:
        self._stack.setCurrentWidget(self._home)
        self._sidebar.set_active(None)

    # ------------------------------------------------------------------
    # Close handling — let each module handle its own unsaved-changes
    # prompt; we just clean up the navigator's references after.
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        event.accept()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("OpenKev")
    window = Navigator()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
