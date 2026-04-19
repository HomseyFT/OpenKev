"""Main entrypoint for the Keems chat UI."""

import sys
import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from apps.Keems.message import MessageWidget

from apps.Keems.chatwindow import ChatWindow
from apps.Keems.chatbar import ChatBar
from apps.Keems.recvMessage import MessageReceiver
from apps.Keems.ipbar import IpBar
class KeemsWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Keems")
        self.resize(900, 700)

        central_widget = QWidget(self)
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        self.chat_window = ChatWindow(self)
        self.chat_bar = ChatBar(parent=self, chat_window=self.chat_window)
        self.ip_bar = IpBar(self.chat_window)

        central_layout.addWidget(self.ip_bar)
        central_layout.addWidget(self.chat_window, stretch=1)
        central_layout.addWidget(self.chat_bar)

        self.setCentralWidget(central_widget)

        self.receiver = MessageReceiver()
        self.receiver.message_received.connect(self.receive_remote_message)

    def receive_remote_message(self, username: str, message: str) -> None:
        self.chat_window.add_message(
            MessageWidget(username, message, is_self=False, parent=self.chat_bar)
        )

def main() -> int:
    app = QApplication(sys.argv)
    window = KeemsWindow()
    window.show()

    #Starting window as a thread
    ws_thread = threading.Thread(target=window.receiver.run, daemon=True)
    ws_thread.start()

    return app.exec()


if __name__ == "__main__":
    main()
