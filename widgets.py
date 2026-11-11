import math
import random
from PySide6.QtWidgets import QPushButton, QLabel, QWidget
from PySide6.QtCore import Property, Signal, Qt, QTimer, QElapsedTimer, QPoint, QPointF, QRectF, QPropertyAnimation, QVariantAnimation, QParallelAnimationGroup, QSequentialAnimationGroup, QEasingCurve
from PySide6.QtGui import QPainter, QPainterPath, QColor, QPen, QFont, QPolygonF, QLinearGradient
from utils import cover_crop

CARD_WIDTH = 200
CARD_HEIGHT = 120
MIN_CARD_SCALE = 0.75
MAX_CARD_SCALE = 1.3
SETTLE_GROW = 0.08
CARD_LIFT = 15
SIDE_DIM = 0.55
CARD_SINK = 30
BAND_WIDTH = 260
BAND_IDLE = 0.35
BAND_APPLIED_WIDTH = 420
CLICK_WIDEN = 0.15
SWEEP_DURATION = 2000
SWEEP_SLOPE = 0.6
SWEEP_BAND = 220
SWEEP_ALPHA = 70
GEAR_TEETH = 8
GEAR_TURN = 30
BADGE_RADIUS = 3
BADGE_FADE = 800


class BandButton(QPushButton):
    resized = Signal()

    def __init__(self, text, done_text):
        super().__init__(text)
        self.done_text = done_text
        self._reveal = 0.0
        self._hover = 0.0
        self._breath = 1.0
        self._flash = 0.0
        self._done = 0.0
        self._widen = 0.0
        self.hovered = False
        self.setFixedSize(BAND_APPLIED_WIDTH + 40, 48)
        self.setMouseTracking(True)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

    def get_reveal(self):
        return self._reveal

    def set_reveal(self, value):
        self._reveal = value
        self.update()

    reveal = Property(float, get_reveal, set_reveal)

    def get_hover(self):
        return self._hover

    def set_hover(self, value):
        self._hover = value
        self.update()

    hover = Property(float, get_hover, set_hover)

    def get_breath(self):
        return self._breath

    def set_breath(self, value):
        self._breath = value
        self.update()

    breath = Property(float, get_breath, set_breath)

    def get_flash(self):
        return self._flash

    def set_flash(self, value):
        self._flash = value
        self.update()

    flash = Property(float, get_flash, set_flash)

    def get_done(self):
        return self._done

    def set_done(self, value):
        self._done = value
        self.update()

    done = Property(float, get_done, set_done)

    def get_widen(self):
        return self._widen

    def set_widen(self, value):
        self._widen = value
        self.update()
        self.resized.emit()

    widen = Property(float, get_widen, set_widen)

    def animate(self, name, end_value, duration, easing):
        previous = getattr(self, name.decode() + "_animation", None)
        if previous:
            previous.stop()
        animation = QPropertyAnimation(self, name)
        animation.setDuration(duration)
        animation.setStartValue(self.property(name.decode()))
        animation.setEndValue(end_value)
        animation.setEasingCurve(easing)
        animation.start()
        setattr(self, name.decode() + "_animation", animation)

    def appear(self):
        self.animate(b"reveal", 1.0, 300, QEasingCurve.OutCubic)

    def disappear(self):
        self.animate(b"reveal", 0.0, 180, QEasingCurve.InCubic)

    def play_flash(self):
        self._flash = 0.0
        self.animate(b"flash", 1.0, 700, QEasingCurve.OutCubic)

    def press_widen(self):
        self.animate(b"widen", CLICK_WIDEN, 150, QEasingCurve.OutCubic)

    def set_applied(self, applied, animated):
        target = 1.0 if applied else 0.0
        if animated:
            self.animate(b"done", target, 500, QEasingCurve.InOutSine)
            self.animate(b"widen", target, 700, QEasingCurve.OutCubic)
            return
        for name in ("done_animation", "widen_animation"):
            previous = getattr(self, name, None)
            if previous:
                previous.stop()
        self.set_done(target)
        self.set_widen(target)

    def is_applied(self):
        return self._done >= 0.5

    def band_width(self):
        return BAND_WIDTH + (BAND_APPLIED_WIDTH - BAND_WIDTH) * self._widen

    def band_area(self):
        width = self.band_width()
        return QRectF((self.width() - width) / 2, (self.height() - 34) / 2, width, 34)

    def hitButton(self, pos):
        return self.band_area().contains(QPointF(pos))

    def set_hovered(self, hovered):
        if hovered == self.hovered:
            return
        self.hovered = hovered
        if hovered:
            self.animate(b"hover", 1.0, 220, QEasingCurve.OutCubic)
            if getattr(self, "breath_animation", None):
                self.breath_animation.stop()
            self.breath_animation = QPropertyAnimation(self, b"breath")
            self.breath_animation.setDuration(2500)
            self.breath_animation.setKeyValueAt(0, 1.0)
            self.breath_animation.setKeyValueAt(0.5, 0.7)
            self.breath_animation.setKeyValueAt(1, 1.0)
            self.breath_animation.setEasingCurve(QEasingCurve.InOutSine)
            self.breath_animation.setLoopCount(-1)
            self.breath_animation.start()
        else:
            self.animate(b"hover", 0.0, 260, QEasingCurve.OutCubic)
            self.animate(b"breath", 1.0, 260, QEasingCurve.OutCubic)

    def mouseMoveEvent(self, event):
        self.set_hovered(self.hitButton(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.set_hovered(False)
        super().leaveEvent(event)

    def draw_band(self, painter, band, level):
        fill = QLinearGradient(band.left(), 0, band.right(), 0)
        fill.setColorAt(0, QColor(255, 255, 255, 0))
        fill.setColorAt(0.5, QColor(255, 255, 255, min(255, int(70 * level))))
        fill.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(band, fill)

        edge = QLinearGradient(band.left(), 0, band.right(), 0)
        edge.setColorAt(0, QColor(255, 255, 255, 0))
        edge.setColorAt(0.5, QColor(255, 255, 255, min(255, int(140 * level))))
        edge.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(band.left(), band.top(), band.width(), 1), edge)
        painter.fillRect(QRectF(band.left(), band.bottom() - 1, band.width(), 1), edge)

    def paintEvent(self, event):
        if self._reveal <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        active = 1 - self._done
        pressed = self.isDown() and active > 0.5
        level = BAND_IDLE + (1 - BAND_IDLE) * self._hover * self._breath * active
        level *= (1 - 0.35 * self._done) * self._reveal
        if pressed:
            level = min(1.0, level * 1.25)

        width = self.band_width() * self._reveal
        height = 30 if pressed else 34
        center_x = self.width() / 2
        center_y = self.height() / 2
        self.draw_band(painter, QRectF(center_x - width / 2, center_y - height / 2, width, height), level)

        if 0 < self._flash < 1:
            spread = width * (1 + 0.55 * self._flash)
            self.draw_band(painter, QRectF(center_x - spread / 2, center_y - height / 2, spread, height), 1.3 * (1 - self._flash) ** 1.5)

        font = QFont(self.font())
        font.setPixelSize(15 if pressed else 16)
        painter.setFont(font)
        text_fade = max(0.0, 1 - self._done * 2)
        done_fade = max(0.0, self._done * 2 - 1)
        if text_fade > 0:
            painter.setPen(QColor(255, 255, 255, int((170 + 85 * self._hover) * self._reveal * text_fade)))
            painter.drawText(self.rect(), Qt.AlignCenter, self.text())
        if done_fade > 0:
            painter.setPen(QColor(255, 255, 255, int(150 * self._reveal * done_fade)))
            painter.drawText(self.rect(), Qt.AlignCenter, self.done_text)
        painter.end()


class ClickableLabel(QLabel):
    clicked = Signal(object)

    def __init__(self, filename, thumbnail):
        super().__init__()
        self.filename = filename
        self.thumbnail = thumbnail
        self._opacity = 1.0
        self._focus = 0.0
        self._settle = 0.0
        self._sink = 0.0
        self._presence = 1.0
        self.setFixedSize(345, 255)

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, value):
        self._opacity = value
        self.update()

    opacity = Property(float, get_opacity, set_opacity)

    def get_settle(self):
        return self._settle

    def set_settle(self, value):
        self._settle = value
        self.update()

    settle = Property(float, get_settle, set_settle)

    def get_sink(self):
        return self._sink

    def set_sink(self, value):
        self._sink = value
        self.update()

    sink = Property(float, get_sink, set_sink)

    def sink_away(self, on_finished):
        self.away_animation = QParallelAnimationGroup(self)
        for name, start, end in ((b"opacity", self._opacity, 0.0), (b"sink", self._sink, CARD_SINK)):
            animation = QPropertyAnimation(self, name)
            animation.setDuration(300)
            animation.setStartValue(start)
            animation.setEndValue(end)
            animation.setEasingCurve(QEasingCurve.InOutSine)
            self.away_animation.addAnimation(animation)
        self.away_animation.finished.connect(on_finished)
        self.away_animation.start()

    def set_focus(self, value):
        if value != self._focus:
            self._focus = value
            self.update()

    def animate_settle(self, end_value, duration):
        self.settle_animation = QPropertyAnimation(self, b"settle")
        self.settle_animation.setDuration(duration)
        self.settle_animation.setStartValue(self._settle)
        self.settle_animation.setEndValue(end_value)
        self.settle_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.settle_animation.start()

    def card_rect(self):
        scale = MIN_CARD_SCALE + (MAX_CARD_SCALE - MIN_CARD_SCALE) * self._focus
        scale *= 1 + SETTLE_GROW * self._settle
        width = CARD_WIDTH * scale
        height = CARD_HEIGHT * scale
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2 - CARD_LIFT * self._focus + self._sink, width, height)

    def get_presence(self):
        return self._presence

    def set_presence(self, value):
        self._presence = value
        self.update()

    presence = Property(float, get_presence, set_presence)

    def animate_presence(self, end_value, duration):
        if hasattr(self, "presence_animation"):
            self.presence_animation.stop()
        self.presence_animation = QPropertyAnimation(self, b"presence")
        self.presence_animation.setDuration(duration)
        self.presence_animation.setStartValue(self._presence)
        self.presence_animation.setEndValue(end_value)
        self.presence_animation.setEasingCurve(QEasingCurve.InOutSine)
        self.presence_animation.start()

    def paintEvent(self, event):
        if self._opacity * self._presence <= 0:
            return
        painter = QPainter(self)
        self.draw_card(painter)
        painter.end()

    def draw_card(self, painter):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setOpacity(self._opacity * self._presence)
        rect = self.card_rect()

        painter.setBrush(Qt.NoBrush)
        if self._settle > 0:
            self.draw_halo(painter, rect, 18, 60)

        painter.drawPixmap(rect, self.thumbnail, cover_crop(self.thumbnail, CARD_WIDTH / CARD_HEIGHT))

        dim = SIDE_DIM * (1 - self._focus)
        if dim > 0:
            painter.fillRect(rect, QColor(0, 0, 0, int(255 * dim)))

        pen = QPen(QColor(255, 255, 255, int(60 + 70 * self._settle)))
        pen.setWidthF(1)
        painter.setPen(pen)
        painter.drawRect(rect)

    def draw_halo(self, painter, rect, spread, peak):
        for i in range(spread, 0, -1):
            fade = (1 - i / (spread + 1)) ** 2
            pen = QPen(QColor(255, 255, 255, int(peak * fade * self._settle)))
            pen.setWidthF(1.5)
            painter.setPen(pen)
            painter.drawRoundedRect(rect.adjusted(-i, -i, i, i), i * 0.9, i * 0.9)

    def mouseReleaseEvent(self, event):
        self.clicked.emit(self)


