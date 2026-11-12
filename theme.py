"""RKBully Darts System neon-HUD megjelenés: színek, stíluslap, neon keretes kártya, kerek profilkép.

Minden méret egy `k` szorzóval skálázódik (az ablak méretéhez igazodik), így a felület kis és nagy képernyőn is
ugyanúgy néz ki.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QWidget

ORANGE, ORANGE_HI, BLUE, GREEN, RED, YELLOW = "#ff8a1f", "#ffb454", "#3a9bff", "#38e07b", "#ff4d4d", "#ffd23f"
BG, TEXT, MUTED = "#070a14", "#eef1ff", "#8f9bd1"


def build_qss(k=1.0):
    """A teljes stíluslap, minden méret a k szorzóval skálázva."""
    def px(v):
        return max(2, int(round(v * k)))

    def fs(v):                                    # betűméret: kis képernyőn sem lehet olvashatatlanul apró
        return max(10, int(round(v * k)))
    return f"""
QWidget {{ background: transparent; color: {TEXT}; font-family: 'Segoe UI', 'Segoe UI Variable', Arial, sans-serif; font-size: {fs(14)}px; }}
QDialog, QMessageBox, QInputDialog {{ background: #0b0f1f; }}
QLabel {{ background: transparent; }}
QToolTip {{ background: #12162b; color: {TEXT}; border: 1px solid {ORANGE}; padding: 4px; }}
QMenu {{ background: #12162b; border: 1px solid #2d3a78; padding: 4px; }}
QMenu::item {{ padding: 6px 22px; }}
QMenu::item:selected {{ background: #2a1808; }}

QPushButton {{ background: rgba(21, 28, 60, 235); border: 1px solid #2d3a78; border-radius: {px(11)}px;
              padding: {px(7)}px {px(12)}px; font-weight: 600; }}
QPushButton:hover {{ border-color: {ORANGE}; background: rgba(42, 30, 20, 235); }}
QPushButton:pressed {{ background: #2a1808; }}
QPushButton:checked {{ background: #2a1808; border: 2px solid {ORANGE}; }}
QPushButton:disabled {{ color: #5b6390; border-color: #1d2650; }}
QPushButton#go {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3d2208, stop:1 #251304);
                 border: 2px solid {ORANGE}; color: #fff; font-size: {fs(19)}px; font-weight: 800; }}
QPushButton#go:hover {{ background: #4a2a0c; }}
QPushButton#tab {{ background: transparent; border: none; border-bottom: 3px solid transparent; border-radius: 0;
                  padding: {px(10)}px {px(22)}px; color: {MUTED}; font-size: {fs(16)}px; font-weight: 700; }}
QPushButton#tab:hover {{ color: #fff; }}
QPushButton#tabon {{ color: #fff; border-bottom: 3px solid {ORANGE}; background: rgba(255, 138, 31, 40); border-radius: 0;
                    padding: {px(10)}px {px(22)}px; font-size: {fs(16)}px; font-weight: 700; border-top: none; border-left: none; border-right: none; }}
QPushButton#icon {{ padding: {px(5)}px; min-width: {px(38)}px; max-width: {px(44)}px; font-size: {fs(18)}px; }}
QPushButton#pad {{ padding: {px(5)}px; font-size: {fs(15)}px; }}
QPushButton#slot {{ background: rgba(20, 26, 56, 150); border: 1px dashed #2d3a78; color: {MUTED}; text-align: left;
                   padding: {px(8)}px {px(14)}px; font-weight: 600; }}
QPushButton#slot:hover {{ border-color: {ORANGE}; color: #fff; }}
QPushButton#addcam {{ background: rgba(20, 26, 56, 170); border: 1px dashed #2d3a78; padding: {px(9)}px; font-weight: 700; }}
QPushButton#addcam:hover {{ border-color: {ORANGE}; }}
QPushButton#addcam_empty {{ background: rgba(20, 26, 56, 170); border: 1px dashed #2d3a78; padding: {px(9)}px; font-weight: 700;
                           font-size: {fs(20)}px; color: {MUTED}; border-radius: {px(16)}px; }}
QPushButton#addcam_empty:hover {{ border-color: {ORANGE}; color: #fff; }}
QLabel#statico {{ font-size: {fs(30)}px; }}

QComboBox {{ background: rgba(21, 28, 60, 235); border: 1px solid #2d3a78; border-radius: {px(11)}px; padding: {px(7)}px {px(10)}px; font-weight: 600; }}
QComboBox:hover {{ border-color: {ORANGE}; }}
QComboBox QAbstractItemView {{ background: #12162b; border: 1px solid #2d3a78; selection-background-color: #2a1808; outline: 0; }}
QComboBox::drop-down {{ border: none; width: {px(22)}px; }}
QLineEdit, QSpinBox {{ background: rgba(14, 19, 42, 240); border: 1px solid #2d3a78; border-radius: {px(9)}px; padding: {px(7)}px {px(10)}px; selection-background-color: {ORANGE}; }}
QLineEdit:focus, QSpinBox:focus {{ border-color: {ORANGE}; }}
QCheckBox {{ spacing: {px(8)}px; }}
QCheckBox::indicator {{ width: {px(20)}px; height: {px(20)}px; border-radius: {px(5)}px; border: 1px solid #2d3a78; background: #0e132a; }}
QCheckBox::indicator:checked {{ background: {ORANGE}; border-color: {ORANGE}; }}
QListWidget {{ background: rgba(12, 17, 38, 235); border: 1px solid #2d3a78; border-radius: {px(11)}px; outline: 0; padding: 4px; }}
QListWidget::item {{ padding: {px(6)}px; border-radius: {px(8)}px; }}
QListWidget::item:selected {{ background: #2a1808; border: 1px solid {ORANGE}; color: #fff; }}
QProgressBar {{ background: #1a2347; border: none; border-radius: 4px; }}
QProgressBar::chunk {{ background: {BLUE}; border-radius: 4px; }}
QTableWidget {{ background: rgba(12, 17, 38, 235); border: 1px solid #2d3a78; border-radius: {px(11)}px; gridline-color: #1d2650; outline: 0; }}
QTableWidget::item {{ padding: {px(6)}px; border-bottom: 1px solid #1d2650; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: #12183a; color: {ORANGE_HI}; border: none; border-bottom: 2px solid {ORANGE}; padding: {px(8)}px; font-weight: 800; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2d3a78; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QLabel#big {{ font-size: {fs(112)}px; font-weight: 900; font-style: italic; color: #ff9d2e; }}
QLabel#logo {{ font-size: {fs(44)}px; font-weight: 900; font-style: italic; letter-spacing: 1px; }}
QLabel#logosub {{ font-size: {fs(13)}px; font-weight: 800; color: #8fb4ff; letter-spacing: 4px; padding-left: {px(3)}px; }}
QLabel#who {{ font-size: {fs(30)}px; font-weight: 800; }}
QLabel#kicker {{ font-size: {fs(15)}px; font-weight: 800; color: {ORANGE_HI}; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#section {{ font-size: {fs(16)}px; font-weight: 700; color: #dfe6ff; }}
QLabel#statv {{ font-size: {fs(26)}px; font-weight: 800; }}
QLabel#statk {{ color: {MUTED}; font-size: {fs(13)}px; }}
QLabel#pts {{ font-size: {fs(24)}px; font-weight: 800; color: #ff9d2e; }}
QLabel#badge {{ background: {ORANGE}; color: #1a0f04; border-radius: {px(9)}px; padding: {px(2)}px {px(9)}px; font-size: {fs(12)}px; font-weight: 900; }}
QLabel#banner {{ font-size: {fs(17)}px; font-weight: 900; color: #fff; letter-spacing: 1px; }}
"""


def glow(widget, color=ORANGE, blur=28, alpha=170):
    """Neon fény egy elem körül (nagy számoknál, gomboknál)."""
    fx = QGraphicsDropShadowEffect(widget)
    c = QColor(color)
    c.setAlpha(alpha)
    fx.setColor(c)
    fx.setBlurRadius(blur)
    fx.setOffset(0, 0)
    widget.setGraphicsEffect(fx)


class Card(QFrame):
    """Sötét panel neon keretttel: narancs -> kék színátmenetes szegély, külső fénnyel."""

    KINDS = {                      # kind: (szegély kezdő, szegély vég, fény)
        "plain": ("#ff8a1f", "#3a9bff", 0.55),
        "active": ("#ff8a1f", "#ffb454", 1.0),
        "review": ("#3a9bff", "#6fc3ff", 0.9),
        "quiet": ("#2d3a78", "#2d3a78", 0.0),
    }

    def __init__(self, kind="plain", parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setAttribute(Qt.WA_StyledBackground, False)

    def set_kind(self, kind):
        if kind != self.kind:
            self.kind = kind
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c1, c2, glow_k = self.KINDS.get(self.kind, self.KINDS["plain"])
        r = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        k = getattr(self.window(), "k", 1.0)           # a főablak méretarányát követi
        radius = 14 * k
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        fill = QLinearGradient(r.topLeft(), r.bottomLeft())
        fill.setColorAt(0, QColor(17, 23, 52, 238))
        fill.setColorAt(1, QColor(9, 13, 30, 238))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(fill))
        p.drawRoundedRect(r, radius, radius)
        for width, alpha in ((7, 22), (4.5, 40), (2.6, 70)):          # külső fény: egyre keskenyebb, egyre erősebb körvonalak
            if glow_k <= 0:
                break
            a, b = QColor(c1), QColor(c2)
            a.setAlpha(int(alpha * glow_k))
            b.setAlpha(int(alpha * glow_k))
            grad.setColorAt(0, a)
            grad.setColorAt(1, b)
            p.setPen(QPen(QBrush(grad), width))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r, radius, radius)
        a, b = QColor(c1), QColor(c2)
        a.setAlpha(235 if glow_k else 255)
        b.setAlpha(235 if glow_k else 255)
        grad.setColorAt(0, a)
        grad.setColorAt(1, b)
        p.setPen(QPen(QBrush(grad), 1.5))
        p.drawRoundedRect(r, radius, radius)


class Avatar(QWidget):
    """Kerek profilkép: feltöltött kép, vagy a név kezdőbetűje színes körben."""

    def __init__(self, size=48, parent=None):
        super().__init__(parent)
        self.pm, self.initial, self.color, self.ring = None, "?", ORANGE, BLUE
        self.set_size(size)

    def set_size(self, size):
        self.setFixedSize(int(size), int(size))
        self.update()

    def set_player(self, name, path=None, color=ORANGE, ring=BLUE):
        self.initial = (name.strip()[:1] or "?").upper()
        self.color, self.ring = color, ring
        pm = QPixmap(str(path)) if path else QPixmap()
        self.pm = pm if not pm.isNull() else None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s = min(self.width(), self.height())
        ring = max(2.0, s / 22)
        r = QRectF(ring / 2, ring / 2, s - ring, s - ring)
        clip = QPainterPath()
        clip.addEllipse(r)
        p.save()
        p.setClipPath(clip)
        if self.pm:
            side = min(self.pm.width(), self.pm.height())              # négyzetre vágva, középről
            src = QRectF((self.pm.width() - side) / 2, (self.pm.height() - side) / 2, side, side)
            p.drawPixmap(r, self.pm, src)
        else:
            g = QRadialGradient(QPointF(s * 0.35, s * 0.3), s)
            base = QColor(self.color)
            g.setColorAt(0, base.lighter(130))
            g.setColorAt(1, base.darker(210))
            p.fillRect(r, QBrush(g))
            f = QFont(self.font())
            f.setPixelSize(int(s * 0.5))
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("#fff"))
            p.drawText(r, Qt.AlignCenter, self.initial)
        p.restore()
        p.setPen(QPen(QColor(self.ring), ring))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(r)


def paint_backdrop(widget, painter):
    """A főablak háttere: sötét alap, a sarkokban narancs és kék fénnyel (a koncepciótervhez hasonlóan)."""
    w, h = widget.width(), widget.height()
    painter.fillRect(widget.rect(), QColor(BG))
    for cx, cy, rad, col in ((0, h, h * 0.9, QColor(255, 120, 20, 70)), (0, 0, h * 0.6, QColor(255, 120, 20, 40)),
                             (w, h * 0.25, h * 0.8, QColor(40, 120, 255, 55)), (w, h, h * 0.7, QColor(255, 120, 20, 35))):
        g = QRadialGradient(QPointF(cx, cy), rad)
        g.setColorAt(0, col)
        g.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(widget.rect(), QBrush(g))
