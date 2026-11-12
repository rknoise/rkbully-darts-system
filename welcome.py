"""Üdvözlő ablak: induláskor a bemutató kép, bezárható, és egy pipával végleg el is rejthető."""
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QLayout, QPushButton, QVBoxLayout

from appinfo import APP_NAME

IMAGE_NAME = "welcome.jpg"
FOOTER_PX = 78            # a kép alatti sáv (pipa + gomb) és az ablakkeret helyigénye a képernyő magasságából


def image_path(app_dir):
    return Path(app_dir) / "assets" / IMAGE_NAME


def fit_size(src, avail):
    """A kép mérete a képernyőn: az arányt megtartva belefér a rendelkezésre álló területre (nagyítani nem kell)."""
    w, h = src.width(), src.height()
    scale = min(1.0, avail.width() * 0.92 / max(w, 1), (avail.height() * 0.9 - FOOTER_PX) / max(h, 1))
    scale = max(scale, 0.1)
    return QSize(max(int(w * scale), 160), max(int(h * scale), 90))


class WelcomeDialog(QDialog):
    """A bemutató kép egy ablakban. A „Többé ne jelenjen meg” pipa állapotát a hívó olvassa ki (`hide_forever`)."""

    def __init__(self, parent, path, hide_checked=False):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        src = QPixmap(str(path))
        if src.isNull():
            raise ValueError(f"A kép nem tölthető be: {path}")
        screen = (parent.screen() if parent is not None else None) or QGuiApplication.primaryScreen()
        size = fit_size(src, screen.availableGeometry().size())
        dpr = screen.devicePixelRatio()
        pm = src.scaled(size * dpr, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
        self.image = QLabel()
        self.image.setPixmap(pm)
        self.image.setFixedSize(size)
        self.hide_box = QCheckBox("Többé ne jelenjen meg")
        self.hide_box.setChecked(bool(hide_checked))
        self.close_btn = QPushButton("Bezárás")
        self.close_btn.setObjectName("go")
        self.close_btn.setDefault(True)
        self.close_btn.setMinimumWidth(150)
        self.close_btn.clicked.connect(self.accept)
        foot = QHBoxLayout()
        foot.setContentsMargins(8, 4, 8, 0)
        foot.addWidget(self.hide_box)
        foot.addStretch()
        foot.addWidget(self.close_btn)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)
        lay.addWidget(self.image)
        lay.addLayout(foot)
        lay.setSizeConstraint(QLayout.SetFixedSize)      # az ablak pontosan a képhez igazodik

    def hide_forever(self):
        return self.hide_box.isChecked()
