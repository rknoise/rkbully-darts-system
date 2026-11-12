#!/usr/bin/env python3
"""RKBully Darts System – többjátékos darts kezelőfelület (max. 8 játékos)

Telepítés:  pip install -r requirements.txt
Indítás:    python rkbully.py
Kamerás dobásfelismerés (nem kötelező):  pip install ultralytics  +  modellfájl, lásd README.md
"""
import gc
import html
import json
import math
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QEventLoop, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QIcon, QImage, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QInputDialog, QLabel, QMessageBox, QProgressBar, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

try:
    import cv2
except ImportError:
    cv2 = None

import ask
import finish
import fusion
import history
import options
import profiles as pf
import review as rv_mod
import sounds
import speech
import stats
import trainer_ui
import vision
import welcome
import wizard
from appinfo import APP_NAME, SUBTITLE, TAGLINE
from statsview import StatsDialog
from games import GROUPS, MODES, X01, apply_round, checkout_routes, label
from theme import Avatar, BLUE, Card, GREEN, MUTED, ORANGE, RED, YELLOW, build_qss, glow, paint_backdrop

MODE_BY_ID = {m.id: m for m in MODES}
APP_DIR = Path(__file__).resolve().parent
CFG_FILE = Path.home() / ".rkbully" / "settings.json"
LOGO_FILE = APP_DIR / "assets" / "rkbully.png"
APP_ID = "RKBully.Darts.App"          # Windows: ettől lesz saját az ikon a tálcán, nem a Python-é
MAX_CAMS = 3
REF_W, REF_H = 1600, 900              # erre a méretre tervezett a felület; kisebb/nagyobb ablaknál arányosan skálázódik