class BackgroundEffect(QWidget):
    swept = Signal()

    def __init__(self):
        super().__init__()
        self._pixmap = None
        self._photo_opacity = 0.0
        self._sharp = None
        self._front = 0.0
        self._sharp_opacity = 0.0
        self._tint = QColor(0, 0, 0, 180)

    def set_tint(self, color, duration):
        if hasattr(self, 'tint_animation'):
            self.tint_animation.stop()
        if duration <= 0:
            self.update_tint(QColor(color))
            return
        self.tint_animation = QVariantAnimation(self)
        self.tint_animation.setDuration(duration)
        self.tint_animation.setStartValue(self._tint)
        self.tint_animation.setEndValue(QColor(color))
        self.tint_animation.setEasingCurve(QEasingCurve.InOutSine)
        self.tint_animation.valueChanged.connect(self.update_tint)
        self.tint_animation.start()

    def update_tint(self, color):
        self._tint = color
        self.update()

    def set_pixmap(self, pixmap):
        self._pixmap = pixmap
        self.update()

    def get_photo_opacity(self):
        return self._photo_opacity

    def set_photo_opacity(self, value):
        self._photo_opacity = value
        self.update()

    photo_opacity = Property(float, get_photo_opacity, set_photo_opacity)

    def get_front(self):
        return self._front

    def set_front(self, value):
        self._front = value
        self.update()

    front = Property(float, get_front, set_front)

    def get_sharp_opacity(self):
        return self._sharp_opacity

    def set_sharp_opacity(self, value):
        self._sharp_opacity = value
        self.update()

    sharp_opacity = Property(float, get_sharp_opacity, set_sharp_opacity)

    def start_sweep(self, picture):
        self.clear_sweep()
        self._sharp = picture
        self._sharp_opacity = 1.0
        self.sweep_animation = QPropertyAnimation(self, b"front")
        self.sweep_animation.setDuration(SWEEP_DURATION)
        self.sweep_animation.setStartValue(0.0)
        self.sweep_animation.setEndValue(1.0)
        self.sweep_animation.setEasingCurve(QEasingCurve.InOutSine)
        self.sweep_animation.finished.connect(self.swept.emit)
        self.sweep_animation.start()

    def has_sharp(self):
        return self._sharp is not None

    def fade_sharp(self, duration):
        if not self.has_sharp():
            return
        self.sweep_animation.stop()
        self.fade_animation = QPropertyAnimation(self, b"sharp_opacity")
        self.fade_animation.setDuration(duration)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutSine)
        self.fade_animation.setStartValue(self._sharp_opacity)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.finished.connect(self.clear_sweep)
        self.fade_animation.start()

    def clear_sweep(self):
        for name in ('sweep_animation', 'fade_animation'):
            if hasattr(self, name):
                getattr(self, name).stop()
        self._sharp = None
        self._front = 0.0
        self._sharp_opacity = 0.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        painter.fillRect(self.rect(), self._tint)

        if self._pixmap:
            painter.setOpacity(self._photo_opacity)
            painter.drawPixmap(self.rect(), self._pixmap)

        if self._sharp is None or self._sharp_opacity <= 0:
            return
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        width = self.width()
        height = self.height()
        position = -SWEEP_BAND + (width + SWEEP_SLOPE * height + SWEEP_BAND * 2) * self._front

        painter.save()
        passed = QPainterPath()
        passed.addPolygon(QPolygonF([QPointF(0, 0), QPointF(position, 0), QPointF(position - SWEEP_SLOPE * height, height), QPointF(0, height)]))
        painter.setClipPath(passed)
        painter.setOpacity(self._sharp_opacity)
        painter.drawImage(QRectF(self.rect()), self._sharp, cover_crop(self._sharp, width / height))
        painter.restore()

        if 0 < self._front < 1:
            normal = 1 + SWEEP_SLOPE ** 2
            start = (position - SWEEP_BAND) / normal
            end = (position + SWEEP_BAND * 0.25) / normal
            light = QLinearGradient(start, start * SWEEP_SLOPE, end, end * SWEEP_SLOPE)
            light.setColorAt(0, QColor(255, 255, 255, 0))
            light.setColorAt(0.8, QColor(255, 255, 255, SWEEP_ALPHA))
            light.setColorAt(1, QColor(255, 255, 255, 0))
            painter.setOpacity(self._sharp_opacity)
            painter.fillRect(self.rect(), light)


