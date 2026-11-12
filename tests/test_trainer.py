import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

import dartboard as db
import trainer as tr
import vision
from tests import synth

SIZE = 640
CAL4 = ("20", "3", "11", "6")


def frames(collector, img, seconds=1.2, t0=0.0, step=0.1):
    """Ugyanazt a képet adja a figyelőnek `seconds` ideig (nyugodt jelenet). Visszaad: (események, a következő időpont)."""
    ev, t = [], t0
    while t < t0 + seconds:
        ev += collector.feed(img, t)
        t += step
    return ev, t


def board(darts_mm=(), **kw):
    img, tips, cal, H = synth.render(SIZE, darts_mm=darts_mm, **kw)
    return img, tips


def new_collector():
    _, _, cal, _ = synth.render(SIZE)
    col = tr.Collector(tr.Calibration(cal, SIZE))
    col.set_empty(board()[0])
    return col


class CropTests(unittest.TestCase):
    def test_square_crop_takes_the_centre_like_the_detector(self):
        wide = np.zeros((720, 1280, 3), np.uint8)
        wide[:, 280:1000] = 255
        sq, x0, y0 = tr.square_crop(wide)
        self.assertEqual(sq.shape[:2], (720, 720))
        self.assertEqual((x0, y0), (280, 0))
        self.assertTrue((sq == 255).all())

    def test_square_image_is_returned_as_is(self):
        sq = np.zeros((300, 300, 3), np.uint8)
        out, x0, y0 = tr.square_crop(sq)
        self.assertIs(out, sq)
        self.assertEqual((x0, y0), (0, 0))

    def test_tall_image_is_cropped_vertically(self):
        tall = np.zeros((900, 500, 3), np.uint8)
        sq, x0, y0 = tr.square_crop(tall)
        self.assertEqual(sq.shape[:2], (500, 500))
        self.assertEqual((x0, y0), (0, 200))


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        _, _, self.cal, self.H = synth.render(SIZE)
        self.c = tr.Calibration(self.cal, SIZE)

    def test_initial_guess_is_close_to_a_centred_board(self):
        guess = tr.initial_points(SIZE)
        for n in CAL4:
            self.assertLess(math.hypot(guess[n][0] - self.cal[n][0], guess[n][1] - self.cal[n][1]), 0.05 * SIZE)

    def test_good_points_are_accepted_and_round_trip(self):
        self.assertIsNone(self.c.problem())
        for p in [(100.0, 200.0), (320.0, 320.0), (500.0, 100.0)]:
            back = self.c.to_px(*self.c.to_mm(*p))
            self.assertAlmostEqual(back[0], p[0], places=3)
            self.assertAlmostEqual(back[1], p[1], places=3)

    def test_board_centre_is_found(self):
        cx, cy = self.c.center_px()
        tx, ty = db.apply_h(self.H, [(0.0, 0.0)])[0]
        self.assertAlmostEqual(cx, tx, places=2)
        self.assertAlmostEqual(cy, ty, places=2)

    def test_points_too_close_together_are_rejected(self):
        c = tr.Calibration({n: (300.0 + i * 3, 300.0 + i * 2) for i, n in enumerate(CAL4)}, SIZE)
        self.assertIsNotNone(c.problem())

    def test_points_in_one_line_are_rejected(self):
        c = tr.Calibration({n: (100.0 + i * 150, 320.0) for i, n in enumerate(CAL4)}, SIZE)
        self.assertIsNotNone(c.problem())

    def test_missing_point_is_a_problem(self):
        pts = dict(self.cal)
        del pts["6"]
        self.assertIsNotNone(tr.Calibration(pts, SIZE).problem())

    def test_point_outside_the_image_is_a_problem(self):
        pts = dict(self.cal)
        pts["20"] = (SIZE * 2.0, 10.0)
        self.assertIsNotNone(tr.Calibration(pts, SIZE).problem())

    def test_mask_covers_board_and_not_the_corner(self):
        mask = self.c.board_mask()
        cx, cy = (int(v) for v in self.c.center_px())
        self.assertEqual(mask[cy, cx], 255)
        self.assertEqual(mask[2, 2], 0)

    def test_overlay_shapes_are_projected_circles(self):
        rings, wires = self.c.shapes(n=720)
        self.assertEqual(len(rings), 6)
        self.assertEqual(len(wires), 20)
        # a legkülső gyűrű átmegy a kalibrációs pontok környékén
        outer = rings[-1]
        for n in CAL4:
            d = np.min(np.hypot(outer[:, 0] - self.cal[n][0], outer[:, 1] - self.cal[n][1]))
            self.assertLess(d, 0.01 * SIZE)

    def test_dump_and_load(self):
        again = tr.Calibration.load(json.loads(json.dumps(self.c.dump())))
        self.assertEqual(again.size, SIZE)
        self.assertIsNone(again.problem())
        self.assertTrue(np.allclose(again.H, self.c.H))

    def test_calibration_matches_the_vision_module(self):
        """Ugyanazt a kalibrációt számolja, mint az éles felismerés."""
        H, err = db.homography({n: self.cal[n] for n in CAL4})
        self.assertTrue(np.allclose(H, self.c.H))


