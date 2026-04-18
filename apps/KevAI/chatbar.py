from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout,
    QLineEdit, QPushButton
)
from PySide6.QtCore import Qt
from message import MessageWidget

class ChatBar(QWidget):
    def __init__(self, chatWindow):
        super().__init__()
        self.chatWindow = chatWindow
        self.setWindowTitle("Chat Input Bar")
        self.setFixedHeight(80)
        # self.setMaximumWidth(parent.width())


        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Text input
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a message...")
        self.input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 20px;
                padding: 10px;
                font-size: 14px;
            }
        """)

        # Send button
        self.send_button = QPushButton("Send")
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.setFixedWidth(80)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 20px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        # Connect action
        self.send_button.clicked.connect(self.send_message)
        self.input.returnPressed.connect(self.send_message)

        layout.addWidget(self.input)
        layout.addWidget(self.send_button)

        self.setLayout(layout)

    def send_message(self):
        text = self.input.text().strip()
        self.chatWindow.add_message(MessageWidget("You", text, is_self=True, parent=self.chatWindow))
        if text:
            print("Sent:", text)
            self.input.clear()
