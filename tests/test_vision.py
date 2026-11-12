import math
import random
import unittest

import numpy as np

import dartboard as db
import vision as v

# "kamera": a tábla síkja (mm) -> kép pixel, 1280x720-as képen, enyhén ferdén nézve
H_CAM = np.array([[1.9, 0.12, 640.0], [-0.08, 1.85, 360.0], [0.00008, 0.00012, 1.0]])
W, HGT = 1280, 720


def polar(r, ang_deg):
    a = math.radians(ang_deg)
    return r * math.sin(a), -r * math.cos(a)


def px(mm):
    return tuple(db.apply_h(H_CAM, [mm])[0])


class FakeBackend:
    """Modell helyett: a megadott nyilakat és kalibrációs pontokat a "kamera" szerint pixelekbe vetíti."""

    def __init__(self, noise=0.0, seed=0):
        self.noise, self.rnd = noise, random.Random(seed)
        self.darts_mm, self.hidden = [], set()

    def _j(self):
        return self.rnd.gauss(0, self.noise) if self.noise else 0.0

    def detect(self, img):
        x0 = (W - img.shape[1]) // 2              # a felület négyzetre vágja a képet
        det = v.Detections()
        for n in ("20", "3", "11", "6"):
            if n not in self.hidden:
                x, y = px(db.cal_point_mm(n))
                det.cal[n] = (x - x0 + self._j(), y + self._j(), 0.9)
        for mm in self.darts_mm:
            x, y = px(mm)
            det.darts.append((x - x0 + self._j(), y + self._j(), 0.8))
        return det


FRAME = np.zeros((HGT, W, 3), np.uint8)


def run(detector, backend, schedule):
    """schedule: [(képkockák száma, [nyilak mm-ben])] – visszaadja az eseményeket."""
    events = []
    for count, darts in schedule:
        backend.darts_mm = darts
        for _ in range(count):
            events += detector.process(FRAME)
    return events


class SourceTests(unittest.TestCase):
    def test_normalize_source(self):
        self.assertEqual(v.normalize_source("0"), 0)
        self.assertEqual(v.normalize_source(" 2 "), 2)
        self.assertEqual(v.normalize_source("192.168.0.56:8080"), "http://192.168.0.56:8080/video")
        self.assertEqual(v.normalize_source("http://192.168.0.56:8080"), "http://192.168.0.56:8080/video")
        self.assertEqual(v.normalize_source("http://10.0.0.5:8080/video"), "http://10.0.0.5:8080/video")
        self.assertEqual(v.normalize_source("rtsp://cam/stream"), "rtsp://cam/stream")