class DiffTests(unittest.TestCase):
    def test_identical_images_have_no_blobs(self):
        img, _ = board()
        blobs = tr.find_blobs(tr.diff_binary(tr.prep(img), tr.prep(img)), SIZE)
        self.assertEqual(blobs, [])

    def test_brightness_change_is_not_a_dart(self):
        empty, _ = board()
        dim, _ = board(brightness=0.85)
        mask = tr.Calibration(synth.render(SIZE)[2], SIZE).board_mask()
        blobs = tr.find_blobs(tr.diff_binary(tr.prep(empty), tr.prep(dim), mask), SIZE)
        self.assertEqual(blobs, [])

    def test_a_dart_is_one_blob_of_plausible_size(self):
        empty, _ = board()
        dart, _ = board([(0, -103)])
        mask = tr.Calibration(synth.render(SIZE)[2], SIZE).board_mask()
        blobs = tr.find_blobs(tr.diff_binary(tr.prep(empty), tr.prep(dart), mask), SIZE)
        self.assertEqual(len(blobs), 1)
        self.assertFalse(blobs[0]["too_big"])

    def test_propose_tip_picks_the_end_nearer_the_centre_by_default(self):
        ys, xs = np.mgrid[100:160, 300:306]
        pts = np.stack([xs.ravel(), ys.ravel()], 1).astype(np.float32)        # függőleges szár
        x, y = tr.propose_tip(pts, (303, 320))
        self.assertGreater(y, 150)

    def test_propose_tip_follows_the_learned_direction(self):
        ys, xs = np.mgrid[100:160, 300:306]
        pts = np.stack([xs.ravel(), ys.ravel()], 1).astype(np.float32)
        x, y = tr.propose_tip(pts, (303, 320), mean_dir=np.array([0.0, -1.0]))   # a hegy felfelé áll
        self.assertLess(y, 110)

    def test_tiny_blob_does_not_crash(self):
        x, y = tr.propose_tip(np.array([[5.0, 5.0]], np.float32), (50, 50))
        self.assertEqual((x, y), (5.0, 5.0))


