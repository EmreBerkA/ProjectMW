import os
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QAbstractButton
from PySide6.QtCore import Property, Signal, Qt, QUrl, QPropertyAnimation, QVariantAnimation, QEasingCurve, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QDesktopServices

from dialogs import FloatingDialog, DialogPanel
from feedback_page import FeedbackPage
from donate_page import DonatePage
from widgets import ShrinkButton, quiet_button
from paths import APP_NAME, APP_VERSION, library_dir
from themes import THEMES, THEME_FADE, dialog_color
from styles import TITLE_STYLE, SMALL_BUTTON_STYLES

SWATCH_SIZE = 22
TOGGLE_DURATION = 180
PAGE_DURATION = 320

ROW_LABEL_STYLE = "color: white; font-size: 15px; background: transparent;"

LINK_STYLE = """
    QPushButton { color: rgba(255, 255, 255, 140); background: transparent; border: none; font-size: 13px; padding: 2px 4px; }
    QPushButton:hover { color: white; }
"""

UPDATE_LINK_STYLE = """
    QPushButton { color: rgba(255, 255, 255, 200); background: transparent; border: none; font-size: 12px; padding: 2px 0px; text-decoration: underline; }
    QPushButton:hover { color: white; }
"""


class ToggleSwitch(QAbstractButton):
    def __init__(self, checked=False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 22)
        self._position = 1.0 if checked else 0.0
        self.toggled.connect(self.animate_knob)

    def get_position(self):
        return self._position

    def set_position(self, value):
        self._position = value
        self.update()

    position = Property(float, get_position, set_position)

    def animate_knob(self, checked):
        if hasattr(self, 'knob_animation'):
            self.knob_animation.stop()
        self.knob_animation = QPropertyAnimation(self, b"position")
        self.knob_animation.setDuration(TOGGLE_DURATION)
        self.knob_animation.setStartValue(self._position)
        self.knob_animation.setEndValue(1.0 if checked else 0.0)
        self.knob_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.knob_animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        t = self._position
        track = QRectF(1, 1, self.width() - 2, self.height() - 2)
        radius = track.height() / 2
        painter.setPen(QPen(QColor(255, 255, 255, int(120 + 80 * t)), 1.2))
        painter.setBrush(QColor(255, 255, 255, int(200 * t)))
        painter.drawRoundedRect(track, radius, radius)

        knob = radius - 4
        x = track.left() + radius + (track.width() - 2 * radius) * t
        painter.setPen(Qt.NoPen)
        dark = QColor(20, 20, 20)
        light = QColor(255, 255, 255, 200)
        painter.setBrush(QColor(
            round(light.red() + (dark.red() - light.red()) * t),
            round(light.green() + (dark.green() - light.green()) * t),
            round(light.blue() + (dark.blue() - light.blue()) * t),
        ))
        painter.drawEllipse(QPointF(x, track.center().y()), knob, knob)
        painter.end()


class ColorSwatch(QAbstractButton):
    def __init__(self, color):
        super().__init__()
        self.color = QColor(color)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(SWATCH_SIZE + 12, SWATCH_SIZE + 12)
        self.hovered = False

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = SWATCH_SIZE / 2
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.setBrush(self.color)
        painter.drawEllipse(center, radius, radius)
        if self.isChecked() or self.hovered:
            alpha = 230 if self.isChecked() else 90
            painter.setPen(QPen(QColor(255, 255, 255, alpha), 1.4))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, radius + 4, radius + 4)
        painter.end()