class IconButton(QPushButton):
    def __init__(self):
        super().__init__()
        self._hover = 0.0
        self._badge = 0.0
        self.setFixedSize(40, 40)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

    def get_hover(self):
        return self._hover

    def set_hover(self, value):
        self._hover = value
        self.update()

    hover = Property(float, get_hover, set_hover)

    def get_badge(self):
        return self._badge

    def set_badge(self, value):
        self._badge = value
        self.update()

    badge = Property(float, get_badge, set_badge)

    def show_badge(self):
        self.badge_animation = QPropertyAnimation(self, b"badge")
        self.badge_animation.setDuration(BADGE_FADE)
        self.badge_animation.setStartValue(self._badge)
        self.badge_animation.setEndValue(1.0)
        self.badge_animation.setEasingCurve(QEasingCurve.InOutSine)
        self.badge_animation.start()

    def animate_hover(self, end_value, duration):
        self.hover_animation = QPropertyAnimation(self, b"hover")
        self.hover_animation.setDuration(duration)
        self.hover_animation.setStartValue(self._hover)
        self.hover_animation.setEndValue(end_value)
        self.hover_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.hover_animation.start()

    def enterEvent(self, event):
        self.animate_hover(1.0, 220)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animate_hover(0.0, 260)
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        size = self.width()
        painter.translate(size / 2, size / 2)
        if self.isDown():
            painter.scale(0.9, 0.9)
        painter.translate(-size / 2, -size / 2)

        painter.setPen(Qt.NoPen)
        self.draw_background(painter, size)

        pen = QPen(QColor(255, 255, 255, int(140 + 115 * self._hover)))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.save()
        self.draw_icon(painter, size)
        painter.restore()
        if self._badge > 0:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, int(220 * self._badge)))
            painter.drawEllipse(QPointF(size * 0.74, size * 0.27), BADGE_RADIUS, BADGE_RADIUS)
        painter.end()

    def draw_background(self, painter, size):
        painter.setBrush(QColor(255, 255, 255, int((60 if self.isDown() else 28) * self._hover)))
        painter.drawEllipse(QRectF(1, 1, size - 2, size - 2))

    def draw_icon(self, painter, size):
        pass