def set_app_id():
    """Windowson külön alkalmazásazonosító, különben a tálcán a Python ikonja látszik. Máshol nem csinál semmit."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def logo_pixmap():
    """A logó képe (üres, ha a fájl hiányzik: a program ikon nélkül is működik)."""
    pm = QPixmap(str(LOGO_FILE))
    return pm if not pm.isNull() else None


def load_cfg():
    try:
        return json.loads(CFG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cfg(cfg):
    try:
        CFG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CFG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass                                  # a beállítások mentése sosem állíthatja meg a játékot


QSS = build_qss(1.0)


def dispose(win):
    """Az ablak szabályos lebontása. Nélküle a főablak az értelmező leállásakor, véletlen sorrendben semmisül meg, és a
    PySide6 ilyenkor időnként összeomlik (kilépéskor hibaablak). Offscreen teszteken 100 futásból ~15-ben reprodukálható."""
    win.close()
    win.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


def clear(lay):
    """Egy elrendezés tartalmának törlése. Csak widgetek vannak benne (a sorok és cellák saját widgetbe csomagolva),
    mert a dinamikusan kivett al-elrendezések a PySide6-ban kilépéskor összeomlást okoztak."""
    while lay.count():
        item = lay.takeAt(0)
        w = item.widget()
        if w:
            w.hide()
            w.setParent(None)            # azonnal eltűnik (a deleteLater csak később fut le)
            w.deleteLater()


def rules_html(mode, n_players):
    """A játék leírása az infóablakhoz: hányan játszhatják, és hogyan kell játszani."""
    esc = html.escape
    if n_players < mode.min_players:
        now = f"<span style='color:#ff8a8a'>✗ Most {n_players} játékos van: ehhez a játékhoz legalább {mode.min_players} kell.</span>"
    else:
        now = f"<span style='color:#38e07b'>✓ Most {n_players} játékos van beállítva: ez megfelel.</span>"
    parts = [
        f"<div style='font-size:24px; font-weight:800; color:#ff9d2e;'>{esc(mode.name)}</div>",
        f"<div style='color:#9fb0ff; margin-bottom:6px;'>{esc(mode.group)} játék</div>",
        f"<p style='font-size:16px;'>👥 <b>Játékosok száma: {esc(mode.players_text())}</b><br>{now}</p>",
        "<div style='font-size:17px; font-weight:800; color:#ffb454; margin-top:6px;'>Hogyan kell játszani?</div>",
    ]
    for head, body in mode.rules:
        parts.append(f"<p style='margin:6px 0;'><b style='color:#ffb454;'>{esc(head)}</b><br>{esc(body)}</p>")
    return "".join(parts)


class InfoDialog(QDialog):
    """Egy játékmód leírása: játékosszám és szabályok."""

    def __init__(self, parent, mode, n_players):
        super().__init__(parent)
        self.setWindowTitle(f"Szabályok: {mode.name}")
        self.resize(620, 560)
        text = QLabel(rules_html(mode, n_players))
        text.setTextFormat(Qt.RichText)
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        text.setMargin(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(text)
        close = QPushButton("Rendben")
        close.setObjectName("go")
        close.clicked.connect(self.accept)
        lay = QVBoxLayout(self)
        lay.addWidget(scroll, 1)
        lay.addWidget(close)


def show_mode_info(parent, mode, n_players):
    InfoDialog(parent, mode, n_players).exec()


class ModeDialog(QDialog):
    """Játékmód-választó: csoportosított kártyák, mindegyiken ℹ gomb a szabályokkal."""

    def __init__(self, parent, current_id, n_players):
        super().__init__(parent)
        self.setWindowTitle("Játékmód választása")
        self.resize(1000, 720)
        self.picked, self.n_players = None, n_players
        inner = QWidget()
        col = QVBoxLayout(inner)
        for group in GROUPS:
            title = QLabel(group.upper())
            title.setStyleSheet("font-size: 15px; font-weight: 800; color: #ffb454; margin-top: 8px;")
            col.addWidget(title)
            grid = QGridLayout()
            grid.setSpacing(8)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            for k, mode in enumerate([m for m in MODES if m.group == group]):
                grid.addWidget(self._card(mode, mode.id == current_id), k // 2, k % 2)
            col.addLayout(grid)
        col.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(inner)
        note = QLabel("ℹ  Minden játéknál a kis ℹ gombbal megnézheted, hányan játszhatják, és hogyan kell játszani.")
        note.setStyleSheet("color: #9fb0ff;")
        lay = QVBoxLayout(self)
        lay.addWidget(note)
        lay.addWidget(scroll, 1)

    def _card(self, mode, current):
        card = Card("active" if current else "plain")
        esc = html.escape
        text = (f"<div style='font-size:17px; font-weight:800; color:#ff9d2e;'>{esc(mode.name)}</div>"
                f"<div>{esc(mode.desc)}</div><div style='color:#9fb0ff;'>👥 {esc(mode.players_text())}</div>")
        few = self.n_players < mode.min_players
        if few:
            text += f"<div style='color:#ffd23f;'>⚠ Most kevés a játékos (legalább {mode.min_players} kell)</div>"
        body = QLabel(text)
        body.setTextFormat(Qt.RichText)
        body.setWordWrap(True)
        body.setAttribute(Qt.WA_TransparentForMouseEvents)       # a kattintás a gombhoz érjen
        body.setStyleSheet("background: transparent;")
        pick = QPushButton()
        pick.setMinimumHeight(112 if few else 92)
        pick.setStyleSheet("border: none; background: transparent;")
        inner = QVBoxLayout(pick)
        inner.setContentsMargins(10, 6, 10, 6)
        inner.addWidget(body)
        pick.clicked.connect(lambda _, mid=mode.id: self.choose(mid))
        info = QPushButton("ℹ")
        info.setFixedSize(42, 42)
        info.setToolTip("Szabályok és játékosszám")
        info.clicked.connect(lambda _, m=mode: show_mode_info(self, m, self.n_players))
        lay = QHBoxLayout(card)
        lay.setContentsMargins(8, 8, 12, 8)
        lay.addWidget(pick, 1)
        lay.addWidget(info, 0, Qt.AlignTop)
        return card

    def choose(self, mode_id):
        self.picked = mode_id
        self.accept()


def draw_overlay(img, ov):
    """Rárajzolja a kalibrációs pontokat és a felismert nyilakat a kamerakép egy másolatára."""
    k = max(1.0, img.shape[1] / 900)
    if ov.get("square"):
        x0, y0, s = ov["square"]
        cv2.rectangle(img, (x0, y0), (x0 + s, y0 + s), (255, 255, 255), max(1, int(k)))
    for x, y, name in ov["cal"]:
        cv2.circle(img, (int(x), int(y)), int(8 * k), (60, 220, 60), max(2, int(2 * k)))
        cv2.putText(img, name, (int(x) + int(10 * k), int(y) - int(8 * k)), cv2.FONT_HERSHEY_SIMPLEX, 0.6 * k, (60, 220, 60), max(1, int(k)))
    for x, y, txt in ov["darts"]:
        cv2.circle(img, (int(x), int(y)), int(8 * k), (40, 40, 255), max(2, int(2 * k)))
        cv2.putText(img, txt, (int(x) + int(10 * k), int(y) + int(22 * k)), cv2.FONT_HERSHEY_SIMPLEX, 0.8 * k, (40, 40, 255), max(2, int(2 * k)))


def fmt_time(seconds):
    s = max(0, int(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def ultralytics_help(python_exe, app_dir):
    """A hiányzó dobásfelismerő csomag üzenete: pontos telepítési parancs ugyanahhoz a Pythonhoz, amivel a program fut."""
    exe = str(python_exe)
    if exe.lower().endswith("pythonw.exe"):                     # a parancsikon konzol nélküli Pythonja nem ír ki semmit
        exe = exe[:-len("pythonw.exe")] + "python.exe"
    return ("A dobásfelismeréshez két dolog kell:\n\n"
            "1.  az ultralytics csomag. Kattints duplán a Felismeres_telepitese.bat fájlra a program mappájában, "
            f"vagy futtasd:\n      \"{exe}\" -m pip install ultralytics\n\n"
            f"2.  egy YOLO modellfájl (.pt) a(z) {Path(app_dir) / 'models'} mappában. A program nem tartalmaz modellt.\n\n"
            "Telepítés után indítsd újra a programot. A részletek a README.md „Kamerás dobásfelismerés” részében vannak.")


class Cam(Card):
    """Egy kamera élő képe (USB webkamera vagy telefon IP-kamera stream)."""

    def __init__(self, title, src, text, on_close, on_detect):
        super().__init__("plain")
        self.src, self.text, self.service, self.title = src, text, None, title
        self.frame, self.alive, self.ok = None, True, None
        name = QLabel("📷  " + title)
        name.setObjectName("section")
        self.status = QLabel()
        x = QPushButton("✕")
        x.setObjectName("icon")
        x.setToolTip("Kamera eltávolítása")
        x.clicked.connect(lambda: on_close(self))
        top = QHBoxLayout()
        top.addWidget(name, 1)
        top.addWidget(self.status)
        top.addWidget(x)
        self.view = QLabel()
        self.view.setMinimumSize(1, 70)
        self.view.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)   # a kép mérete ne diktálja az elrendezést
        self.view.setAlignment(Qt.AlignCenter)
        self.det = QPushButton("🎯  Dobásfelismerés")
        self.det.setCheckable(True)
        self.det.clicked.connect(lambda checked: on_detect(self, checked))
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color: #9fb0ff; font-size: 12px;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        lay.addLayout(top)
        lay.addWidget(self.view, 1)
        lay.addWidget(self.det)
        lay.addWidget(self.info)
        threading.Thread(target=self.grab, daemon=True).start()

    def _open(self):
        if isinstance(self.src, int) and sys.platform == "win32":
            cap = cv2.VideoCapture(self.src, cv2.CAP_DSHOW)       # Windowson gyorsabban indul
        else:
            cap = cv2.VideoCapture(self.src)
        if isinstance(self.src, int):
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        return cap

    def grab(self):
        cap, fails = self._open(), 0
        while self.alive:
            ok, f = cap.read() if cap.isOpened() else (False, None)
            if ok:
                self.frame, fails = f, 0
            else:
                self.frame, fails = None, fails + 1
                time.sleep(0.3)
                if fails % 10 == 0:                              # megszakadt kapcsolat: újracsatlakozás
                    cap.release()
                    cap = self._open()
        cap.release()

    def update_view(self):
        f = self.frame
        ok = f is not None
        if ok != self.ok:
            self.ok = ok
            self.status.setText("● LIVE" if ok else "● NINCS KÉP")
            self.status.setStyleSheet(f"color: {GREEN if ok else RED}; font-weight: 800;")
            if not ok:
                self.view.setText("Kapcsolódás…")
        if self.service:
            err = self.service.error
            self.info.setText(("⚠ " + err) if err else self.service.overlay["status"])
        if ok:
            if self.service:
                f = f.copy()
                draw_overlay(f, self.service.overlay)
            h, w = f.shape[:2]
            rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
            img = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
            self.view.setPixmap(QPixmap.fromImage(img).scaled(self.view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


class Main(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        scr = QGuiApplication.primaryScreen()
        avail = scr.availableGeometry() if scr else QRect(0, 0, 1920, 1080)
        self.setMinimumSize(640, 420)
        self.resize(min(1500, int(avail.width() * 0.94)), min(900, int(avail.height() * 0.92)))   # sosem lóg ki a képernyőről
        self.k = 1.0
        self.logo_file, self.app_dir, self.avatar_dir = LOGO_FILE, APP_DIR, pf.AVATAR_DIR
        self.cfg = load_cfg()
        self.profiles, self.pids = pf.load(self.cfg)
        self.history_file = history.history_path(CFG_FILE)    # a beállításfájl mellett (a tesztek külön mappát használnak)
        self.history = history.load(self.history_file)
        self.game_pids, self._rec = [], None
        self.sound = sounds.SoundBoard(self.app_dir / "assets" / "sounds", bool(self.cfg.get("sound", True)),
                                       int(self.cfg.get("volume", 70)) / 100)
        self.sound.preload()
        self.speaker = speech.Announcer(bool(self.cfg.get("speech", True)))
        self._snd = (None, 0)                                 # (a játék azonosítója, hány dobás volt) az utolsó frissítéskor
        self.names = [self.profile_by_id(p)["name"] for p in self.pids]
        mid = self.cfg.get("mode_id")
        if mid not in MODE_BY_ID:                              # régi beállításfájl: sorszám alapján
            mid = MODES[min(max(int(self.cfg.get("mode", 1)), 0), len(MODES) - 1)].id
        self.mode_id = mid
        self.pad_visible = bool(self.cfg.get("pad", True))
        self.countdown = int(self.cfg.get("countdown", 60))
        self.paused, self.turn_key, self.turn_t0, self.pause_t = False, None, time.monotonic(), None
        self.fill_players(self.cur_mode().min_players)         # pl. Killerhez legalább 2 játékos kell
        self.mult, self.cams, self.service, self.backend = 1, [], None, None
        self.flash, self._sig = "", None
        self._end_for, self.end_force = None, False           # a meccs végi képernyő már megjelent-e ennél a játéknál
        self.game_mode_id, self.game_out = self.mode_id, True
        self.cramped, self.squeeze, self.help_has, self._styled, self._fitting = False, 0, False, False, False
        self.pad_forced, self._pad_sig = False, None
        self.fit_timer = QTimer(self)
        self.fit_timer.setSingleShot(True)
        self.fit_timer.timeout.connect(self.fit)
        self.review = self.new_review()

        # ── fejléc ──
        self.logo = QLabel("<span style='color:#e9edf8'>RK</span><span style='color:#ff8a1f'>Bully</span>")
        self.logo.setObjectName("logo")
        self.logo.setTextFormat(Qt.RichText)
        self.logo_sub = QLabel(SUBTITLE)
        self.logo_sub.setObjectName("logosub")
        self.logo_box = QVBoxLayout()
        self.logo_box.setSpacing(0)
        self.logo_box.addWidget(self.logo)
        self.logo_box.addWidget(self.logo_sub)
        self.mark = QLabel()
        pm = logo_pixmap()
        if pm is not None:
            self.setWindowIcon(QIcon(pm))
            self.mark.setPixmap(pm)
            self.mark.setScaledContents(True)
        else:
            self.mark.hide()
        self.tab_play = QPushButton("🏠  Játék")
        self.tab_stats = QPushButton("📊  Statisztikák")
        self.tab_play.setObjectName("tabon")                 # az aktív fül: külön azonosító (a dinamikus tulajdonság-szelektor
        self.tab_stats.setObjectName("tab")                  # a Qt stíluslap-motorjában memóriahibát okozott)
        self.tab_stats.clicked.connect(self.show_stats)
        self.conn = QLabel()
        self.clock = QLabel()
        self.snd_btn = QPushButton()
        self.snd_btn.setObjectName("icon")
        self.snd_btn.clicked.connect(lambda: self.set_sound(not self.sound.enabled))
        self.update_sound_button()
        self.gear = QPushButton("⚙")
        self.gear.setObjectName("icon")
        self.gear.setToolTip("Beállítások")
        self.gear.clicked.connect(lambda: self.open_options())
        quit_btn = QPushButton("⏻")
        quit_btn.setObjectName("icon")
        quit_btn.setToolTip("Kilépés")
        quit_btn.clicked.connect(self.close)
        self.head = QHBoxLayout()
        self.head.addWidget(self.mark)
        self.head.addLayout(self.logo_box)
        self.head.addStretch(2)
        self.head.addWidget(self.tab_play)
        self.head.addWidget(self.tab_stats)
        self.head.addStretch(3)
        for w in (self.conn, self.clock, self.snd_btn, self.gear, quit_btn):
            self.head.addWidget(w)
            self.head.addSpacing(8)

        # ── bal oszlop: kamerák ──
        self.left = QVBoxLayout()
        self.addcam = QPushButton("⊕  Kamera hozzáadása")
        self.addcam.setObjectName("addcam")
        self.addcam.clicked.connect(self.add_cam)
        self.left.addWidget(self.addcam)
        lw = QWidget()
        lw.setMinimumWidth(180)
        lw.setLayout(self.left)

        # ── közép ──
        self.title_lbl, self.hdr, self.timer_lbl = QLabel(), QLabel(), QLabel()
        self.title_lbl.setObjectName("kicker")
        self.hdr.setObjectName("section")
        self.timer_lbl.setObjectName("kicker")
        self.hdr.setAlignment(Qt.AlignCenter)
        self.timer_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        status = Card("plain")
        sl = QHBoxLayout(status)
        sl.setContentsMargins(16, 6, 16, 6)
        sl.addWidget(self.title_lbl, 2)
        sl.addWidget(self.hdr, 3)
        sl.addWidget(self.timer_lbl, 2)
        self.pause_top = QPushButton("⏸")
        self.pause_top.setObjectName("icon")
        self.pause_top.setToolTip("Szünet: megállítja a kör óráját (P)")
        self.pause_top.clicked.connect(self.toggle_pause)
        sl.addWidget(self.pause_top)

        self.who, self.big, self.stat, self.tbt = QLabel(), QLabel(), QLabel(), QLabel()
        self.who.setObjectName("who")
        self.big.setObjectName("big")
        self.stat.setObjectName("muted")
        self.tbt.setObjectName("section")
        self.banner = QLabel()
        self.banner.setObjectName("banner")
        self.banner.setAlignment(Qt.AlignCenter)
        self.big.setAlignment(Qt.AlignCenter)
        self.stat.setAlignment(Qt.AlignCenter)
        self.tbt.setAlignment(Qt.AlignCenter)
        glow(self.big, ORANGE, 40, 150)
        self.main_avatar = Avatar(64)
        self.player_card = Card("plain")
        pl = QVBoxLayout(self.player_card)
        pl.setContentsMargins(16, 10, 16, 8)
        who_row = QHBoxLayout()
        who_row.addWidget(self.main_avatar)
        who_row.addWidget(self.who)
        who_row.addStretch()
        who_row.addWidget(self.banner)
        pl.addLayout(who_row)
        pl.addWidget(self.big, 1)
        pl.addWidget(self.stat)

        row, self.tb, self.tcell = QHBoxLayout(), [], []
        for _ in range(3):
            t = QLabel()
            t.setAlignment(Qt.AlignCenter)
            cell = Card("quiet")
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(6, 8, 6, 8)
            cl.addWidget(t)
            self.tb.append(t)
            self.tcell.append(cell)
            row.addWidget(cell)

        self.help_card = Card("active")
        self.help_title, self.help_badge = QLabel(), QLabel()
        self.help_title.setObjectName("section")
        self.help_badge.setObjectName("muted")
        self.help_row = QHBoxLayout()
        hl = QVBoxLayout(self.help_card)
        hl.setContentsMargins(14, 8, 14, 10)
        hh = QHBoxLayout()
        hh.addWidget(self.help_title)
        hh.addStretch()
        hh.addWidget(self.help_badge)
        hl.addLayout(hh)
        hl.addLayout(self.help_row)

        self.strip_card = Card("plain")
        self.strip_row = QHBoxLayout(self.strip_card)
        self.strip_row.setContentsMargins(10, 6, 10, 6)

        self.pad_box = self._build_pad()

        self.center = QVBoxLayout()
        self.center.addWidget(status)
        self.center.addWidget(self.player_card, 5)
        row.setContentsMargins(0, 0, 0, 0)
        self.cells_box = QWidget()
        self.cells_box.setLayout(row)
        self.center.addWidget(self.tbt)
        self.center.addWidget(self.cells_box)
        self.center.addWidget(self._build_review_box())
        self.center.addWidget(self.help_card)
        self.center.addWidget(self.strip_card)
        self.center.addWidget(self.pad_box)
        cw = QWidget()
        cw.setMinimumWidth(340)
        cw.setLayout(self.center)

        # ── jobb oszlop: játékosok, legutóbbi dobások ──
        self.pcount, self.plist = QLabel(), QVBoxLayout()
        self.pcount.setObjectName("section")
        ph = QHBoxLayout()
        ph.addWidget(self.pcount)
        ph.addStretch()
        for txt, fn, tip in (("－", self.del_player, "Utolsó játékos kivétele"), ("＋", self.add_player, "Játékos hozzáadása")):
            b = QPushButton(txt)
            b.setObjectName("icon")
            b.setToolTip(tip)
            b.clicked.connect(fn)
            ph.addWidget(b)
        self.players_card = Card("plain")
        pc = QVBoxLayout(self.players_card)
        pc.setContentsMargins(12, 10, 12, 10)
        pc.addLayout(ph)
        pc.addLayout(self.plist)
        pc.addStretch()
        self.recent_title = QLabel("📊  Legutóbbi dobások")
        self.recent_title.setObjectName("section")
        self.recent_card = Card("plain")
        self.recent_box = QVBoxLayout()
        rc = QVBoxLayout(self.recent_card)
        rc.setContentsMargins(12, 10, 12, 10)
        rc.addWidget(self.recent_title)
        rc.addLayout(self.recent_box)
        rc.addStretch()
        right = QVBoxLayout()
        right.addWidget(self.players_card, 3)
        right.addWidget(self.recent_card, 2)
        rw = QWidget()
        rw.setMinimumWidth(210)
        rw.setLayout(right)

        # ── alsó sáv ──
        self.mode_btn, self.out = QPushButton(), QComboBox()
        self.mode_btn.setToolTip("Játékmód választása")
        self.mode_btn.clicked.connect(self.choose_mode)
        self.info_btn = QPushButton("ℹ")
        self.info_btn.setObjectName("icon")
        self.info_btn.setToolTip("Szabályok: hányan játszhatják és hogyan kell játszani")
        self.info_btn.clicked.connect(lambda: show_mode_info(self, self.cur_mode(), len(self.names)))
        self.out.addItems(["Double Out", "Straight Out"])
        self.out.setCurrentIndex(int(self.cfg.get("out", 0)) % 2)
        self.out.setToolTip("Játékbeállítás: kiszállás módja (301/501/701)")
        self.go = QPushButton("▶   Játék indítása")
        self.go.setObjectName("go")
        self.go.clicked.connect(self.new_game)
        self.pause_btn = QPushButton("⏸  Szünet")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.undo_btn = QPushButton("↶  Visszavonás")
        self.undo_btn.clicked.connect(self.undo)
        self.last_btn = QPushButton("↻  Legutóbbi meccs")
        self.last_btn.clicked.connect(self.restart_last_match)
        self.pad_btn = QPushButton("⌨  Kézi bevitel")
        self.pad_btn.setCheckable(True)
        self.pad_btn.setChecked(self.pad_visible)
        self.pad_btn.toggled.connect(self.set_pad_visible)
        fs = QPushButton("⛶  Teljes képernyő")
        fs.clicked.connect(self.toggle_fullscreen)
        self.tagline = QLabel(TAGLINE)
        self.tagline.setStyleSheet("color: #ff8a1f; font-style: italic; font-weight: 700;")
        self.bar = QHBoxLayout()
        self.bar.addWidget(self.go, 3)
        for w, st in ((self.pause_btn, 1), (self.undo_btn, 1), (self.last_btn, 1), (self.mode_btn, 2), (self.info_btn, 0), (self.out, 1),
                      (self.pad_btn, 1), (fs, 1)):
            self.bar.addWidget(w, st)
        self.bar.addWidget(self.tagline, 1, Qt.AlignRight | Qt.AlignBottom)

        self.body = QHBoxLayout()
        self.body.addWidget(lw, 30)
        self.body.addWidget(cw, 52)
        self.body.addWidget(rw, 30)
        self.root = QVBoxLayout(self)
        self.root.addLayout(self.head)
        self.root.addLayout(self.body, 1)
        self.root.addLayout(self.bar)

        for key in (Qt.Key_Return, Qt.Key_Enter):
            QShortcut(QKeySequence(key), self, self.accept_round)
        for key in (Qt.Key_P, Qt.Key_Pause):
            QShortcut(QKeySequence(key), self, self.toggle_pause)
        self.new_game()
        self.out.currentIndexChanged.connect(self.new_game)
        for text in self.cfg.get("cameras", [])[:MAX_CAMS]:
            self.add_cam_source(str(text))
        self.update_left()
        self.fit()
        timer = QTimer(self)
        timer.timeout.connect(self.tick)
        timer.start(40)

    # ───────────── megjelenés ─────────────
    def paintEvent(self, _):
        painter = QPainter(self)
        paint_backdrop(self, painter)

    def set_scale(self, k):
        """Betűk, térközök, méretek a k szorzóval; a tartalom újraépül."""
        self.k = k
        # A stíluslap az egész alkalmazásra érvényes (a párbeszédablakokra is). Közvetlenül a főablakra állítva a Qt
        # stíluslap-motorja a kilépéskor véletlenszerűen memóriahibával állt le (offscreen teszteken reprodukálva).
        QApplication.instance().setStyleSheet(build_qss(k))
        m = int(16 * k)
        self.root.setContentsMargins(m, int(10 * k), m, int(10 * k))
        self.root.setSpacing(int(10 * k))
        self.body.setSpacing(int(14 * k))
        for lay in (self.center, self.left, self.plist):
            lay.setSpacing(int(8 * k))
        self.bar.setSpacing(int(10 * k))
        side = int(54 * k)
        self.mark.setFixedSize(side, side)
        self.go.setMinimumHeight(int(58 * k))
        self.mode_btn.setMinimumHeight(int(58 * k))
        self.refresh()
        self.settle()

    def settle(self):
        """Lefuttatja a függő elrendezési eseményeket, hogy a méretek (fits) a valós állapotot mutassák."""
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        self.layout().invalidate()
        self.layout().activate()

    def fits(self):
        need = self.layout().minimumSize()
        return need.height() <= self.height() and need.width() <= self.width()

    def fit(self):
        """A felület az ablakhoz igazodik. A méretarány az ablak méretéből jön; ha így is kilógna (kis képernyő vagy sok
        látható elem), sorban: kicsit kisebb méret, a segédlet és az átlagsáv elrejtése, a kézi bevitel összecsukása,
        végül még kisebb méret. Így semmi sem lóg ki az ablakból vagy a képernyőről."""
        if self._fitting:
            return
        self._fitting = True
        try:
            k = base = max(0.55, min(1.6, min(self.width() / REF_W, self.height() / REF_H)))
            self.cramped, self.squeeze = False, 0
            self.logo_sub.setVisible(self.width() >= 760 and self.height() >= 560)
            self.last_btn.setVisible(self.width() >= 1180)            # szűk ablakban a ritkább gombok átadják a helyet
            self.tagline.setVisible(self.width() >= 1150)           # keskeny ablakban a díszítő felirat átadja a helyet
            if abs(k - self.k) >= 0.02 or not self._styled:
                self._styled = True
                self.set_scale(k)
            else:
                self.update_pad()
                self.settle()
            for _ in range(16):
                if self.fits():
                    break
                if k > 0.72:                                         # először csak kicsit kisebbre skálázunk
                    k = max(0.72, k * 0.95)
                    self.set_scale(k)
                elif self.squeeze < 1 and (self.strip_card.isVisibleTo(self) or self.help_card.isVisibleTo(self)):
                    self.squeeze = 1                                 # a segédlet és az átlagsáv átadja a helyet
                    self.update_pad()
                    self.settle()
                elif self.pad_box.isVisibleTo(self) and not self.cramped and not self.pad_forced and not self.editing():
                    self.cramped = True                              # a kézi bevitel összecsukódik
                    self.update_pad()
                    self.settle()
                elif k > 0.6:
                    k = max(0.6, k * 0.94)
                    self.set_scale(k)
                elif self.squeeze < 2:
                    self.squeeze = 2                                 # végszükségben a dobáskártyák is (a jóváhagyó panelen látszanak)
                    self.update_pad()
                    self.settle()
                elif k > 0.55:
                    k = max(0.55, k * 0.94)
                    self.set_scale(k)
                else:
                    break
            for _ in range(6):                                       # ha maradt hely, a méret visszanő (legfeljebb az alapméretig)
                up = min(base, k * 1.07)
                if up <= k + 0.005 or not self.fits():
                    break
                self.set_scale(up)
                if not self.fits():
                    self.set_scale(k)
                    break
                k = up
        finally:
            self._fitting = False

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.fit_timer.start(70)                     # húzás közben nem számolunk újra minden képpontnál

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    # ───────────── kézi bevitel ─────────────
    def _build_pad(self):
        box = Card("quiet")
        kp, grp, self.mbtn = QGridLayout(box), QButtonGroup(self), []
        kp.setContentsMargins(10, 8, 10, 8)
        kp.setSpacing(6)
        for txt, v, col, span in (("Szimpla", 1, 0, 4), ("Dupla", 2, 4, 4), ("Tripla", 3, 8, 3)):
            b = QPushButton(txt)
            b.setObjectName("pad")
            b.setCheckable(True)
            b.setChecked(v == 1)
            b.clicked.connect(lambda _, v=v: setattr(self, "mult", v))
            grp.addButton(b)
            self.mbtn.append(b)
            kp.addWidget(b, 0, col, 1, span)
        for n in range(1, 21):
            b = QPushButton(str(n))
            b.setObjectName("pad")
            b.clicked.connect(lambda _, n=n: self.hit(n))
            kp.addWidget(b, 1 + (n - 1) // 10, (n - 1) % 10)
        for r, (txt, n) in enumerate((("Bull", 25), ("Mellé", 0))):
            b = QPushButton(txt)
            b.setObjectName("pad")
            b.clicked.connect(lambda _, n=n: self.hit(n))
            kp.addWidget(b, 1 + r, 10)
        return box

    def set_pad_visible(self, on):
        """A „Kézi bevitel” gomb. Kis képernyőn (összecsukott állapotban) csak erre a munkamenetre nyit, a mentett
        beállítás ilyenkor nem változik. Amit a játékos kérésre kinyitott, azt a program nem csukja be magától."""
        on = bool(on)
        self.pad_forced = on
        if not self.cramped:
            self.pad_visible = on
            self.cfg["pad"] = on
            self.save_state()
        self.update_pad()

    def editing(self):
        return self.review.selected is not None

    def update_pad(self):
        """A kézi bevitel kapcsolható; egy nyíl javításakor magától megjelenik. Ha az ablak kicsi, a fit() összecsukja
        (a gomb ilyenkor is megnyitja), és a segédlet meg az átlagsáv átadja a helyét."""
        show = self.editing() or self.pad_forced or (self.pad_visible and not self.cramped)
        self.pad_btn.blockSignals(True)
        self.pad_btn.setChecked(bool(show))
        self.pad_btn.blockSignals(False)
        self.pad_box.setVisible(bool(show))
        self.strip_card.setVisible(self.squeeze < 1)
        self.help_card.setVisible(self.help_has and self.squeeze < 1)
        self.tbt.setVisible(self.squeeze < 2)
        self.cells_box.setVisible(self.squeeze < 2)
        sig = (self.review.active, bool(show))
        if sig != self._pad_sig:                      # megjelent/eltűnt valami: az elrendezést újra kell illeszteni
            self._pad_sig = sig
            if not self._fitting:
                self.fit_timer.start(0)                   # a következő eseményciklusban, még rajzolás előtt

    # ───────────── kamerás kör jóváhagyása ─────────────
    def new_review(self):
        return rv_mod.RoundReview(countdown=self.countdown, auto=self.approval_idx == 0)

    @property
    def approval_idx(self):
        return int(self.cfg.get("approval", 0)) % 2

    def set_approval(self, idx):
        self.cfg["approval"] = int(idx) % 2
        self.review.auto = self.approval_idx == 0
        self.save_state()

    def set_countdown(self, seconds):
        self.countdown = int(seconds)
        self.review.countdown = self.countdown
        self.cfg["countdown"] = self.countdown
        self.save_state()

    def _build_review_box(self):
        self.rv_box = Card("review")
        self.rv_head, self.rv_time, self.rv_sum, self.rv_hint = QLabel(), QLabel(), QLabel(), QLabel()
        self.rv_head.setStyleSheet("font-size: 15px; font-weight: 700; color: #8cc8ff;")
        self.rv_time.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffd08a;")
        self.rv_time.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.rv_sum.setStyleSheet("font-size: 22px; font-weight: 800;")
        self.rv_sum.setAlignment(Qt.AlignCenter)
        self.rv_hint.setStyleSheet("color: #9fb0ff;")
        self.rv_hint.setWordWrap(True)
        self.rv_bar = QProgressBar()
        self.rv_bar.setTextVisible(False)
        self.rv_bar.setFixedHeight(8)
        top = QHBoxLayout()
        top.addWidget(self.rv_head)
        top.addStretch()
        top.addWidget(self.rv_time)
        darts, self.rv_btns = QHBoxLayout(), []
        for i in range(3):
            b = QPushButton()
            b.setMinimumHeight(54)
            b.clicked.connect(lambda _, i=i: self.rv_click(i))
            self.rv_btns.append(b)
            darts.addWidget(b)
        ok = QPushButton("✓  Jóváhagyom  (Enter)")
        ok.setObjectName("go")
        ok.clicked.connect(self.accept_round)
        no = QPushButton("✕  Elvetem a kört")
        no.clicked.connect(self.discard_round)
        acts = QHBoxLayout()
        acts.addWidget(ok, 2)
        acts.addWidget(no, 1)
        lay = QVBoxLayout(self.rv_box)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)
        for item in (top, self.rv_sum, self.rv_bar, darts, self.rv_hint, acts):
            lay.addLayout(item) if hasattr(item, "addWidget") else lay.addWidget(item)
        self.rv_box.hide()
        return self.rv_box

    def rv_click(self, i):
        self.review.select(i)
        self.flash = ""
        self.refresh_review(force=True)

    def accept_round(self):
        if not self.review.active or self.game.winner is not None or self.paused:
            return
        apply_round(self.game, self.review.accept())
        self.flash = ""
        self.refresh()

    def discard_round(self):
        self.review.discard()
        self.flash = ""
        self.refresh()

    def refresh_review(self, force=False):
        rv = self.review
        self.rv_box.setVisible(rv.active)
        self.update_pad()
        self.update_banner()
        if not rv.active:
            self._sig = None
            return
        left = rv.seconds_left()
        if left is None:
            self.rv_time.setText(f"A kör a {rv.size}. nyíl után zárul")
            self.rv_bar.setValue(0)
        else:
            self.rv_bar.setRange(0, int(rv.countdown * 10))
            self.rv_bar.setValue(int(left * 10))
            if left > 0 and rv.auto and not rv.needs_manual():
                self.rv_time.setText(f"⏱  {int(left + 0.99)} mp, utána automatikusan elfogadom")
            elif left > 0:
                self.rv_time.setText(f"⏱  {int(left + 0.99)} mp")
            else:
                self.rv_time.setText("⏸  Jóváhagyásra vár")
        sig = (tuple((i.mult, i.num, i.uncertain, i.orig, i.note) for i in rv.items), rv.selected, self.flash, rv.full)
        if sig == self._sig and not force:
            return
        self._sig = sig
        self.rv_head.setText("📷  Felismert kör: ellenőrizd" if rv.full else "📷  Felismert dobások")
        self.rv_sum.setText("Érzékelt: " + rv.text())
        for i, b in enumerate(self.rv_btns):
            b.setVisible(i < rv.size)                      # a kör nyílszáma játékonként változhat (pl. Killer számválasztás: 1)
            if i >= len(rv.items):
                b.setText(f"{i + 1}. nyíl\n·")
                b.setEnabled(False)
                b.setStyleSheet("")
                continue
            it = rv.items[i]
            name = rv_mod.show(it.mult, it.num)
            note = "javítva (volt: " + rv_mod.show(*it.orig) + ")" if it.edited else (
                "hiányzó nyíl, mellének vettem" if it.source == "fill" else
                (("ellenőrizd: " + it.note if it.note else "ellenőrizd") if it.uncertain else it.note))
            b.setEnabled(True)
            b.setText(f"{i + 1}. nyíl:  {name}" + ("  ✎" if it.edited else "") + (f"\n{note}" if note else ""))
            if rv.selected == i:
                b.setStyleSheet("background: #2a1808; border: 3px solid #ff8a1f; font-size: 16px;")
            elif it.uncertain:
                b.setStyleSheet("border: 2px dashed #ffd23f; font-size: 16px;")
            else:
                b.setStyleSheet("font-size: 16px;")
        if self.flash:
            self.rv_hint.setText(self.flash)
        elif rv.selected is not None:
            self.rv_hint.setText(f"A(z) {rv.selected + 1}. nyíl javítása: üsd be a helyes mezőt (Szimpla / Dupla / Tripla + szám).")
        elif rv.full:
            self.rv_hint.setText("Nem egyezik? Koppints arra a nyílra, amit javítani szeretnél. Ha minden stimmel: Jóváhagyom.")
        else:
            self.rv_hint.setText("Hiányzik egy nyíl (pl. a tábla mellé ment)? Üsd be kézzel, például a Mellé gombbal.")

    # ───────────── játék ─────────────
    def cur_mode(self):
        return MODE_BY_ID[self.mode_id]

    def choose_mode(self):
        dlg = ModeDialog(self, self.mode_id, len(self.names))
        if dlg.exec() and dlg.picked:
            self.set_mode(dlg.picked)

    def set_mode(self, mode_id):
        mode = MODE_BY_ID[mode_id]
        if len(self.names) < mode.min_players:
            QMessageBox.information(
                self, mode.name, f"A(z) {mode.name} játékhoz legalább {mode.min_players} játékos kell.\n"
                                 "Add hozzá őket a jobb oldali ＋ gombbal, majd válaszd újra a játékot.")
            return
        self.mode_id = mode_id
        self.new_game()

    def new_game(self, *_):
        self.remember_match()                                 # a lecserélt (már dobott) játék lesz a „legutóbbi meccs”
        mode = self.cur_mode()
        self.mode_btn.setText(f"Játékmód választó\n{mode.name}  ▾")
        self.out.setVisible(mode.uses_out)                    # Double/Straight Out csak a 301/501/701-nél számít
        self.game = mode.make(list(self.names), self.out.currentIndex() == 0)
        self.game_pids, self._rec = list(self.pids[:len(self.names)]), None
        self.game_mode_id, self.game_out = self.mode_id, self.out.currentIndex() == 0
        self.review = self.new_review()
        self.set_paused(False)
        self.turn_key, self.turn_t0 = None, time.monotonic()
        if self.service:
            self.service.reset_round()
        self.refresh()
        self.save_state()

    # ── legutóbbi meccs és meccs végi képernyő ──
    def remember_match(self):
        """A játék beállításai (játékosok, játékmód, kiszállás) a „legutóbbi meccshez”, ha már dobtak benne."""
        g = getattr(self, "game", None)
        if g is None or not g.hist or not self.game_pids:
            return
        self.cfg["last_match"] = {"mode_id": self.game_mode_id, "pids": list(self.game_pids), "out": bool(self.game_out)}

    def last_match(self):
        """A mentett legutóbbi meccs, ha még érvényes (van játékosa és ismert játékmódja); különben None."""
        lm = self.cfg.get("last_match")
        if not isinstance(lm, dict) or lm.get("mode_id") not in MODE_BY_ID:
            return None
        pids = [p for p in lm.get("pids", []) if self.profile_by_id(p)]
        return {"mode_id": lm["mode_id"], "pids": pids, "out": bool(lm.get("out", True))} if pids else None

    def update_last_button(self):
        lm = self.last_match()
        self.last_btn.setEnabled(lm is not None)
        if lm is None:
            self.last_btn.setToolTip("Még nincs legutóbbi meccs: az első dobás után megjegyzi a program.")
            return
        mode = MODE_BY_ID[lm["mode_id"]]
        names = ", ".join(self.profile_by_id(p)["name"] for p in lm["pids"])
        out = (" · Double Out" if lm["out"] else " · Straight Out") if mode.uses_out else ""
        self.last_btn.setToolTip(f"Újraindítja a legutóbbi meccset: {mode.name}{out}\nJátékosok: {names}")

    def restart_last_match(self):
        """Visszaállítja a legutóbbi meccs játékosait, játékmódját és kiszállását, és újraindítja a játékot."""
        g = self.game
        if g.hist and g.winner is None and not ask.confirm(
                self, APP_NAME, "A most folyó játék megszakad. Biztosan újraindítod a legutóbbi meccset?"):
            return
        self.remember_match()
        lm = self.last_match()
        if lm is None:
            return
        self.pids = list(lm["pids"])
        self.names = [self.profile_by_id(p)["name"] for p in self.pids]
        self.mode_id = lm["mode_id"]
        self.out.blockSignals(True)
        self.out.setCurrentIndex(0 if lm["out"] else 1)
        self.out.blockSignals(False)
        self.fill_players(self.cur_mode().min_players)
        self.game_pids = []                                   # a visszaállítás nem számít „legutóbbi meccsnek”
        self.new_game()

    def show_match_end(self):
        g = self.game
        if g.winner is None or self._end_for != id(g):
            return
        avatars = {}
        for i in range(g.n):
            p = self.profile_at(i)
            avatars[i] = {"path": pf.avatar_path(p, self.avatar_dir) if p else None, "color": p["color"] if p else ORANGE}
        dlg = finish.MatchEndDialog(self, g, avatars)
        dlg.exec()
        choice = dlg.choice
        dlg.deleteLater()
        if choice == "rematch":
            self.new_game()
        elif choice == "stats":
            self.show_stats()

    def schedule_match_end(self):
        """A győzelem után kis késéssel (a fanfár és a felolvasás kezdete után) megjelenik a meccs végi képernyő."""
        if not self.cfg.get("end_screen", True):
            return
        if QGuiApplication.platformName() in sounds.HEADLESS and not self.end_force:
            return                                            # képernyő nélküli futtatásnál (tesztek) nem nyílik ablak
        QTimer.singleShot(1100, self.show_match_end)

    def toggle_pause(self):
        self.set_paused(not self.paused)
        self.refresh()

    def set_paused(self, on):
        if on == self.paused:
            return
        now = time.monotonic()
        self.paused = on
        if on:
            self.pause_t = now
        else:                                                 # a szünet ideje nem számít bele a kör idejébe
            if self.pause_t is not None:
                self.turn_t0 += now - self.pause_t
            self.pause_t = None
        (self.review.pause if on else self.review.resume)()
        self.pause_btn.setText("▶  Folytatás" if on else "⏸  Szünet")
        self.pause_btn.setProperty("paused", on)
        self.pause_top.setText("▶" if on else "⏸")
        self.pause_top.setToolTip("Folytatás (P)" if on else "Szünet: megállítja a kör óráját (P)")

    def hit(self, n):
        if self.paused:
            return
        m = 0 if n == 0 else (2 if n == 25 and self.mult == 3 else self.mult)
        self.mult = 1
        self.mbtn[0].setChecked(True)
        if self.service:                                      # kamerás játék: a kézi bevitel is a jóváhagyandó körbe kerül
            rv = self.review
            if rv.selected is not None:
                rv.edit(rv.selected, m, n)
                self.flash = ""
            elif not rv.add_manual(m, n):
                self.flash = "A kör teljes. Koppints arra a nyílra, amit javítani szeretnél."
            self.refresh_review(force=True)
            return
        self.game.throw(m, n)
        self.refresh()

    def undo(self, *_):
        if self.service and self.review.active:
            self.review.undo()
            self.refresh_review(force=True)
        else:
            self.game.undo()
            self.refresh()

    # ── a képernyő frissítése ──
    def update_banner(self):
        g = self.game
        if g.winner is not None:
            text, color = "🏆  GYŐZTES", GREEN
        elif self.paused:
            text, color = "⏸  SZÜNET", YELLOW
        elif self.review.active:
            text, color = "📷  KAMERA: ELLENŐRIZD", BLUE
        else:
            text, color = "»   JÁTÉKOS KÖVETKEZIK   «", ORANGE
        self.banner.setText(text)
        self.banner.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0,0,0,0), "
                                  f"stop:0.25 {color}, stop:1 rgba(0,0,0,0)); color: #fff; font-weight: 900; "
                                  f"padding: {int(6 * self.k)}px {int(26 * self.k)}px; border-radius: {int(10 * self.k)}px; "
                                  f"font-size: {int(17 * self.k)}px; letter-spacing: 1px;")

    def sync_history(self):
        """A befejezett játék egyszer mentődik az előzménybe; ha a visszavonás visszaviszi a játékot, a bejegyzés is törlődik."""
        done = self.game.winner is not None
        if done and self._rec is None:
            rec = history.make_record(self.game, self.game_pids, self.cur_mode())
            self.history.append(rec)
            self._rec = rec["id"]
            history.save(self.history, self.history_file)
        elif not done and self._rec is not None:
            self.history = [r for r in self.history if r["id"] != self._rec]
            self._rec = None
            history.save(self.history, self.history_file)

    # ───────────── hangok ─────────────
    def update_sound_button(self):
        on = self.sound.enabled
        self.snd_btn.setText("🔊" if on else "🔇")
        self.snd_btn.setToolTip("Hangok: be (kattintásra kikapcsol)" if on else "Hangok: ki (kattintásra bekapcsol)")

    def set_sound(self, on):
        """A hangeffektek be/ki (a fejléc hangszóró gombja és a beállítások is ezt hívja)."""
        self.sound.enabled = bool(on)
        self.cfg["sound"] = bool(on)
        self.update_sound_button()
        self.save_state()

    def set_speech(self, on):
        """A pontszám felolvasása be/ki."""
        self.speaker.enabled = bool(on)
        self.cfg["speech"] = bool(on)
        self.save_state()

    def set_volume(self, percent):
        percent = min(max(int(percent), 0), 100)
        self.sound.set_volume(percent / 100)
        self.cfg["volume"] = percent
        self.save_state()

    def play_cue(self):
        """Egy új dobás után a megfelelő hang. Új játéknál és visszavonásnál nem szól semmi."""
        g = self.game
        key, n = id(g), len(g.hist)
        last_key, last_n = self._snd
        self._snd = (key, n)
        if key != last_key or n <= last_n:
            return
        cue = sounds.cue_for(g)
        if cue:
            self.sound.play(cue)
        if self.sound.enabled:                                # a némított program nem beszél
            self.speaker.speak_for(g)

    def stats_since(self):
        """Profilonként a statisztika nullázásának ideje (csak a nullázott profiloké)."""
        return {p["id"]: p["stats_from"] for p in self.profiles if p.get("stats_from")}

    def reset_stats(self, pid):
        """Egy profil statisztikájának nullázása: a mostantól befejezett játékok számítanak. A játékok listája megmarad."""
        p = self.profile_by_id(pid)
        if p:
            p["stats_from"] = time.time()
            self.profiles_changed()

    def clear_history(self):
        self.history = []
        history.save(self.history, self.history_file)

    def refresh(self):
        self.sync_history()
        self.play_cue()
        g, k = self.game, self.k
        if g.winner is None:
            self._end_for = None
        elif self._end_for != id(g):
            self._end_for = id(g)
            self.remember_match()
            self.save_state()
            self.schedule_match_end()
        self.update_last_button()
        self.review.set_size(g.turn_darts())                  # a következő kör nyílszáma (a legtöbb játékban 3)
        w = g.winner
        cur = g.cur if w is None else w
        winners = (g.tied or [w]) if w is not None else []
        key = (id(g), g.cur, g.round, w)
        if key != self.turn_key:                              # új kör kezdődött: a kör-időmérő újraindul
            self.turn_key, self.turn_t0 = key, time.monotonic()
            if self.paused:
                self.pause_t = self.turn_t0
        self.title_lbl.setText(f"🎯  {g.title}")
        if w is None:
            self.hdr.setText(f"{g.round_text()} {g.unit}  ·  {len(g.darts) + 1}. DOBÁS")
        elif len(winners) > 1:
            self.hdr.setText("🤝 Döntetlen: " + ", ".join(g.names[i] for i in winners))
        else:
            self.hdr.setText(f"🏆 {g.names[w]} nyert!")
        self.who.setText(("👑 " if cur in winners else "") + g.names[cur])
        self.set_avatar(self.main_avatar, cur, 64 * k, ORANGE)
        big = g.big(cur)
        self.big.setText(big)
        size = 118 if len(big) <= 3 else 98 if len(big) == 4 else 74 if len(big) <= 6 else 52
        self.big.setStyleSheet(f"font-size: {int(size * k)}px;")
        self.stat.setText(f"{g.start} kezdőpontból  ·  {g.start - g.left[cur]} pont dobva" if isinstance(g, X01) else g.stats(cur))
        shown, title = (g.darts, "Aktuális kör dobásai") if g.darts or not g.prev else (g.prev[1], f"Előző kör: {g.prev[0]}")
        self.tbt.setText(title)
        for i, t in enumerate(self.tb):
            self.tcell[i].setVisible(i < max(g.turn_darts(), len(shown)))
            d = shown[i] if i < len(shown) else None
            body = (f"<span style='font-size:{int(26 * k)}px; font-weight:800'>{rv_mod.show(*d)}</span><br>"
                    f"<span style='color:#ffb454'>{d[0] * d[1]} pont</span>" if d
                    else f"<span style='font-size:{int(26 * k)}px; color:#5b6390'>·</span><br>&nbsp;")
            t.setText(f"<span style='color:#9fb0ff'>{i + 1}. dobás</span><br>{body}")
        self.refresh_helper(g, cur, w)
        self.refresh_strip(g, cur)
        self.refresh_players(g, cur, winners)
        self.refresh_recent(g)
        self.update_timer()
        self.refresh_review(force=True)

    def refresh_helper(self, g, cur, winner):
        """Segédlet: 301/501/701-nél kiszálló útvonalak (a legkevesebb nyíllal), más játékoknál a játék tippje."""
        clear(self.help_row)
        k = self.k
        self.help_has = False
        if winner is not None:
            self.help_card.hide()
            return
        cells, note = [], ""                                   # cells: (szöveg, ajánlott); note: egyszerű üzenet útvonal helyett
        self.help_badge.setText("")
        if isinstance(g, X01):
            left, darts_left = g.left[cur], g.turn_darts() - len(g.darts)
            self.help_title.setText("💡  Kiszállási segédlet")
            routes = checkout_routes(left, darts_left, g.dbl) if 2 <= left <= 170 and darts_left > 0 else []
            for n, route in enumerate(routes):
                names = "  →  ".join(label(*d) for d in route)
                sums = " + ".join(str(m * v) for m, v in route) + f" = {left}"
                tag = "<br><span style='color:#ffb454; font-weight:800'>AJÁNLOTT ✓</span>" if n == 0 else ""
                cells.append((f"<span style='font-size:{int(18 * k)}px; font-weight:800'>{names}</span><br>"
                              f"<span style='color:#9fb0ff'>{sums}</span>{tag}", n == 0))
            if routes:
                self.help_badge.setText(f"✔ {darts_left} nyíllal")
            elif left > 170:
                note = f"A kiszállás 170 pont alatt kezdődik (most {left} van hátra)."
            else:
                note = f"A hátralévő {left} pontot ebből a körből nem lehet kiszállni."
        else:
            hint = g.hint()
            self.help_title.setText("💡  Segédlet")
            if not hint:
                self.help_card.hide()
                return
            note = hint
        self.help_has = True
        self.help_card.setVisible(self.squeeze < 1)
        if note:
            lb = QLabel(html.escape(note))
            lb.setObjectName("muted")
            lb.setWordWrap(True)
            lb.setAlignment(Qt.AlignCenter)
            self.help_row.addWidget(lb, 1)
        for text, best in cells:
            cell = Card("active" if best else "quiet")
            lb = QLabel(text)
            lb.setTextFormat(Qt.RichText)
            lb.setWordWrap(True)
            lb.setAlignment(Qt.AlignCenter)
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(8, 6, 8, 6)
            cl.addWidget(lb)
            self.help_row.addWidget(cell, 1)

    def refresh_strip(self, g, cur):
        clear(self.strip_row)
        if isinstance(g, X01):
            thrown = g.thrown[cur]
            scored = g.start - g.left[cur]
            visits = math.ceil(thrown / 3) if thrown else 0
            cells = [("📈", "Körátlag", f"{scored / visits:.1f}" if visits else "0.0"), ("🏆", "Összpontszám", str(scored)),
                     ("🎯", "3 Darts Avg", f"{scored / thrown * 3:.1f}" if thrown else "0.0")]
        else:
            ps = stats.player_stats(g)[cur]
            cells = [("🎯", "Állás", g.score(cur)), ("🔁", "Kör", f"{g.round_text()} {g.unit}".lower()),
                     ("🏹", "Nyilak", str(ps["darts"]))]
        for n, (icon, key, val) in enumerate(cells):
            if n:
                sep = QFrame()
                sep.setFrameShape(QFrame.VLine)
                sep.setStyleSheet("color: #2d3a78;")
                self.strip_row.addWidget(sep)
            ico = QLabel(icon)
            ico.setObjectName("statico")
            v = QLabel(val)
            v.setObjectName("statv")
            kk = QLabel(key)
            kk.setObjectName("statk")
            cell = QWidget()
            lay = QHBoxLayout(cell)
            lay.setContentsMargins(0, 0, 0, 0)
            txt = QVBoxLayout()
            txt.setSpacing(0)
            txt.addWidget(kk)
            txt.addWidget(v)
            lay.addStretch()
            lay.addWidget(ico)
            lay.addLayout(txt)
            lay.addStretch()
            self.strip_row.addWidget(cell, 1)

    def set_avatar(self, widget, i, size, ring):
        p = self.profile_at(i)
        name = self.game.names[i] if i < self.game.n else "?"
        widget.set_size(int(size))
        widget.set_player(name, pf.avatar_path(p, self.avatar_dir), p["color"] if p else ORANGE, ring)

    def refresh_players(self, g, cur, winners):
        k = self.k
        self.pcount.setText(f"👥  Játékosok ({g.n}/8)")
        clear(self.plist)
        big_font = 24 if max(len(g.score(i)) for i in range(g.n)) <= 6 else 15      # hosszabb pontszövegnél kisebb betű, mindenkinél egységesen
        for i in range(8):
            if i >= g.n:
                slot = QPushButton(f"⊕   {i + 1}. Új játékos")
                slot.setObjectName("slot")
                slot.clicked.connect(self.add_player)
                self.plist.addWidget(slot)
                continue
            rowf = Card("active" if i == cur else "quiet")
            hl = QHBoxLayout(rowf)
            hl.setContentsMargins(10, 4, 12, 4)
            av = Avatar(40 * k)
            self.set_avatar(av, i, 40 * k, ORANGE if i == cur else BLUE)
            hl.addWidget(av)
            nm = QLabel(("👑 " if i in winners else "") + g.names[i])
            nm.setStyleSheet(f"font-size: {int(17 * k)}px; font-weight: {800 if i == cur else 600};")
            hl.addWidget(nm, 1)
            if i == cur and g.winner is None:
                badge = QLabel("JÁTSZIK!")
                badge.setObjectName("badge")
                hl.addWidget(badge)
            s = QLabel(g.score(i))
            s.setObjectName("pts")
            s.setStyleSheet(f"font-size: {int(big_font * k)}px;")
            hl.addWidget(s)
            self.plist.addWidget(rowf)

    def refresh_recent(self, g):
        clear(self.recent_box)
        rows = stats.recent(g, 4)
        if not rows:
            lb = QLabel("Még nem volt befejezett kör.")
            lb.setObjectName("muted")
            self.recent_box.addWidget(lb)
            return
        for name, darts, total in rows:
            box = QWidget()
            row = QHBoxLayout(box)
            row.setContentsMargins(0, 0, 0, 0)
            nm = QLabel(name)
            nm.setStyleSheet("font-weight: 700;")
            row.addWidget(nm, 3)
            for d in darts:
                lb = QLabel(d)
                lb.setAlignment(Qt.AlignCenter)
                row.addWidget(lb, 1)
            for _ in range(3 - len(darts)):
                row.addWidget(QLabel(""), 1)
            tot = QLabel(str(total))
            tot.setObjectName("pts")
            tot.setStyleSheet(f"font-size: {int(18 * self.k)}px;")
            tot.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(tot, 1)
            self.recent_box.addWidget(box)

    def update_timer(self):
        rv = self.review
        left = rv.seconds_left() if rv.active else None
        now = self.pause_t if self.paused and self.pause_t is not None else time.monotonic()     # szünetben az óra áll
        text = f"⏱  {fmt_time(left)}" if left is not None else f"⏱  {fmt_time(now - self.turn_t0)}"
        if self.paused:
            text = "⏸  SZÜNET  " + text[3:]
        if self.timer_lbl.text() != text:
            self.timer_lbl.setText(text)

    def update_connection(self):
        live = sum(1 for c in self.cams if c.ok)
        if live:
            self.conn.setText(f"<span style='color:{GREEN}'>●</span>  Élő kapcsolat ({live})")
        else:
            self.conn.setText(f"<span style='color:{MUTED}'>●</span>  <span style='color:{MUTED}'>Nincs élő kamera</span>")

    # ───────────── játékosok és profilok ─────────────
    def profile_by_id(self, pid):
        return next((p for p in self.profiles if p["id"] == pid), None)

    def profile_at(self, i):
        """A i. játékos profilja (azonosító alapján, ennek hiányában név alapján); None, ha nincs."""
        pid = self.pids[i] if i < len(self.pids) else None
        p = self.profile_by_id(pid)
        name = self.names[i] if i < len(self.names) else None
        if p is None or (name is not None and p["name"] != name):
            p = next((q for q in self.profiles if q["name"] == name), None)
        return p

    def fill_players(self, minimum):
        """Legalább `minimum` játékos legyen: a hiányzókat még nem játszó profilokból, vagy újakból pótolja."""
        while len(self.names) < minimum:
            free = next((p for p in self.profiles if p["id"] not in self.pids), None)
            if free is None:
                free = pf.make_profile(pf.unique_name(self.profiles, "Játékos"), [p["color"] for p in self.profiles])
                self.profiles.append(free)
            self.pids.append(free["id"])
            self.names.append(free["name"])

    def add_player(self):
        if len(self.names) >= 8:
            return
        dlg = options.AddPlayerDialog(self)
        if dlg.exec() and dlg.picked:
            p = self.profile_by_id(dlg.picked)
            if p:
                del self.pids[len(self.names):]
                self.pids.append(p["id"])
                self.names.append(p["name"])
                self.new_game()

    def del_player(self):
        need = self.cur_mode().min_players
        if len(self.names) > max(1, need):
            self.names.pop()
            del self.pids[len(self.names):]
            self.new_game()
        elif len(self.names) > 1:
            QMessageBox.information(self, self.cur_mode().name,
                                    f"A(z) {self.cur_mode().name} játékhoz legalább {need} játékos kell.")

    def rename_profile(self, pid, new):
        """Átnevezés: a most játszó játékos neve, a játék és az előzmények is frissülnek."""
        p = self.profile_by_id(pid)
        if not p:
            return
        old, p["name"] = p["name"], new
        g = self.game
        for i, q in enumerate(self.pids[:len(self.names)]):
            if q != pid:
                continue
            self.names[i] = new
            if i < g.n:
                g.names[i] = new
                for s in g.hist:                              # a visszavonás se hozza vissza a régi nevet
                    if i < len(s["names"]):
                        s["names"][i] = new
        for state in [g.__dict__] + list(g.hist):
            if state.get("prev") and state["prev"][0] == old:
                state["prev"] = (new, state["prev"][1])
        self.profiles_changed()

    def profiles_changed(self):
        self.save_state()
        self.refresh()

    def open_options(self, page=0):
        options.OptionsDialog(self, page).exec()
        self.refresh()

    def show_stats(self):
        names = {p["id"]: p["name"] for p in self.profiles}
        StatsDialog(self, self.game, self.history, names, self.clear_history, self.stats_since()).exec()

    # ───────────── kamerák ─────────────
    def add_cam(self):
        if cv2 is None:
            return QMessageBox.warning(self, APP_NAME, "Az OpenCV nincs telepítve:\npip install opencv-python")
        if len(self.cams) >= MAX_CAMS:
            return
        t, ok = QInputDialog.getText(
            self, "Kamera hozzáadása",
            "USB webkamera: írd be a számát (0, 1, 2…)\n"
            "Telefon: indítsd el az IP Webcam (Android) alkalmazást, nyomd meg a Start server gombot,\n"
            "és írd be a kijelzőn látható címet, például 192.168.0.56:8080", text="0")
        if ok and t.strip():
            self.add_cam_source(t.strip())
            self.save_state()

    def add_cam_source(self, text):
        if cv2 is None or len(self.cams) >= MAX_CAMS:
            return
        src = vision.normalize_source(text)
        title = f"Webkamera {src}" if isinstance(src, int) else f"Telefon ({text})"
        cam = Cam(title, src, text, self.rm_cam, self.toggle_detect)
        self.cams.append(cam)
        self.left.insertWidget(len(self.cams) - 1, cam, 1)
        self.update_left()

    def rm_cam(self, cam):
        if cam.service:
            self.detect_off(cam)
        cam.alive = False
        self.cams.remove(cam)
        cam.setParent(None)
        cam.deleteLater()
        self.update_left()
        self.save_state()

    def update_left(self):
        """A kamerák egyenlően osztják el a bal oszlopot; a „Kamera hozzáadása” gomb elrejtődik, ha elértük a maximumot."""
        empty = not self.cams
        self.addcam.setObjectName("addcam_empty" if empty else "addcam")
        self.addcam.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding if empty else QSizePolicy.Fixed)
        self.addcam.setText("⊕\nKamera hozzáadása\n\nUSB webkamera vagy\ntelefon (IP Webcam)" if empty else "⊕  Kamera hozzáadása")
        self.addcam.style().unpolish(self.addcam)
        self.addcam.style().polish(self.addcam)
        self.addcam.setVisible(len(self.cams) < MAX_CAMS)

    # ───────────── dobásfelismerés ─────────────
    def get_backend(self):
        if self.backend:
            return self.backend
        try:
            import ultralytics  # noqa: F401
        except ImportError:
            QMessageBox.information(self, "Dobásfelismerés", ultralytics_help(sys.executable, APP_DIR))
            return None
        path = vision.find_model(APP_DIR, self.cfg.get("model"))
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Válaszd ki a dobásfelismerő modell fájlját (.pt)",
                                                  str(APP_DIR), "YOLO modell (*.pt)")
            if not path:
                return None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.backend = vision.YoloBackend(path)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Dobásfelismerés", f"A modell nem tölthető be:\n{e}")
            return None
        QApplication.restoreOverrideCursor()
        self.cfg["model"] = str(path)
        self.save_state()
        return self.backend

    def toggle_detect(self, cam, on):
        """Egy kamera dobásfelismerésének be- és kikapcsolása. Több kamera egyszerre is mehet: a dobásaikat a
        program összeveti (fusion.py), így egy nyíl csak egyszer számít, és eltérésnél jóváhagyást kér."""
        if not on:
            self.detect_off(cam)
            return
        backend = self.get_backend()
        if backend is None:
            cam.det.setChecked(False)
            return
        cam.det.setChecked(True)
        cam.service = vision.DetectionService(vision.Detector(backend), lambda c=cam: c.frame)
        if self.service is None:
            self.service = fusion.FusionService()
        self.service.add(id(cam), cam.service)
        self.restart_round()

    def detect_off(self, cam):
        if self.service and cam.service:
            self.service.remove(id(cam))
        cam.service = None
        cam.det.setChecked(False)
        cam.info.setText("")
        if self.service and not self.service.children:
            self.service = None
        self.restart_round()

    def stop_detection(self):
        if self.service:
            self.service.stop()
        for c in self.cams:
            c.service = None
            c.det.setChecked(False)
            c.info.setText("")
        self.service = None
        self.restart_round()

    def restart_round(self):
        """A kamerák köre megváltozott: tiszta jóváhagyó panel, a követők és az összevető is újraindul."""
        if self.service:
            self.service.reset_round()
        self.review = self.new_review()
        self.paused = False
        self.pause_btn.setText("⏸  Szünet")
        self.refresh()

    def poll_detection(self):
        """A háttérszál eseményeinek átvétele (új dobás / nyilak kihúzva)."""
        changed = False
        for ev in (self.service.poll() if self.service else []):
            if self.game.winner is not None:
                continue
            if isinstance(ev, vision.Throw):
                self.review.add_detected(ev)
            elif isinstance(ev, vision.Removed):
                self.review.on_removed()
            changed = True
        return changed

    def tick(self):
        self.clock.setText(time.strftime("%H:%M:%S"))
        self.update_timer()
        self.update_connection()
        for c in self.cams:
            c.update_view()
        if self.service and not self.paused:
            changed = self.poll_detection()
            if self.review.due():
                self.accept_round()
            elif self.review.active or changed:
                self.refresh_review(force=changed)

    # ───────────── kalibrációs varázsló ─────────────
    def calib_file(self):
        return CFG_FILE.parent / "calibration.json"           # a beállításfájl mellett (a tesztek külön mappát használnak)

    def silent_backend(self):
        """A modell párbeszédablakok nélkül (a varázsló háttérszálából): None, ha nincs modell vagy ultralytics."""
        if self.backend:
            return self.backend
        try:
            import ultralytics  # noqa: F401
        except ImportError:
            return None
        path = vision.find_model(APP_DIR, self.cfg.get("model"))
        if not path:
            return None
        self.backend = vision.YoloBackend(path)
        return self.backend

    def open_wizard(self, startup=False):
        """Kalibrációs varázsló. A kamerák nevei a főképernyőn látható nevek; ha nincs kamera, a varázsló elmagyarázza a
        telepítést, és onnan is hozzáadható egy kamera."""
        sources = [{"label": c.title, "text": str(c.text), "get": lambda c=c: c.frame} for c in self.cams]

        def add_camera():
            self.add_cam()
            dlg.set_sources([{"label": c.title, "text": str(c.text), "get": lambda c=c: c.frame} for c in self.cams])

        dlg = wizard.CalibrationWizard(self, sources, self.calib_file(), get_backend=self.silent_backend,
                                       add_camera=add_camera, hide_checked=bool(self.cfg.get("wizard_hidden", False)),
                                       startup=startup)
        dlg.exec()
        self.cfg["wizard_hidden"] = dlg.hide_offer()
        if dlg.saved_any:
            self.cfg["wizard_done"] = True
        dlg.deleteLater()
        self.save_state()

    def open_trainer(self):
        """Modell-betanító: a saját kamerák képeiből tanít dobásfelismerő modellt."""
        def sources():
            return [{"label": c.title, "text": str(c.text), "get": lambda c=c: c.frame} for c in self.cams]

        def add_camera():
            self.add_cam()
            dlg.set_sources(sources())

        def take_model(path):
            self.cfg["model"] = str(path)
            self.backend = None                               # a következő bekapcsolásnál az új modell töltődik be
            self.save_state()

        dlg = trainer_ui.TrainerDialog(self, sources(), self.calib_file(), CFG_FILE.parent / "training", APP_DIR / "models",
                                       open_wizard=self.open_wizard, add_camera=add_camera, on_model=take_model)
        dlg.exec()
        dlg.deleteLater()

    def startup_wizard(self):
        """Az első indításkor (a telepítés után) a kalibrációs varázsló, hacsak nem kapcsolták ki vagy már megvolt."""
        if self.cfg.get("wizard_hidden", False) or self.cfg.get("wizard_done", False):
            return
        if QGuiApplication.platformName() in sounds.HEADLESS:
            return
        self.open_wizard(startup=True)

    # ───────────── üdvözlő ablak ─────────────
    def startup_welcome(self):
        """Induláskor a bemutató kép, hacsak a felhasználó nem pipálta be a „Többé ne jelenjen meg” jelölőt."""
        if not self.cfg.get("welcome_hidden", False):
            self.show_welcome()

    def show_welcome(self):
        path = welcome.image_path(self.app_dir)
        if not path.is_file():
            return
        try:
            dlg = welcome.WelcomeDialog(self, path, hide_checked=bool(self.cfg.get("welcome_hidden", False)))
        except ValueError:
            return                                           # sérült kép: az indulást nem akadályozza
        dlg.exec()
        self.cfg["welcome_hidden"] = dlg.hide_forever()
        dlg.deleteLater()
        self.save_state()

    def startup(self):
        """Induláskor: bemutató kép, majd (először) a kalibrációs varázsló."""
        self.startup_welcome()
        self.startup_wizard()

    def save_state(self):
        valid = [pid for pid in self.pids[:len(self.names)] if self.profile_by_id(pid)]
        self.cfg.update(profiles=self.profiles, players=valid, cameras=[c.text for c in self.cams], mode_id=self.mode_id,
                        out=self.out.currentIndex())
        self.cfg.pop("mode", None)                           # a régi, sorszám alapú beállítás már nem kell
        self.cfg.pop("names", None)                          # a nevek a profilokban vannak
        save_cfg(self.cfg)

    def closeEvent(self, e):
        self.remember_match()
        self.save_state()
        if self.service:
            self.service.stop()
        for c in self.cams:
            c.alive = False
        super().closeEvent(e)


if __name__ == "__main__":
    set_app_id()
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    _pm = logo_pixmap()
    if _pm is not None:
        app.setWindowIcon(QIcon(_pm))
    win = Main()
    win.showMaximized() if win.cfg.get("maximized", True) else win.show()
    QTimer.singleShot(250, win.startup)            # a főablak már látszik, mire az üdvözlő ablak megnyílik
    code = app.exec()
    dispose(win)
    del win
    sys.exit(code)
