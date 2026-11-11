import sys
import os
import ctypes
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QScrollArea, QFrame, QMessageBox, QFileDialog,
    QHBoxLayout, QVBoxLayout, QStackedLayout, QSpacerItem, QSizePolicy, QGraphicsOpacityEffect,
)
from PySide6.QtGui import QPixmap, QIcon, QMouseEvent, QFontDatabase, QFont, QShortcut, QKeySequence
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QVariantAnimation, QEasingCurve

from utils import blur_pixmap
from widgets import BandButton, ClickableLabel, BackgroundEffect, TrashButton, EmptyStateOverlay, ShrinkButton, GearButton, CloseButton
from dialogs import DeleteConfirmDialog
from settings_dialog import SettingsDialog
from themes import THEMES, THEME_FADE, add_button_styles, tint_color, dialog_color, theme_index
from settings import load_settings, save_settings
from splash import SplashOverlay
from paths import APP_NAME, APP_ID, resource_path, ensure_data_dirs
from library import list_wallpapers, load_thumbnail, import_wallpaper, delete_wallpaper, wallpaper_path
from applier import WallpaperApplier, get_current_wallpaper
from updater import UpdateChecker

SNAP_DURATION = 360
SETTLE_DELAY = 30
SETTLE_DURATION = 350
SHARP_HOLD = 1200
CLOSE_FADE = 600
EXTRAS_HIDE = 300
EXTRAS_SHOW = 800
UPDATE_CHECK_DELAY = 3000


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.settings = load_settings()
        self.theme_index = theme_index(self.settings["theme"])
        self.settings["theme"] = THEMES[self.theme_index]["name"]

        self.labels = []
        self.pixmap_cache = {}
        self.highlighted_label = None
        self.key_target = None
        self.gallery_ready = False
        self.intro_waiting = False
        self.is_dragging = False
        self.drag_start_x = None
        self.scroll_start_value = 0
        self.scroll_animation = None
        self.gap_animation = None
        self.close_fade = None
        self.pending_apply = None
        self.extras_hidden = False
        self.extra_effects = []
        self.update_release = None

        self.center_timer = self.make_timer(self.on_centered_still)
        self.wheel_stop_timer = self.make_timer(self.snap_to_center)
        self.sharp_timer = self.make_timer(self.end_sharp_hold)

        self.applier = WallpaperApplier()
        self.applier.image_ready.connect(self.on_image_ready)
        self.applier.applied.connect(self.on_applied)
        self.update_checker = UpdateChecker(self)
        self.update_checker.available.connect(self.on_update_available)

        main_container = QWidget()
        main_container.setStyleSheet("background-color: transparent;")
        main_container.setFixedSize(900, 500)
        main_layout = QVBoxLayout(main_container)
        main_layout.addLayout(self.build_top_bar())
        main_layout.addWidget(self.build_gallery())
        main_layout.addWidget(self.build_action_panel())

        self.setup_shortcuts()
        self.load_wallpapers()
        self.setCentralWidget(self.build_layers(main_container))

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.topLeft())
        self.resize(screen.width(), screen.height())

    def fade_effect(self, widget):
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(1.0)
        widget.setGraphicsEffect(effect)
        return effect

    def make_timer(self, handler):
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(handler)
        return timer

    def build_top_bar(self):
        logo_label = QLabel()
        logo_label.setAttribute(Qt.WA_TranslucentBackground)
        logo_label.setAutoFillBackground(False)
        logo_label.setStyleSheet("background: transparent;")
        ratio = QApplication.primaryScreen().devicePixelRatio()
        logo_pixmap = QPixmap(resource_path("logo.png")).scaledToWidth(round(43 * ratio), Qt.SmoothTransformation)
        logo_pixmap.setDevicePixelRatio(ratio)
        logo_label.setPixmap(logo_pixmap)
        logo_label.setFixedSize(80, 61)
        logo_label.setAlignment(Qt.AlignCenter)

        self.settings_button = GearButton()
        self.settings_button.clicked.connect(self.open_settings)
        close_button = CloseButton()
        close_button.clicked.connect(self.close)
        for widget in (logo_label, self.settings_button, close_button):
            self.extra_effects.append(self.fade_effect(widget))

        top_bar = QHBoxLayout()
        top_bar.addWidget(logo_label)
        top_bar.addStretch()
        top_bar.addWidget(self.settings_button)
        top_bar.addWidget(close_button)
        return top_bar

    def build_gallery(self):
        container = QWidget()
        self.gallery_layout = QHBoxLayout(container)
        self.gallery_layout.setSpacing(18)
        self.gallery_layout.addItem(QSpacerItem(350, 20, QSizePolicy.Fixed, QSizePolicy.Minimum))
        self.add_button = ShrinkButton("+", *add_button_styles(THEMES[self.theme_index]))
        self.add_button.setFixedSize(100, 50)
        self.add_button.clicked.connect(self.add_wallpaper)
        self.extra_effects.append(self.fade_effect(self.add_button))
        self.gallery_layout.addWidget(self.add_button)
        self.gallery_layout.addItem(QSpacerItem(350, 20, QSizePolicy.Fixed, QSizePolicy.Minimum))

        self.scroll_area = QScrollArea()
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidget(container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.viewport().installEventFilter(self)
        self.scroll_area.setFocusPolicy(Qt.NoFocus)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        return self.scroll_area

    def build_action_panel(self):
        action_panel = QWidget()
        self.panel_opacity = QGraphicsOpacityEffect()
        action_panel.setGraphicsEffect(self.panel_opacity)
        self.panel_opacity.setOpacity(0)
        action_panel.setFixedHeight(90)
        self.action_layout = QHBoxLayout(action_panel)
        self.action_layout.setAlignment(Qt.AlignCenter)

        self.apply_button = BandButton("Apply", "Applied")
        self.apply_button.clicked.connect(self.apply_centered)
        self.action_layout.addWidget(self.apply_button)

        self.delete_button = TrashButton()
        self.delete_button.clicked.connect(self.delete_current_wallpaper)
        self.delete_button.setParent(action_panel)
        self.apply_button.resized.connect(self.place_delete_button)
        self.delete_button.raise_()
        self.extra_effects.append(self.fade_effect(self.delete_button))
        return action_panel

    def build_layers(self, main_container):
        self.bg_effect = BackgroundEffect()
        self.bg_effect.set_tint(tint_color(THEMES[self.theme_index]), 0)
        screen_size = QApplication.primaryScreen().geometry()
        self.bg_effect.setFixedSize(screen_size.width(), screen_size.height())
        self.bg_effect.swept.connect(self.on_swept)

        foreground_widget = QWidget()
        foreground_widget.setStyleSheet("background-color: transparent;")
        foreground_layout = QVBoxLayout(foreground_widget)
        foreground_layout.addWidget(main_container, alignment=Qt.AlignCenter)

        central_widget = QWidget()
        stacked = QStackedLayout(central_widget)
        stacked.setStackingMode(QStackedLayout.StackAll)
        stacked.addWidget(self.bg_effect)
        stacked.addWidget(foreground_widget)
        self.empty_overlay = EmptyStateOverlay(self.add_button, "Add your first wallpaper...")
        stacked.addWidget(self.empty_overlay)
        self.splash = SplashOverlay(resource_path("logo.png"))
        stacked.addWidget(self.splash)
        self.bg_effect.lower()
        self.empty_overlay.raise_()
        self.splash.raise_()
        return central_widget

    def setup_shortcuts(self):
        for key, handler in ((Qt.Key_Left, lambda: self.step_selection(-1)),
                             (Qt.Key_Right, lambda: self.step_selection(1)),
                             (Qt.Key_Return, self.activate_centered),
                             (Qt.Key_Enter, self.activate_centered),
                             (Qt.Key_Delete, self.delete_centered)):
            QShortcut(QKeySequence(key), self, handler)

    def start(self):
        self.splash.finished.connect(self.reveal)
        self.splash.finished.connect(self.splash.hand_over)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowOpacity(0.0)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.show()
        QTimer.singleShot(100, self.begin_intro)
        QTimer.singleShot(UPDATE_CHECK_DELAY, self, self.update_checker.check)

    def begin_intro(self):
        if self.settings["play_intro"]:
            self.splash.start()
        else:
            self.splash.hide()
            self.reveal()
        self.window_fade = QPropertyAnimation(self, b"windowOpacity")
        self.window_fade.setDuration(200)
        self.window_fade.setStartValue(0.0)
        self.window_fade.setEndValue(1.0)
        self.window_fade.setEasingCurve(QEasingCurve.OutCubic)
        self.window_fade.finished.connect(self.settle_window)
        self.window_fade.start()

    def settle_window(self):
        handle = self.windowHandle()
        handle.setFlags(handle.flags() & ~Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.raise_()
        self.activateWindow()

    def reveal(self):
        self.gallery_ready = True
        if self.settings["play_intro"]:
            self.play_intro_scroll()
        else:
            self.show_active_label()
        self.update_empty_state()

    def find_active_label(self):
        current_filename = os.path.basename(get_current_wallpaper())
        for label in self.labels:
            if label.filename == current_filename:
                return label
        return self.labels[0] if self.labels else self.add_button

    def play_intro_scroll(self):
        target_label = self.find_active_label()
        if len(self.labels) < 2:
            self.snap_to_label(target_label)
            return
        start_label = self.labels[0] if target_label is self.labels[-1] else self.labels[-1]
        cards_passed = abs(self.labels.index(start_label) - self.labels.index(target_label))
        self.hide_action_panel()
        self.scroll_area.horizontalScrollBar().setValue(self.scroll_value_for(start_label))
        self.refresh_visual_sizes()
        duration = min(1400, 600 + 120 * cards_passed)
        self.intro_waiting = True
        QTimer.singleShot(250, lambda: self.start_intro_scroll(target_label, duration))

    def start_intro_scroll(self, target_label, duration):
        self.intro_waiting = False
        self.animate_scroll_to(self.scroll_value_for(target_label), duration, QEasingCurve.OutCubic)

    def show_active_label(self):
        target_label = self.find_active_label()
        self.relayout_gallery()
        self.scroll_area.horizontalScrollBar().setValue(self.scroll_value_for(target_label))
        self.refresh_visual_sizes()

    def viewport_center(self):
        return self.scroll_area.horizontalScrollBar().value() + self.scroll_area.viewport().width() / 2

    def distance_to_center(self, widget):
        return abs(widget.x() + widget.width() / 2 - self.viewport_center())

    def gallery_items(self):
        return self.labels + [self.add_button]

    def centered_item(self):
        return min(self.gallery_items(), key=self.distance_to_center)

    def get_centered_label(self):
        return min(self.labels, key=self.distance_to_center, default=None)

    def scroll_value_for(self, widget):
        return int(widget.x() + widget.width() / 2 - self.scroll_area.viewport().width() / 2)

    def refresh_visual_sizes(self):
        for label in self.labels:
            label.set_focus(1.0 - min(self.distance_to_center(label) / 400, 1.0))
        self.center_timer.start(SETTLE_DELAY)

    def relayout_gallery(self):
        self.gallery_layout.invalidate()
        container_width = max(self.gallery_layout.sizeHint().width(), self.scroll_area.viewport().width())
        self.scroll_area.widget().resize(container_width, self.scroll_area.widget().height())
        self.gallery_layout.activate()

    def is_scrolling(self):
        return self.scroll_animation is not None and self.scroll_animation.state() == QPropertyAnimation.Running

    def is_gap_moving(self):
        return self.gap_animation is not None and self.gap_animation.state() == QVariantAnimation.Running

    def animate_scroll_to(self, target_value, duration=SNAP_DURATION, easing=QEasingCurve.OutCubic):
        self.scroll_animation = QPropertyAnimation(self.scroll_area.horizontalScrollBar(), b"value")
        self.scroll_animation.setDuration(duration)
        self.scroll_animation.setStartValue(self.scroll_area.horizontalScrollBar().value())
        self.scroll_animation.setEndValue(target_value)
        self.scroll_animation.setEasingCurve(easing)
        self.scroll_animation.valueChanged.connect(lambda: self.refresh_visual_sizes())
        self.scroll_animation.finished.connect(lambda: self.center_timer.start(SETTLE_DELAY))
        self.scroll_animation.start()

    def snap_to_label(self, target_label):
        self.hide_action_panel()
        self.refresh_visual_sizes()
        self.animate_scroll_to(self.scroll_value_for(target_label))

    def snap_to_center(self):
        self.snap_to_label(self.get_centered_label() or self.add_button)

    def on_centered_still(self):
        if self.intro_waiting or self.is_scrolling() or self.is_gap_moving() or self.wheel_stop_timer.isActive():
            return
        if QApplication.mouseButtons() & Qt.LeftButton:
            return
        closest_label = self.centered_item()
        if closest_label is self.add_button:
            return
        if abs(self.scroll_value_for(closest_label) - self.scroll_area.horizontalScrollBar().value()) > 2:
            self.snap_to_label(closest_label)
            return

        pixmap = self.pixmap_cache[closest_label.filename]
        blur_radius = 40 * pixmap.width() / self.bg_effect.width()
        self.bg_effect.set_pixmap(blur_pixmap(pixmap, blur_radius))
        self.fade_background_photo(1.0, 400)
        self.highlight_centered_label(closest_label)
        self.apply_button.set_applied(self.is_active(closest_label.filename), False)

        self.action_layout.activate()
        self.show_action_panel()

    def highlight_centered_label(self, target_label):
        for label in self.labels:
            if label is not target_label and label.settle > 0:
                label.animate_settle(0.0, 200)
        self.highlighted_label = target_label
        target_label.animate_settle(1.0, SETTLE_DURATION)

    def unhighlight_centered_label(self):
        if self.highlighted_label:
            label = self.highlighted_label
            self.highlighted_label = None
            try:
                label.animate_settle(0.0, 200)
            except RuntimeError:
                pass

    def eventFilter(self, source, event):
        if source == self.scroll_area.viewport() or isinstance(source, ClickableLabel):
            if event.type() == QMouseEvent.Type.MouseButtonPress:
                self.drag_start_x = event.globalPosition().x()
                self.scroll_start_value = self.scroll_area.horizontalScrollBar().value()
                self.is_dragging = False
            elif event.type() == QMouseEvent.Type.MouseMove:
                if self.drag_start_x is not None and (event.buttons() & Qt.MouseButton.LeftButton):
                    delta = event.globalPosition().x() - self.drag_start_x
                    if abs(delta) > 5:
                        self.is_dragging = True
                        self.hide_action_panel()
                        self.scroll_area.horizontalScrollBar().setValue(self.scroll_start_value - int(delta))
                        self.refresh_visual_sizes()
            elif event.type() == event.Type.Wheel:
                delta = event.angleDelta().x()
                if delta == 0:
                    delta = event.angleDelta().y()
                self.hide_action_panel()
                current = self.scroll_area.horizontalScrollBar().value()
                self.scroll_area.horizontalScrollBar().setValue(current - delta)
                self.refresh_visual_sizes()
                self.wheel_stop_timer.start(300)
                return True
            elif event.type() == QMouseEvent.Type.MouseButtonRelease:
                if self.is_dragging:
                    self.snap_to_center()
        return super().eventFilter(source, event)

    def on_card_clicked(self, label):
        if not self.is_dragging:
            self.snap_to_label(label)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def step_selection(self, direction):
        if not self.gallery_ready:
            return
        items = self.gallery_items()
        scrolling = self.is_scrolling()
        current = self.key_target if scrolling and self.key_target in items else self.centered_item()
        index = max(0, min(len(items) - 1, items.index(current) + direction))
        self.key_target = items[index]
        self.snap_to_label(self.key_target)

    def activate_centered(self):
        if not self.gallery_ready:
            return
        if self.centered_item() is self.add_button:
            self.add_wallpaper()
        elif self.apply_button.isEnabled():
            self.apply_centered()

    def delete_centered(self):
        if self.gallery_ready and self.centered_item() is not self.add_button and self.delete_button.isEnabled():
            self.delete_current_wallpaper()

    def fade_background_photo(self, end_value, duration):
        self.bg_anim = QPropertyAnimation(self.bg_effect, b"photo_opacity")
        self.bg_anim.setDuration(duration)
        self.bg_anim.setStartValue(self.bg_effect.photo_opacity)
        self.bg_anim.setEndValue(end_value)
        self.bg_anim.start()

    def fade_action_panel(self, end_value, duration):
        self.panel_animation = QPropertyAnimation(self.panel_opacity, b"opacity")
        self.panel_animation.setDuration(duration)
        self.panel_animation.setStartValue(self.panel_opacity.opacity())
        self.panel_animation.setEndValue(end_value)
        self.panel_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.panel_animation.start()

    def set_action_buttons_enabled(self, enabled):
        self.apply_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    def place_delete_button(self):
        band = self.apply_button.geometry()
        x = band.center().x() + round(self.apply_button.band_width() / 2) + 8
        y = band.center().y() - self.delete_button.height() // 2
        self.delete_button.move(x, y)

    def show_action_panel(self):
        self.place_delete_button()
        self.apply_button.appear()
        self.fade_action_panel(1, 350)
        self.panel_animation.finished.connect(lambda: self.set_action_buttons_enabled(True))

    def hide_action_panel(self):
        if self.pending_apply:
            self.on_swept()
        if self.bg_effect.has_sharp():
            self.sharp_timer.stop()
            self.bg_effect.fade_sharp(250)
        self.unhighlight_centered_label()
        self.show_extras(400)
        self.fade_background_photo(0.0, 200)
        self.set_action_buttons_enabled(False)
        self.apply_button.disappear()
        self.fade_action_panel(0, 200)

    def set_extras_level(self, end_value, duration, keep=None):
        for label in self.labels:
            if label is not keep:
                label.animate_presence(end_value, duration)
        self.extra_animations = []
        for effect in self.extra_effects:
            animation = QPropertyAnimation(effect, b"opacity")
            animation.setDuration(duration)
            animation.setStartValue(effect.opacity())
            animation.setEndValue(end_value)
            animation.setEasingCurve(QEasingCurve.InOutSine)
            animation.start()
            self.extra_animations.append(animation)

    def hide_extras(self, keep):
        self.extras_hidden = True
        self.set_extras_level(0.0, EXTRAS_HIDE, keep)

    def show_extras(self, duration=EXTRAS_SHOW):
        if self.extras_hidden:
            self.extras_hidden = False
            self.set_extras_level(1.0, duration)

    def is_active(self, filename):
        current = os.path.normcase(os.path.abspath(get_current_wallpaper()))
        return current == os.path.normcase(os.path.abspath(wallpaper_path(filename)))

    def apply_centered(self):
        label = self.get_centered_label()
        if label is None or self.apply_button.is_applied() or self.bg_effect.has_sharp() or self.pending_apply:
            return
        if not os.path.exists(wallpaper_path(label.filename)):
            self.show_error("This wallpaper file is missing from your library.")
            return
        self.apply_button.play_flash()
        self.apply_button.press_widen()
        self.pending_apply = {"label": label, "swept": False, "result": None}
        self.hide_extras(label)
        ratio = self.devicePixelRatio()
        self.applier.start(label.filename, round(self.width() * ratio), round(self.height() * ratio))

    def on_image_ready(self, filename, image):
        pending = self.pending_apply
        if not pending or pending["label"].filename != filename:
            return
        if image is None or self.highlighted_label is not pending["label"]:
            pending["swept"] = True
            return
        self.bg_effect.start_sweep(image)

    def on_applied(self, filename, success):
        pending = self.pending_apply
        if not pending or pending["label"].filename != filename:
            return
        if not success:
            self.pending_apply = None
            self.bg_effect.fade_sharp(250)
            self.show_extras()
            if self.highlighted_label is pending["label"]:
                self.apply_button.set_applied(False, True)
            self.show_error("Windows could not apply this wallpaper.")
            return
        pending["result"] = True
        if self.highlighted_label and self.highlighted_label is not pending["label"]:
            self.apply_button.set_applied(self.is_active(self.highlighted_label.filename), True)
        if pending["swept"]:
            self.finish_apply()

    def on_swept(self):
        if not self.pending_apply:
            return
        self.pending_apply["swept"] = True
        if self.pending_apply["result"]:
            self.finish_apply()

    def finish_apply(self):
        label = self.pending_apply["label"]
        self.pending_apply = None
        if self.highlighted_label is label:
            self.apply_button.set_applied(True, True)
            self.sharp_timer.start(SHARP_HOLD)
        else:
            self.bg_effect.fade_sharp(250)

    def end_sharp_hold(self):
        if self.settings["close_after_apply"]:
            self.fade_out_and_close()
        else:
            self.bg_effect.fade_sharp(800)
            self.show_extras(800)

    def fade_out_and_close(self):
        if self.close_fade is not None:
            return
        self.close_fade = QPropertyAnimation(self, b"windowOpacity")
        self.close_fade.setDuration(CLOSE_FADE)
        self.close_fade.setStartValue(self.windowOpacity())
        self.close_fade.setEndValue(0.0)
        self.close_fade.setEasingCurve(QEasingCurve.InOutSine)
        self.close_fade.finished.connect(self.close)
        self.close_fade.start()

    def load_wallpapers(self):
        existing_files = [label.filename for label in self.labels]
        for filename in list_wallpapers():
            if filename in existing_files:
                continue
            thumbnail = load_thumbnail(filename)
            if thumbnail is None:
                continue
            label = self.create_label(filename, thumbnail)
            self.labels.append(label)
            self.gallery_layout.insertWidget(self.gallery_layout.indexOf(self.add_button), label)

    def create_label(self, filename, thumbnail):
        self.pixmap_cache[filename] = thumbnail
        label = ClickableLabel(filename, thumbnail)
        label.clicked.connect(self.on_card_clicked)
        label.installEventFilter(self)
        return label

    def add_wallpaper(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Choose Wallpaper", "", "Images (*.png *.jpg *.jpeg)")
        if not file_path:
            return
        try:
            filename = import_wallpaper(file_path)
        except OSError:
            self.show_error("The wallpaper could not be copied to your library.")
            return
        if filename is None:
            self.show_error("This file could not be opened as an image.")
            return
        thumbnail = load_thumbnail(filename)
        if thumbnail is None:
            self.show_error("This file could not be opened as an image.")
            return
        self.empty_overlay.disappear()
        self.hide_action_panel()
        self.open_gap(self.create_label(filename, thumbnail))

    def open_gap(self, label):
        gap_width = label.width() + self.gallery_layout.spacing()
        bar = self.scroll_area.horizontalScrollBar()
        start_scroll = bar.value()
        if self.labels:
            last_label = self.labels[-1]
            card_x = last_label.x() + last_label.width() + self.gallery_layout.spacing()
        else:
            card_x = self.gallery_layout.contentsMargins().left() + self.gallery_layout.itemAt(0).sizeHint().width()
        target_scroll = card_x + label.width() / 2 - self.scroll_area.viewport().width() / 2
        gap = QSpacerItem(0, 20, QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.gallery_layout.insertItem(self.gallery_layout.indexOf(self.add_button), gap)
        self.gap_animation = QVariantAnimation()
        self.gap_animation.setDuration(480 if self.labels else 650)
        self.gap_animation.setStartValue(0.0)
        self.gap_animation.setEndValue(1.0)
        self.gap_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.gap_animation.valueChanged.connect(
            lambda progress: self.grow_gap(gap, gap_width * progress, start_scroll + (target_scroll - start_scroll) * progress)
        )
        self.gap_animation.finished.connect(lambda: self.fill_gap(gap, label))
        self.gap_animation.start()

    def grow_gap(self, gap, width, scroll_value):
        gap.changeSize(int(width), 20, QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.relayout_gallery()
        self.scroll_area.horizontalScrollBar().setValue(int(scroll_value))
        self.refresh_visual_sizes()

    def fill_gap(self, gap, label):
        index = self.gallery_layout.indexOf(gap)
        self.gallery_layout.removeItem(gap)
        label.set_opacity(0.0)
        self.gallery_layout.insertWidget(index, label)
        label.show()
        self.labels.append(label)
        self.relayout_gallery()
        self.refresh_visual_sizes()
        self.fade_in_animation = QPropertyAnimation(label, b"opacity")
        self.fade_in_animation.setDuration(450)
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_in_animation.start()

    def delete_current_wallpaper(self):
        closest_label = self.get_centered_label()
        if closest_label is None:
            return

        dialog = DeleteConfirmDialog(dialog_color(THEMES[self.theme_index]), self)
        dialog.exec()

        if dialog.result_value:
            try:
                delete_wallpaper(closest_label.filename)
            except OSError:
                self.show_error("This wallpaper could not be deleted. It may be in use by another program.")
                return
            follow_left = closest_label is self.labels[-1] and len(self.labels) > 1
            self.highlighted_label = None
            self.hide_action_panel()
            self.labels.remove(closest_label)
            closest_label.animate_settle(0.0, 250)
            closest_label.sink_away(lambda: self.remove_label(closest_label, follow_left))

    def remove_label(self, label, follow_left):
        self.pixmap_cache.pop(label.filename, None)
        index = self.gallery_layout.indexOf(label)
        gap_width = label.width() + self.gallery_layout.spacing()
        label.hide()
        self.gallery_layout.removeWidget(label)
        label.deleteLater()
        self.close_gap(index, gap_width, follow_left)

    def close_gap(self, index, gap_width, follow_left):
        gap = QSpacerItem(gap_width, 20, QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.gallery_layout.insertItem(index, gap)
        self.relayout_gallery()
        start_scroll = self.scroll_area.horizontalScrollBar().value()
        self.gap_animation = QVariantAnimation()
        self.gap_animation.setDuration(350)
        self.gap_animation.setStartValue(gap_width)
        self.gap_animation.setEndValue(0)
        self.gap_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.gap_animation.valueChanged.connect(
            lambda width: self.resize_gap(gap, width, start_scroll - (gap_width - width) if follow_left else None)
        )
        self.gap_animation.finished.connect(lambda: self.remove_gap(gap))
        self.gap_animation.start()

    def resize_gap(self, gap, width, scroll_value):
        gap.changeSize(int(width), 20, QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.relayout_gallery()
        if scroll_value is not None:
            self.scroll_area.horizontalScrollBar().setValue(int(scroll_value))
        self.refresh_visual_sizes()

    def remove_gap(self, gap):
        self.gallery_layout.removeItem(gap)
        self.relayout_gallery()
        self.snap_to_center()
        self.update_empty_state()

    def update_empty_state(self):
        if self.labels:
            self.empty_overlay.disappear()
        else:
            self.hide_action_panel()
            self.empty_overlay.appear()

    def open_settings(self):
        dialog = SettingsDialog(self.theme_index, self.settings, self.update_release, self)
        dialog.theme_selected.connect(self.apply_theme)
        dialog.setting_changed.connect(self.update_setting)
        dialog.exec()

    def on_update_available(self, version, url):
        self.update_release = (version, url)
        self.settings_button.show_badge()

    def update_setting(self, key, value):
        self.settings[key] = value
        save_settings(self.settings)

    def apply_theme(self, index):
        self.theme_index = index
        theme = THEMES[index]
        self.bg_effect.set_tint(tint_color(theme), THEME_FADE)
        normal, pressed = add_button_styles(theme)
        self.add_button.pressed_style = pressed
        self.add_button.set_normal_style(normal)
        self.update_setting("theme", theme["name"])

    def show_error(self, message):
        QMessageBox.warning(self, APP_NAME, message)


if __name__ == "__main__":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("icon.ico")))
    ensure_data_dirs()
    font_id = QFontDatabase.addApplicationFont(resource_path("fonts/Outfit-Regular.ttf"))
    font_families = QFontDatabase.applicationFontFamilies(font_id)
    if font_families:
        app.setFont(QFont(font_families[0], 12))
    window = MainWindow()
    window.start()
    sys.exit(app.exec())