class TrashButton(IconButton):
    def draw_icon(self, painter, size):
        s = 18
        x = (size - s) / 2
        y = (size - s) / 2 + 1
        painter.drawPolyline(QPolygonF([
            QPointF(x + s * 0.27, y + s * 0.32),
            QPointF(x + s * 0.33, y + s * 0.92),
            QPointF(x + s * 0.67, y + s * 0.92),
            QPointF(x + s * 0.73, y + s * 0.32),
        ]))
        painter.drawLine(QPointF(x + s * 0.44, y + s * 0.45), QPointF(x + s * 0.44, y + s * 0.78))
        painter.drawLine(QPointF(x + s * 0.56, y + s * 0.45), QPointF(x + s * 0.56, y + s * 0.78))

        painter.translate(x + s * 0.85, y + s * 0.2)
        painter.rotate(22 * self._hover)
        painter.drawLine(QPointF(0, 0), QPointF(-s * 0.7, 0))
        painter.drawLine(QPointF(-s * 0.45, -s * 0.1), QPointF(-s * 0.25, -s * 0.1))


class GearButton(IconButton):
    def draw_icon(self, painter, size):
        painter.translate(size / 2, size / 2)
        painter.rotate(GEAR_TURN * self._hover)
        points = []
        for i in range(GEAR_TEETH):
            angle = 360 / GEAR_TEETH * i
            for offset, radius in ((-15, 6.0), (-8, 8.2), (8, 8.2), (15, 6.0)):
                rad = math.radians(angle + offset)
                points.append(QPointF(math.cos(rad) * radius, math.sin(rad) * radius))
        points.append(points[0])
        painter.drawPolyline(QPolygonF(points))
        painter.drawEllipse(QPointF(0, 0), 2.6, 2.6)


