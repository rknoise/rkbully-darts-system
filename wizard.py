"""Kalibrációs varázsló: élő kameraképpel segít a táblát és a fényeket a felismerő modellnek megfelelően beállítani.

A kép zöld (minden rendben), sárga (figyelmeztetés) vagy piros (javítandó) kerettel jelzi az állapotot, mellette
pipás lista mutatja, mi rendben és mi nem, szöveges teendőkkel. A négy kalibrációs pont húzható (vagy a program
megkeresi a táblát), a tábla rajza élőben követi. A mentett kalibrációt a betanító is használja."""
import json
import threading
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
                               QWidget)

import camcheck as cc
import trainer as tr
from theme import GREEN, MUTED, RED, YELLOW

try:
    import cv2
except ImportError:                                    # pragma: no cover
    cv2 = None

LEVEL_COLOR = {cc.OK: GREEN, cc.WARN: YELLOW, cc.BAD: RED, cc.NONE: "#5b6390"}
HANDLE_HELP = {"20": "5 | 20 drót (felül)", "6": "13 | 6 drót (jobbra)", "3": "17 | 3 drót (alul)", "11": "8 | 11 drót (balra)"}
PLACEMENT = (
    "1.  Rögzítsd a telefont vagy a webkamerát állványra a tábla elé (kézben tartva remeg a kép).\n"
    "2.  A tábla közepe a kép közepén legyen, és a kép ~70-90%-át töltse ki. A 20-as szám legyen felül.\n"
    "3.  Két kameránál a tábla két oldalán, kb. 30-45°-ban helyezd el őket, hogy a nyilak mindkettőről látszanak.\n"
    "4.  Világítsd meg a táblát szemből és egyenletesen, tükröződés és erős árnyék nélkül.")


# ───────────── tárolás ─────────────
def load_store(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and isinstance(data.get("cameras"), dict) else {"cameras": {}}
    except Exception:
        return {"cameras": {}}


def save_calibration(path, camera, points, size):
    """Egy kamera kalibrációja a közös fájlba, a kép méretére normalizálva (így felbontásváltásnál is érvényes)."""
    store = load_store(path)
    store["cameras"][str(camera)] = {"points": {n: [x / size, y / size] for n, (x, y) in points.items()}, "saved": time.time()}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(store, indent=1), encoding="utf-8")


def saved_points(path, camera, size):
    """A kamera mentett kalibrációja pixelben az adott képmérethez, vagy None."""
    entry = load_store(path)["cameras"].get(str(camera))
    try:
        pts = {n: (float(x) * size, float(y) * size) for n, (x, y) in entry["points"].items() if n in tr.CAL_NAMES}
    except Exception:
        return None
    return pts if len(pts) == 4 else None


