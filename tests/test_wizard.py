"""Kalibrációs varázsló: kamera- és fényellenőrzés, a tábla automatikus keresése, mentés, felület (szintetikus képekkel)."""
import math
import os
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np

import camcheck as cc
import trainer as tr
import vision
from tests import synth

try:
    from PySide6.QtWidgets import QApplication
    import wizard
except Exception:                                       # pragma: no cover
    wizard = None

SIZE = 640


def frame(**kw):
    img, tips, cal, H = synth.render(SIZE, **kw)
    return img, tr.Calibration(cal, SIZE), cal


def levels(checks):
    return {c.key: c.level for c in checks}


class CheckTests(unittest.TestCase):
    def test_a_good_setup_is_all_green(self):
        img, cal, _ = frame(noise=1.0)
        checks = cc.analyze(img, cal)
        self.assertEqual(set(levels(checks).values()), {cc.OK})
        self.assertEqual(cc.overall(checks), cc.OK)
        self.assertEqual(cc.instructions(checks), [])

    def test_blurry_image_is_red_with_a_focus_hint(self):
        img, cal, _ = frame()
        checks = cc.analyze(cv2.GaussianBlur(img, (0, 0), 4), cal)
        self.assertEqual(levels(checks)["sharp"], cc.BAD)
        self.assertEqual(cc.overall(checks), cc.BAD)
        self.assertIn("élesíts", " ".join(cc.instructions(checks)))

    def test_dark_and_overexposed_images(self):
        img, cal, _ = frame(brightness=0.3)
        self.assertEqual(levels(cc.analyze(img, cal))["light"], cc.BAD)
        img, cal, _ = frame(brightness=2.4)
        self.assertEqual(levels(cc.analyze(img, cal))["glare"], cc.BAD)
        img, cal, _ = frame(brightness=5.0)
        got = levels(cc.analyze(img, cal))
        self.assertEqual(got["light"], cc.BAD)
        self.assertEqual(got["glare"], cc.BAD)

    def test_a_glare_spot_is_found(self):
        img, cal, _ = frame()
        img = img.copy()
        cv2.circle(img, (260, 300), 55, (255, 255, 255), -1)
        checks = cc.analyze(img, cal)
        self.assertNotEqual(levels(checks)["glare"], cc.OK)
        self.assertTrue(any("tükröz" in c.title.lower() or "Fényvissza" in c.detail for c in checks if c.key == "glare"))

    def test_one_sided_light_is_reported(self):
        img, cal, _ = frame()
        img = img.copy()
        img[:, :SIZE // 2] = (img[:, :SIZE // 2] * 0.35).astype(np.uint8)
        self.assertNotEqual(levels(cc.analyze(img, cal))["even"], cc.OK)

    def test_off_centre_board_says_which_way_to_turn(self):
        img, cal, _ = frame(shift=(0.16, 0.0))
        got = [c for c in cc.analyze(img, cal) if c.key == "center"][0]
        self.assertEqual(got.level, cc.BAD)
        self.assertIn("jobbra", got.detail)
        img, cal, _ = frame(shift=(0.0, -0.09))
        got = [c for c in cc.analyze(img, cal) if c.key == "center"][0]
        self.assertEqual(got.level, cc.WARN)
        self.assertIn("felfelé", got.detail)

    def test_board_too_small_or_cut_off(self):
        img, cal, _ = frame(fill=0.2)
        got = [c for c in cc.analyze(img, cal) if c.key == "fill"][0]
        self.assertEqual(got.level, cc.BAD)
        self.assertIn("közelebb", got.detail)
        img, cal, _ = frame(fill=0.55)
        got = [c for c in cc.analyze(img, cal) if c.key == "fill"][0]
        self.assertEqual(got.level, cc.BAD)
        self.assertIn("kilóg", got.detail)

    def test_steep_viewing_angle(self):
        img, cal0, pts = frame()
        c = SIZE / 2
        squeezed = {n: (x, c + 0.5 * (y - c)) for n, (x, y) in pts.items()}
        got = [ch for ch in cc.analyze(img, tr.Calibration(squeezed, SIZE)) if ch.key == "angle"][0]
        self.assertEqual(got.level, cc.BAD)

    def test_worst_checks_come_first(self):
        checks = [cc.Check("a", cc.OK, "a"), cc.Check("b", cc.BAD, "b", "x"), cc.Check("c", cc.WARN, "c", "y")]
        self.assertEqual([c.key for c in cc.worst_first(checks)], ["b", "c", "a"])
        self.assertEqual(cc.instructions(checks), ["x", "y"])
        self.assertEqual(cc.overall([cc.Check("a", cc.OK, "a"), cc.Check("c", cc.WARN, "c")]), cc.WARN)

    def test_shake_meter(self):
        img, _, _ = frame()
        m = cc.ShakeMeter()
        m.feed(img)
        self.assertEqual(m.check().level, cc.NONE)               # még kevés kép
        for _ in range(8):
            m.feed(img)
        self.assertEqual(m.check().level, cc.OK)
        rng = np.random.default_rng(0)
        shaky = cc.ShakeMeter()
        for _ in range(10):
            shaky.feed(rng.integers(0, 255, img.shape, dtype=np.uint8))
        self.assertEqual(shaky.check().level, cc.BAD)
        self.assertIn("állvány", shaky.check().detail)


class ModelCheckTests(unittest.TestCase):
    def setUp(self):
        _, self.cal, pts = frame()
        self.pts = pts

    def det(self, dx=0.0, drop=(), conf=0.9):
        d = vision.Detections()
        d.cal = {n: (x + dx, y, conf) for n, (x, y) in self.pts.items() if n not in drop}
        return d

    def test_model_sees_all_four(self):
        self.assertEqual(cc.model_check(self.det(), self.cal).level, cc.OK)

    def test_missing_point_is_red_and_named(self):
        got = cc.model_check(self.det(drop=("3",)), self.cal)
        self.assertEqual(got.level, cc.BAD)
        self.assertIn("3", got.detail)

    def test_low_confidence_counts_as_unseen(self):
        self.assertEqual(cc.model_check(self.det(conf=0.4), self.cal).level, cc.BAD)

    def test_marked_points_far_from_the_models_are_a_warning(self):
        self.assertEqual(cc.model_check(self.det(dx=40.0), self.cal).level, cc.WARN)

    def test_no_model_is_neutral(self):
        self.assertEqual(cc.model_check(None, self.cal).level, cc.NONE)


class EstimateTests(unittest.TestCase):
    def err(self, **kw):
        img, _, pts = frame(**kw)
        est = cc.estimate_points(img)
        self.assertIsNotNone(est, kw)
        return max(math.hypot(est[n][0] - pts[n][0], est[n][1] - pts[n][1]) for n in pts)

    def test_finds_the_board(self):
        self.assertLess(self.err(), 0.03 * SIZE)

    def test_finds_a_shifted_and_dimmer_board(self):
        self.assertLess(self.err(shift=(0.05, -0.03)), 0.03 * SIZE)
        self.assertLess(self.err(brightness=0.6), 0.04 * SIZE)

    def test_result_is_a_valid_calibration(self):
        img, _, _ = frame()
        self.assertIsNone(tr.Calibration(cc.estimate_points(img), SIZE).problem())

    def test_no_board_means_no_estimate(self):
        self.assertIsNone(cc.estimate_points(np.full((SIZE, SIZE, 3), 90, np.uint8)))


class StoreTests(unittest.TestCase):
    def test_saved_points_are_resolution_independent(self):
        path = Path(tempfile.mkdtemp()) / "c.json"
        pts = {"20": (100.0, 50.0), "3": (200.0, 350.0), "11": (60.0, 200.0), "6": (300.0, 180.0)}
        wizard_mod = wizard
        wizard_mod.save_calibration(path, "0", pts, 400)
        self.assertEqual(wizard_mod.saved_points(path, "0", 400), pts)
        big = wizard_mod.saved_points(path, "0", 800)
        self.assertEqual(big["20"], (200.0, 100.0))
        self.assertIsNone(wizard_mod.saved_points(path, "1", 400))

    def test_broken_or_missing_file_is_harmless(self):
        path = Path(tempfile.mkdtemp()) / "c.json"
        self.assertEqual(wizard.load_store(path), {"cameras": {}})
        path.write_text("{ nem json", encoding="utf-8")
        self.assertEqual(wizard.load_store(path), {"cameras": {}})
        self.assertIsNone(wizard.saved_points(path, "0", 100))

    def test_cameras_are_stored_separately(self):
        path = Path(tempfile.mkdtemp()) / "c.json"
        a = {"20": (1.0, 2.0), "3": (3.0, 4.0), "11": (5.0, 6.0), "6": (7.0, 8.0)}
        wizard.save_calibration(path, "0", a, 10)
        wizard.save_calibration(path, "192.168.0.5:8080", {n: (y, x) for n, (x, y) in a.items()}, 10)
        self.assertEqual(wizard.saved_points(path, "0", 10), a)
        self.assertEqual(wizard.saved_points(path, "192.168.0.5:8080", 10)["20"], (2.0, 1.0))


class FakeBackend:
    def __init__(self, cal, offset=0.0, none=False):
        self.cal, self.offset, self.none = cal, offset, none

    def detect(self, img):
        d = vision.Detections()
        if not self.none:
            d.cal = {n: (x - self.offset, y, 0.9) for n, (x, y) in self.cal.items()}
        return d


@unittest.skipIf(wizard is None, "PySide6 nincs telepítve")
class WizardUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = self.tmp / "calibration.json"
        self.img, _, self.cal = frame(noise=1.0)
        self.state = {"img": self.img}
        self.src = [{"label": "Webkamera 0", "text": "0", "get": lambda: self.state["img"]}]
        self.made = []

    def tearDown(self):
        for w in self.made:
            w.timer.stop()
            w.done(0)
            w.deleteLater()

    def make(self, sources=None, **kw):
        w = wizard.CalibrationWizard(None, self.src if sources is None else sources, self.store, **kw)
        self.made.append(w)
        return w

    def run_ticks(self, w, n=6):
        for _ in range(n):
            w._last_check = -1.0
            w.tick()
            self.app.processEvents()

    def use_auto_points(self, w):
        w.tick()
        w.auto_find()
        self.run_ticks(w)

    def test_good_setup_shows_green_and_allows_saving(self):
        w = self.make()
        self.use_auto_points(w)
        self.assertEqual(w.view.border, wizard.GREEN)
        self.assertIn("Minden rendben", w.banner.text())
        self.assertTrue(w.save_btn.isEnabled())
        self.assertEqual(w.todo.text(), w.estimate_msg)

    def test_blurry_camera_shows_red_and_a_todo(self):
        self.state["img"] = cv2.GaussianBlur(self.img, (0, 0), 4)
        w = self.make()
        self.use_auto_points(w)
        self.assertEqual(w.view.border, wizard.RED)
        self.assertIn("Javítandó", w.banner.text())
        self.assertIn("élesíts", w.todo.text())

    def test_warning_gives_yellow(self):
        self.state["img"] = synth.render(SIZE, shift=(0.065, 0.0), noise=1.0)[0]
        w = self.make()
        self.use_auto_points(w)
        self.assertEqual(w.view.border, wizard.YELLOW)

    def test_invalid_points_block_saving_and_say_why(self):
        w = self.make()
        w.tick()
        for i, n in enumerate(tr.CAL_NAMES):
            w.norm[n] = (0.5 + 0.01 * i, 0.5)                  # mind egy vonalban
        w.tick()
        self.assertFalse(w.save_btn.isEnabled())
        self.assertEqual(w.view.border, wizard.RED)
        self.assertIn("✖", w.banner.text())

    def test_dragging_a_handle_updates_the_calibration(self):
        w = self.make()
        w.tick()
        before = w.points(SIZE)["20"]
        w.view.handles["20"] = (before[0] + 30, before[1])
        w.view.handle_moved.emit("20", before[0] + 30, before[1])
        self.assertAlmostEqual(w.points(SIZE)["20"][0], before[0] + 30, delta=1.0)

    def test_save_persists_per_camera_and_is_reloaded(self):
        w = self.make()
        self.use_auto_points(w)
        w.save()
        self.assertTrue(w.saved_any)
        saved = wizard.saved_points(self.store, "0", SIZE)
        self.assertEqual(set(saved), set(tr.CAL_NAMES))
        w2 = self.make()
        w2.tick()
        for n in tr.CAL_NAMES:
            self.assertAlmostEqual(w2.points(SIZE)[n][0], saved[n][0], delta=1.0)

    def test_reset_returns_to_the_initial_guess(self):
        w = self.make()
        self.use_auto_points(w)
        w.reset_points()
        guess = tr.initial_points(SIZE)
        for n in tr.CAL_NAMES:
            self.assertAlmostEqual(w.points(SIZE)[n][0], guess[n][0], delta=1.0)

    def test_failed_search_gives_a_message(self):
        self.state["img"] = np.full((SIZE, SIZE, 3), 80, np.uint8)
        w = self.make()
        w.tick()
        w.auto_find()
        self.assertIn("Nem találtam", w.estimate_msg)

    def test_no_camera_explains_how_to_start(self):
        added = []
        w = self.make(sources=[], add_camera=lambda: added.append(1))
        w.tick()
        self.assertIn("Még nincs kamera", w.view.caption)
        self.assertFalse(w.save_btn.isEnabled())
        self.assertFalse(w.find_btn.isEnabled())
        w.add_btn.click()
        self.assertEqual(added, [1])
        w.set_sources(self.src)
        w.tick()
        self.assertEqual(w.view.caption, "")

    def test_camera_without_a_picture_waits(self):
        w = self.make(sources=[{"label": "x", "text": "9", "get": lambda: None}])
        w.tick()
        self.assertIn("Kapcsolódás", w.view.caption)

    def test_wide_pictures_are_cropped_to_the_centre_square(self):
        wide = synth.render(SIZE, width=1280)[0]
        self.state["img"] = wide
        w = self.make()
        w.tick()
        self.assertEqual(w.view.img_size, (SIZE, SIZE))

    def test_two_cameras_are_calibrated_separately(self):
        other = synth.render(SIZE, shift=(0.03, 0.0))[0]
        sources = self.src + [{"label": "Telefon", "text": "192.168.0.5:8080", "get": lambda: other}]
        w = self.make(sources=sources)
        self.assertTrue(w.combo.isVisible() or len(w.sources) == 2)
        self.use_auto_points(w)
        w.save()
        w.combo.setCurrentIndex(1)
        self.use_auto_points(w)
        w.save()
        store = wizard.load_store(self.store)
        self.assertEqual(set(store["cameras"]), {"0", "192.168.0.5:8080"})

    def test_model_probe_adds_the_model_check(self):
        w = self.make(get_backend=lambda: FakeBackend(self.cal, offset=0))
        self.use_auto_points(w)
        t0 = time.time()
        while w.probe.det is None and time.time() - t0 < 5:
            time.sleep(0.05)
        self.run_ticks(w)
        got = levels(w.checks)["model"]
        self.assertIn(got, (cc.OK, cc.WARN))                   # az automatikus pontok kissé eltérhetnek a valóditól
        self.assertEqual(w.probe.state, "ok")

    def test_a_model_that_sees_nothing_is_red(self):
        w = self.make(get_backend=lambda: FakeBackend(self.cal, none=True))
        self.use_auto_points(w)
        t0 = time.time()
        while w.probe.det is None and time.time() - t0 < 5:
            time.sleep(0.05)
        self.run_ticks(w)
        self.assertEqual(levels(w.checks)["model"], cc.BAD)
        self.assertEqual(w.view.border, wizard.RED)

    def test_missing_model_or_a_broken_one_never_blocks_the_wizard(self):
        w = self.make(get_backend=lambda: None)
        self.use_auto_points(w)
        t0 = time.time()
        while w.probe.state == "loading" and time.time() - t0 < 5:
            time.sleep(0.05)
        self.run_ticks(w)
        self.assertEqual(levels(w.checks)["model"], cc.NONE)

        def boom():
            raise RuntimeError("nincs modell")
        w2 = self.make(get_backend=boom)
        self.use_auto_points(w2)
        t0 = time.time()
        while w2.probe.state == "loading" and time.time() - t0 < 5:
            time.sleep(0.05)
        self.assertEqual(w2.probe.state, "error")
        self.run_ticks(w2)
        self.assertEqual(levels(w2.checks)["model"], cc.NONE)

    def test_hide_offer_checkbox(self):
        w = self.make(hide_checked=True)
        self.assertTrue(w.hide_offer())
        w.hide_box.setChecked(False)
        self.assertFalse(w.hide_offer())

    def test_view_coordinates_round_trip(self):
        w = self.make()
        w.resize(900, 700)
        w.show()
        w.tick()
        self.app.processEvents()
        v = w.view
        for x, y in ((10.0, 20.0), (320.0, 320.0), (600.0, 100.0)):
            p = v.to_view(x, y)
            rx, ry = v.to_img(p)
            self.assertAlmostEqual(rx, x, places=3)
            self.assertAlmostEqual(ry, y, places=3)




try:
    import rkbully
except Exception:                                       # pragma: no cover
    rkbully = None


@unittest.skipIf(rkbully is None, "PySide6 nincs telepítve")
class MainIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(rkbully.QSS)

    def setUp(self):
        self._cfg = rkbully.CFG_FILE
        self.tmp = Path(tempfile.mkdtemp())
        rkbully.CFG_FILE = self.tmp / "settings.json"
        self.win = rkbully.Main()
        self.opened = []
        self._wiz = wizard.CalibrationWizard
        outer = self

        class Fake(self._wiz):
            def exec(self):
                outer.opened.append(self)
                self.saved_any = outer.save_on_open
                return 0
        wizard.CalibrationWizard = Fake
        self.save_on_open = False

    def tearDown(self):
        wizard.CalibrationWizard = self._wiz
        rkbully.dispose(self.win)
        self.win = None
        rkbully.CFG_FILE = self._cfg

    def test_calibration_file_is_next_to_the_settings(self):
        self.assertEqual(self.win.calib_file(), self.tmp / "calibration.json")

    def test_no_camera_opens_with_no_sources(self):
        self.win.open_wizard()
        self.assertEqual(len(self.opened), 1)
        self.assertEqual(self.opened[0].sources, [])

    def test_cameras_become_sources_with_their_frames(self):
        with unittest.mock.patch.object(rkbully.Cam, "grab", lambda self: None):    # nincs valódi kamera-szál
            self.win.add_cam_source("0")
        img = frame()[0]
        self.win.cams[0].frame = img
        self.win.open_wizard()
        src = self.opened[0].sources[0]
        self.assertEqual(src["text"], "0")
        self.assertIs(src["get"](), img)

    def test_startup_wizard_only_once_and_never_when_hidden(self):
        self.win.startup_wizard()                              # fej nélküli módban nem nyílik meg
        self.assertEqual(self.opened, [])
        with unittest.mock.patch.object(rkbully.QGuiApplication, "platformName", return_value="windows"):
            self.save_on_open = True
            self.win.startup_wizard()
            self.assertEqual(len(self.opened), 1)
            self.assertTrue(self.win.cfg["wizard_done"])
            self.win.startup_wizard()                          # elmentett kalibráció után nem ajánlja fel újra
            self.assertEqual(len(self.opened), 1)
            self.win.cfg["wizard_done"] = False
            self.win.cfg["wizard_hidden"] = True
            self.win.startup_wizard()
            self.assertEqual(len(self.opened), 1)

    def test_hide_choice_is_remembered(self):
        self.win.open_wizard()
        self.assertFalse(self.win.cfg["wizard_hidden"])

    def test_silent_backend_never_asks_anything(self):
        self.win.cfg["model"] = None
        self.assertIsNone(self.win.silent_backend())

    def test_settings_page_has_the_wizard_button(self):
        import options
        page = options.CameraPage(self.win)
        names = [b.text() for b in page.findChildren(rkbully.QPushButton)]
        self.assertTrue(any("Kalibrációs varázsló" in n for n in names))


if __name__ == "__main__":
    unittest.main()
