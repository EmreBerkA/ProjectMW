import json
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from paths import APP_NAME, APP_VERSION, UPDATE_REPO

CHECK_TIMEOUT = 10000


def version_tuple(text):
    parts = []
    for piece in text.strip().lstrip("vV").split("."):
        digits = ""
        for character in piece:
            if not character.isdigit():
                break
            digits += character
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


class UpdateChecker(QObject):
    available = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.network = QNetworkAccessManager(self)

    def check(self):
        request = QNetworkRequest(QUrl(f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", f"{APP_NAME}/{APP_VERSION}".encode())
        request.setTransferTimeout(CHECK_TIMEOUT)
        reply = self.network.get(request)
        reply.finished.connect(lambda: self.on_finished(reply))

    def on_finished(self, reply):
        reply.deleteLater()
        if reply.error() != QNetworkReply.NoError:
            return
        try:
            release = json.loads(bytes(reply.readAll()).decode("utf-8"))
        except ValueError:
            return
        if not isinstance(release, dict):
            return
        tag = str(release.get("tag_name", ""))
        url = str(release.get("html_url", ""))
        latest = version_tuple(tag)
        if latest and latest > version_tuple(APP_VERSION) and url.startswith("https://github.com/"):
            self.available.emit(tag.lstrip("vV"), url)