# ───────────── a kép megjelenítése húzható pontokkal ─────────────
class FrameView(QWidget):
    """Egy kép (BGR) arányosan kifeszítve, rárajzolt vonalakkal és húzható pontokkal. Koordináták: a kép pixelei."""
    clicked = Signal(float, float, int)                # kép-koordináta, gomb (1 bal, 2 jobb)
    handle_moved = Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 270)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.qimg, self._buf, self.img_size = None, None, (0, 0)
        self.lines, self.markers, self.handles = [], [], {}
        self.handle_text = {}
        self.border, self.caption, self._drag = None, "", None

    def set_frame(self, bgr):
        h, w = bgr.shape[:2]
        rgb = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        self._buf = rgb                                # a QImage nem másol: a puffernek élnie kell
        self.qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        self.img_size = (w, h)
        self.update()

    def clear_frame(self):
        self.qimg, self._buf, self.img_size = None, None, (0, 0)
        self.update()

    def _geom(self):
        w, h = self.img_size
        if not w or not h:
            return 1.0, 0.0, 0.0
        m = 8
        s = min((self.width() - 2 * m) / w, (self.height() - 2 * m) / h)
        return s, (self.width() - w * s) / 2, (self.height() - h * s) / 2

    def to_view(self, x, y):
        s, ox, oy = self._geom()
        return QPointF(ox + x * s, oy + y * s)

    def to_img(self, pos):
        s, ox, oy = self._geom()
        w, h = self.img_size
        return min(max((pos.x() - ox) / s, 0.0), float(w)), min(max((pos.y() - oy) / s, 0.0), float(h))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#05070f"))
        s, ox, oy = self._geom()
        if self.qimg is not None:
            w, h = self.img_size
            p.drawImage(QRectF(ox, oy, w * s, h * s), self.qimg)
            for pts, color, width in self.lines:
                poly = QPolygonF([self.to_view(x, y) for x, y in pts])
                p.setPen(QPen(QColor(color), width))
                p.drawPolyline(poly)
            for x, y, color, text in self.markers:
                c = self.to_view(x, y)
                p.setPen(QPen(QColor(color), 2))
                p.drawEllipse(c, 9, 9)
                p.drawLine(QPointF(c.x() - 14, c.y()), QPointF(c.x() + 14, c.y()))
                p.drawLine(QPointF(c.x(), c.y() - 14), QPointF(c.x(), c.y() + 14))
                if text:
                    p.drawText(QPointF(c.x() + 12, c.y() - 12), text)
            for name, (x, y) in self.handles.items():
                c = self.to_view(x, y)
                p.setPen(QPen(QColor("#ffffff"), 2))
                p.setBrush(QColor(255, 138, 31, 200))
                p.drawEllipse(c, 11, 11)
                f = QFont(self.font())
                f.setBold(True)
                f.setPixelSize(13)
                p.setFont(f)
                p.drawText(QRectF(c.x() - 11, c.y() - 11, 22, 22), Qt.AlignCenter, name)
                p.setBrush(Qt.NoBrush)
        if self.border:
            p.setPen(QPen(QColor(self.border), 7))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(self.rect()).adjusted(3, 3, -3, -3))
        if self.caption:
            f = QFont(self.font())
            f.setPixelSize(16)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("#eef1ff"))
            p.drawText(QRectF(self.rect()).adjusted(24, 24, -24, -24), Qt.AlignCenter | Qt.TextWordWrap, self.caption)

    def _handle_at(self, pos):
        for name, (x, y) in self.handles.items():
            c = self.to_view(x, y)
            if (c.x() - pos.x()) ** 2 + (c.y() - pos.y()) ** 2 <= 18 ** 2:
                return name
        return None

    def mousePressEvent(self, e):
        if not self.qimg:
            return
        name = self._handle_at(e.position()) if e.button() == Qt.LeftButton else None
        if name:
            self._drag = name
        else:
            x, y = self.to_img(e.position())
            self.clicked.emit(x, y, 1 if e.button() == Qt.LeftButton else 2)

    def mouseMoveEvent(self, e):
        if self._drag:
            x, y = self.to_img(e.position())
            self.handles[self._drag] = (x, y)
            self.handle_moved.emit(self._drag, x, y)
            self.update()
        elif self.qimg:
            self.setCursor(Qt.OpenHandCursor if self._handle_at(e.position()) else Qt.ArrowCursor)

    def mouseReleaseEvent(self, _):
        self._drag = None


# ───────────── a modell háttérellenőrzése ─────────────
class ModelProbe:
    """Háttérszál: a betöltött modellel ~2 képkockát/mp elemez, hogy a varázsló lássa, felismeri-e a kalibrációs pontokat.
    A modell betöltése is a szálban fut (lassú lehet), hiba esetén csendben leáll."""

    def __init__(self, get_backend, get_frame, period=0.5):
        self.get_backend, self.get_frame, self.period = get_backend, get_frame, period
        self.det, self.state, self.error = None, "loading", None
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            backend = self.get_backend()
            if backend is None:
                self.state = "none"
                return
            self.state = "ok"
            while not self._stop.is_set():
                f = self.get_frame()
                if f is not None:
                    self.det = backend.detect(tr.square_crop(f)[0])
                self._stop.wait(self.period)
        except Exception as e:                           # a varázsló modell nélkül is használható
            self.state, self.error = "error", str(e)

    def stop(self):
        self._stop.set()


