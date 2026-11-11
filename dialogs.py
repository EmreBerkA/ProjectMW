import math
import random
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Property, Qt, QRectF, QVariantAnimation, QPropertyAnimation, QParallelAnimationGroup, QSequentialAnimationGroup, QEasingCurve, QPointF, QPoint, QTimer, QElapsedTimer
from PySide6.QtGui import QPainter, QPen, QColor, QRadialGradient
from widgets import ShrinkButton, CloseButton, quiet_button
from styles import TITLE_STYLE

TRASH_MARGIN = 18

DIALOG_BUTTON_NORMAL = """
    QPushButton { color: white; background: transparent; border: 1px solid white; border-radius: 16px; padding: 8px 24px; }
"""

DIALOG_BUTTON_SELECTED = """
    QPushButton { color: white; background-color: rgba(255, 255, 255, 30); border: 1px solid white; border-radius: 16px; padding: 8px 24px; }
"""

DIALOG_BUTTON_PRESSED = """
    QPushButton { color: white; background-color: rgba(255, 255, 255, 40); border: 2px solid white; border-radius: 16px; padding: 5px 21px; margin: 3px; }
"""

CLOUDS = [
    (6, -2, 12, 135, 0), (13, -2, 11, 120, 0), (20, -2, 11, 100, 0), (27, -2, 10, 80, 0), (33, -2, 9, 60, 0),
    (8, -10, 9, 85, 1), (16, -9, 8, 70, 1), (24, -8, 7, 55, 1),
    (9, 7, 8, 70, 0), (18, 7, 8, 60, 0), (27, 7, 7, 45, 0),
]


class Wisp:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-10, -7)
        self.vy = random.uniform(-6, -3)
        self.age = 0.0
        self.life = random.uniform(7.5, 9.0)
        self.size = random.uniform(4, 6)
        self.phase = random.uniform(0, math.tau)
        self.outside = False
        self.on_floor = False
        self.floor_age = 0.0

    def step(self, dt, rim_x, floor_y):
        self.age += dt
        if not self.outside and self.x < rim_x - 2:
            self.outside = True
        if self.on_floor:
            self.floor_age += dt
            self.vx *= math.exp(-0.6 * dt)
        elif self.outside:
            self.vx *= math.exp(-1.5 * dt)
            self.vy = min(self.vy + 14 * dt, 16)
        else:
            self.vy = min(self.vy, -3)
        self.x += self.vx * dt + math.sin(self.phase + self.age * 1.3) * 3 * dt
        self.y += self.vy * dt
        if self.outside and not self.on_floor and self.y >= floor_y:
            self.y = floor_y
            self.vy = 0
            self.on_floor = True
            self.vx = random.uniform(-17, -10) if random.random() < 0.75 else random.uniform(8, 14)

    def state(self):
        progress = self.age / self.life
        radius = self.size + 1.6 * self.age + 3 * self.floor_age
        alpha = 65 * min(1.0, self.age / 0.15) * (1 - progress) ** 1.5
        return self.x, self.y - radius * 0.35 if self.on_floor else self.y, radius, alpha


