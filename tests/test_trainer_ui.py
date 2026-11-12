"""A modell-betanító ablak: gyűjtés szintetikus kamerával, betanítás hamis folyamattal, próba, használatba vétel."""
import hashlib
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np

import trainer as tr
import vision
from tests import synth

try:
    from PySide6.QtWidgets import QApplication
    import trainer_ui
    import wizard
except Exception:                                       # pragma: no cover
    trainer_ui = None

SIZE = 640
TIP = (0, -103)                                         # egy nyíl helye mm-ben (a 20-as mező külső része)


class FakeJob:
    """Hamis tanítófolyamat: a tesztek adják a sorait."""
    created = []

    def __init__(self, command, cwd=None):
        self.command, self.cwd = command, cwd
        self.pending, self.is_running, self.cancelled = [], False, False
        FakeJob.created.append(self)

    def start(self):
        self.is_running = True

    def poll(self):
        out, self.pending = self.pending, []
        return out

    @property
    def running(self):
        return self.is_running

    def finished(self):
        return not self.is_running and not self.pending

    def cancel(self):
        self.cancelled, self.is_running = True, False


class OracleBackend:
    """Tökéletes „modell”: a képből (bájtazonosság alapján) tudja a helyes választ."""

    def __init__(self, truth, noise=0.0):
        self.truth, self.noise = truth, noise

    def detect(self, img):
        darts, cal = self.truth[hashlib.md5(img.tobytes()).hexdigest()]
        d = vision.Detections()
        d.darts = [(x + self.noise, y, 0.9) for x, y in darts]
        d.cal = {n: (x, y, 0.9) for n, (x, y) in cal.items()}
        return d


