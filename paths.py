import os
import sys

APP_NAME = "ProjectMW"
APP_VERSION = "1.0.0"
UPDATE_REPO = "EmreBerkA/ProjectMW"
APP_ID = "EmreBerk.ProjectMW"
DEFAULT_LIBRARY = "Default"


def resource_path(relative_path):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


def data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME)


def library_dir(library=DEFAULT_LIBRARY):
    return os.path.join(data_dir(), "wallpapers", "library", library)


def thumbs_dir(library=DEFAULT_LIBRARY):
    return os.path.join(data_dir(), "thumbs", library)


def ensure_data_dirs(library=DEFAULT_LIBRARY):
    os.makedirs(library_dir(library), exist_ok=True)
    os.makedirs(thumbs_dir(library), exist_ok=True)