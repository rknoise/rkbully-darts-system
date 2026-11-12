"""Modell-betanító ablak: a saját kamerád képeiből tanít dobásfelismerő modellt.

Négy lépés (fülek): ① előkészítés (kalibráció, csomagok), ② gyűjtés (a program javasolja a nyílhegyeket, te jóváhagyod),
③ betanítás (külön folyamatban, haladásjelzővel), ④ próba (a modell megméri magát a tanításban nem használt képeken,
majd használatba veheted). A logika a trainer.py-ban van; ez csak a felület."""
import json
import shutil
import threading
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar,
                               QPushButton, QTabWidget, QVBoxLayout, QWidget)

import ask
import sounds
import trainer as tr
import vision
import wizard
from theme import GREEN, ORANGE, RED, YELLOW

try:
    import cv2
except ImportError:                                    # pragma: no cover
    cv2 = None

TABS = ("①  Előkészítés", "②  Gyűjtés", "③  Betanítás", "④  Próba")
HOWTO = (
    "Így tanul a program a saját kameráidból:\n\n"
    "1.  Kalibrációt mentesz a Kalibrációs varázslóval (a tábla négy jele). Ez kamerán­ként egyszer kell.\n"
    "2.  A ②  Gyűjtés lapon rögzíted az üres tábla képét, majd dobsz: a program észreveszi az új nyilat, és megjelöli a\n"
    "     javasolt nyílhegyet. Te jóváhagyod (Enter), vagy a képre kattintva kijavítod, vagy „Nem nyíl”-nak jelölöd (Del).\n"
    "3.  Kb. 150 jóváhagyott nyílnál jön használható modell; minél több és változatosabb (a tábla minden részére, több\n"
    "     fényben, több nyíltípussal), annál jobb. A gyűjtés bármikor folytatható.\n"
    "4.  A ③  Betanítás lap elindítja a tanítást (processzoron percekig-órákig tarthat, közben a gép használható), a\n"
    "     ④  Próba lap megméri a modellt, és ha jó, használatba veszed.")


def dataset_darts_mm(store):
    """A gyűjtött nyilak helye mm-ben (körönként a legtöbb nyilat tartalmazó minta): a lefedettség ellenőrzéséhez."""
    best = {}
    for m in store.all_meta():
        if m["round"] not in best or len(m["darts"]) > len(best[m["round"]]["darts"]):
            best[m["round"]] = m
    out = []
    for m in best.values():
        try:
            cal = tr.Calibration({n: tuple(p) for n, p in m["cal"].items()}, int(m["size"]))
            if cal.H is not None:
                out += [cal.to_mm(x, y) for x, y in m["darts"]]
        except Exception:
            continue
    return out


def fmt_time(seconds):
    if seconds is None:
        return "…"
    s = int(round(seconds))
    return f"{s // 3600} ó {s % 3600 // 60} p" if s >= 3600 else f"{s // 60} p {s % 60:02d} mp"


