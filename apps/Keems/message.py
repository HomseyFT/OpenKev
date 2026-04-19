from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt


BUBBLE_MAX_WIDTH = 480  # px — keeps long lines readable regardless of window size
AVATAR_SIZE = 40


class MessageWidget(QWidget):
    def __init__(self, username, message, avatar_path=None, is_self=False, parent=None, error=False):
        super().__init__(parent)
        self.is_self = is_self

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5)

        # --- Avatar ---
        self.avatar = None
        if avatar_path:
            self.avatar = QLabel()
            self.avatar.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
            pixmap = QPixmap(avatar_path).scaled(
                AVATAR_SIZE,
                AVATAR_SIZE,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
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
        text_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text_container.setMaximumWidth(BUBBLE_MAX_WIDTH)
        text_layout = QVBoxLayout(text_container)
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
        self.message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if not error:
            if is_self:
                bubble_color = "#DCF8C6"  # light green
            else:
                bubble_color = "#F1F0F0"  # light gray
        else:
            bubble_color = "#FF0000"

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

        # --- Alignment Logic + Error Display---
        if not error:
            if is_self:
                # Right side (you)
                main_layout.addStretch()
                main_layout.addWidget(text_container)
                if self.avatar is not None:
                    main_layout.addWidget(self.avatar)
            else:
                # Left side (other person)
                if self.avatar is not None:
                    main_layout.addWidget(self.avatar)
                main_layout.addWidget(text_container)
                main_layout.addStretch()
        else:
            main_layout.addWidget(text_container)



        self.setLayout(main_layout)


#         msg1 = MessageWidget("Alice", "Hey there!", "avatar1.png", is_self=False)
# msg2 = MessageWidget("Me", "Yo 👋", "avatar2.png", is_self=True)