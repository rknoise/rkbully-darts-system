"""Beállítások (fogaskerék menü) és játékos hozzáadása. Minden beállítás egy helyen, a bal oldali menüből választva.

A felület (Main) adja az adatokat és a műveleteket; ez a modul csak a párbeszédablakokat tartalmazza.
"""
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSlider, QSpinBox,
                               QStackedWidget, QVBoxLayout, QWidget)

import ask
import history
import profiles as pf
import sounds
from appinfo import APP_NAME, AUTHOR, GITHUB_URL, VERSION
from theme import Avatar


def avatar_pixmap(profile, size=40):
    """A profil kerek képe (vagy kezdőbetűje) kis ikonként a listákhoz."""
    a = Avatar(size)
    a.set_player(profile["name"], pf.avatar_path(profile), profile["color"])
    return a.grab()


def label(text, name="muted", wrap=True):
    lb = QLabel(text)
    lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


class ProfilesPage(QWidget):
    """Profilok szerkesztése: név, profilkép feltöltése, szín, új profil, törlés."""

    def __init__(self, main):
        super().__init__()
        self.main, self.cur = main, None
        self.list = QListWidget()
        self.list.setIconSize(QSize(40, 40))
        self.list.setMinimumWidth(240)
        self.list.currentRowChanged.connect(self._select)
        add = QPushButton("＋  Új profil")
        add.clicked.connect(self.add_profile)
        left = QVBoxLayout()
        left.addWidget(self.list, 1)
        left.addWidget(add)

        self.avatar = Avatar(120)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Név")
        self.name.setMaxLength(24)
        self.name.editingFinished.connect(self.rename)
        self.upload = QPushButton("📷  Kép feltöltése…")
        self.upload.clicked.connect(self.choose_image)
        self.remove_img = QPushButton("Kép törlése")
        self.remove_img.clicked.connect(self.clear_image)
        self.swatches = []
        sw = QHBoxLayout()
        for c in pf.COLORS:
            b = QPushButton()
            b.setFixedSize(30, 30)
            b.setCheckable(True)
            b.setStyleSheet(f"QPushButton {{ background: {c}; border: 2px solid #0b0f1f; border-radius: 15px; padding: 0; }}"
                            f"QPushButton:checked {{ border: 3px solid #fff; }}")
            b.clicked.connect(lambda _, c=c: self.set_color(c))
            self.swatches.append((c, b))
            sw.addWidget(b)
        sw.addStretch()
        self.state = label("")
        self.msg = label("", "muted")
        self.msg.setStyleSheet("color: #ffd23f;")
        self.delete = QPushButton("🗑  Profil törlése")
        self.delete.clicked.connect(self.delete_profile)
        self.stats = label("")
        self.reset_stats = QPushButton("↺  Statisztika nullázása")
        self.reset_stats.clicked.connect(self.reset_profile_stats)

        pic = QHBoxLayout()
        pic.addWidget(self.avatar)
        btns = QVBoxLayout()
        btns.addStretch()
        btns.addWidget(self.upload)
        btns.addWidget(self.remove_img)
        btns.addStretch()
        pic.addLayout(btns)
        pic.addStretch()
        right = QVBoxLayout()
        right.addLayout(pic)
        right.addWidget(label("Név", "section"))
        right.addWidget(self.name)
        right.addWidget(label("Szín (kép nélkül ez látszik a kezdőbetű mögött)", "section"))
        right.addLayout(sw)
        right.addWidget(label("Statisztika", "section"))
        right.addWidget(self.stats)
        right.addWidget(self.reset_stats, 0, Qt.AlignLeft)
        right.addWidget(self.state)
        right.addWidget(self.msg)
        right.addStretch()
        right.addWidget(self.delete)

        lay = QHBoxLayout(self)
        lay.addLayout(left, 2)
        lay.addSpacing(16)
        lay.addLayout(right, 3)
        self.reload()

    # ── lista ──
    def reload(self, select=None):
        self.list.blockSignals(True)
        self.list.clear()
        playing = set(self.main.pids)
        for p in self.main.profiles:
            it = QListWidgetItem(QIcon(avatar_pixmap(p)), p["name"] + ("   ● játékban" if p["id"] in playing else ""))
            it.setData(Qt.UserRole, p["id"])
            self.list.addItem(it)
        self.list.blockSignals(False)
        ids = [p["id"] for p in self.main.profiles]
        want = select or self.cur
        self.list.setCurrentRow(ids.index(want) if want in ids else (0 if ids else -1))
        self._select(self.list.currentRow())

    def profile(self):
        return next((p for p in self.main.profiles if p["id"] == self.cur), None)

    def _select(self, row):
        item = self.list.item(row) if row >= 0 else None
        self.cur = item.data(Qt.UserRole) if item else None
        p = self.profile()
        on = p is not None
        for w in (self.name, self.upload, self.remove_img, self.delete) + tuple(b for _, b in self.swatches):
            w.setEnabled(on)
        self.msg.setText("")
        self.show_stats(p)
        if not p:
            self.avatar.set_player("?", None)
            self.name.setText("")
            self.state.setText("")
            return
        self.name.setText(p["name"])
        self.avatar.set_player(p["name"], pf.avatar_path(p), p["color"])
        self.remove_img.setEnabled(pf.avatar_path(p) is not None)
        for c, b in self.swatches:
            b.setChecked(c == p["color"])
        self.state.setText("● Most a játékban szerepel" if p["id"] in self.main.pids else "Nincs a játékban")

    # ── statisztika ──
    def stats_row(self, p):
        """A profil összesítése a mentett játékokból (None, ha még nincs egy sem a nullázás óta)."""
        if not p:
            return None
        rows = history.aggregate(self.main.history, since=self.main.stats_since())
        return next((r for r in rows if r["pid"] == p["id"]), None)

    def show_stats(self, p):
        r = self.stats_row(p)
        if r is None:
            self.stats.setText("Még nincs mentett játék ennél a profilnál.")
        else:
            parts = [f"{r['games']} játék", f"{r['wins']} győzelem" + (f" ({r['win_pct']:.0f}%)" if r["win_pct"] is not None else "")]
            if r["avg3"] is not None:
                parts.append(f"3 nyilas átlag {r['avg3']:.1f}")
            if r["best"]:
                parts.append(f"legjobb kör {r['best']}")
            if r["c180"]:
                parts.append(f"{r['c180']}× 180")
            if r["checkout"]:
                parts.append(f"legjobb kiszálló {r['checkout']}")
            self.stats.setText("  ·  ".join(parts))
        self.reset_stats.setEnabled(r is not None)

    def reset_profile_stats(self):
        p = self.profile()
        if not p or self.stats_row(p) is None:
            return
        if not ask.confirm(self, "Statisztika nullázása",
                           f"Biztosan nullázod {p['name']} statisztikáit?\n\nA játékok és győzelmek száma, az átlag, a legjobb kör, "
                           "a 180-ak és a legjobb kiszálló is nullázódik. A befejezett játékok listája (Statisztikák → Előzmények) "
                           "megmarad.\nEz nem vonható vissza."):
            return
        self.main.reset_stats(p["id"])
        self.show_stats(p)
        self.msg.setText(f"{p['name']} statisztikái nullázva.")

    # ── szerkesztés ──
    def _changed(self):
        self.main.profiles_changed()
        self.reload(self.cur)

    def add_profile(self):
        name, ok = QInputDialog.getText(self, "Új profil", "Név:", text=pf.unique_name(self.main.profiles, "Játékos"))
        name = name.strip()
        if not ok or not name:
            return
        if pf.name_taken(self.main.profiles, name):
            self.msg.setText(f"„{name}” nevű profil már van.")
            return
        p = pf.make_profile(name, [x["color"] for x in self.main.profiles])
        self.main.profiles.append(p)
        self.main.profiles_changed()
        self.reload(p["id"])

    def rename(self):
        p = self.profile()
        if not p:
            return
        new = self.name.text().strip()
        if new == p["name"]:
            return
        if not new:
            self.msg.setText("A név nem lehet üres.")
            self.name.setText(p["name"])
        elif pf.name_taken(self.main.profiles, new, p["id"]):
            self.msg.setText(f"„{new}” nevű profil már van.")
            self.name.setText(p["name"])
        else:
            self.main.rename_profile(p["id"], new)
            self._changed()

    def set_color(self, color):
        p = self.profile()
        if p:
            p["color"] = color
            self._changed()

    def choose_image(self):
        p = self.profile()
        if not p:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Profilkép kiválasztása", str(Path.home()),
                                              "Képek (*.jpg *.jpeg *.png *.bmp *.webp)")
        if not path:
            return
        try:
            name = pf.import_avatar(path, p["id"], self.main.avatar_dir)
        except ValueError as e:
            self.msg.setText(str(e))
            return
        pf.delete_avatar(p, self.main.avatar_dir)          # a régi kép törlése, majd az újé
        p["avatar"] = name
        self._changed()

    def clear_image(self):
        p = self.profile()
        if p:
            pf.delete_avatar(p, self.main.avatar_dir)
            self._changed()

    def delete_profile(self):
        p = self.profile()
        if not p:
            return
        if p["id"] in self.main.pids:
            self.msg.setText("Ez a profil most játszik: előbb vedd ki a játékból (jobb oldali − gomb).")
            return
        if len(self.main.profiles) <= 1:
            self.msg.setText("Legalább egy profilnak maradnia kell.")
            return
        if not ask.confirm(self, "Profil törlése", f"Biztosan törlöd: {p['name']}?"):
            return
        pf.delete_avatar(p, self.main.avatar_dir)
        self.main.profiles.remove(p)
        self.cur = None
        self.main.profiles_changed()
        self.reload()


