"""Felület-tesztek képernyő nélkül (offscreen Qt). PySide6 nélkül a tesztek kihagyják magukat."""
import json
import os
import random
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    import rkbully
except Exception:                                       # pragma: no cover
    rkbully = None

import games as g
import vision as v
from tests.test_fusion import Cam as FakeCam, D1, FRAME, H_A


def thr(m, n):
    return v.Throw(m, n, 0.0, 0.0, 10.0, 0.9, False)


@unittest.skipIf(rkbully is None, "PySide6 nincs telepítve")
class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(rkbully.QSS)

    def setUp(self):
        self._cfg, self._info = rkbully.CFG_FILE, rkbully.QMessageBox.information
        rkbully.CFG_FILE = Path(tempfile.mkdtemp()) / "settings.json"     # ne írjon a valódi beállításokba
        self.messages = []
        rkbully.QMessageBox.information = staticmethod(lambda *a, **k: self.messages.append(a))
        self.win = rkbully.Main()

    def tearDown(self):
        rkbully.dispose(self.win)
        self.win = None
        rkbully.CFG_FILE, rkbully.QMessageBox.information = self._cfg, self._info

    def test_missing_ultralytics_explains_both_requirements(self):
        import sys
        saved = sys.modules.get("ultralytics", "hiányzik")
        sys.modules["ultralytics"] = None                     # az import ImportError-t dob, akkor is, ha a csomag fel van telepítve
        try:
            self.assertIsNone(self.win.get_backend())
        finally:
            if saved == "hiányzik":
                del sys.modules["ultralytics"]
            else:
                sys.modules["ultralytics"] = saved
        text = self.messages[-1][2]
        self.assertIn("Felismeres_telepitese.bat", text)
        self.assertIn("pip install ultralytics", text)
        self.assertIn("models", text)                          # a modellfájl helye is benne van
        self.assertIn("-m pip install", text)                  # ugyanahhoz a Pythonhoz, amivel a program fut

    def test_help_text_uses_python_exe_even_when_started_with_pythonw(self):
        text = rkbully.ultralytics_help(r"C:\Python313\pythonw.exe", r"E:\rkbully")
        self.assertIn("python.exe", text)
        self.assertNotIn("pythonw", text)
        self.assertIn("models", text)

    def test_every_mode_plays_in_the_ui(self):
        self.win.names = ["A", "B", "C"]
        rnd = random.Random(7)
        for mode in g.MODES:
            self.win.set_mode(mode.id)
            self.assertEqual(self.win.game.n, 3, mode.name)
            for _ in range(60):
                self.win.mult = rnd.choice((1, 2, 3))
                self.win.hit(rnd.choice([0, 25] + list(range(1, 21))))
                self.assertTrue(self.win.hdr.text(), mode.name)
                self.assertTrue(self.win.big.text(), mode.name)
                if self.win.game.winner is not None:
                    break
            self.win.undo()                                # a visszavonás sem dobhat hibát

    def test_window_has_the_app_icon_and_header_logo(self):
        self.assertIsNotNone(rkbully.logo_pixmap())
        self.assertFalse(self.win.windowIcon().isNull())
        marks = [lbl for lbl in self.win.findChildren(QLabel) if lbl.pixmap() is not None and not lbl.pixmap().isNull()]
        self.assertTrue(marks, "nincs logó a fejlécben")

    def test_app_works_without_the_logo_file(self):
        old = rkbully.LOGO_FILE
        rkbully.LOGO_FILE = Path(tempfile.mkdtemp()) / "nincs.png"
        try:
            win = rkbully.Main()
            self.assertIn("Bully", win.findChild(QLabel, "logo").text())       # kép nélkül a szöveges embléma marad
            self.assertTrue(win.mark.isHidden())
            rkbully.dispose(win)
        finally:
            rkbully.LOGO_FILE = old

    def test_info_text_has_player_count_and_rules(self):
        by = {m.id: m for m in g.MODES}
        text = rkbully.rules_html(by["killer"], 3)
        self.assertIn("2–8 játékos", text)
        self.assertIn("Hogyan kell játszani", text)
        self.assertIn("GYENGÉBBIK", text)                  # a szabályok szövege is benne van
        self.assertIn("✓", text)
        self.assertIn("legalább 2", rkbully.rules_html(by["killer"], 1))
        self.assertIn("✗", rkbully.rules_html(by["killer"], 1))
        for m in g.MODES:                                  # minden mód leírása összeáll, a HTML-nek veszélyes karakterek kikerülnek
            self.assertIn(m.players_text().split(" (")[0], rkbully.rules_html(m, 4))

    def test_info_dialog_builds(self):
        dlg = rkbully.InfoDialog(self.win, g.MODES[0], 2)
        self.assertIn("Szabályok", dlg.windowTitle())

    def test_mode_dialog_has_an_info_button_for_every_mode(self):
        dlg = rkbully.ModeDialog(self.win, "501", 3)
        infos = [b for b in dlg.findChildren(QPushButton) if b.text() == "ℹ"]
        self.assertEqual(len(infos), len(g.MODES))
        picks = [b for b in dlg.findChildren(QPushButton) if b.text() == ""]
        self.assertEqual(len(picks), len(g.MODES))
        texts = [lbl.text() for lbl in dlg.findChildren(QLabel)]
        self.assertTrue(any("2–8 játékos" in t for t in texts))          # a kártyán a játékosszám is látszik
        self.assertTrue(any("Killer" in t for t in texts))
        dlg.choose("golf")
        self.assertEqual(dlg.picked, "golf")

    def test_minimum_players_are_enforced(self):
        self.win.names = ["Egyedül"]
        self.win.set_mode("501")
        self.win.set_mode("killer")
        self.assertEqual(self.win.mode_id, "501")           # nem váltott át
        self.assertEqual(len(self.messages), 1)
        self.win.names = ["A", "B"]
        self.win.set_mode("killer")
        self.assertEqual(self.win.mode_id, "killer")
        self.win.del_player()                              # 2 alá nem lehet menni Killernél
        self.assertEqual(len(self.win.names), 2)
        self.assertEqual(len(self.messages), 2)

    def test_double_out_selector_only_for_x01(self):
        self.win.set_mode("501")
        self.assertFalse(self.win.out.isHidden())
        self.win.set_mode("golf")
        self.assertTrue(self.win.out.isHidden())

    def test_legacy_settings_use_the_old_mode_index(self):
        rkbully.CFG_FILE.write_text(json.dumps({"mode": 3, "names": ["A", "B"]}), encoding="utf-8")
        win = rkbully.Main()
        self.assertEqual(win.mode_id, "cricket")
        rkbully.dispose(win)

    def test_settings_pad_players_for_modes_that_need_more(self):
        rkbully.CFG_FILE.write_text(json.dumps({"mode_id": "killer", "names": ["Csak én"]}), encoding="utf-8")
        win = rkbully.Main()
        self.assertEqual(len(win.names), 2)
        rkbully.dispose(win)

    def test_mode_is_saved_by_id(self):
        self.win.set_mode("bobs27")
        self.assertEqual(json.loads(rkbully.CFG_FILE.read_text(encoding="utf-8"))["mode_id"], "bobs27")

    def test_review_round_size_follows_the_game(self):
        """Killer számválasztás: a jóváhagyó panel 1 nyilas kört vár, utána 3 nyilasat."""
        self.win.names = ["A", "B"]
        self.win.set_mode("killer")
        self.assertEqual(self.win.review.size, 1)
        self.win.review.add_detected(thr(1, 7))
        self.assertTrue(self.win.review.full)
        self.assertIsNotNone(self.win.review.seconds_left())      # már az első nyílnál indul a visszaszámlálás
        self.win.accept_round()
        self.assertEqual(self.win.game.num, [7, None])
        self.win.review.add_detected(thr(1, 12))
        self.win.accept_round()
        self.assertFalse(self.win.game.picking)
        self.assertEqual(self.win.review.size, 3)                 # a játék indul: újra 3 nyíl egy kör

    def test_two_cameras_are_fused_into_one_throw(self):
        """Két kamera ugyanazt a nyilat látja: a jóváhagyó panelre egyetlen dobás kerül, a megjegyzés szerint 2 kamera egyezik."""
        orig_grab = rkbully.Cam.grab
        rkbully.Cam.grab = lambda self: None                     # nincs valódi kamera-szál
        try:
            backend = FakeCam(H_A)
            backend.darts_mm = [D1]
            self.win.backend = backend
            self.win.add_cam_source("0")
            self.win.add_cam_source("1")
            a, b = self.win.cams
            self.win.toggle_detect(a, True)
            self.win.toggle_detect(b, True)
            self.assertEqual(len(self.win.service.children), 2)
            for cam in (a, b):
                cam.service.get_frame = lambda: FRAME.copy()      # minden lekérdezés új képkocka, mint egy élő streamnél
            t0 = time.time()
            while time.time() - t0 < 10 and not self.win.review.items:
                self.win.tick()
                time.sleep(0.05)
            time.sleep(0.4)
            self.win.tick()
            items = self.win.review.items
            self.assertEqual([(i.mult, i.num) for i in items], [(3, 20)])
            self.assertEqual(items[0].note, "2 kamera egyezik")
            self.assertFalse(items[0].uncertain)
            self.win.toggle_detect(a, False)                      # az egyik kamera kikapcsolva: a másik tovább megy
            self.assertEqual(len(self.win.service.children), 1)
            self.win.toggle_detect(b, False)
            self.assertIsNone(self.win.service)
        finally:
            self.win.stop_detection()
            rkbully.Cam.grab = orig_grab

    def test_review_shows_why_a_dart_needs_checking(self):
        self.win.review.add_detected(v.Throw(1, 20, 0.0, 0.0, 10.0, 0.9, True, reason="kamerák eltérnek"))
        self.win.refresh_review(force=True)
        self.assertIn("ellenőrizd: kamerák eltérnek", self.win.rv_btns[0].text())

    def test_draw_is_announced(self):
        self.win.names = ["A", "B"]
        self.win.set_mode("highscore")
        for _ in range(60):
            self.win.hit(0)
        self.assertIn("Döntetlen", self.win.hdr.text())


if __name__ == "__main__":
    unittest.main()