# ───────────── a varázsló ─────────────
class CalibrationWizard(QDialog):
    """sources: [{"label", "text", "get"}] – a kamerák (a get a legfrissebb BGR képkockát adja). get_backend: modell
    betöltése (vagy None). store: a kalibrációs fájl útvonala. add_camera: a „Kamera hozzáadása” művelete (vagy None)."""

    def __init__(self, parent, sources, store, get_backend=None, add_camera=None, hide_checked=False, startup=False,
                 current=0, clock=time.monotonic):
        super().__init__(parent)
        self.setWindowTitle("Kalibrációs varázsló")
        self.resize(1180, 760)
        self.sources, self.store, self.add_camera, self.clock = list(sources), Path(store), add_camera, clock
        self.get_backend = get_backend
        self.current = min(max(int(current), 0), max(len(self.sources) - 1, 0))
        self.saved_any, self.norm = False, {}
        self.checks, self.cal, self.sq, self._sig = [], None, None, None
        self.shake, self._last_check, self.probe = cc.ShakeMeter(), -1.0, None
        self.estimate_msg = ""

        self.view = FrameView()
        self.view.handle_moved.connect(self.on_handle)
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setMinimumHeight(54)
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self.pick_camera)
        self.add_btn = QPushButton("⊕  Kamera hozzáadása")
        self.add_btn.clicked.connect(self.on_add)
        top = QHBoxLayout()
        top.addWidget(QLabel("Kamera:"))
        top.addWidget(self.combo, 1)
        top.addWidget(self.add_btn)
        left = QVBoxLayout()
        left.addLayout(top)
        left.addWidget(self.view, 1)
        left.addWidget(self.banner)

        title = QLabel("🧭  Kalibrációs varázsló")
        title.setObjectName("kicker")
        howto = QLabel(PLACEMENT)
        howto.setWordWrap(True)
        howto.setObjectName("muted")
        self.help = QLabel("Húzd a 4 narancs jelet a külső dupla gyűrű szélére, az itt jelölt drótokhoz:  "
                           + "  ·  ".join(f"{n}: {t}" for n, t in HANDLE_HELP.items()))
        self.help.setWordWrap(True)
        self.rows = {}
        self.list = QVBoxLayout()
        self.list.setSpacing(3)
        self.todo = QLabel()
        self.todo.setWordWrap(True)
        self.todo.setStyleSheet(f"color: {YELLOW}; font-weight: 600;")
        self.find_btn = QPushButton("🔍  Tábla automatikus keresése")
        self.find_btn.clicked.connect(self.auto_find)
        self.reset_btn = QPushButton("↺  Alaphelyzet")
        self.reset_btn.clicked.connect(self.reset_points)
        self.save_btn = QPushButton("💾  Kalibráció mentése")
        self.save_btn.setObjectName("go")
        self.save_btn.clicked.connect(self.save)
        self.hide_box = QCheckBox("Többé ne ajánlja fel induláskor")
        self.hide_box.setChecked(bool(hide_checked))
        self.close_btn = QPushButton("Bezárás")
        self.close_btn.clicked.connect(self.accept)
        tools = QHBoxLayout()
        tools.addWidget(self.find_btn)
        tools.addWidget(self.reset_btn)
        foot = QHBoxLayout()
        foot.addWidget(self.hide_box)
        foot.addStretch()
        foot.addWidget(self.close_btn)
        right = QVBoxLayout()
        for w in (title, howto, self.help):
            right.addWidget(w)
        right.addLayout(tools)
        right.addLayout(self.list)
        right.addWidget(self.todo)
        right.addStretch(1)
        right.addWidget(self.save_btn)
        right.addLayout(foot)
        panel = QWidget()
        panel.setFixedWidth(400)
        panel.setLayout(right)
        lay = QHBoxLayout(self)
        lay.addLayout(left, 1)
        lay.addWidget(panel)

        self.fill_sources()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(60)

    # ── kamerák ──
    def fill_sources(self):
        self.combo.blockSignals(True)
        self.combo.clear()
        for s in self.sources:
            self.combo.addItem(s["label"])
        self.combo.setCurrentIndex(self.current if self.sources else -1)
        self.combo.blockSignals(False)
        self.combo.setVisible(len(self.sources) > 1)
        self.add_btn.setVisible(self.add_camera is not None)
        self.start_probe()
        self.load_points()

    def set_sources(self, sources):
        """A kamerák listája megváltozott (pl. kamerát adtak hozzá a varázslóból)."""
        self.sources = list(sources)
        self.current = min(self.current, max(len(self.sources) - 1, 0))
        self.fill_sources()

    def on_add(self):
        if self.add_camera:
            self.add_camera()

    def pick_camera(self, i):
        if 0 <= i < len(self.sources):
            self.current = i
            self.start_probe()
            self.load_points()

    def frame(self):
        if not self.sources:
            return None
        try:
            return self.sources[self.current]["get"]()
        except Exception:
            return None

    def start_probe(self):
        if self.probe:
            self.probe.stop()
            self.probe = None
        if self.get_backend is not None and self.sources:
            self.probe = ModelProbe(self.get_backend, self.frame)

    def key(self):
        return self.sources[self.current]["text"] if self.sources else ""

    # ── pontok ──
    def load_points(self):
        """A kamera mentett kalibrációja, vagy a kiinduló becslés."""
        self.norm = {}
        self.sq = None
        self._sig = None
        self.cal = None
        self.shake = cc.ShakeMeter()
        self.estimate_msg = ""

    def init_points(self, size):
        saved = saved_points(self.store, self.key(), size)
        pts = saved or tr.initial_points(size)
        self.norm = {n: (x / size, y / size) for n, (x, y) in pts.items()}

    def points(self, size):
        return {n: (x * size, y * size) for n, (x, y) in self.norm.items()}

    def on_handle(self, name, x, y):
        size = self.view.img_size[0] or 1
        self.norm[name] = (x / size, y / size)
        self._sig = None
        self._last_check = -1.0                          # azonnal újraszámol

    def reset_points(self):
        if self.sq is not None:
            size = self.sq.shape[0]
            self.norm = {n: (x / size, y / size) for n, (x, y) in tr.initial_points(size).items()}
            self.estimate_msg = ""
            self._last_check = -1.0

    def auto_find(self):
        if self.sq is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            est = cc.estimate_points(self.sq)
        finally:
            QApplication.restoreOverrideCursor()
        if est is None:
            self.estimate_msg = ("Nem találtam meg a táblát a képen. Győződj meg róla, hogy a 20-as felül van, és a tábla "
                                 "jól látszik; vagy húzd a pontokat kézzel.")
        else:
            size = self.sq.shape[0]
            self.norm = {n: (x / size, y / size) for n, (x, y) in est.items()}
            self.estimate_msg = "Megtaláltam a táblát. Ellenőrizd, és ha kell, finomítsd a pontokat húzással."
        self._last_check = -1.0

    # ── élő frissítés ──
    def tick(self):
        f = self.frame()
        if f is None:
            self.sq = None
            self.view.clear_frame()
            self.view.border, self.view.lines, self.view.handles = None, [], {}
            if not self.sources:
                self.view.caption = ("Még nincs kamera hozzáadva.\n\nHelyezd el a telefont vagy a webkamerát (lásd jobbra), "
                                     "majd add hozzá a ⊕ gombbal.")
            else:
                self.view.caption = "Kapcsolódás a kamerához…"
            self.set_banner("A kalibráláshoz élő kép kell.", cc.NONE)
            self.render_checks([], None)
            self.save_btn.setEnabled(False)
            self.find_btn.setEnabled(False)
            self.reset_btn.setEnabled(False)
            return
        self.view.caption = ""
        sq = tr.square_crop(f)[0]
        size = sq.shape[0]
        if not self.norm:
            self.init_points(size)
        self.sq = sq
        self.view.set_frame(sq)
        self.find_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        self.shake.feed(sq)
        self.cal = tr.Calibration(self.points(size), size)
        problem = self.cal.problem()
        now = self.clock()
        if problem is None and now - self._last_check >= 0.25:
            self._last_check = now
            self.checks = cc.analyze(sq, self.cal) + [self.shake.check(), self.model_check()]
        elif problem is not None:
            self.checks = []
        level = cc.overall(self.checks) if self.checks else (cc.BAD if problem else cc.NONE)
        self.view.border = LEVEL_COLOR[level]
        rings, wires = self.cal.shapes() if problem is None else ([], [])
        color = LEVEL_COLOR[level]
        self.view.lines = [(np.vstack([r, r[:1]]), color, 2) for r in rings] + [(w_, "#70ffffff", 1) for w_ in wires]
        self.view.handles = {n: self.points(size)[n] for n in tr.CAL_NAMES}
        self.view.update()
        self.update_texts(problem, level)
        self.save_btn.setEnabled(problem is None)

    def model_check(self):
        if self.probe is None or self.probe.state in ("loading", "none", "error"):
            return cc.Check("model", cc.NONE, "A modell látja a 4 kalibrációs pontot")
        return cc.model_check(self.probe.det, self.cal)

    def update_texts(self, problem, level):
        if problem:
            self.set_banner("✖  " + problem, cc.BAD)
            self.render_checks([], problem)
            self.todo.setText(self.estimate_msg)
            return
        todo = cc.instructions(self.checks)
        if level == cc.OK:
            self.set_banner("✔  Minden rendben: a tábla és a fény megfelelő. Mentsd a kalibrációt!", cc.OK)
        elif level == cc.WARN:
            self.set_banner("⚠  Használható, de javítható: " + todo[0] if todo else "⚠  Használható, de javítható.", cc.WARN)
        else:
            self.set_banner("✖  Javítandó: " + todo[0] if todo else "✖  Javítandó.", cc.BAD)
        self.render_checks(self.checks, None)
        parts = ["➜ " + t for t in todo[:3]]
        if self.estimate_msg:
            parts.append(self.estimate_msg)
        self.todo.setText("\n\n".join(parts))

    def set_banner(self, text, level):
        color = LEVEL_COLOR[level]
        self.banner.setText(text)
        self.banner.setStyleSheet(f"background: rgba(0,0,0,120); border: 2px solid {color}; border-radius: 10px; "
                                  f"padding: 8px 12px; font-size: 15px; font-weight: 700; color: #fff;")

    def render_checks(self, checks, problem):
        sig = tuple((c.key, c.level) for c in checks), bool(problem)
        if sig == self._sig:
            return
        self._sig = sig
        while self.list.count():
            w = self.list.takeAt(0).widget()
            if w:
                w.hide()                                      # azonnal eltűnjön (a törlés csak később fut le)
                w.setParent(None)
                w.deleteLater()
        for c in checks:
            lb = QLabel(f"<span style='color:{LEVEL_COLOR[c.level]}; font-weight:900'>{c.icon}</span>  {c.title}"
                        + ("" if c.level != cc.NONE else f"  <span style='color:{MUTED}'>(nem ellenőrizhető)</span>"))
            self.list.addWidget(lb)

    # ── mentés ──
    def save(self):
        if self.sq is None or self.cal is None or self.cal.problem() is not None:
            return
        save_calibration(self.store, self.key(), self.cal.points, self.cal.size)
        self.saved_any = True
        self.estimate_msg = "✔ A kalibráció elmentve ehhez a kamerához."
        self._last_check = -1.0

    def hide_offer(self):
        return self.hide_box.isChecked()

    def done(self, result):
        self.timer.stop()
        if self.probe:
            self.probe.stop()
        super().done(result)

