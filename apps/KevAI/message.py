from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt


class MessageWidget(QWidget):
    def __init__(self, username, message, avatar_path=None, is_self=False, parent=None):
        super().__init__(parent)
        print("Message Widget: ", parent)
        self.is_self = is_self
        # self.setMaximumWidth(parent.width())


        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10, 5, 10, 5)

        # --- Avatar ---
        self.avatar = QLabel()
        self.avatar.setFixedSize(40, 40)

        if avatar_path:
            pixmap = QPixmap(avatar_path).scaled(
                40, 40,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            self.avatar.setPixmap(pixmap)

        self.avatar.setStyleSheet("""
            QLabel {
                border-radius: 20px;
                background-color: #ccc;
            }
        """)

        # --- Text Container ---
        text_container = QWidget()
        text_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # Set a maximum width on the text container to constrain the message
        text_container.setMaximumWidth(400)  # Adjust based on your chat window width
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        

        # Username
        self.username_label = QLabel(username)
        self.username_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 12px;
                color: #555;
            }
        """)

        # Message bubble
        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setMaximumWidth(parent.width())

        self.message_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        if is_self:
            bubble_color = "#DCF8C6"  # light green
        else:
            bubble_color = "#F1F0F0"  # light gray

        self.message_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                background-color: {bubble_color};
                border-radius: 12px;
                padding: 8px;
            }}
        """)

        text_layout.addWidget(self.username_label)
        text_layout.addWidget(self.message_label)
        text_container.setLayout(text_layout)

        # --- Alignment Logic ---
        if is_self:
            # Right side (you)
            main_layout.addStretch()
            main_layout.addWidget(text_container)
            main_layout.addWidget(self.avatar)
        else:
            # Left side (other person)
            main_layout.addWidget(self.avatar)
            main_layout.addWidget(text_container)
            main_layout.addStretch()

        self.setLayout(main_layout)

#         msg1 = MessageWidget("Alice", "Hey there!", "avatar1.png", is_self=False)
# msg2 = MessageWidget("Me", "Yo 👋", "avatar2.png", is_self=True)