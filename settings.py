import json
import os

from paths import data_dir

DEFAULT_SETTINGS = {
    "theme": "Dark",
    "play_intro": True,
    "close_after_apply": False,
}


def settings_path():
    return os.path.join(data_dir(), "settings.json")


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(settings_path(), encoding="utf-8") as file:
            saved = json.load(file)
    except (OSError, ValueError):
        return settings
    if isinstance(saved, dict):
        for key, default in DEFAULT_SETTINGS.items():
            if isinstance(saved.get(key), type(default)):
                settings[key] = saved[key]
    return settings


def save_settings(settings):
    path = settings_path()
    temporary = path + ".tmp"
    try:
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(settings, file, indent=2)
        os.replace(temporary, path)
    except OSError:
        pass
