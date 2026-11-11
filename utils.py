from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect
from PySide6.QtCore import Qt, QRectF


def blur_pixmap(pixmap, radius):
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(pixmap)
    blur = QGraphicsBlurEffect()
    blur.setBlurRadius(radius)
    item.setGraphicsEffect(blur)
    scene.addItem(item)
    result = QPixmap(pixmap.size())
    result.fill(Qt.transparent)
    painter = QPainter(result)
    scene.render(painter)
    painter.end()
    return result


def cover_crop(pixmap, ratio):
    source_width = pixmap.width()
    source_height = pixmap.height()
    if source_width / source_height > ratio:
        crop_width = source_height * ratio
        return QRectF((source_width - crop_width) / 2, 0, crop_width, source_height)
    crop_height = source_width / ratio
    return QRectF(0, (source_height - crop_height) / 2, source_width, crop_height)
