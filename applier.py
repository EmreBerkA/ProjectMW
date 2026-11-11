import ctypes
import threading
from PySide6.QtCore import Qt, QObject, Signal

from library import wallpaper_path, read_image

SPI_SETDESKWALLPAPER = 0x0014
SPI_GETDESKWALLPAPER = 0x0073
SPIF_UPDATE_AND_BROADCAST = 0x03


def get_current_wallpaper():
    buffer = ctypes.create_unicode_buffer(512)
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, len(buffer), buffer, 0)
    return buffer.value


class WallpaperApplier(QObject):
    image_ready = Signal(str, object)
    applied = Signal(str, bool)

    def start(self, filename, width, height):
        threading.Thread(target=self.work, args=(filename, width, height), daemon=True).start()

    def work(self, filename, width, height):
        path = wallpaper_path(filename)
        self.image_ready.emit(filename, read_image(path, width, height, Qt.KeepAspectRatioByExpanding))
        success = bool(ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, path, SPIF_UPDATE_AND_BROADCAST))
        self.applied.emit(filename, success)