class GamePage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.approval = QComboBox()
        self.approval.addItems(["Automatikus elfogadás, ha minden nyíl biztos", "Mindig kézi jóváhagyás"])
        self.approval.setCurrentIndex(main.approval_idx)
        self.approval.currentIndexChanged.connect(main.set_approval)
        self.countdown = QSpinBox()
        self.countdown.setRange(10, 180)
        self.countdown.setSuffix(" mp")
        self.countdown.setValue(int(main.countdown))
        self.countdown.valueChanged.connect(main.set_countdown)
        self.end_screen = QCheckBox("Meccs végén a győztes képernyő megjelenik (konfettivel, átlagokkal)")
        self.end_screen.setChecked(bool(main.cfg.get("end_screen", True)))
        self.end_screen.toggled.connect(self.set_end_screen)
        lay = QVBoxLayout(self)
        lay.addWidget(label("Meccs vége", "section"))
        lay.addWidget(self.end_screen)
        lay.addWidget(label("Kamerás kör jóváhagyása", "section"))
        lay.addWidget(label("Amikor a kamera felismerte a kör nyilait, a program ennyi időt ad az ellenőrzésre, "
                            "utána (ha nincs bizonytalan nyíl) magától elfogadja."))
        lay.addWidget(self.approval)
        lay.addWidget(label("Ellenőrzési idő", "section"))
        lay.addWidget(self.countdown)
        lay.addWidget(label("A módosítás a következő körtől érvényes. A Double Out / Straight Out kiszállást az alsó "
                            "sávban, a játékmódot a Játékmód választóval állíthatod."))
        lay.addStretch()

    def set_end_screen(self, on):
        self.main.cfg["end_screen"] = bool(on)
        self.main.save_state()


class CameraPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.model = label("")
        pick = QPushButton("Modellfájl kiválasztása…")
        pick.clicked.connect(self.choose)
        lay = QVBoxLayout(self)
        lay.addWidget(label("Dobásfelismerő modell (.pt)", "section"))
        lay.addWidget(self.model)
        lay.addWidget(pick)
        lay.addWidget(label("Kalibrációs varázsló", "section"))
        lay.addWidget(label("Élő képpel segít a tábla és a fények beállításában a felismerő modellnek: zöld/piros kerettel és "
                            "teendőkkel jelzi, mi van rendben."))
        wiz = QPushButton("🧭  Kalibrációs varázsló megnyitása")
        wiz.clicked.connect(self.main.open_wizard)
        lay.addWidget(wiz)
        lay.addWidget(label("Saját modell betanítása", "section"))
        lay.addWidget(label("A program a saját kameráid képeiből tanít dobásfelismerő modellt: te dobsz, a program javasolja a "
                            "nyílhegyeket, te jóváhagyod, aztán betanít és megméri a modellt. Nem kell hozzá külső modellfájl."))
        train = QPushButton("🎓  Modell betanítása a saját kamerámból")
        train.clicked.connect(self.main.open_trainer)
        lay.addWidget(train)
        lay.addWidget(label("Kamerák hozzáadása és eltávolítása a főképernyő bal oldalán történik. Két kamera egyszerre is "
                            "használható: a Dobásfelismerést mindkettőn be kell kapcsolni, a program összeveti a két képet."))
        lay.addStretch()
        self.refresh()

    def refresh(self):
        path = self.main.cfg.get("model")
        self.model.setText(f"Jelenlegi: {path}" if path else "Még nincs kiválasztva (az első bekapcsoláskor a program megkérdezi).")

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(self, "Dobásfelismerő modell", str(self.main.app_dir), "YOLO modell (*.pt)")
        if path:
            self.main.cfg["model"] = path
            self.main.backend = None                      # a következő bekapcsolásnál az új modell töltődik be
            self.main.save_state()
            self.refresh()