class CollectorTests(unittest.TestCase):
    def test_nothing_happens_without_a_reference(self):
        _, _, cal, _ = synth.render(SIZE)
        col = tr.Collector(tr.Calibration(cal, SIZE))
        self.assertEqual(col.state, "no_reference")
        self.assertEqual(col.feed(board()[0], 0.0), [])

    def test_empty_board_stays_quiet(self):
        col = new_collector()
        ev, _ = frames(col, board(noise=2.0, seed=1)[0], 2.0)
        self.assertEqual([e for e in ev if e[0] == "candidate"], [])

    def test_candidate_appears_only_after_the_picture_settles(self):
        col = new_collector()
        img, tips = board([(0, -103)])
        ev, _ = frames(col, img, 0.5)
        self.assertEqual(ev, [])
        ev, _ = frames(col, img, 1.0, t0=0.5)
        cands = [e[1] for e in ev if e[0] == "candidate"]
        self.assertEqual(len(cands), 1)

    def test_tip_proposal_is_near_the_real_tip(self):
        col = new_collector()
        img, tips = board([(0, -103)])
        ev, _ = frames(col, img)
        c = [e[1] for e in ev if e[0] == "candidate"][0]
        self.assertLess(math.hypot(c.tip[0] - tips[0][0], c.tip[1] - tips[0][1]), 0.03 * SIZE)

    def test_movement_resets_the_wait(self):
        col = new_collector()
        a, _ = board([(0, -103)])
        b, _ = board([(0, -103)], brightness=0.7)
        t = 0.0
        ev = []
        for i in range(12):                              # felváltva két teljesen más fényerejű kép: sosem nyugszik meg
            ev += col.feed(a if i % 2 == 0 else b, t)
            t += 0.1
        self.assertEqual(ev, [])
        self.assertEqual(col.state, "moving")

    def test_accept_makes_a_sample_with_the_tip_and_calibration(self):
        col = new_collector()
        img, tips = board([(0, -103)])
        frames(col, img)
        sample = col.accept()
        self.assertEqual(len(sample.darts), 1)
        self.assertEqual(set(sample.cal), set(CAL4))
        self.assertEqual(sample.image.shape[:2], (SIZE, SIZE))

    def test_corrected_tip_is_used(self):
        col = new_collector()
        frames(col, board([(0, -103)])[0])
        sample = col.accept(tip=(111.0, 222.0))
        self.assertEqual(sample.darts, [(111.0, 222.0)])

    def test_the_same_dart_is_not_proposed_twice(self):
        col = new_collector()
        img, _ = board([(0, -103)])
        ev, t = frames(col, img)
        col.accept()
        ev, _ = frames(col, img, 2.0, t0=t)
        self.assertEqual([e for e in ev if e[0] == "candidate"], [])

    def test_second_dart_gives_a_sample_with_both_tips(self):
        col = new_collector()
        img1, tips1 = board([(0, -103)])
        ev, t = frames(col, img1)
        col.accept()
        img2, tips2 = board([(0, -103), (-80, 50)])
        ev, t = frames(col, img2, t0=t)
        cands = [e[1] for e in ev if e[0] == "candidate"]
        self.assertEqual(len(cands), 1)
        sample = col.accept()
        self.assertEqual(len(sample.darts), 2)

    def test_two_new_darts_at_once_need_two_decisions_and_only_then_a_sample(self):
        col = new_collector()
        img, _ = board([(0, -103), (-80, 50)])
        ev, t = frames(col, img)
        c = [e[1] for e in ev if e[0] == "candidate"][0]
        self.assertEqual(c.unresolved, 1)
        self.assertIsNone(col.accept())                  # a másik nyíl még címkézetlen: nem készül kép
        ev, t = frames(col, img, t0=t)
        c2 = [e[1] for e in ev if e[0] == "candidate"][0]
        self.assertEqual(c2.unresolved, 0)
        sample = col.accept()
        self.assertEqual(len(sample.darts), 2)

    def test_rejected_blob_is_not_proposed_again_and_does_not_block_samples(self):
        col = new_collector()
        img, _ = board([(0, -103)])
        ev, t = frames(col, img)
        col.reject()
        ev, t = frames(col, img, 2.0, t0=t)
        self.assertEqual([e for e in ev if e[0] == "candidate"], [])
        img2, _ = board([(0, -103), (90, 40)])           # új nyíl a kidobott folt mellett
        ev, t = frames(col, img2, t0=t)
        cands = [e[1] for e in ev if e[0] == "candidate"]
        self.assertEqual(len(cands), 1)
        sample = col.accept()
        self.assertEqual(len(sample.darts), 1)           # csak az új nyíl, a kidobott nem címke

    def test_removing_the_darts_ends_the_round(self):
        col = new_collector()
        ev, t = frames(col, board([(0, -103)])[0])
        col.accept()
        first = col.round_id
        ev, t = frames(col, board()[0], t0=t)
        self.assertIn(("removed",), ev)
        self.assertEqual(col.round_id, first + 1)

    def test_rounds_get_different_ids_in_the_samples(self):
        col = new_collector()
        ev, t = frames(col, board([(0, -103)])[0])
        s1 = col.accept()
        ev, t = frames(col, board()[0], t0=t)
        ev, t = frames(col, board([(60, 60)])[0], t0=t)
        s2 = col.accept()
        self.assertNotEqual(s1.round_id, s2.round_id)

    def test_hand_in_the_picture_waits(self):
        col = new_collector()
        img, _ = board()
        img = img.copy()
        cv2.rectangle(img, (150, 150), (480, 480), (120, 140, 200), -1)       # egy nagy tárgy (kéz)
        ev, _ = frames(col, img)
        self.assertEqual([e for e in ev if e[0] == "candidate"], [])
        self.assertEqual([e[0] for e in ev], ["busy"])

    def test_merged_darts_taint_the_round(self):
        col = new_collector()
        ev, t = frames(col, board([(0, -103)])[0])
        col.accept()
        merged, _ = board([(0, -103), (4, -100)])         # a második nyíl majdnem az elsőn
        merged = merged.copy()
        cv2.rectangle(merged, (285, 100), (315, 175), (0, 0, 0), -1)            # nagyobb, összeolvadt folt
        ev, t = frames(col, merged, t0=t)
        self.assertTrue(col.tainted)
        self.assertEqual(col.state, "tainted")
        self.assertEqual([e for e in ev if e[0] == "candidate"], [])
        ev, t = frames(col, board()[0], t0=t)             # a kör vége feloldja
        self.assertFalse(col.tainted)

    def test_light_change_between_reference_and_play_is_tolerated(self):
        col = new_collector()
        ev, _ = frames(col, board([(0, -103)], brightness=0.88)[0])
        cands = [e[1] for e in ev if e[0] == "candidate"]
        self.assertEqual(len(cands), 1)

    def test_new_reference_forgets_the_old_darts(self):
        col = new_collector()
        frames(col, board([(0, -103)])[0])
        col.accept()
        col.set_empty(board()[0])
        self.assertEqual(col.known, [])
        self.assertEqual(col.state, "watching")

    def test_undo_removes_the_last_accepted_dart(self):
        col = new_collector()
        frames(col, board([(0, -103)])[0])
        col.accept()
        self.assertEqual(len(col.known), 1)
        col.undo()
        self.assertEqual(col.known, [])

    def test_the_tip_direction_is_learned_from_approvals(self):
        """A nyíl szára a hegytől a tábla közepe felé áll (a szintetikus nyíl mindig balra-fel): az első javaslat
        a lenti nyilaknál rossz véget választja, három jóváhagyás után viszont már a tanult irányt követi."""
        col = new_collector()
        spots = [(60, 40), (-50, 70), (30, 90), (70, -20)]
        img_mm, t = [], 0.0
        for k, spot in enumerate(spots):
            img_mm.append(spot)
            img, tips = board(list(img_mm))
            ev, t = frames(col, img, t0=t)
            c = [e[1] for e in ev if e[0] == "candidate"][0]
            err = math.hypot(c.tip[0] - tips[-1][0], c.tip[1] - tips[-1][1])
            if k < 3:
                col.accept(tip=tips[-1])                 # a felhasználó javít
            else:
                self.assertLess(err, 0.03 * SIZE)        # a negyediket már jól javasolja
                col.accept()


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = tr.DatasetStore(Path(self.tmp.name) / "set")

    def tearDown(self):
        self.tmp.cleanup()

    def sample(self, n_darts=1, round_id=0):
        img, tips, cal, _ = synth.render(SIZE, darts_mm=[(0, -103), (60, 40), (-60, 40)][:n_darts])
        return tr.Sample(img, tips, cal, round_id)

    def test_add_writes_image_label_and_meta(self):
        sid = self.store.add(self.sample(2), "a")
        root = Path(self.tmp.name) / "set"
        self.assertTrue((root / "images" / f"{sid}.jpg").is_file())
        lines = (root / "labels" / f"{sid}.txt").read_text().strip().splitlines()
        self.assertEqual(len(lines), 2 + 4)
        classes = [int(l.split()[0]) for l in lines]
        self.assertEqual(classes.count(0), 2)
        self.assertEqual(sorted(classes[2:]), [1, 2, 3, 4])
        for line in lines:
            vals = [float(v) for v in line.split()[1:]]
            self.assertTrue(all(0.0 <= v <= 1.0 for v in vals))

    def test_label_position_matches_the_pixel(self):
        sample = self.sample(1)
        sid = self.store.add(sample, "a")
        first = (Path(self.tmp.name) / "set" / "labels" / f"{sid}.txt").read_text().splitlines()[0].split()
        self.assertAlmostEqual(float(first[1]) * SIZE, sample.darts[0][0], delta=0.01)
        self.assertAlmostEqual(float(first[2]) * SIZE, sample.darts[0][1], delta=0.01)

    def test_class_names_are_the_ones_the_detector_expects(self):
        self.assertEqual(tr.CLASS_NAMES[0], "dart")
        self.assertTrue(set(tr.CAL_NAMES) <= set(db.CAL_ANGLES))
        self.assertEqual(len(tr.CAL_NAMES), 4)

    def test_ids_grow_and_remove_last(self):
        a = self.store.add(self.sample(), "a")
        b = self.store.add(self.sample(), "a")
        self.assertLess(a, b)
        self.assertEqual(self.store.count(), 2)
        self.assertEqual(self.store.remove_last(), b)
        self.assertEqual(self.store.count(), 1)
        c = self.store.add(self.sample(), "a")
        self.assertEqual(c, b)                       # a törölt azonosító újra szabad, nincs lyuk a sorban

    def test_dart_count_counts_each_round_once(self):
        self.store.add(self.sample(1, 1), "a")
        self.store.add(self.sample(2, 1), "a")
        self.store.add(self.sample(3, 1), "a")
        self.store.add(self.sample(1, 2), "a")
        self.assertEqual(self.store.n_darts(), 3 + 1)

    def test_rounds_of_different_sessions_do_not_merge(self):
        self.store.add(self.sample(1, 1), "a")
        self.store.add(self.sample(1, 1), "b")
        self.assertEqual(self.store.n_darts(), 2)

    def test_reopening_the_folder_keeps_the_samples(self):
        self.store.add(self.sample(), "a")
        again = tr.DatasetStore(Path(self.tmp.name) / "set")
        self.assertEqual(again.count(), 1)

    def test_build_separates_validation_by_round(self):
        for rnd in range(1, 11):
            for k in (1, 2, 3):
                self.store.add(self.sample(k, rnd), "a")
        yaml, n_train, n_val = self.store.build()
        self.assertEqual(n_train + n_val, 30)
        self.assertEqual(n_val, 6)                    # a 10 körből kettő (minden 5.)
        train = set(Path(self.store.folder / "train.txt").read_text().split())
        val = set(Path(self.store.folder / "val.txt").read_text().split())
        self.assertFalse(train & val)
        text = yaml.read_text()
        for i, name in enumerate(tr.CLASS_NAMES):
            self.assertIn(f"{i}: '{name}'", text)
        self.assertIn("train:", text)

    def test_build_with_a_single_round_validates_on_the_same_images(self):
        self.store.add(self.sample(1, 1), "a")
        self.store.add(self.sample(2, 1), "a")
        _, n_train, n_val = self.store.build()
        self.assertEqual((n_train, n_val), (2, 2))

    def test_build_without_samples_fails(self):
        with self.assertRaises(ValueError):
            self.store.build()

    def test_images_are_listed_with_absolute_paths(self):
        self.store.add(self.sample(), "a")
        self.store.build()
        for line in (self.store.folder / "train.txt").read_text().split():
            self.assertTrue(Path(line).is_absolute() and Path(line).is_file())


