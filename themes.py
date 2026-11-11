from PySide6.QtGui import QColor

THEME_FADE = 450
THEME_STRENGTH = 0.1
DIALOG_STRENGTH = 0.20
DIALOG_BASE = 20
DIALOG_ALPHA = 230
TINT_ALPHA = 180
BUTTON_ALPHA = 110

THEMES = [
    {"name": "Dark", "hue": QColor(0, 0, 0), "swatch": QColor("#2a2a2e")},
    {"name": "Silver", "hue": QColor(130, 135, 145), "swatch": QColor("#686b72")},
    {"name": "Purple", "hue": QColor(90, 50, 150), "swatch": QColor("#4a3770")},
    {"name": "Bordeaux", "hue": QColor(140, 35, 60), "swatch": QColor("#662a38")},
    {"name": "Blue", "hue": QColor(40, 75, 150), "swatch": QColor("#2f4570")},
    {"name": "Green", "hue": QColor(40, 120, 75), "swatch": QColor("#31593f")},
]


def theme_index(name):
    for index, theme in enumerate(THEMES):
        if theme["name"] == name:
            return index
    return 0


def mixed(theme, alpha):
    hue = theme["hue"]
    return QColor(round(hue.red() * THEME_STRENGTH), round(hue.green() * THEME_STRENGTH), round(hue.blue() * THEME_STRENGTH), alpha)


def tint_color(theme):
    return mixed(theme, TINT_ALPHA)


def dialog_color(theme):
    hue = theme["hue"]
    return QColor(*(round(DIALOG_BASE + value * DIALOG_STRENGTH) for value in (hue.red(), hue.green(), hue.blue())), DIALOG_ALPHA)


def rgba(color, alpha_change=0, lighten=0):
    channels = [min(255, value + lighten) for value in (color.red(), color.green(), color.blue())]
    alpha = min(255, color.alpha() + alpha_change)
    return f"rgba({channels[0]}, {channels[1]}, {channels[2]}, {alpha})"


def add_button_styles(theme):
    color = mixed(theme, BUTTON_ALPHA)
    normal = f"""
            QPushButton {{ color: white; background-color: {rgba(color)}; border: none; font-size: 22px; border-radius: 6px; }}
            QPushButton:hover {{ background-color: {rgba(color, 50)}; }}
        """
    pressed = f"""
            QPushButton {{ color: white; background-color: {rgba(color, 40, 55)}; border: none; font-size: 19px; border-radius: 6px; }}
        """
    return normal, pressed
