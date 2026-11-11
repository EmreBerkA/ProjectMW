import math
import platform
import re
from PySide6.QtWidgets import QWidget, QLabel, QPlainTextEdit, QLineEdit, QVBoxLayout, QHBoxLayout, QSizePolicy
from PySide6.QtCore import Signal, QUrl, QUrlQuery, QTimer, QVariantAnimation, QSize
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from dialogs import page_header
from widgets import ShrinkButton, quiet_button
from paths import APP_NAME, APP_VERSION
from styles import NOTE_STYLE, SMALL_BUTTON_STYLES

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScmK-YcbDJR2HM5-BHCN4KOuNKW-7UBNZxl52JIhWCLV1xR_g/formResponse"
ENTRY_MESSAGE = "entry.1773617707"
ENTRY_EMAIL = "entry.1792349430"
ENTRY_INFO = "entry.1523583625"
SEND_TIMEOUT = 10000
THANKS_HOLD = 1500
SHAKE_DISTANCE = 5
SHAKE_COUNT = 3
SHAKE_DURATION = 380
SHAKE_ROOM = 8

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

DEFAULT_NOTE = "App and Windows versions are included."

FIELD_STYLE = """
    QPlainTextEdit, QLineEdit { color: white; background-color: rgba(255, 255, 255, 14); border: 1px solid rgba(255, 255, 255, 60); border-radius: 6px; padding: 6px 8px; font-size: 13px; selection-background-color: rgba(255, 255, 255, 70); }
    QPlainTextEdit:focus, QLineEdit:focus { border: 1px solid rgba(255, 255, 255, 150); }
    QScrollBar:vertical { background: transparent; width: 6px; margin: 4px 2px 4px 0; }
    QScrollBar::handle:vertical { background: rgba(255, 255, 255, 70); border-radius: 2px; min-height: 20px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { height: 0; background: none; }
"""

WARNING_STYLE = "color: rgba(255, 175, 165, 230); font-size: 12px; background: transparent;"
INVALID_FIELD_STYLE = "QLineEdit, QLineEdit:focus { border: 1px solid rgba(255, 175, 165, 200); }"


def system_info():
    version = platform.version()
    build = version.split(".")[-1]
    name = "Windows 11" if build.isdigit() and int(build) >= 22000 else f"Windows {platform.release()}"
    return f"{APP_NAME} {APP_VERSION} | {name} ({version})"


class ShakeHolder(QWidget):
    def __init__(self, field):
        super().__init__()
        self.field = field
        field.setParent(self)
        self.offset = 0
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self):
        hint = self.field.sizeHint()
        return QSize(hint.width() + 2 * SHAKE_ROOM, hint.height())

    def minimumSizeHint(self):
        return self.sizeHint()

    def resizeEvent(self, event):
        self.place_field()
        super().resizeEvent(event)

    def place_field(self):
        self.field.setGeometry(SHAKE_ROOM + self.offset, 0, self.width() - 2 * SHAKE_ROOM, self.height())

    def shake(self):
        if hasattr(self, 'shake_animation'):
            self.shake_animation.stop()
        self.shake_animation = QVariantAnimation(self)
        self.shake_animation.setDuration(SHAKE_DURATION)
        self.shake_animation.setStartValue(0.0)
        self.shake_animation.setEndValue(1.0)
        self.shake_animation.valueChanged.connect(self.set_shake)
        self.shake_animation.start()

    def set_shake(self, t):
        self.offset = round(SHAKE_DISTANCE * math.sin(t * math.pi * 2 * SHAKE_COUNT) * (1 - t))
        self.place_field()


class FeedbackPage(QWidget):
    back_requested = Signal()
    sent = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(FIELD_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(0)

        layout.addLayout(page_header("Feedback", self.back_requested.emit))
        layout.addSpacing(14)

        self.message = QPlainTextEdit()
        self.message.setPlaceholderText("Ideas, problems, anything you'd like to tell us...")
        self.message.setFixedHeight(140)
        self.message.setTabChangesFocus(True)
        message_row = QHBoxLayout()
        message_row.setContentsMargins(SHAKE_ROOM, 0, SHAKE_ROOM, 0)
        message_row.addWidget(self.message)
        layout.addLayout(message_row)
        layout.addSpacing(10)
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email (optional, if you'd like a reply)")
        self.email_holder = ShakeHolder(self.email)
        layout.addWidget(self.email_holder)
        layout.addStretch()

        footer = QHBoxLayout()
        footer.setContentsMargins(SHAKE_ROOM, 0, SHAKE_ROOM, 0)
        self.note = QLabel(DEFAULT_NOTE)
        self.note.setStyleSheet(NOTE_STYLE)
        footer.addWidget(self.note)
        footer.addStretch()
        self.send_button = ShrinkButton("Send", *SMALL_BUTTON_STYLES)
        quiet_button(self.send_button)
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self.send)
        footer.addWidget(self.send_button)
        layout.addLayout(footer)

        self.message.textChanged.connect(self.update_send_button)
        self.email.textChanged.connect(self.clear_warning)

        self.network = QNetworkAccessManager(self)
        self.reply = None

    def update_send_button(self):
        self.send_button.setEnabled(self.reply is None and bool(self.message.toPlainText().strip()))

    def show_note(self, text, warning=False):
        self.note.setText(text)
        self.note.setStyleSheet(WARNING_STYLE if warning else NOTE_STYLE)

    def clear_warning(self):
        self.email.setStyleSheet("")
        if self.reply is None:
            self.show_note(DEFAULT_NOTE)

    def send(self):
        message = self.message.toPlainText().strip()
        email = self.email.text().strip()
        if not message or self.reply is not None:
            return
        if email and not EMAIL_PATTERN.match(email):
            self.email.setStyleSheet(INVALID_FIELD_STYLE)
            self.show_note("Please enter a valid email, like name@example.com", True)
            self.email.setFocus()
            self.email_holder.shake()
            return
        fields = QUrlQuery()
        fields.addQueryItem(ENTRY_MESSAGE, message)
        fields.addQueryItem(ENTRY_EMAIL, email)
        fields.addQueryItem(ENTRY_INFO, system_info())
        request = QNetworkRequest(QUrl(FORM_URL))
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/x-www-form-urlencoded")
        request.setTransferTimeout(SEND_TIMEOUT)
        self.reply = self.network.post(request, fields.query(QUrl.FullyEncoded).encode())
        self.reply.finished.connect(self.on_reply_finished)
        self.show_note("Sending...")
        self.update_send_button()

    def on_reply_finished(self):
        reply = self.reply
        self.reply = None
        reply.deleteLater()
        if reply.error() == QNetworkReply.NoError:
            self.show_note("Thanks! Your feedback was sent.")
            QTimer.singleShot(THANKS_HOLD, self, self.finish_sent)
        else:
            self.show_note("Couldn't send. Please try again.", True)
            self.update_send_button()

    def finish_sent(self):
        self.message.clear()
        self.email.clear()
        self.show_note(DEFAULT_NOTE)
        self.sent.emit()

    def focus_message(self):
        self.message.setFocus()