@unittest.skipIf(trainer_ui is None, "PySide6 nincs telepítve")
class TrainerUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        FakeJob.created = []
        self.tmp = Path(tempfile.mkdtemp())
        self.store_path = self.tmp / "calibration.json"
        self.empty, _, self.cal, _ = synth.render(SIZE)
        self.state = {"img": self.empty}
        self.src = [{"label": "Webkamera 0", "text": "0", "get": lambda: self.state["img"]}]
        self.t = 0.0
        self.models = []
        self.made = []

    def tearDown(self):
        for d in self.made:
            d.timer.stop()
            d.done(0)
            d.deleteLater()

    def calibrate(self):
        wizard.save_calibration(self.store_path, "0", self.cal, SIZE)

    def make(self, sources=None, **kw):
        kw.setdefault("job_factory", FakeJob)
        kw.setdefault("on_model", self.models.append)
        d = trainer_ui.TrainerDialog(None, self.src if sources is None else sources, self.store_path, self.tmp / "data",
                                     self.tmp / "models", clock=lambda: self.t, **kw)
        self.made.append(d)
        return d

    def run_for(self, d, seconds=2.0, step=0.1):
        end = self.t + seconds
        while self.t < end:
            self.t += step
            d.tick()
        self.app.processEvents()

    def with_dart(self, *darts):
        self.state["img"] = synth.render(SIZE, darts_mm=list(darts))[0]

    def collecting(self):
        """Kalibrált ablak a Gyűjtés lapon, rögzített üres táblával."""
        self.calibrate()
        d = self.make()
        d.tabs.setCurrentIndex(1)
        self.run_for(d, 0.3)
        d.empty_btn.click()
        return d

    def fill_dataset(self, d, n=40, per_round=3):
        for i in range(n):
            dart = (float((i * 37) % 120 - 60), float((i * 53) % 120 - 60))
            img = synth.render(SIZE, darts_mm=[dart])[0]
            tip = synth.render(SIZE, darts_mm=[dart])[1][0]
            d.store.add(tr.Sample(img, [tip], dict(self.cal), i // per_round), "t")
        d.refresh_all()

    # ── előkészítés ──
    def test_without_a_camera_it_explains_what_to_do(self):
        d = self.make(sources=[])
        d.tabs.setCurrentIndex(1)
        self.run_for(d, 0.3)
        self.assertIn("Még nincs kamera", d.cal_lbl.text())
        self.assertIn("Még nincs kamera", d.view.caption)
        self.assertFalse(d.empty_btn.isEnabled())

    def test_missing_calibration_blocks_collecting_and_offers_the_wizard(self):
        called = []
        d = self.make(open_wizard=lambda: called.append(1))
        d.tabs.setCurrentIndex(1)
        self.run_for(d, 0.3)
        self.assertIn("nincs kalibráció", d.cal_lbl.text())
        self.assertIn("kalibrációját", d.status.text())
        self.assertIsNone(d.collector)
        d.wiz_btn.click()
        self.assertEqual(called, [1])

    def test_saved_calibration_is_recognised(self):
        self.calibrate()
        d = self.make()
        self.assertIn("van mentett kalibráció", d.cal_lbl.text())

    # ── gyűjtés ──
    def test_a_thrown_dart_is_proposed_and_saved_on_enter(self):
        d = self.collecting()
        self.run_for(d, 1.5)
        self.assertIn("Figyelem", d.status.text())
        self.with_dart(TIP)
        self.run_for(d, 2.5)
        c = d.collector.candidate
        self.assertIsNotNone(c)
        self.assertTrue(d.ok_btn.isEnabled())
        tip = synth.render(SIZE, darts_mm=[TIP])[1][0]
        self.assertLess(np.hypot(c.tip[0] - tip[0], c.tip[1] - tip[1]), 0.03 * SIZE)
        d.accept_candidate()
        self.assertEqual(d.store.count(), 1)
        self.assertEqual(d.store.n_darts(), 1)
        labels = (d.store.folder / "labels" / "s00001.txt").read_text().splitlines()
        self.assertEqual(len(labels), 5)                       # 1 nyíl + 4 kalibrációs pont
        self.assertIn("1 nyíl", d.count_lbl.text())

    def test_a_click_corrects_the_tip_before_saving(self):
        d = self.collecting()
        self.with_dart(TIP)
        self.run_for(d, 2.5)
        d.on_click(111.0, 222.0, 1)
        self.assertEqual(d.pending_tip, (111.0, 222.0))
        d.accept_candidate()
        meta = d.store.meta(d.store.ids()[0])
        self.assertEqual(meta["darts"], [[111.0, 222.0]])

    def test_not_a_dart_is_ignored_from_then_on(self):
        d = self.collecting()
        self.with_dart(TIP)
        self.run_for(d, 2.5)
        d.reject_candidate()
        self.run_for(d, 2.0)
        self.assertIsNone(d.collector.candidate)
        self.assertEqual(d.store.count(), 0)

    def test_undo_removes_the_saved_sample(self):
        d = self.collecting()
        self.with_dart(TIP)
        self.run_for(d, 2.5)
        d.accept_candidate()
        self.assertTrue(d.undo_btn.isEnabled())
        d.undo_last()
        self.assertEqual(d.store.count(), 0)
        self.assertFalse(d.undo_btn.isEnabled())
        self.run_for(d, 2.5)
        self.assertIsNotNone(d.collector.candidate)           # a nyíl újra jelölt

    def test_pulling_the_darts_out_starts_a_new_round(self):
        d = self.collecting()
        self.with_dart(TIP)
        self.run_for(d, 2.5)
        d.accept_candidate()
        self.state["img"] = self.empty
        self.run_for(d, 3.0)
        self.assertEqual(d.collector.round_id, 1)
        self.assertIn("kihúzva", d.status.text())

    def test_hints_about_weak_zones_appear_with_enough_data(self):
        self.calibrate()
        d = self.make()
        self.fill_dataset(d, 24, per_round=1)
        self.assertIn("Dobj még ide", d.hint_lbl.text())

    def test_a_different_picture_size_resets_the_reference(self):
        d = self.collecting()
        self.assertEqual(d.collector.state, "watching")
        old = d.collector
        self.state["img"] = synth.render(320)[0]
        self.run_for(d, 0.3)
        self.assertIsNot(d.collector, old)                    # a mentett kalibráció átskálázódik, de új gyűjtő kell
        self.assertEqual(d.collector.size, 320)
        self.assertEqual(d.collector.state, "no_reference")

    # ── betanítás ──
    def test_training_needs_enough_images_and_the_package(self):
        self.calibrate()
        d = self.make()
        with unittest.mock.patch.object(tr, "ultralytics_available", return_value=True):
            d.refresh_all()
            self.assertFalse(d.start_btn.isEnabled())
            self.fill_dataset(d, 40)
            self.assertTrue(d.start_btn.isEnabled())
        with unittest.mock.patch.object(tr, "ultralytics_available", return_value=False):
            d.refresh_all()
            self.assertFalse(d.start_btn.isEnabled())
            self.assertIn("ultralytics", d.dep_lbl.text())

    def start(self, d):
        self.fill_dataset(d, 40)
        with unittest.mock.patch.object(tr, "ultralytics_available", return_value=True):
            d.refresh_all()
            d.start_training()
        return FakeJob.created[-1]

    def test_training_starts_the_worker_with_the_chosen_preset(self):
        self.calibrate()
        d = self.make()
        d.preset.setCurrentIndex(0)
        job = self.start(d)
        self.assertTrue(job.running)
        self.assertTrue(job.command[1].endswith("train_worker.py"))
        import json
        cfg = json.loads(Path(job.command[2]).read_text(encoding="utf-8"))
        self.assertEqual(cfg["epochs"], tr.PRESETS["fast"][0])
        self.assertTrue(Path(cfg["data"]).is_file())
        self.assertFalse(d.start_btn.isEnabled())
        self.assertTrue(d.stop_btn.isEnabled())

    @unittest.mock.patch.object(tr, "ultralytics_available", return_value=True)
    def test_progress_eta_and_done(self, _):
        self.calibrate()
        d = self.make()
        job = self.start(d)
        for n in (1, 2, 3):
            self.t += 30.0
            job.pending = [f"RKBULLY_EPOCH|{n}|80|0.{n}0"]
            d.tick()
        self.assertIn("Kör 3/80", d.progress_lbl.text())
        self.assertIn("mAP50", d.progress_lbl.text())
        self.assertIn("hátralévő", d.progress_lbl.text())
        self.assertEqual(d.bar.value(), 3)
        best = self.tmp / "best.pt"
        best.write_bytes(b"x")
        job.pending = [f"RKBULLY_DONE|{best}"]
        job.is_running = False
        d.tick()
        self.assertEqual(d.model_path, best)
        self.assertEqual(d.bar.value(), 100)
        self.assertIn("kész", d.progress_lbl.text())
        self.assertTrue(d.start_btn.isEnabled())
        self.assertTrue(d.use_btn.isEnabled())

    def test_worker_error_is_shown(self):
        self.calibrate()
        d = self.make()
        job = self.start(d)
        job.pending = ["RKBULLY_ERROR|Az ultralytics csomag nincs telepítve."]
        job.is_running = False
        d.tick()
        self.assertIn("ultralytics", d.progress_lbl.text())
        self.assertIsNone(d.model_path)

    def test_unexpected_exit_is_reported(self):
        self.calibrate()
        d = self.make()
        job = self.start(d)
        job.pending = ["Traceback (most recent call last):"]
        job.is_running = False
        d.tick()
        d.tick()
        self.assertIn("váratlanul", d.progress_lbl.text())
        self.assertIn("Traceback", d.log.toPlainText())

    def test_cancel_and_closing_stop_the_job(self):
        self.calibrate()
        d = self.make()
        job = self.start(d)
        d.cancel_training()
        self.assertTrue(job.cancelled)
        self.assertIn("megszakítva", d.progress_lbl.text())
        job2 = self.start(d)
        d.close()
        self.assertTrue(job2.cancelled)

    # ── próba és használatba vétel ──
    def truth_and_backend(self, d, noise=0.0):
        truth = {}
        for sid in d.store.ids():
            m = d.store.meta(sid)
            img = cv2.imread(str(d.store.folder / "images" / f"{sid}.jpg"))
            truth[hashlib.md5(img.tobytes()).hexdigest()] = ([tuple(p) for p in m["darts"]], {n: tuple(p) for n, p in m["cal"].items()})
        return lambda path: OracleBackend(truth, noise)

    def wait_eval(self, d):
        if d._eval_thread is not None:
            d._eval_thread.join(10)
        d.tick()

    def test_good_model_gets_a_good_verdict_on_unseen_images(self):
        self.calibrate()
        d = self.make()
        job = self.start(d)
        d.backend_factory = self.truth_and_backend(d)
        d.model_path = self.tmp / "m.pt"
        d.evaluate_model()
        self.wait_eval(d)
        self.assertTrue(d.verdict_lbl.text().startswith("Jó modell"), d.verdict_lbl.text())
        self.assertIn("nem használt", d.verdict_lbl.text())
        self.assertTrue(d.eval_separate)
        self.assertIsNotNone(job)

    def test_poor_model_is_called_poor(self):
        self.calibrate()
        d = self.make()
        self.fill_dataset(d, 40)
        d.backend_factory = self.truth_and_backend(d, noise=60.0)
        d.model_path = self.tmp / "m.pt"
        d.evaluate_model()
        self.wait_eval(d)
        self.assertIn("gyenge", d.verdict_lbl.text())

    def test_broken_model_file_is_reported_not_raised(self):
        self.calibrate()
        d = self.make()
        self.fill_dataset(d, 5)

        def boom(path):
            raise RuntimeError("sérült fájl")
        d.backend_factory = boom
        d.model_path = self.tmp / "m.pt"
        d.evaluate_model()
        self.wait_eval(d)
        self.assertIn("nem tölthető be", d.verdict_lbl.text())

    def test_nothing_to_compare_without_images(self):
        d = self.make()
        d.model_path = self.tmp / "m.pt"
        d.evaluate_model()
        self.assertIn("gyűjts képeket", d.verdict_lbl.text())

    def test_install_copies_the_model_and_tells_the_main_window(self):
        d = self.make()
        best = self.tmp / "best.pt"
        best.write_bytes(b"modell")
        d.model_path = best
        d.install_model()
        self.assertEqual(len(self.models), 1)
        self.assertTrue(self.models[0].is_file())
        self.assertEqual(self.models[0].parent, self.tmp / "models")
        self.assertEqual(self.models[0].read_bytes(), b"modell")
        self.assertIn("használatban", d.verdict_lbl.text())

    def test_install_without_a_model_file_does_nothing(self):
        d = self.make()
        d.model_path = self.tmp / "nincs.pt"
        d.install_model()
        self.assertEqual(self.models, [])

    def test_clear_dataset_asks_first(self):
        self.calibrate()
        d = self.make()
        self.fill_dataset(d, 3)
        with unittest.mock.patch.object(trainer_ui.ask, "confirm", return_value=False):
            d.clear_dataset()
        self.assertEqual(d.store.count(), 3)
        with unittest.mock.patch.object(trainer_ui.ask, "confirm", return_value=True):
            d.clear_dataset()
        self.assertEqual(d.store.count(), 0)

    def test_dataset_persists_between_sessions(self):
        self.calibrate()
        d = self.make()
        self.fill_dataset(d, 4)
        d2 = self.make()
        self.assertEqual(d2.store.count(), 4)

    def test_fmt_time(self):
        self.assertEqual(trainer_ui.fmt_time(None), "…")
        self.assertEqual(trainer_ui.fmt_time(95), "1 p 35 mp")
        self.assertEqual(trainer_ui.fmt_time(3700), "1 ó 1 p")


try:
    import rkbully
except Exception:                                       # pragma: no cover
    rkbully = None


@unittest.skipIf(rkbully is None or trainer_ui is None, "PySide6 nincs telepítve")
class MainTrainerTests(unittest.TestCase):
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
        self._cls = trainer_ui.TrainerDialog
        outer = self

        class Fake(self._cls):
            def exec(self):
                outer.opened.append(self)
                self.on_model(Path("E:/modellek/uj.pt"))
                return 0
        trainer_ui.TrainerDialog = Fake

    def tearDown(self):
        trainer_ui.TrainerDialog = self._cls
        rkbully.dispose(self.win)
        self.win = None
        rkbully.CFG_FILE = self._cfg

    def test_open_trainer_uses_the_shared_files_and_takes_the_model(self):
        self.win.backend = object()
        self.win.open_trainer()
        dlg = self.opened[0]
        self.assertEqual(dlg.store_path, self.tmp / "calibration.json")
        self.assertEqual(dlg.data_dir, self.tmp / "training")
        self.assertEqual(dlg.models_dir, rkbully.APP_DIR / "models")
        self.assertEqual(self.win.cfg["model"], str(Path("E:/modellek/uj.pt")))
        self.assertIsNone(self.win.backend)                    # a következő bekapcsolásnál az új modell töltődik be

    def test_settings_page_has_the_trainer_button(self):
        import options
        page = options.CameraPage(self.win)
        names = [b.text() for b in page.findChildren(rkbully.QPushButton)]
        self.assertTrue(any("Modell betanítása" in n for n in names))


if __name__ == "__main__":
    unittest.main()