class TrainingHelpersTests(unittest.TestCase):
    def test_python_exe_prefers_the_console_python(self):
        self.assertEqual(tr.python_exe(r"C:\Python\pythonw.exe"), r"C:\Python\python.exe")
        self.assertEqual(tr.python_exe("/usr/bin/python3"), "/usr/bin/python3")

    def test_base_weights_prefers_the_bundled_file_and_falls_back_to_the_auto_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(tr.base_weights(tmp), "yolov8n.pt")                  # nincs helyi fájl: az ultralytics tölti le
            self.assertEqual(tr.base_weights(None), "yolov8n.pt")
            (Path(tmp) / "base").mkdir()
            (Path(tmp) / "base" / "yolov8n.pt").write_bytes(b"x")
            self.assertEqual(tr.base_weights(tmp), str(Path(tmp) / "base" / "yolov8n.pt"))

    def test_job_config_uses_the_preset(self):
        cfg = tr.job_config("d.yaml", "fast", "proj")
        self.assertEqual((cfg["epochs"], cfg["imgsz"]), (tr.PRESETS["fast"][0], tr.PRESETS["fast"][1]))
        self.assertEqual(cfg["data"], "d.yaml")

    def test_parse_progress_lines(self):
        self.assertEqual(tr.parse_line("RKBULLY_EPOCH|3|40|0.512"), ("epoch", 3, 40, 0.512))
        self.assertEqual(tr.parse_line("RKBULLY_EPOCH|3|40|"), ("epoch", 3, 40, None))
        self.assertEqual(tr.parse_line("RKBULLY_DONE|/x/best.pt"), ("done", "/x/best.pt"))
        self.assertEqual(tr.parse_line("RKBULLY_ERROR|baj"), ("error", "baj"))
        self.assertIsNone(tr.parse_line("valami más"))
        self.assertIsNone(tr.parse_line("RKBULLY_EPOCH|x|y"))

    def test_estimate_remaining(self):
        self.assertIsNone(tr.estimate_remaining([], 0, 10))
        self.assertEqual(tr.estimate_remaining([10.0, 10.0], 2, 10), 80.0)
        self.assertEqual(tr.estimate_remaining([10.0], 10, 10), 0.0)

    def test_coverage_and_hint(self):
        self.assertEqual(tr.coverage_hint([(0, -100)] * 5), "")           # az elején még nem szól
        darts = [(0, -100)] * 30                                          # mind ugyanott
        hint = tr.coverage_hint(darts)
        self.assertTrue(hint.startswith("Dobj még ide"))
        spread = [tr.db.cal_point_mm("20")] * 0
        pts = []
        for q in range(4):
            for r in (30, 90, 150):
                a = math.radians(q * 90 + 45)
                pts += [(r * math.sin(a), -r * math.cos(a))] * 5
        self.assertEqual(tr.coverage_hint(pts), "Szép az eloszlás.")
        self.assertEqual(spread, [])

    def test_ultralytics_check_returns_a_bool(self):
        self.assertIsInstance(tr.ultralytics_available(), bool)