class SoundPage(QWidget):
    """Hangeffektek: be/ki, hangerő és próbagombok minden hanghoz."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.on = QCheckBox("Hangeffektek bekapcsolva")
        self.on.setChecked(main.sound.enabled)
        self.on.toggled.connect(main.set_sound)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(round(main.sound.volume * 100))
        self.value = QLabel(f"{self.slider.value()}%")
        self.value.setMinimumWidth(48)
        self.slider.valueChanged.connect(self.set_volume)
        self.slider.sliderReleased.connect(lambda: main.sound.play("dart", force=True))
        vol = QHBoxLayout()
        vol.addWidget(QLabel("Hangerő"))
        vol.addWidget(self.slider, 1)
        vol.addWidget(self.value)
        grid = QGridLayout()
        self.tests = {}
        for i, cue in enumerate(sounds.CUES):
            b = QPushButton(sounds.NAMES[cue])
            b.clicked.connect(lambda _=False, cue=cue: main.sound.play(cue, force=True))
            self.tests[cue] = b
            grid.addWidget(b, i // 2, i % 2)
        lay = QVBoxLayout(self)
        lay.addWidget(label("Hang", "section"))
        lay.addWidget(self.on)
        lay.addLayout(vol)
        lay.addWidget(label("Kipróbálás:"))
        lay.addLayout(grid)
        self.speech = QCheckBox("Pontszám felolvasása a kör végén (és a győzelemnél)")
        self.speech.setChecked(main.speaker.enabled)
        self.speech.toggled.connect(main.set_speech)
        self.speech_test = QPushButton("🗣  Felolvasás kipróbálása")
        self.speech_test.clicked.connect(main.speaker.sample)
        lay.addWidget(self.speech)
        lay.addWidget(self.speech_test)
        lay.addWidget(label("A felolvasás a gép hangját használja (Windowson magyar hang esetén magyarul, különben "
                            "számjegyekkel, a hang saját nyelvén). A magyar hang a Windows Beállítások → Idő és nyelv → Nyelv "
                            "→ Magyar → Beszéd menüpontban telepíthető."))
        lay.addWidget(label("A hang a dobás után szól: nyíl a táblán, dupla, tripla, bull, következő játékos, 100+ kör, 180, bust "
                            "és győzelem (a bust és a 100+ X01-nél a ténylegesen levont pontot nézi). A visszavonás és az új játék néma. "
                            "A fejléc 🔊 gombjával gyorsan némíthatod. A hangok az assets/sounds mappában vannak, "
                            "bármelyik felülírható saját WAV fájllal."))
        lay.addStretch()

    def set_volume(self, percent):
        self.value.setText(f"{percent}%")
        self.main.set_volume(percent)


class LookPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.maximized = QCheckBox("Induláskor kitölti a képernyőt")
        self.maximized.setChecked(bool(main.cfg.get("maximized", True)))
        self.maximized.toggled.connect(self.set_max)
        full = QPushButton("⛶  Teljes képernyő be/ki")
        full.clicked.connect(main.toggle_fullscreen)
        self.welcome = QCheckBox("Induláskor az üdvözlő ablak megjelenik")
        self.welcome.setChecked(not main.cfg.get("welcome_hidden", False))
        self.welcome.toggled.connect(self.set_welcome)
        show_now = QPushButton("🖼  Üdvözlő ablak megnyitása")
        show_now.clicked.connect(self.open_welcome)
        lay = QVBoxLayout(self)
        lay.addWidget(label("Megjelenés", "section"))
        lay.addWidget(self.maximized)
        lay.addWidget(self.welcome)
        lay.addWidget(show_now)
        lay.addWidget(label("A felület méretei az ablak méretéhez igazodnak, így kisebb képernyőn is ráfér."))
        lay.addWidget(full)
        lay.addStretch()

    def set_max(self, on):
        self.main.cfg["maximized"] = bool(on)
        self.main.save_state()

    def set_welcome(self, on):
        self.main.cfg["welcome_hidden"] = not on
        self.main.save_state()

    def open_welcome(self):
        self.main.show_welcome()
        self.welcome.blockSignals(True)                      # az ablak pipája átírhatta a beállítást
        self.welcome.setChecked(not self.main.cfg.get("welcome_hidden", False))
        self.welcome.blockSignals(False)


class AboutPage(QWidget):
    def __init__(self, main):
        super().__init__()
        lay = QVBoxLayout(self)
        logo = QLabel()
        pm = QPixmap(str(main.logo_file))
        if not pm.isNull():
            logo.setPixmap(pm.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(logo)
        lay.addWidget(label(APP_NAME, "section"))
        lay.addWidget(label(f"Verzió: {VERSION}"))
        self.author = label(f"A programot {AUTHOR} készítette.", "section")
        lay.addWidget(self.author)
        self.link = QLabel(f"<a href='{GITHUB_URL}' style='color:#ff9d2e'>{GITHUB_URL}</a>")
        self.link.setTextFormat(Qt.RichText)
        self.link.setOpenExternalLinks(True)
        lay.addWidget(self.link)
        lay.addWidget(label("Többjátékos darts kezelőfelület élő kameraképpel és kamerás dobásfelismeréssel. "
                            "A beállításokat a program a felhasználói mappa .rkbully könyvtárába menti. "
                            "A játékmódok szabályai a játékmód-választó ℹ gombjával olvashatók."))
        lay.addStretch()


class OptionsDialog(QDialog):
    PAGES = ("👤  Profilok", "🎮  Játék", "📷  Kamera", "🔊  Hang", "🖥  Megjelenés", "ℹ  Névjegy")

    def __init__(self, main, page=0):
        super().__init__(main)
        self.setWindowTitle("Beállítások")
        self.resize(940, 600)
        self.nav = QListWidget()
        self.nav.setFixedWidth(210)
        self.nav.addItems(self.PAGES)
        self.pages = QStackedWidget()
        self.profiles_page = ProfilesPage(main)
        for w in (self.profiles_page, GamePage(main), CameraPage(main), SoundPage(main), LookPage(main), AboutPage(main)):
            self.pages.addWidget(w)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(page)
        close = QPushButton("Kész")
        close.setObjectName("go")
        close.clicked.connect(self.accept)
        title = QLabel("⚙  Beállítások")
        title.setObjectName("kicker")
        body = QHBoxLayout()
        body.addWidget(self.nav)
        body.addWidget(self.pages, 1)
        lay = QVBoxLayout(self)
        lay.addWidget(title)
        lay.addLayout(body, 1)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        lay.addLayout(row)


class AddPlayerDialog(QDialog):
    """Játékos hozzáadása a játékhoz: egy még nem játszó profil, vagy új profil."""

    def __init__(self, main):
        super().__init__(main)
        self.main, self.picked = main, None
        self.setWindowTitle("Játékos hozzáadása")
        self.resize(420, 480)
        self.list = QListWidget()
        self.list.setIconSize(QSize(40, 40))
        self.list.itemDoubleClicked.connect(lambda _: self.accept_pick())
        self.fill()
        new = QPushButton("＋  Új profil…")
        new.clicked.connect(self.new_profile)
        ok = QPushButton("Hozzáadás")
        ok.setObjectName("go")
        ok.clicked.connect(self.accept_pick)
        lay = QVBoxLayout(self)
        lay.addWidget(label("Válassz a profilok közül, vagy hozz létre újat:", "section"))
        lay.addWidget(self.list, 1)
        lay.addWidget(new)
        lay.addWidget(ok)

    def fill(self):
        self.list.clear()
        playing = set(self.main.pids)
        for p in self.main.profiles:
            if p["id"] in playing:
                continue
            it = QListWidgetItem(QIcon(avatar_pixmap(p)), p["name"])
            it.setData(Qt.UserRole, p["id"])
            self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(0)

    def accept_pick(self):
        it = self.list.currentItem()
        if it:
            self.picked = it.data(Qt.UserRole)
            self.accept()

    def new_profile(self):
        name, ok = QInputDialog.getText(self, "Új profil", "Név:", text=pf.unique_name(self.main.profiles, "Játékos"))
        name = name.strip()
        if not ok or not name:
            return
        if pf.name_taken(self.main.profiles, name):
            QMessageBox.information(self, "Új profil", f"„{name}” nevű profil már van.")
            return
        p = pf.make_profile(name, [x["color"] for x in self.main.profiles])
        self.main.profiles.append(p)
        self.main.profiles_changed()
        self.picked = p["id"]
        self.accept()
