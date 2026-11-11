from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, Signal, Property, QPointF, QRectF, QPropertyAnimation
from PySide6.QtGui import QPainter, QColor, QPixmap, QPen, QTransform

TURN_ANGLE = 90
TURN_IN = 1
TURN_OUT = -1
TURN_SLIDE = 45
TIMELINE_DURATION = 850
LEAVE_DURATION = 750
BACKDROP_ALPHA = 180 / 255
LOGO_WIDTH = 200
SOURCE_WIDTH = 622
CIRCLE_CENTER = (310.5, 254.5)
CIRCLE_RADIUS = 245.5
SETTLE_ANGLE = 120
SETTLE_END = 1.1
TAIL_ANGLES = (16, 197)
SPLIT_GAP = 16
RING_GAP = 10
RING_COLOR = QColor(215, 215, 215, 210)
RING_WIDTH = 1.5


def clamp(value):
    return max(0.0, min(1.0, value))


def smooth(value):
    value = clamp(value)
    return value * value * (3 - 2 * value)


def ease_out(value):
    return 1 - (1 - clamp(value)) ** 3


def ease_in(value):
    return clamp(value) ** 3


def turn_transform(center, settle, away):
    transform = QTransform()
    transform.translate(center.x() - TURN_SLIDE * (1 - settle) + TURN_SLIDE * away, center.y())
    transform.rotate(TURN_IN * TURN_ANGLE * (1 - settle) + TURN_OUT * TURN_ANGLE * away, Qt.YAxis)
    scale = 0.9 + 0.1 * settle - 0.1 * away
    transform.scale(scale, scale)
    transform.translate(-center.x(), -center.y())
    return transform


class SplashOverlay(QWidget):
    finished = Signal()

    def __init__(self, logo_path):
        super().__init__()
        ratio = QApplication.primaryScreen().devicePixelRatio()
        self.logo = QPixmap(logo_path).scaledToWidth(round(LOGO_WIDTH * ratio), Qt.SmoothTransformation)
        self.logo.setDevicePixelRatio(ratio)
        self.logo_size = self.logo.deviceIndependentSize()

        self._progress = 0.0
        self._leave = 0.0

    def get_progress(self):
        return self._progress

    def set_progress(self, value):
        self._progress = value
        self.update()

    progress = Property(float, get_progress, set_progress)

    def get_leave(self):
        return self._leave

    def set_leave(self, value):
        self._leave = value
        self.update()

    leave = Property(float, get_leave, set_leave)

    def app_opacity(self):
        return smooth((self._leave - 0.15) / 0.85)

    def start(self):
        self.animation = QPropertyAnimation(self, b"progress")
        self.animation.setDuration(TIMELINE_DURATION)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.finished.connect(self.finished.emit)
        self.animation.start()

    def hand_over(self):
        self.leave_animation = QPropertyAnimation(self, b"leave")
        self.leave_animation.setDuration(LEAVE_DURATION)
        self.leave_animation.setStartValue(0.0)
        self.leave_animation.setEndValue(1.0)
        self.leave_animation.finished.connect(self.hide)
        self.leave_animation.start()

    def draw_ring(self, painter, center, circle_radius):
        radius = circle_radius + RING_GAP
        rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        pen = QPen(RING_COLOR)
        pen.setWidthF(RING_WIDTH)
        pen.setCapStyle(Qt.FlatCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        offset = SETTLE_ANGLE * (1 - ease_out(self._progress / SETTLE_END))
        right_gap_end = TAIL_ANGLES[0] + SPLIT_GAP + offset
        left_gap_start = TAIL_ANGLES[1] - SPLIT_GAP + offset
        left_gap_end = TAIL_ANGLES[1] + SPLIT_GAP + offset
        right_gap_start = TAIL_ANGLES[0] + 360 - SPLIT_GAP + offset
        painter.drawArc(rect, int(right_gap_end * 16), int((left_gap_start - right_gap_end) * 16))
        painter.drawArc(rect, int(left_gap_end * 16), int((right_gap_start - left_gap_end) * 16))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        app = self.app_opacity()
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.fillRect(self.rect(), QColor(0, 0, 0, round(255 * app)))
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        painter.fillRect(self.rect(), QColor(0, 0, 0, round(255 * BACKDROP_ALPHA * (1 - app))))
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        appear = smooth(self._progress / 0.15)
        settle = ease_out(self._progress / 0.6)
        away = ease_in(self._leave / 0.6)
        fade = smooth((self._leave - 0.35) / 0.25)
        width = self.logo_size.width()
        height = self.logo_size.height()
        left = (self.width() - width) / 2
        top = (self.height() - height) / 2
        target = QRectF(left, top, width, height)
        unit = width / SOURCE_WIDTH
        center = QPointF(left + CIRCLE_CENTER[0] * unit, top + CIRCLE_CENTER[1] * unit)

        painter.setOpacity(smooth((self._progress - 0.12) / 0.2) * (1 - smooth(self._leave / 0.45)))
        self.draw_ring(painter, center, CIRCLE_RADIUS * unit)

        painter.setTransform(turn_transform(center, settle, away))
        painter.setOpacity(appear * (1 - fade))
        painter.drawPixmap(target, self.logo, QRectF(self.logo.rect()))
        painter.end()