class CloseButton(IconButton):
    def draw_icon(self, painter, size):
        half = 5.5
        c = size / 2
        painter.drawLine(QPointF(c - half, c - half), QPointF(c + half, c + half))
        painter.drawLine(QPointF(c - half, c + half), QPointF(c + half, c - half))


class Particle:
    def __init__(self, x, y, vx, vy, life, size, peak):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.age = 0.0
        self.life = life
        self.size = size
        self.peak = peak
        self.wobble = random.uniform(0, 2 * math.pi)
        self.rotation = random.uniform(0, 2 * math.pi)
        self.spin = random.uniform(-1.2, 1.2)
        corners = random.randint(5, 7)
        self.shape = [
            (2 * math.pi * i / corners + random.uniform(-0.3, 0.3), random.uniform(0.55, 1.25))
            for i in range(corners)
        ]

    def polygon(self, x, y):
        return QPolygonF([
            QPointF(x + math.cos(angle + self.rotation) * radius * self.size,
                    y + math.sin(angle + self.rotation) * radius * self.size)
            for angle, radius in self.shape
        ])


class EmptyStateOverlay(QWidget):
    def __init__(self, anchor, text):
        super().__init__()
        self.anchor = anchor
        self.text = text
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._reveal = 0.0
        self._phase = 0.0
        self.active = False
        self.particles = []
        self.spawn_budget = 0.0
        self.clock = QElapsedTimer()

        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self.advance)

        self.breath_animation = QPropertyAnimation(self, b"phase")
        self.breath_animation.setDuration(3000)
        self.breath_animation.setStartValue(0.0)
        self.breath_animation.setEndValue(1.0)
        self.breath_animation.setLoopCount(-1)

    def get_reveal(self):
        return self._reveal

    def set_reveal(self, value):
        self._reveal = value
        self.update()

    reveal = Property(float, get_reveal, set_reveal)

    def get_phase(self):
        return self._phase

    def set_phase(self, value):
        self._phase = value

    phase = Property(float, get_phase, set_phase)

    def breath(self):
        return 0.5 - 0.5 * math.cos(2 * math.pi * self._phase)

    def appear(self):
        if self.active:
            return
        self.active = True
        self.clock.start()
        self.frame_timer.start(16)
        self.breath_animation.start()

        fade_in = QPropertyAnimation(self, b"reveal")
        fade_in.setDuration(1600)
        fade_in.setStartValue(self._reveal)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.InOutSine)
        self.reveal_animation = QSequentialAnimationGroup()
        self.reveal_animation.addPause(700)
        self.reveal_animation.addAnimation(fade_in)
        self.reveal_animation.start()

    def disappear(self):
        if not self.active:
            return
        self.active = False
        self.reveal_animation.stop()
        self.reveal_animation = QPropertyAnimation(self, b"reveal")
        self.reveal_animation.setDuration(350)
        self.reveal_animation.setStartValue(self._reveal)
        self.reveal_animation.setEndValue(0.0)
        self.reveal_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.reveal_animation.finished.connect(self.stop_frames)
        self.reveal_animation.start()

    def stop_frames(self):
        if self.active:
            return
        self.frame_timer.stop()
        self.breath_animation.stop()
        self.particles.clear()
        self.update()

    def anchor_rect(self):
        top_left = self.anchor.mapTo(self.window(), QPoint(0, 0)) - self.mapTo(self.window(), QPoint(0, 0))
        return QRectF(top_left.x(), top_left.y(), self.anchor.width(), self.anchor.height())

    def create_particle(self):
        rect = self.anchor_rect()
        center = rect.center()
        angle = random.uniform(0, 2 * math.pi)
        x = center.x() + math.cos(angle) * (rect.width() / 2 + 6)
        y = center.y() + math.sin(angle) * (rect.height() / 2 + 6)
        direction = angle + random.uniform(-0.35, 0.35)
        speed = random.uniform(10, 32)
        return Particle(
            x, y,
            math.cos(direction) * speed, math.sin(direction) * speed,
            random.uniform(3.0, 5.5), random.uniform(1.4, 3.4), random.uniform(0.35, 0.85),
        )

    def advance(self):
        dt = self.clock.restart() / 1000
        if self.active:
            self.spawn_budget += dt * 9
            while self.spawn_budget >= 1:
                self.spawn_budget -= 1
                self.particles.append(self.create_particle())
        for particle in self.particles:
            particle.age += dt
            particle.rotation += particle.spin * dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
        self.particles = [particle for particle in self.particles if particle.age < particle.life]
        self.update(self.anchor_rect().adjusted(-260, -260, 260, 260).toAlignedRect())

    def paintEvent(self, event):
        if self._reveal <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        breath = self.breath()

        painter.setPen(Qt.NoPen)
        for particle in self.particles:
            progress = particle.age / particle.life
            alpha = int(255 * particle.peak * math.sin(math.pi * progress) * self._reveal)
            if alpha <= 0:
                continue
            painter.setBrush(QColor(255, 255, 255, alpha))
            x = particle.x + math.sin(particle.age * 1.4 + particle.wobble) * 3
            painter.drawPolygon(particle.polygon(x, particle.y))

        rect = self.anchor_rect()
        glow = self._reveal * (0.35 + 0.65 * breath)
        painter.setBrush(Qt.NoBrush)
        rings = 9
        for i in range(1, rings):
            alpha = int(60 * glow * (1 - i / rings))
            if alpha <= 0:
                continue
            pen = QPen(QColor(255, 255, 255, alpha))
            pen.setWidthF(2)
            painter.setPen(pen)
            grow = i * 1.6
            painter.drawRoundedRect(rect.adjusted(-grow, -grow, grow, grow), 6 + grow, 6 + grow)

        font = QFont(self.font())
        font.setPixelSize(20)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, int(255 * self._reveal * (0.6 + 0.4 * breath))))
        text_rect = QRectF(rect.center().x() - 200, rect.bottom() + 26, 400, 36)
        painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignTop, self.text)
        painter.end()


def quiet_button(button):
    button.setFocusPolicy(Qt.NoFocus)
    button.setAutoDefault(False)


class ShrinkButton(QPushButton):
    def __init__(self, text, normal_style, pressed_style):
        super().__init__(text)
        self.normal_style = normal_style
        self.pressed_style = pressed_style
        self.setStyleSheet(normal_style)

    def set_normal_style(self, style):
        self.normal_style = style
        if not self.isDown():
            self.setStyleSheet(style)

    def mousePressEvent(self, event):
        self.setStyleSheet(self.pressed_style)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setStyleSheet(self.normal_style)
        super().mouseReleaseEvent(event)