class TrainJobTests(unittest.TestCase):
    def wait(self, job, limit=20.0):
        import time
        lines, t0 = [], time.time()
        while time.time() - t0 < limit:
            lines += job.poll()
            if job.finished():
                lines += job.poll()
                break
            time.sleep(0.05)
        return lines

    def test_output_lines_and_carriage_returns_are_read(self):
        code = "import sys;sys.stdout.write('a\\rb\\nRKBULLY_EPOCH|1|2|0.5\\n');sys.stdout.flush()"
        job = tr.TrainJob([sys.executable, "-c", code])
        job.start()
        lines = self.wait(job)
        self.assertEqual([l for l in lines if l.strip()], ["a", "b", "RKBULLY_EPOCH|1|2|0.5"])
        self.assertEqual(job.returncode, 0)

    def test_failing_process_reports_its_return_code(self):
        job = tr.TrainJob([sys.executable, "-c", "import sys;sys.exit(3)"])
        job.start()
        self.wait(job)
        self.assertEqual(job.returncode, 3)

    def test_cancel_stops_a_long_job(self):
        job = tr.TrainJob([sys.executable, "-c", "import time;time.sleep(60)"])
        job.start()
        self.assertTrue(job.running)
        job.cancel()
        self.assertFalse(job.running)


class FakeModel:
    """Modell helyett: a megadott nyilakat találja meg (kis eltolással), a többit nem."""

    def __init__(self, dx=0.0, miss=(), extra=(), cal=None):
        self.dx, self.miss, self.extra, self.cal = dx, set(miss), list(extra), cal

    def detect(self, img):
        det = vision.Detections()
        det.cal = {n: (x, y, 0.9) for n, (x, y) in self.cal.items()} if self.cal else {}
        det.darts = [(x + self.dx, y, 0.9) for i, (x, y) in enumerate(self.tips) if i not in self.miss]
        det.darts += [(x, y, 0.5) for x, y in self.extra]
        return det


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self.img, self.tips, self.cal, _ = synth.render(SIZE, darts_mm=[(0, -103), (60, 40)])

    def run_eval(self, model):
        model.tips = self.tips
        return tr.evaluate(model, [(self.img, self.tips, self.cal)])

    def test_perfect_model(self):
        r = self.run_eval(FakeModel(cal=self.cal))
        self.assertEqual((r["darts"], r["found"], r["false"], r["cal_ok"]), (2, 2, 0, 1))
        self.assertAlmostEqual(r["err_px"], 0.0, places=6)
        self.assertTrue(tr.verdict(r).startswith("Jó modell"))

    def test_missed_and_false_detections_are_counted(self):
        r = self.run_eval(FakeModel(miss=[1], extra=[(30.0, 30.0)], cal=self.cal))
        self.assertEqual((r["found"], r["false"]), (1, 1))

    def test_small_error_is_measured_in_millimetres(self):
        r = self.run_eval(FakeModel(dx=2.0, cal=self.cal))
        self.assertEqual(r["found"], 2)
        self.assertGreater(r["err_mm"], 0.3)
        self.assertLess(r["err_mm"], 3.0)

    def test_far_detection_does_not_match(self):
        r = self.run_eval(FakeModel(dx=60.0, cal=self.cal))
        self.assertEqual(r["found"], 0)
        self.assertTrue(tr.verdict(r).startswith("Még gyenge"))

    def test_missing_calibration_points_lower_the_verdict(self):
        r = self.run_eval(FakeModel(cal={"20": self.cal["20"]}))
        self.assertEqual(r["cal_ok"], 0)
        self.assertFalse(tr.verdict(r).startswith("Jó modell"))

    def test_no_labels_means_nothing_to_compare(self):
        self.assertEqual(tr.verdict({"darts": 0}), "Nincs mivel összehasonlítani.")


if __name__ == "__main__":
    unittest.main()
