import os
import shutil
from PySide6.QtCore import Qt
from PySide6.QtGui import QImageReader, QPixmap

from paths import library_dir, thumbs_dir

SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg")
THUMB_WIDTH = 600
THUMB_HEIGHT = 360


def is_supported(filename):
    return filename.lower().endswith(SUPPORTED_EXTENSIONS)


def wallpaper_path(filename):
    return os.path.join(library_dir(), filename)


def thumbnail_path(filename):
    return os.path.join(thumbs_dir(), filename + ".jpg")


def list_wallpapers():
    folder = library_dir()
    return [
        filename for filename in os.listdir(folder)
        if is_supported(filename) and os.path.isfile(os.path.join(folder, filename))
    ]


def read_image(path, width, height, mode=Qt.KeepAspectRatio):
    reader = QImageReader(path)
    size = reader.size()
    if not size.isValid():
        return None
    target = size.scaled(width, height, mode)
    if target.width() < size.width():
        reader.setScaledSize(target)
    image = reader.read()
    if image.isNull():
        return None
    return image


def create_thumbnail(source_path, filename):
    image = read_image(source_path, THUMB_WIDTH, THUMB_HEIGHT)
    if image is None:
        return None
    image.save(thumbnail_path(filename), "JPG", 90)
    return QPixmap.fromImage(image)


def load_thumbnail(filename):
    source = wallpaper_path(filename)
    thumb = thumbnail_path(filename)
    try:
        if os.path.exists(thumb) and os.path.getmtime(thumb) >= os.path.getmtime(source):
            pixmap = QPixmap(thumb)
            if not pixmap.isNull():
                return pixmap
    except OSError:
        return None
    return create_thumbnail(source, filename)


def unique_filename(filename):
    name, extension = os.path.splitext(filename)
    candidate = filename
    counter = 2
    while os.path.exists(wallpaper_path(candidate)):
        candidate = f"{name} ({counter}){extension}"
        counter += 1
    return candidate


def import_wallpaper(source_path):
    if read_image(source_path, THUMB_WIDTH, THUMB_HEIGHT) is None:
        return None
    filename = unique_filename(os.path.basename(source_path))
    shutil.copy(source_path, wallpaper_path(filename))
    create_thumbnail(wallpaper_path(filename), filename)
    return filename


def delete_wallpaper(filename):
    os.remove(wallpaper_path(filename))
    try:
        os.remove(thumbnail_path(filename))
    except OSError:
        pass