class TrashIcon(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(120, 120)
        self._lid_open = 0.0
        self._steam = 0.0
        self.wisps = []
        self.spawn_credit = 0.0
        self.time = 0.0
        self.cloud_starts = [0.0] * len(CLOUDS)
        self.clock = QElapsedTimer()
        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(16)
        self.frame_timer.timeout.connect(self.advance)

    def get_lid_open(self):
        return self._lid_open

    def set_lid_open(self, value):
        self._lid_open = value
        self.update()

    lid_open = Property(float, get_lid_open, set_lid_open)

    def get_steam(self):
        return self._steam

    def set_steam(self, value):
        if self._steam <= 0 < value:
            self.plan_clouds()
        self._steam = value
        if value > 0 and not self.frame_timer.isActive():
            self.spawn_credit = 0.0
            self.clock.start()
            self.frame_timer.start()
        self.update()

    steam = Property(float, get_steam, set_steam)

    def plan_clouds(self):
        mouth_slots = random.sample(range(8), 8)
        upper_slots = random.sample(range(8, 11), 3)
        for i, cloud in enumerate(CLOUDS):
            slots = mouth_slots if cloud[4] == 0 else upper_slots
            self.cloud_starts[i] = slots.pop() * 0.05

    def mouth(self):
        w = self.width() - TRASH_MARGIN * 2
        h = self.height() - TRASH_MARGIN * 2
        return TRASH_MARGIN + w * 0.28, TRASH_MARGIN + h * 0.3, TRASH_MARGIN + h * 0.85

    def advance(self):
        dt = min(self.clock.restart() / 1000, 0.05)
        self.time += dt
        rim_x, mouth_y, floor_y = self.mouth()
        self.spawn_credit += dt * 6 * max(0.0, (self._steam - 0.75) / 0.25)
        while self.spawn_credit >= 1:
            self.spawn_credit -= 1
            self.wisps.append(Wisp(random.uniform(rim_x + 1, rim_x + 6), mouth_y + 1 - random.uniform(0, 8)))
        for wisp in self.wisps:
            wisp.step(dt, rim_x, floor_y)
        self.wisps = [wisp for wisp in self.wisps if wisp.age < wisp.life]
        if self._steam <= 0 and not self.wisps:
            self.frame_timer.stop()
        self.update()

    def draw_steam(self, painter):
        rim_x, mouth_y, floor_y = self.mouth()
        painter.setPen(Qt.NoPen)

        if self._steam > 0:
            for k, (offset_x, offset_y, size, brightness, row) in enumerate(CLOUDS):
                local = min(1.0, max(0.0, (self._steam - self.cloud_starts[k]) / 0.45))
                if local <= 0:
                    continue
                formed = local * local * (3 - 2 * local)
                radius = size * (0.5 + 0.5 * formed)
                center_x = rim_x + offset_x + math.sin(self.time * 0.7 + k * 1.9) * 2
                center_y = mouth_y + offset_y + math.sin(self.time * 1.0 + k * 1.3) * 1.2
                gradient = QRadialGradient(center_x, center_y, radius)
                gradient.setColorAt(0.0, QColor(255, 255, 255, int(brightness * formed)))
                gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
                painter.setBrush(gradient)
                painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

        for wisp in self.wisps:
            x, y, radius, alpha = wisp.state()
            if alpha < 1:
                continue
            gradient = QRadialGradient(x, y, radius)
            gradient.setColorAt(0.0, QColor(255, 255, 255, int(alpha)))
            gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(gradient)
            painter.drawEllipse(QPointF(x, y), radius, radius)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.draw_steam(painter)

        pen = QPen(QColor(255, 255, 255, 230))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        w = self.width() - TRASH_MARGIN * 2
        h = self.height() - TRASH_MARGIN * 2
        painter.translate(TRASH_MARGIN, TRASH_MARGIN)

        painter.drawLine(int(w * 0.28), int(h * 0.3), int(w * 0.32), int(h * 0.85))
        painter.drawLine(int(w * 0.72), int(h * 0.3), int(w * 0.68), int(h * 0.85))
        painter.drawLine(int(w * 0.32), int(h * 0.85), int(w * 0.68), int(h * 0.85))
        painter.drawLine(int(w * 0.42), int(h * 0.4), int(w * 0.42), int(h * 0.75))
        painter.drawLine(int(w * 0.58), int(h * 0.4), int(w * 0.58), int(h * 0.75))

        pivot_x = w * 0.8
        pivot_y = h * 0.3
        painter.translate(pivot_x, pivot_y)
        painter.rotate(self._lid_open * 35)

        lid_width = w * 0.6
        painter.drawLine(0, 0, int(-lid_width), 0)
        painter.drawLine(int(-lid_width * 0.33), int(-h * 0.08), int(-lid_width * 0.67), int(-h * 0.08))
        painter.end()


class DialogCloseButton(CloseButton):
    def draw_background(self, painter, size):
        painter.setBrush(QColor(255, 255, 255, int(30 * self._hover)))
        painter.drawRoundedRect(QRectF(0, 0, size, size), 6, 6)


class DialogBackButton(DialogCloseButton):
    def draw_icon(self, painter, size):
        c = size / 2
        half = 5.5
        painter.drawPolyline([QPointF(c + half * 0.45, c - half), QPointF(c - half * 0.55, c), QPointF(c + half * 0.45, c + half)])


def page_header(title_text, on_back):
    header = QHBoxLayout()
    header.setSpacing(6)
    back_button = DialogBackButton()
    back_button.setFixedSize(26, 26)
    quiet_button(back_button)
    back_button.clicked.connect(on_back)
    header.addWidget(back_button)
    title = QLabel(title_text)
    title.setStyleSheet(TITLE_STYLE)
    header.addWidget(title)
    header.addStretch()
    return header


class DialogPanel(QWidget):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self._color = QColor(color)

    def set_color(self, color, duration):
        if hasattr(self, 'color_animation'):
            self.color_animation.stop()
        self.color_animation = QVariantAnimation(self)
        self.color_animation.setDuration(duration)
        self.color_animation.setStartValue(self._color)
        self.color_animation.setEndValue(QColor(color))
        self.color_animation.setEasingCurve(QEasingCurve.InOutSine)
        self.color_animation.valueChanged.connect(self.update_color)
        self.color_animation.start()

    def update_color(self, color):
        self._color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color)
        painter.drawRoundedRect(QRectF(self.rect()), 8, 8)
        painter.end()


class FloatingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.0)

    def showEvent(self, event):
        super().showEvent(event)
        end = self.pos()
        start = end + QPoint(0, 14)
        self.move(start)
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(260)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        slide = QPropertyAnimation(self, b"pos")
        slide.setDuration(320)
        slide.setStartValue(start)
        slide.setEndValue(end)
        slide.setEasingCurve(QEasingCurve.OutCubic)
        self.intro_animation = QParallelAnimationGroup(self)
        self.intro_animation.addAnimation(fade)
        self.intro_animation.addAnimation(slide)
        self.intro_animation.start()

    def add_close_button(self, panel):
        close_button = DialogCloseButton()
        close_button.setParent(panel)
        close_button.setFixedSize(26, 26)
        close_button.move(panel.width() - 34, 8)
        close_button.clicked.connect(self.reject)
        quiet_button(close_button)
        close_button.raise_()


class DeleteConfirmDialog(FloatingDialog):
    def __init__(self, panel_color, parent=None):
        super().__init__(parent)
        self.result_value = False

        container = DialogPanel(panel_color, self)
        container.setFixedSize(360, 160)

        outer = QVBoxLayout(self)
        outer.addWidget(container)

        outer_h_layout = QHBoxLayout(container)
        outer_h_layout.setContentsMargins(12, 20, 24, 20)

        self.trash_icon = TrashIcon()
        outer_h_layout.addWidget(self.trash_icon)

        layout = QVBoxLayout()
        outer_h_layout.addLayout(layout)
        layout.setContentsMargins(0, 12, 0, 0)

        message = QLabel("Are you sure you want to delete this wallpaper?")
        message.setStyleSheet("color: white; font-size: 16px; border: none; background: transparent;")
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignLeft)
        layout.addWidget(message)

        button_row = QHBoxLayout()
        yes_button = ShrinkButton("Yes", DIALOG_BUTTON_NORMAL, DIALOG_BUTTON_PRESSED)
        yes_button.clicked.connect(self.accept_delete)

        no_button = ShrinkButton("No", DIALOG_BUTTON_NORMAL, DIALOG_BUTTON_PRESSED)
        no_button.clicked.connect(self.reject)

        self.choice_buttons = [yes_button, no_button]
        for button in self.choice_buttons:
            quiet_button(button)
            button.installEventFilter(self)
            button_row.addWidget(button)
        layout.addLayout(button_row)

        self.selected = None
        self.add_close_button(container)

    def select(self, index):
        if index == self.selected:
            return
        self.selected = index
        for i, button in enumerate(self.choice_buttons):
            button.set_normal_style(DIALOG_BUTTON_SELECTED if i == index else DIALOG_BUTTON_NORMAL)
        if index == 0:
            self.open_lid()
        else:
            self.close_lid()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.select(0)
        elif event.key() == Qt.Key_Right:
            self.select(1)
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.selected is not None:
                self.choice_buttons[self.selected].click()
        else:
            super().keyPressEvent(event)

    def accept_delete(self):
        self.result_value = True
        self.accept()

    def eventFilter(self, source, event):
        if hasattr(self, 'choice_buttons') and source in self.choice_buttons:
            index = self.choice_buttons.index(source)
            if event.type() == event.Type.Enter:
                self.select(index)
            elif event.type() == event.Type.Leave and self.selected == index:
                self.select(None)
        return super().eventFilter(source, event)

    def open_lid(self):
        self.animate_lid(1.0, 360, QEasingCurve.InOutCubic)
        self.animate_steam(1.0, 1300, 120)

    def close_lid(self):
        self.animate_lid(0.0, 220, QEasingCurve.InOutCubic)
        self.animate_steam(0.0, 300, 0)

    def animate_lid(self, end_value, duration, easing):
        self.lid_anim = QPropertyAnimation(self.trash_icon, b"lid_open")
        self.lid_anim.setDuration(duration)
        self.lid_anim.setStartValue(self.trash_icon.lid_open)
        self.lid_anim.setEndValue(end_value)
        self.lid_anim.setEasingCurve(easing)
        self.lid_anim.start()

    def animate_steam(self, end_value, duration, delay):
        steam = QPropertyAnimation(self.trash_icon, b"steam")
        steam.setDuration(duration)
        steam.setStartValue(self.trash_icon.steam)
        steam.setEndValue(end_value)
        steam.setEasingCurve(QEasingCurve.InOutSine)
        if hasattr(self, 'steam_anim'):
            self.steam_anim.stop()
        self.steam_anim = QSequentialAnimationGroup(self)
        self.steam_anim.addPause(delay)
        self.steam_anim.addAnimation(steam)
        self.steam_anim.start()
