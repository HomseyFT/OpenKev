"""Chat message bubble widget used inside the KevPilot chat window."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)


BUBBLE_MAX_WIDTH = 480  # px — keeps long lines readable regardless of window size
AVATAR_SIZE = 40


class MessageWidget(QWidget):
    """A single chat bubble with avatar, username, and message text.

    The bubble is right-aligned when ``is_self`` is True, left-aligned otherwise.
    If ``avatar_path`` is None the avatar slot is omitted entirely (no empty grey circle).
    """

    def __init__(
        self,
        username: str,
        message: str,
        avatar_path: str | None = None,
        is_self: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.is_self = is_self

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5)

        # --- Avatar (only rendered when a path was provided) ---
        self.avatar: QLabel | None = None
        if avatar_path:
            self.avatar = QLabel()
            self.avatar.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
            pixmap = QPixmap(avatar_path).scaled(
                AVATAR_SIZE,
                AVATAR_SIZE,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.avatar.setPixmap(pixmap)
            self.avatar.setStyleSheet(
                """
                QLabel {
                    border-radius: 20px;
                    background-color: #ccc;
                }
                """
            )

        # --- Text container ---
        text_container = QWidget()
        text_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        text_container.setMaximumWidth(BUBBLE_MAX_WIDTH)

        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.username_label = QLabel(username)
        self.username_label.setStyleSheet(
            """
            QLabel {
                font-weight: bold;
                font-size: 12px;
                color: #555;
            }
            """
        )

        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.message_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        bubble_color = "#DCF8C6" if is_self else "#F1F0F0"
        self.message_label.setStyleSheet(
            f"""
            QLabel {{
                font-size: 14px;
                background-color: {bubble_color};
                border-radius: 12px;
                padding: 8px;
            }}
            """
        )

        text_layout.addWidget(self.username_label)
        text_layout.addWidget(self.message_label)

        # --- Alignment ---
        if is_self:
            main_layout.addStretch()
            main_layout.addWidget(text_container)
            if self.avatar is not None:
                main_layout.addWidget(self.avatar)
        else:
            if self.avatar is not None:
                main_layout.addWidget(self.avatar)
            main_layout.addWidget(text_container)
            main_layout.addStretch()