class SettingsDialog(FloatingDialog):
    theme_selected = Signal(int)
    setting_changed = Signal(str, object)

    def __init__(self, theme_index, settings, update=None, parent=None):
        super().__init__(parent)

        container = DialogPanel(dialog_color(THEMES[theme_index]), self)
        container.setFixedSize(420, 320)
        self.panel = container

        outer = QVBoxLayout(self)
        outer.addWidget(container)

        self.settings_page = QWidget(container)
        self.settings_page.setGeometry(container.rect())
        self.feedback_page = FeedbackPage(container)
        self.feedback_page.setGeometry(container.rect())
        self.feedback_page.move(container.width(), 0)
        self.feedback_page.back_requested.connect(self.show_settings)
        self.feedback_page.sent.connect(self.show_settings)
        self.donate_page = DonatePage(container)
        self.donate_page.setGeometry(container.rect())
        self.donate_page.move(container.width(), 0)
        self.donate_page.back_requested.connect(self.show_settings)
        self.subpage = self.feedback_page
        self.page_offset = 0.0

        layout = QVBoxLayout(self.settings_page)
        layout.setContentsMargins(28, 20, 28, 16)
        layout.setSpacing(0)

        title = QLabel("Settings")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)
        layout.addSpacing(18)

        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(0)
        self.swatches = []
        for index, theme in enumerate(THEMES):
            swatch = ColorSwatch(theme["swatch"])
            swatch.clicked.connect(lambda checked, i=index: self.select_theme(i))
            swatch_row.addWidget(swatch)
            self.swatches.append(swatch)
        self.swatches[theme_index].setChecked(True)
        layout.addLayout(self.make_row("Theme", swatch_row))

        self.intro_toggle = ToggleSwitch(settings["play_intro"])
        self.intro_toggle.toggled.connect(lambda checked: self.setting_changed.emit("play_intro", checked))
        layout.addLayout(self.make_row("Play intro animation", self.intro_toggle))

        self.close_toggle = ToggleSwitch(settings["close_after_apply"])
        self.close_toggle.toggled.connect(lambda checked: self.setting_changed.emit("close_after_apply", checked))
        layout.addLayout(self.make_row("Close after applying", self.close_toggle))

        self.folder_button = ShrinkButton("Open", *SMALL_BUTTON_STYLES)
        self.folder_button.clicked.connect(self.open_folder)
        layout.addLayout(self.make_row("Wallpapers folder", self.folder_button))

        layout.addStretch()

        footer = QHBoxLayout()
        if update:
            update_version, update_url = update
            version = QPushButton(f"Update available: {update_version}")
            version.setStyleSheet(UPDATE_LINK_STYLE)
            version.setCursor(Qt.PointingHandCursor)
            version.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(update_url)))
            quiet_button(version)
        else:
            version = QLabel(f"{APP_NAME} {APP_VERSION}")
            version.setStyleSheet("color: rgba(255, 255, 255, 90); font-size: 12px; background: transparent;")
        footer.addWidget(version)
        footer.addStretch()
        self.feedback_button = QPushButton("Feedback")
        self.donate_button = QPushButton("Donate")
        for button in (self.feedback_button, self.donate_button):
            button.setStyleSheet(LINK_STYLE)
            button.setCursor(Qt.PointingHandCursor)
            quiet_button(button)
            footer.addWidget(button)
        layout.addLayout(footer)
        self.feedback_button.clicked.connect(self.show_feedback)
        self.donate_button.clicked.connect(self.show_donate)

        for widget in self.swatches + [self.intro_toggle, self.close_toggle]:
            widget.setFocusPolicy(Qt.NoFocus)
        quiet_button(self.folder_button)
        self.add_close_button(container)

    def show_feedback(self):
        self.show_subpage(self.feedback_page)
        self.feedback_page.focus_message()

    def show_donate(self):
        self.show_subpage(self.donate_page)
        self.setFocus()

    def show_subpage(self, page):
        if self.subpage is not page:
            self.subpage.move(self.panel.width(), 0)
            self.subpage = page
        self.slide_pages(1.0)

    def show_settings(self):
        self.slide_pages(0.0)
        self.setFocus()

    def slide_pages(self, end_value):
        if hasattr(self, 'page_animation'):
            self.page_animation.stop()
        self.page_animation = QVariantAnimation(self)
        self.page_animation.setDuration(PAGE_DURATION)
        self.page_animation.setStartValue(self.page_offset)
        self.page_animation.setEndValue(end_value)
        self.page_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.page_animation.valueChanged.connect(self.set_page_offset)
        self.page_animation.start()

    def set_page_offset(self, value):
        self.page_offset = value
        width = self.panel.width()
        self.settings_page.move(round(-width * value), 0)
        self.subpage.move(round(width * (1 - value)), 0)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.page_offset > 0.5:
            self.show_settings()
        else:
            super().keyPressEvent(event)

    def open_folder(self):
        try:
            os.startfile(library_dir())
        except OSError:
            pass

    def select_theme(self, index):
        self.panel.set_color(dialog_color(THEMES[index]), THEME_FADE)
        self.theme_selected.emit(index)

    def make_row(self, text, control):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text)
        label.setStyleSheet(ROW_LABEL_STYLE)
        label.setFixedHeight(48)
        row.addWidget(label)
        row.addStretch()
        if isinstance(control, QHBoxLayout):
            row.addLayout(control)
        else:
            row.addWidget(control)
        return row
