TITLE_STYLE = "color: white; font-size: 19px; background: transparent;"
NOTE_STYLE = "color: rgba(255, 255, 255, 90); font-size: 12px; background: transparent;"


def outline_button_styles(radius, padding_y, padding_x, font_size):
    normal = f"""
        QPushButton {{ color: white; background: transparent; border: 1px solid rgba(255, 255, 255, 170); border-radius: {radius}px; padding: {padding_y}px {padding_x}px; font-size: {font_size}px; }}
        QPushButton:hover {{ background-color: rgba(255, 255, 255, 30); border: 1px solid white; }}
        QPushButton:disabled {{ color: rgba(255, 255, 255, 80); border: 1px solid rgba(255, 255, 255, 50); }}
    """
    pressed = f"""
        QPushButton {{ color: white; background-color: rgba(255, 255, 255, 40); border: 2px solid white; border-radius: {radius - 1}px; padding: {padding_y - 2}px {padding_x - 2}px; margin: 1px; font-size: {font_size}px; }}
    """
    return normal, pressed


SMALL_BUTTON_STYLES = outline_button_styles(13, 4, 18, 13)
