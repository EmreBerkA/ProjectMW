import os
import sys

sys.path.insert(0, SPECPATH)
from paths import APP_VERSION

a = Analysis(
    ["main.py"],
    datas=[
        ("logo.png", "."),
        ("icon.ico", "."),
        ("fonts/Outfit-Regular.ttf", "fonts"),
    ],
    excludes=["tkinter", "unittest", "pydoc", "PIL", "_hashlib", "_ssl", "ssl"],
)

UNUSED = (
    "opengl32sw.dll",
    "Qt6Quick", "Qt6Qml", "Qt6Pdf", "Qt6VirtualKeyboard", "Qt6Svg",
    "libcrypto-3-x64.dll", "libssl-3-x64.dll", "qopensslbackend", "qcertonlybackend",
    "qdirect2d", "qminimal", "qtuiotouchplugin", "qtvirtualkeyboardplugin", "qsvgicon",
    "qgif", "qicns", "qpdf", "qsvg", "qtga", "qtiff", "qwbmp", "qwebp",
)


def is_used(entry):
    name = entry[0].replace("\\", "/")
    return "PySide6/translations/" not in name and not any(part in name for part in UNUSED)


a.binaries = [entry for entry in a.binaries if is_used(entry)]
a.datas = [entry for entry in a.datas if is_used(entry)]

numbers = tuple(int(part) for part in APP_VERSION.split(".")) + (0,)
version_file = os.path.join(workpath, "version_info.txt")
with open(os.path.join(SPECPATH, "version_template.txt"), encoding="utf-8") as template:
    version_text = template.read().replace("{numbers}", str(numbers[:4])).replace("{version}", APP_VERSION)
with open(version_file, "w", encoding="utf-8") as output:
    output.write(version_text)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="ProjectMW",
    icon="icon.ico",
    version=version_file,
    console=False,
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="ProjectMW",
    upx=False,
)