class TrainerDialog(QDialog):
    """sources: [{"label", "text", "get"}] (mint a varázslónál). store_path: a kalibrációs fájl. data_dir: a tanítókészlet és a
    tanítás mappája. models_dir: ide kerül a használatba vett modell. on_model(path): a főablak átveszi az új modellt."""

    def __init__(self, parent, sources, store_path, data_dir, models_dir, open_wizard=None, add_camera=None, on_model=None,
                 job_factory=None, backend_factory=None, clock=time.monotonic, python=None, current=0):
        super().__init__(parent)
        self.setWindowTitle("Modell betanítása")
        self.resize(1180, 780)
        self.sources, self.store_path, self.clock = list(sources), Path(store_path), clock
        self.data_dir, self.models_dir = Path(data_dir), Path(models_dir)
        self.open_wizard, self.add_camera, self.on_model = open_wizard, add_camera, on_model
        self.job_factory = job_factory or tr.TrainJob
        self.backend_factory = backend_factory or vision.YoloBackend
        self.python = python
        self.store = tr.DatasetStore(self.data_dir / "dataset")
        self.session = time.strftime("%Y%m%d%H%M%S")
        self.current = min(max(int(current), 0), max(len(self.sources) - 1, 0))
        self.cal, self.collector, self._cal_sig, self.sq = None, None, None, None
        self.pending_tip, self.accept_stack, self.message = None, [], ""
        self.job, self.epoch_times, self._epoch_t, self.job_error = None, [], None, None
        self.model_path, self.eval_result, self._eval_thread, self._eval_out = None, None, None, None
        self.installed_path = None

        top = QHBoxLayout()
        top.addWidget(QLabel("Kamera:"))
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self.pick_camera)
        top.addWidget(self.combo, 1)
        self.add_btn = QPushButton("⊕  Kamera hozzáadása")
        self.add_btn.clicked.connect(self.on_add)
        top.addWidget(self.add_btn)

        self.tabs = QTabWidget()
        for page in (self.build_prepare(), self.build_collect(), self.build_train(), self.build_test()):
            self.tabs.addTab(page, TABS[self.tabs.count()])
        self.tabs.currentChanged.connect(self.on_tab)
        self.close_btn = QPushButton("Bezárás")
        self.close_btn.clicked.connect(self.close)
        foot = QHBoxLayout()
        foot.addStretch()
        foot.addWidget(self.close_btn)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.tabs, 1)
        lay.addLayout(foot)

        for key, slot in (("Return", self.accept_candidate), ("Enter", self.accept_candidate), ("Delete", self.reject_candidate),
                          ("Backspace", self.undo_last)):
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(lambda s=slot: self.tabs.currentIndex() == 1 and s())

        self.fill_sources()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(60)
        self.refresh_all()

    # ───────────── a lapok felépítése ─────────────
    def build_prepare(self):
        page = QWidget()
        self.howto = QLabel(HOWTO)
        self.howto.setWordWrap(True)
        self.cal_lbl, self.dep_lbl, self.data_lbl = QLabel(), QLabel(), QLabel()
        for lb in (self.cal_lbl, self.dep_lbl, self.data_lbl):
            lb.setWordWrap(True)
        self.wiz_btn = QPushButton("🧭  Kalibrációs varázsló megnyitása")
        self.wiz_btn.clicked.connect(self.on_wizard)
        self.clear_btn = QPushButton("🗑  Gyűjtött képek törlése…")
        self.clear_btn.clicked.connect(self.clear_dataset)
        lay = QVBoxLayout(page)
        title = QLabel("Saját modell a saját kamerádhoz")
        title.setObjectName("kicker")
        lay.addWidget(title)
        lay.addWidget(self.howto)
        lay.addSpacing(8)
        lay.addWidget(self.cal_lbl)
        lay.addWidget(self.wiz_btn)
        lay.addWidget(self.dep_lbl)
        lay.addWidget(self.data_lbl)
        lay.addWidget(self.clear_btn, 0, Qt.AlignLeft)
        lay.addStretch(1)
        return page

    def build_collect(self):
        page = QWidget()
        self.view = wizard.FrameView()
        self.view.clicked.connect(self.on_click)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(54)
        self.empty_btn = QPushButton("📷  Üres tábla rögzítése")
        self.empty_btn.clicked.connect(self.set_empty)
        self.ok_btn = QPushButton("✔  Jóváhagyom (Enter)")
        self.ok_btn.setObjectName("go")
        self.ok_btn.clicked.connect(self.accept_candidate)
        self.no_btn = QPushButton("✖  Nem nyíl (Del)")
        self.no_btn.clicked.connect(self.reject_candidate)
        self.undo_btn = QPushButton("↶  Visszavonás (Backspace)")
        self.undo_btn.clicked.connect(self.undo_last)
        self.count_lbl = QLabel()
        self.count_lbl.setWordWrap(True)
        self.hint_lbl = QLabel()
        self.hint_lbl.setWordWrap(True)
        self.hint_lbl.setStyleSheet(f"color: {YELLOW}; font-weight: 600;")
        help_ = QLabel("1.  Húzd ki a nyilakat, és kattints az „Üres tábla rögzítése” gombra.\n"
                       "2.  Dobj egy nyilat: a program megjelöli a javasolt nyílhegyet (narancs kereszt).\n"
                       "3.  Ha jó, Enter. Ha nem, kattints a képen a pontos nyílhegyre, majd Enter. Ha nem nyíl, Del.\n"
                       "4.  Három nyíl után húzd ki őket (a program észreveszi), és dobj újra. Dobj a tábla minden részére!")
        help_.setWordWrap(True)
        help_.setObjectName("muted")
        side = QVBoxLayout()
        side.addWidget(help_)
        side.addWidget(self.empty_btn)
        side.addWidget(self.ok_btn)
        side.addWidget(self.no_btn)
        side.addWidget(self.undo_btn)
        side.addSpacing(6)
        side.addWidget(self.count_lbl)
        side.addWidget(self.hint_lbl)
        side.addStretch(1)
        panel = QWidget()
        panel.setFixedWidth(380)
        panel.setLayout(side)
        left = QVBoxLayout()
        left.addWidget(self.view, 1)
        left.addWidget(self.status)
        lay = QHBoxLayout(page)
        lay.addLayout(left, 1)
        lay.addWidget(panel)
        return page

    def build_train(self):
        page = QWidget()
        self.preset = QComboBox()
        for key, (epochs, size, name) in tr.PRESETS.items():
            self.preset.addItem(f"{name}: {epochs} kör, {size} px", key)
        self.preset.setCurrentIndex(1)
        self.train_info = QLabel()
        self.train_info.setWordWrap(True)
        self.start_btn = QPushButton("▶  Betanítás indítása")
        self.start_btn.setObjectName("go")
        self.start_btn.clicked.connect(self.start_training)
        self.stop_btn = QPushButton("■  Megszakítás")
        self.stop_btn.clicked.connect(self.cancel_training)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.progress_lbl = QLabel()
        self.progress_lbl.setWordWrap(True)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(300)
        lay = QVBoxLayout(page)
        title = QLabel("Betanítás")
        title.setObjectName("kicker")
        lay.addWidget(title)
        lay.addWidget(self.train_info)
        row = QHBoxLayout()
        row.addWidget(QLabel("Beállítás:"))
        row.addWidget(self.preset, 1)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(self.start_btn, 2)
        row2.addWidget(self.stop_btn, 1)
        lay.addLayout(row2)
        lay.addWidget(self.bar)
        lay.addWidget(self.progress_lbl)
        lay.addWidget(self.log, 1)
        return page

    def build_test(self):
        page = QWidget()
        self.model_lbl = QLabel()
        self.model_lbl.setWordWrap(True)
        self.pick_btn = QPushButton("Meglévő modell megnyitása…")
        self.pick_btn.clicked.connect(self.pick_model)
        self.eval_btn = QPushButton("🔬  Modell kipróbálása a gyűjtött képeken")
        self.eval_btn.clicked.connect(self.evaluate_model)
        self.verdict_lbl = QLabel()
        self.verdict_lbl.setWordWrap(True)
        self.verdict_lbl.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.use_btn = QPushButton("✔  Modell használatba vétele")
        self.use_btn.setObjectName("go")
        self.use_btn.clicked.connect(self.install_model)
        lay = QVBoxLayout(page)
        title = QLabel("Próba és használatba vétel")
        title.setObjectName("kicker")
        lay.addWidget(title)
        lay.addWidget(self.model_lbl)
        lay.addWidget(self.pick_btn, 0, Qt.AlignLeft)
        lay.addWidget(self.eval_btn)
        lay.addWidget(self.verdict_lbl)
        lay.addStretch(1)
        lay.addWidget(self.use_btn)
        return page

    # ───────────── kamerák ─────────────
    def fill_sources(self):
        self.combo.blockSignals(True)
        self.combo.clear()
        for s in self.sources:
            self.combo.addItem(s["label"])
        self.combo.setCurrentIndex(self.current if self.sources else -1)
        self.combo.blockSignals(False)
        self.combo.setVisible(bool(self.sources))
        self.add_btn.setVisible(self.add_camera is not None)

    def set_sources(self, sources):
        self.sources = list(sources)
        self.current = min(self.current, max(len(self.sources) - 1, 0))
        self.fill_sources()
        self.refresh_all()

    def on_add(self):
        if self.add_camera:
            self.add_camera()

    def pick_camera(self, i):
        if 0 <= i < len(self.sources):
            self.current = i
            self.reset_collection()
            self.refresh_all()

    def key(self):
        return self.sources[self.current]["text"] if self.sources else ""

    def frame(self):
        if not self.sources:
            return None
        try:
            return self.sources[self.current]["get"]()
        except Exception:
            return None

    # ───────────── állapot és szövegek ─────────────
    def on_tab(self, _):
        self.refresh_all()

    def refresh_all(self):
        saved = bool(self.sources) and wizard.saved_points(self.store_path, self.key(), 1000) is not None
        if not self.sources:
            self.cal_lbl.setText("✖  Még nincs kamera. Add hozzá a főképernyőn (vagy a ⊕ gombbal), és helyezd el a táblával szemben.")
        elif saved:
            self.cal_lbl.setText("✔  Ehhez a kamerához van mentett kalibráció.")
        else:
            self.cal_lbl.setText("✖  Ehhez a kamerához még nincs kalibráció. Nyisd meg a Kalibrációs varázslót, és mentsd el.")
        self.cal_lbl.setStyleSheet(f"color: {GREEN if saved else RED}; font-weight: 700;")
        self.wiz_btn.setEnabled(self.open_wizard is not None)
        has = tr.ultralytics_available()
        self.dep_lbl.setText("✔  A tanításhoz szükséges csomag (ultralytics) telepítve van." if has else
                             "✖  Az ultralytics csomag hiányzik: futtasd a Felismeres_telepitese.bat fájlt (vagy a telepítőt újra). "
                             "Gyűjteni így is lehet, tanítani csak a csomaggal.")
        self.dep_lbl.setStyleSheet(f"color: {GREEN if has else YELLOW}; font-weight: 600;")
        n, d = self.store.count(), self.store.n_darts()
        self.data_lbl.setText(f"Gyűjtött tanítóképek: {n} db, ebben {d} nyíl. "
                              f"(Tanításhoz legalább {tr.MIN_SAMPLES} kép kell, használható modellhez kb. {tr.GOOD_DARTS} nyíl.)")
        self.clear_btn.setEnabled(n > 0)
        self.count_lbl.setText(f"Gyűjtve: {n} kép, {d} nyíl  (cél: ~{tr.GOOD_DARTS} nyíl)")
        self.hint_lbl.setText(tr.coverage_hint(dataset_darts_mm(self.store)) if n else "")
        self.train_info.setText(f"A tanítókészlet: {n} kép, {d} nyíl. " + (
            "Indíthatod a tanítást." if n >= tr.MIN_SAMPLES and has else
            f"Még kevés a kép (legalább {tr.MIN_SAMPLES} kell)." if n < tr.MIN_SAMPLES else "Az ultralytics csomag hiányzik."))
        self.update_buttons()
        self.update_test_texts()

    def update_buttons(self):
        c = self.collector.candidate if self.collector else None
        self.ok_btn.setEnabled(c is not None)
        self.no_btn.setEnabled(c is not None)
        self.undo_btn.setEnabled(bool(self.accept_stack))
        self.empty_btn.setEnabled(self.collector is not None)
        running = bool(self.job and self.job.running)
        self.start_btn.setEnabled(not running and self.store.count() >= tr.MIN_SAMPLES and tr.ultralytics_available())
        self.stop_btn.setEnabled(running)
        self.preset.setEnabled(not running)

    def update_test_texts(self):
        if self.model_path:
            self.model_lbl.setText(f"Modell: {self.model_path}")
        else:
            self.model_lbl.setText("Még nincs betanított modell. Tanítsd be a ③ lapon, vagy nyiss meg egy meglévőt.")
        self.eval_btn.setEnabled(bool(self.model_path) and self.store.count() > 0 and self._eval_thread is None)
        self.use_btn.setEnabled(bool(self.model_path))

    # ───────────── gyűjtés ─────────────
    def reset_collection(self):
        self.collector, self._cal_sig, self.pending_tip, self.accept_stack = None, None, None, []

    def ensure_calibration(self, size):
        """A mentett kalibráció az aktuális képmérethez; változásnál új gyűjtő (az üres tábla képét újra kell rögzíteni)."""
        pts = wizard.saved_points(self.store_path, self.key(), size)
        sig = (self.key(), size, None if pts is None else tuple(sorted(pts.items())))
        if sig == self._cal_sig:
            return
        self._cal_sig = sig
        self.cal = self.collector = None
        self.pending_tip, self.accept_stack = None, []
        if pts is None:
            return
        cal = tr.Calibration(pts, size)
        if cal.problem() is None:
            self.cal, self.collector = cal, tr.Collector(cal)

    def set_empty(self):
        if self.collector is None or self.sq is None:
            return
        self.collector.set_empty(self.sq)
        self.pending_tip, self.accept_stack = None, []
        self.message = "Üres tábla rögzítve. Dobj egy nyilat!"

    def on_click(self, x, y, button):
        if self.collector is not None and self.collector.candidate is not None and button == 1:
            self.pending_tip = (x, y)
            self.message = "Javított nyílhegy: nyomj Entert a jóváhagyáshoz."

    def accept_candidate(self):
        c = self.collector.candidate if self.collector else None
        if c is None:
            return
        sample = self.collector.accept(self.pending_tip)
        self.pending_tip = None
        sid = self.store.add(sample, self.session) if sample is not None else None
        self.accept_stack.append(sid)
        self.message = ("Mentve. " if sid else "") + (
            "" if sid else "Még van egy jelöletlen nyíl ugyanezen a képen: jelöld azt is.")
        self.refresh_all()

    def reject_candidate(self):
        if self.collector and self.collector.candidate is not None:
            self.collector.reject()
            self.pending_tip = None
            self.message = "Nem nyílnak jelölve: többé nem foglalkozom ezzel a folttal."
            self.update_buttons()

    def undo_last(self):
        if not self.accept_stack or self.collector is None:
            return
        sid = self.accept_stack.pop()
        self.collector.undo()
        if sid:
            self.store.remove(sid)
        self.message = "Az utolsó nyíl visszavonva."
        self.refresh_all()

    def clear_dataset(self):
        if self.store.count() == 0:
            return
        if not ask.confirm(self, "Modell betanítása", f"Biztosan törlöd mind a {self.store.count()} gyűjtött tanítóképet?"):
            return
        for sid in self.store.ids():
            self.store.remove(sid)
        self.accept_stack = []
        self.refresh_all()

    def on_wizard(self):
        if self.open_wizard:
            self.open_wizard()
            self._cal_sig = None
            self.refresh_all()

    def tick(self):
        self.poll_job()
        self.poll_eval()
        f = self.frame()
        if f is None:
            self.sq = None
            if self.tabs.currentIndex() == 1:
                self.view.clear_frame()
                self.view.caption = ("Még nincs kamera hozzáadva." if not self.sources else "Kapcsolódás a kamerához…")
                self.view.update()
                self.status.setText("")
            return
        sq = tr.square_crop(f)[0]
        self.sq = sq
        self.ensure_calibration(sq.shape[0])
        if self.tabs.currentIndex() != 1:
            return
        self.view.caption = ""
        self.view.set_frame(sq)
        if self.collector is None:
            self.view.lines, self.view.markers, self.view.border = [], [], None
            self.set_status("A gyűjtéshez előbb mentsd el a kamera kalibrációját (① Előkészítés lap).", RED)
            self.update_buttons()
            return
        for ev in self.collector.feed(sq, self.clock()):
            if ev[0] == "removed":
                self.message = "A nyilak kihúzva: dobhatsz újra."
                self.accept_stack = []
            elif ev[0] == "candidate":
                self.pending_tip = None
                self.message = ""
        self.draw_overlay()
        self.update_buttons()

    def draw_overlay(self):
        col = self.collector
        rings, wires = self.cal.shapes()
        self.view.lines = [(np.vstack([r, r[:1]]), "#55ffffff", 1) for r in rings] + [(w, "#33ffffff", 1) for w in wires]
        marks = [(k["tip"][0], k["tip"][1], GREEN, "") for k in col.known]
        c = col.candidate
        if c is not None:
            tip = self.pending_tip or c.tip
            marks.append((tip[0], tip[1], ORANGE, "?" if self.pending_tip is None else "✓"))
        self.view.markers = marks
        state = col.state
        if state == "no_reference":
            text, color = "Húzd ki a nyilakat a tábláról, majd kattints az „Üres tábla rögzítése” gombra.", YELLOW
        elif state == "moving":
            text, color = "Mozgás a képen… várok, amíg megnyugszik.", YELLOW
        elif state == "busy" or state == "tainted":
            text, color = col.message, RED
        elif state == "candidate":
            extra = f" (még {c.unresolved} új folt van a képen)" if c is not None and c.unresolved else ""
            text, color = "Új nyíl! Jó a narancs jelölés? Enter = jóváhagyom, vagy kattints a pontos nyílhegyre." + extra, ORANGE
        else:
            text, color = "Figyelem… dobj egy nyilat.", GREEN
        if self.message:
            text += "\n" + self.message
        self.set_status(text, color)
        self.view.border = color

    def set_status(self, text, color):
        self.status.setText(text)
        self.status.setStyleSheet(f"background: rgba(0,0,0,120); border: 2px solid {color}; border-radius: 10px; "
                                  f"padding: 8px 12px; font-size: 14px; font-weight: 600; color: #fff;")

    # ───────────── betanítás ─────────────
    def start_training(self):
        if self.job and self.job.running:
            return
        if self.store.count() < tr.MIN_SAMPLES:
            return
        key = self.preset.currentData()
        try:
            work = self.data_dir / "run"
            work.mkdir(parents=True, exist_ok=True)
            data_yaml, n_train, n_val = self.store.build(work)
            cfg_path = work / "beallitas.json"
            cfg_path.write_text(json.dumps(tr.job_config(data_yaml, key, work / "runs", base=tr.base_weights(self.models_dir.parent))), encoding="utf-8")
            script = Path(__file__).resolve().parent / "tools" / "train_worker.py"
            self.job = self.job_factory([tr.python_exe(self.python), str(script), str(cfg_path)], cwd=str(work))
            self.job.start()
        except Exception as e:
            self.progress_lbl.setText(f"✖  A tanítás nem indult el: {e}")
            return
        self.split = (n_train, n_val)
        self.epoch_times, self._epoch_t, self.job_error, self.model_path = [], self.clock(), None, None
        self.bar.setValue(0)
        self.log.clear()
        self.progress_lbl.setText(f"Indul… ({n_train} tanító és {n_val} ellenőrző kép; a betöltés egy ideig eltarthat)")
        self.update_buttons()

    def cancel_training(self):
        if self.job and self.job.running:
            self.job.cancel()
            self.progress_lbl.setText("A tanítás megszakítva.")
            self.job_error = "megszakítva"
        self.update_buttons()

    def poll_job(self):
        job = self.job
        if job is None:
            return
        for line in job.poll():
            ev = tr.parse_line(line)
            if ev is None:
                if not line.startswith("RKBULLY_"):
                    self.log.appendPlainText(line[:200])
                else:
                    self.log.appendPlainText(line.split("|", 1)[1][:200])
                continue
            if ev[0] == "epoch":
                _, n, total, m = ev
                now = self.clock()
                if self._epoch_t is not None:
                    self.epoch_times.append(max(now - self._epoch_t, 0.0))
                self._epoch_t = now
                self.bar.setValue(int(100 * n / max(total, 1)))
                eta = tr.estimate_remaining(self.epoch_times, n, total)
                self.progress_lbl.setText(f"Kör {n}/{total}" + (f"  ·  találati arány (mAP50): {m:.2f}" if m is not None else "")
                                          + f"  ·  hátralévő idő: {fmt_time(eta)}")
            elif ev[0] == "done":
                self.model_path = Path(ev[1])
                self.bar.setValue(100)
                self.progress_lbl.setText("✔  A tanítás kész. Próbáld ki a ④ Próba lapon.")
                self.log.appendPlainText("Kész: " + ev[1])
            elif ev[0] == "error":
                self.job_error = ev[1]
                self.progress_lbl.setText("✖  " + ev[1])
        if job.finished():
            if self.model_path is None and self.job_error is None:
                self.job_error = "a tanítás váratlanul leállt"
                self.progress_lbl.setText("✖  A tanítás váratlanul leállt. A napló alatt látszik az oka.")
            self.job = None
            self.update_buttons()
            self.update_test_texts()

    # ───────────── próba ─────────────
    def pick_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Modell megnyitása", str(self.models_dir), "YOLO modell (*.pt)")
        if path:
            self.model_path = Path(path)
            self.eval_result = None
            self.verdict_lbl.setText("")
            self.update_test_texts()

    def eval_items(self):
        """A kiértékelés képei: a tanításban nem használt (validációs) képek, ha vannak; különben az összes."""
        ids = self.store.ids()
        val_file = self.data_dir / "run" / "val.txt"
        train_file = self.data_dir / "run" / "train.txt"
        self.eval_separate = False
        if val_file.is_file() and train_file.is_file():
            val = {Path(p).stem for p in val_file.read_text(encoding="utf-8").split()}
            train = {Path(p).stem for p in train_file.read_text(encoding="utf-8").split()}
            if val and not (val & train):
                ids, self.eval_separate = [i for i in ids if i in val], True
        items = []
        for sid in ids:
            m = self.store.meta(sid)
            img = cv2.imread(str(self.store.folder / "images" / f"{sid}.jpg"))
            if img is not None:
                items.append((img, [tuple(d) for d in m["darts"]], {n: tuple(p) for n, p in m["cal"].items()}))
        return items

    def evaluate_model(self):
        if not self.model_path or self._eval_thread is not None:
            return
        items = self.eval_items()
        if not items:
            self.verdict_lbl.setText("Nincs mivel összehasonlítani: gyűjts képeket.")
            return
        path = self.model_path
        self._eval_out = {}
        self.verdict_lbl.setText("Kipróbálás folyamatban…")
        self.verdict_lbl.setStyleSheet("font-size: 16px; font-weight: 700;")

        def work(out=self._eval_out):
            try:
                out["result"] = tr.evaluate(self.backend_factory(str(path)), items)
            except Exception as e:
                out["error"] = f"{type(e).__name__}: {e}"

        self._eval_thread = threading.Thread(target=work, daemon=True)
        self._eval_thread.start()
        self.update_test_texts()

    def poll_eval(self):
        if self._eval_thread is None or self._eval_thread.is_alive():
            return
        self._eval_thread = None
        out = self._eval_out or {}
        if "error" in out:
            self.verdict_lbl.setText("✖  A modell nem tölthető be: " + out["error"])
            self.verdict_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {RED};")
        else:
            self.eval_result = out["result"]
            text = tr.verdict(self.eval_result)
            text += ("\n(A tanításban nem használt képeken mérve.)" if self.eval_separate else
                     "\n(Figyelem: kevés a kör, ezért a tanításban használt képeken mérve: valósabb eredményhez gyűjts több kört.)")
            self.verdict_lbl.setText(text)
            color = GREEN if text.startswith("Jó") else YELLOW if text.startswith("Használható") else RED
            self.verdict_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {color};")
        self.update_test_texts()

    def install_model(self):
        if not self.model_path or not Path(self.model_path).is_file():
            self.verdict_lbl.setText("✖  A modellfájl nem található.")
            return
        self.models_dir.mkdir(parents=True, exist_ok=True)
        dest = self.models_dir / f"rkbully_{time.strftime('%Y%m%d_%H%M%S')}.pt"
        shutil.copyfile(self.model_path, dest)
        self.installed_path = dest
        if self.on_model:
            self.on_model(dest)
        self.verdict_lbl.setText(f"✔  A modell használatban: {dest.name}. A Dobásfelismerés következő bekapcsolásakor ezt tölti be.")
        self.verdict_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {GREEN};")

    # ───────────── bezárás ─────────────
    def done(self, result):
        self.timer.stop()
        if self.job and self.job.running:
            self.job.cancel()
        super().done(result)

    def closeEvent(self, e):
        if self.job and self.job.running and QGuiApplication.platformName() not in sounds.HEADLESS:
            if not ask.confirm(self, "Modell betanítása", "A tanítás még fut: ha bezárod az ablakot, megszakad. Bezárod?"):
                e.ignore()
                return
        self.timer.stop()
        if self.job and self.job.running:
            self.job.cancel()
        super().closeEvent(e)
