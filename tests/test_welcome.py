"""Az induláskor megjelenő üdvözlő ablak és a „Többé ne jelenjen meg” jelölő (képernyő nélkül)."""
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QApplication
    import options
    import rkbully
    import welcome
except Exception:                                       # pragma: no cover
    rkbully = None


@unittest.skipIf(rkbully is None, "PySide6 nincs telepítve")
class WelcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(rkbully.QSS)

    def setUp(self):
        self._cfg, self._exec = rkbully.CFG_FILE, welcome.WelcomeDialog.exec
        rkbully.CFG_FILE = Path(tempfile.mkdtemp()) / "settings.json"
        self.opened = []
        self.tick = None                                 # mit csináljon a „felhasználó” az ablakban
        welcome.WelcomeDialog.exec = lambda dlg: self.fake_exec(dlg)
        self.win = rkbully.Main()

    def tearDown(self):
        rkbully.dispose(self.win)
        self.win = None
        rkbully.CFG_FILE, welcome.WelcomeDialog.exec = self._cfg, self._exec

    def fake_exec(self, dlg):
        self.opened.append(dlg.hide_box.isChecked())
        if self.tick:
            self.tick(dlg)
        dlg.accept()

    def saved(self):
        return json.loads(rkbully.CFG_FILE.read_text(encoding="utf-8"))

    def test_image_ships_with_the_app(self):
        path = welcome.image_path(rkbully.APP_DIR)
        self.assertTrue(path.is_file())
        self.assertGreater(path.stat().st_size, 10_000)

    def test_shown_on_first_start(self):
        self.win.startup_welcome()
        self.assertEqual(self.opened, [False])           # alapból nincs bepipálva
        self.assertFalse(self.win.cfg["welcome_hidden"])
        self.assertFalse(self.saved()["welcome_hidden"])

    def test_tick_hides_it_on_every_later_start(self):
        self.tick = lambda d: d.hide_box.setChecked(True)
        self.win.startup_welcome()
        self.assertTrue(self.saved()["welcome_hidden"])
        self.tick = None
        win2 = rkbully.Main()                            # új indítás ugyanazzal a beállításfájllal
        try:
            win2.startup_welcome()
        finally:
            rkbully.dispose(win2)
        self.assertEqual(self.opened, [False])           # a második indításkor már nem nyílt meg

    def test_closing_without_tick_keeps_showing_it(self):
        self.win.startup_welcome()
        self.win.startup_welcome()
        self.assertEqual(self.opened, [False, False])

    def test_hidden_flag_does_not_block_the_manual_open(self):
        self.win.cfg["welcome_hidden"] = True
        self.win.show_welcome()
        self.assertEqual(self.opened, [True])            # a pipa állapota látszik, és ki is vehető
        self.tick = lambda d: d.hide_box.setChecked(False)
        self.win.show_welcome()
        self.assertFalse(self.win.cfg["welcome_hidden"])

    def test_missing_or_broken_image_never_stops_the_start(self):
        self.win.app_dir = Path(tempfile.mkdtemp())      # nincs benne assets/welcome.jpg
        self.win.startup_welcome()
        bad = Path(tempfile.mkdtemp())
        (bad / "assets").mkdir()
        (bad / "assets" / "welcome.jpg").write_bytes(b"nem kep")
        self.win.app_dir = bad
        self.win.startup_welcome()
        self.assertEqual(self.opened, [])

    def test_dialog_fits_small_screens_and_keeps_the_aspect(self):
        from PySide6.QtGui import QPixmap
        src = QPixmap(str(welcome.image_path(rkbully.APP_DIR)))
        for w, h in ((1366, 768), (800, 600), (3840, 2160)):
            size = welcome.fit_size(src, QSize(w, h))
            self.assertLessEqual(size.width(), w)
            self.assertLessEqual(size.height() + welcome.FOOTER_PX, h)
            self.assertAlmostEqual(size.width() / size.height(), src.width() / src.height(), delta=0.02)
        self.assertEqual(welcome.fit_size(src, QSize(3840, 2160)), src.size())    # nagyobb képernyőn sem nagyítja

    def test_options_page_toggles_and_reopens(self):
        page = options.OptionsDialog(self.win, 4).pages.currentWidget()   # a főablak gyermekeként
        self.assertIsInstance(page, options.LookPage)
        self.assertTrue(page.welcome.isChecked())
        page.welcome.setChecked(False)
        self.assertTrue(self.saved()["welcome_hidden"])
        self.tick = lambda d: d.hide_box.setChecked(False)
        page.open_welcome()                              # a most kikapcsolt ablak kézzel még megnyitható
        self.assertEqual(self.opened, [True])
        self.assertTrue(page.welcome.isChecked())        # és a pipa visszakerült az oldalra
        self.assertFalse(self.saved()["welcome_hidden"])


if __name__ == "__main__":
    unittest.main()
