import math
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Property, Signal, Qt, QUrl, QPointF, QRectF, QTimer, QElapsedTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QPainterPath, QColor, QPen, QDesktopServices

from dialogs import page_header
from widgets import ShrinkButton, quiet_button
from styles import NOTE_STYLE, outline_button_styles

DONATE_URL = "https://buymeacoffee.com/emreberk"
STEAM_SPEED = 0.7
STEAM_RISE = 4

DONATE_TEXT = "ProjectMW is free and made by one developer.\nIf you enjoy it, you can support it with a coffee."

COFFEE_BUTTON_STYLES = outline_button_styles(16, 6, 24, 14)


class CoffeeIcon(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(64, 56)
        self._hover = 0.0
        self.phase = 0.0
        self.clock = QElapsedTimer()
        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(16)
        self.frame_timer.timeout.connect(self.advance)

    def get_hover(self):
        return self._hover

    def set_hover(self, value):
        self._hover = value
        if value > 0 and not self.frame_timer.isActive():
            self.clock.start()
            self.frame_timer.start()
        self.update()

    hover = Property(float, get_hover, set_hover)

    def animate_hover(self, end_value, duration):
        if hasattr(self, 'hover_animation'):
            self.hover_animation.stop()
        self.hover_animation = QPropertyAnimation(self, b"hover")
        self.hover_animation.setDuration(duration)
        self.hover_animation.setStartValue(self._hover)
        self.hover_animation.setEndValue(end_value)
        self.hover_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.hover_animation.start()

    def advance(self):
        dt = self.clock.restart() / 1000
        self.phase += dt * STEAM_SPEED * math.tau * self._hover
        if self._hover <= 0:
            self.frame_timer.stop()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(255, 255, 255, 200))
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        cup = QPainterPath()
        cup.moveTo(16, 26)
        cup.lineTo(44, 26)
        cup.lineTo(42, 42)
        cup.quadTo(41.5, 47, 36, 47)
        cup.lineTo(24, 47)
        cup.quadTo(18.5, 47, 18, 42)
        cup.closeSubpath()
        painter.drawPath(cup)
        painter.drawArc(QRectF(39, 29, 11, 11), -80 * 16, 170 * 16)
        painter.drawLine(QPointF(12, 51), QPointF(48, 51))

        pen.setColor(QColor(255, 255, 255, int(110 + 90 * self._hover)))
        painter.setPen(pen)
        top = 8 - STEAM_RISE * self._hover
        for index, x in enumerate((25, 33)):
            steam = QPainterPath()
            for step in range(21):
                t = step / 20
                y = 21 + (top - 21) * t
                sway = math.sin(t * math.tau * 0.8 - self.phase - index * 1.6)
                point = QPointF(x - 2.2 * sway * math.sin(t * math.pi + 0.4), y)
                if step == 0:
                    steam.moveTo(point)
                else:
                    steam.lineTo(point)
            painter.drawPath(steam)
        painter.end()


class DonatePage(QWidget):
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 28, 16)
        layout.setSpacing(0)

        layout.addLayout(page_header("Support ProjectMW", self.back_requested.emit))
        layout.addStretch()

        self.icon = CoffeeIcon()
        layout.addWidget(self.icon, 0, Qt.AlignHCenter)
        layout.addSpacing(10)

        text = QLabel(DONATE_TEXT)
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignHCenter)
        text.setStyleSheet("color: rgba(255, 255, 255, 200); font-size: 14px; line-height: 150%; background: transparent;")
        text.setContentsMargins(8, 0, 0, 0)
        layout.addWidget(text)
        layout.addSpacing(20)

        self.coffee_button = ShrinkButton("Buy me a coffee", *COFFEE_BUTTON_STYLES)
        self.coffee_button.setCursor(Qt.PointingHandCursor)
        quiet_button(self.coffee_button)
        self.coffee_button.clicked.connect(self.open_donate_page)
        self.coffee_button.installEventFilter(self)
        layout.addWidget(self.coffee_button, 0, Qt.AlignHCenter)
        layout.addSpacing(8)

        note = QLabel("Opens in your browser.")
        note.setStyleSheet(NOTE_STYLE)
        layout.addWidget(note, 0, Qt.AlignHCenter)
        layout.addStretch()

    def eventFilter(self, source, event):
        if hasattr(self, 'icon') and source is self.coffee_button:
            if event.type() == event.Type.Enter:
                self.icon.animate_hover(1.0, 220)
            elif event.type() == event.Type.Leave:
                self.icon.animate_hover(0.0, 260)
        return super().eventFilter(source, event)

    def open_donate_page(self):
        QDesktopServices.openUrl(QUrl(DONATE_URL))