class DartTrackerTests(unittest.TestCase):
    def feed(self, tr, frames):
        out = []
        for dets in frames:
            out += tr.update(dets)
        return out

    def test_one_event_per_dart(self):
        tr = v.DartTracker()
        d1, d2, d3 = (*polar(103, 0), 0.9), (*polar(135, 342), 0.9), (*polar(166, 234), 0.9)
        ev = self.feed(tr, [[]] * 3 + [[d1]] * 8 + [[d1, d2]] * 8 + [[d1, d2, d3]] * 8)
        self.assertEqual([e.text for e in ev], ["T20", "S5", "D16"])
        self.assertFalse(any(e.uncertain for e in ev))

    def test_flicker_and_blips(self):
        tr = v.DartTracker()
        d1 = (*polar(103, 0), 0.9)
        frames = [[d1], [d1], [], [d1], [], [d1]] + [[d1]] * 6
        blip = [[(*polar(50, 120), 0.9)]] + [[]] * 6                  # egyszeri téves felismerés
        ev = self.feed(tr, blip + frames)
        self.assertEqual([e.text for e in ev], ["T20"])

    def test_removal_starts_new_round(self):
        tr = v.DartTracker()
        d1 = (*polar(103, 0), 0.9)
        ev = self.feed(tr, [[d1]] * 8 + [[]] * 8)
        self.assertEqual([type(e).__name__ for e in ev], ["Throw", "Removed"])
        ev = self.feed(tr, [[d1]] * 8)
        self.assertEqual([e.text for e in ev], ["T20"])                # a kihúzás után ugyanaz a hely újra számít

    def test_fourth_dart_ignored_until_removed(self):
        tr = v.DartTracker()
        ds = [(*polar(103, 0), 0.9), (*polar(135, 342), 0.9), (*polar(166, 234), 0.9), (*polar(60, 100), 0.9)]
        ev = self.feed(tr, [ds[:1]] * 6 + [ds[:2]] * 6 + [ds[:3]] * 6 + [ds] * 8)
        self.assertEqual(len(ev), 3)

    def test_twin_detection_next_to_a_dart_is_ignored(self):
        tr = v.DartTracker()
        real, twin = (*polar(115, 346), 0.75), (*polar(115, 350), 0.51)       # 8 mm-re egymástól (a 6 mm-es egyezési sugáron kívül)
        ev = self.feed(tr, [[real, twin]] * 8)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0].conf > 0.7, True)

    def test_dart_outside_board_is_a_miss(self):
        tr = v.DartTracker()
        ev = self.feed(tr, [[(*polar(180, 40), 0.8)]] * 8 + [[(*polar(180, 40), 0.8), (*polar(250, 200), 0.8)]] * 8)
        self.assertEqual([e.text for e in ev], ["MISS", "MISS"])
        self.assertFalse(ev[0].uncertain)          # a dupla gyűrű mellett leszúrt nyíl: biztos mellé
        self.assertTrue(ev[1].uncertain)           # messze a táblától: kérjen megerősítést

    def test_uncertain_near_wire_or_low_confidence(self):
        tr = v.DartTracker()
        ev = self.feed(tr, [[(*polar(135, 9.2), 0.9)]] * 8)
        self.assertTrue(ev[0].uncertain)
        self.assertEqual(ev[0].text, "S1")
        tr2 = v.DartTracker()
        ev2 = self.feed(tr2, [[(*polar(135, 0), 0.38)]] * 8)
        self.assertTrue(ev2[0].uncertain)


class DetectorTests(unittest.TestCase):
    def test_full_round_through_crop_and_homography(self):
        backend = FakeBackend(noise=0.6, seed=3)
        det = v.Detector(backend)
        darts = [polar(103, 0), polar(135, 342), polar(166, 234)]
        ev = run(det, backend, [(4, []), (8, darts[:1]), (8, darts[:2]), (8, darts), (10, [])])
        self.assertEqual([getattr(e, "text", "Removed") for e in ev], ["T20", "S5", "D16", "Removed"])
        self.assertTrue(all(not e.uncertain for e in ev if isinstance(e, v.Throw)))
        self.assertIn("Kalibrálva", det.overlay["status"])
        self.assertEqual(det.overlay["square"], ((W - HGT) // 2, 0, HGT))

    def test_no_events_before_calibration(self):
        backend = FakeBackend()
        backend.hidden = {"20", "3"}                 # csak 2 kalibrációs pont látszik
        det = v.Detector(backend)
        ev = run(det, backend, [(10, [polar(103, 0)])])
        self.assertEqual(ev, [])
        self.assertIn("Kalibrálás", det.overlay["status"])

    def test_survives_lost_calibration_point(self):
        backend = FakeBackend()
        det = v.Detector(backend)
        run(det, backend, [(5, [])])
        backend.hidden = {"11"}                      # egy pontot eltakar valami
        run(det, backend, [(12, [])])                # a pont már régen nem látszik
        ev = run(det, backend, [(8, [polar(103, 0)])])
        self.assertEqual([e.text for e in ev], ["T20"])
        self.assertTrue(ev[0].uncertain)             # már csak 3 pont látszik: kérjen megerősítést
        self.assertIn("elavult", det.overlay["status"])

    def test_analyze_image(self):
        backend = FakeBackend()
        backend.darts_mm = [polar(103, 0), polar(166, 234), polar(3, 77)]
        out = v.analyze_image(backend, FRAME, crop_square=True)
        got = sorted(db.notation(d["mult"], d["num"]) for d in out["darts"])
        self.assertEqual(got, sorted(["T20", "D16", "DB"]))
        self.assertLess(out["err"], 1e-3)


if __name__ == "__main__":
    unittest.main()
