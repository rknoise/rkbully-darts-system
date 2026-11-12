"""Két kamera összevetése: szimulált kamerákkal (más-más nézőpont = más homográfia), valódi Detectorokkal."""
import math
import random
import time
import unittest

import numpy as np

import dartboard as db
import fusion as f
import vision as v

W, HGT = 1280, 720
FRAME = np.zeros((HGT, W, 3), np.uint8)

# két különböző nézőpont: a tábla síkja (mm) -> kép pixel
H_A = np.array([[1.9, 0.12, 640.0], [-0.08, 1.85, 360.0], [0.00008, 0.00012, 1.0]])
H_B = np.array([[1.75, -0.22, 655.0], [0.18, 1.6, 372.0], [-0.00012, 0.00016, 1.0]])


def polar(r, ang_deg):
    a = math.radians(ang_deg)
    return r * math.sin(a), -r * math.cos(a)


class Cam:
    """Modell helyett: a tábla pontjait a saját nézőpontja szerint pixelekbe vetíti."""

    def __init__(self, H, noise=0.0, seed=0, shift=(0.0, 0.0)):
        self.H, self.noise, self.rnd, self.shift = H, noise, random.Random(seed), shift
        self.darts_mm, self.hidden = [], set()

    def _j(self):
        return self.rnd.gauss(0, self.noise) if self.noise else 0.0

    def _px(self, mm):
        return tuple(db.apply_h(self.H, [mm])[0])

    def detect(self, img):
        x0 = (W - img.shape[1]) // 2
        det = v.Detections()
        for n in ("20", "3", "11", "6"):
            if n not in self.hidden:
                x, y = self._px(db.cal_point_mm(n))
                det.cal[n] = (x - x0 + self._j(), y + self._j(), 0.9)
        for dx, dy in self.darts_mm:
            x, y = self._px((dx + self.shift[0], dy + self.shift[1]))
            det.darts.append((x - x0 + self._j(), y + self._j(), 0.8))
        return det


class Rig:
    """Két kamera + összevető egység, szinkron lépésekkel és hamis órával (nincs szál, nincs alvás)."""

    def __init__(self, noise=0.0, shift_b=(0.0, 0.0), hub_kw=None, cams=("A", "B")):
        self.t = 0.0
        self.hub = f.FusionHub(clock=lambda: self.t, **(hub_kw or {}))
        self.cams = {"A": Cam(H_A, noise, 1), "B": Cam(H_B, noise, 2, shift_b)}
        self.cams = {n: self.cams[n] for n in cams}
        self.dets = {n: v.Detector(c) for n, c in self.cams.items()}
        self.dead = set()                       # nem küld képet, és nem használható az összevetéshez
        self.log = []
        self.resets = []
        self.hub.reset_callback = self.resets.append
        for n in self.cams:
            self.hub.add_camera(n)
        self.step(8)                            # kalibrálás

    def step(self, frames=1, dt=1 / 6):
        for _ in range(frames):
            for n, det in self.dets.items():
                evs = [] if n in self.dead else det.process(FRAME)
                self.hub.set_health(n, det.healthy and n not in self.dead)
                self.log += self.hub.push(n, evs)
            self.t += dt
            self.log += self.hub.poll()

    def show(self, darts, frames, **per_cam):
        """Mindkét kamera ugyanazokat a nyilakat látja; per_cam: egy kamera mást (pl. B=[])."""
        for n, cam in self.cams.items():
            cam.darts_mm = per_cam.get(n, darts)
        self.step(frames)

    def throws(self):
        return [e for e in self.log if isinstance(e, v.Throw)]

    def kinds(self):
        return [type(e).__name__ for e in self.log]


D1, D2, D3 = polar(103, 0), polar(135, 342), polar(166, 234)      # T20, S5, D16


class AgreeTests(unittest.TestCase):
    def test_two_cameras_give_one_event_per_dart(self):
        rig = Rig(noise=0.5)
        rig.show([D1], 8)
        rig.show([D1, D2], 8)
        rig.show([D1, D2, D3], 8)
        rig.show([], 10)
        self.assertEqual([getattr(e, "text", "Removed") for e in rig.log], ["T20", "S5", "D16", "Removed"])
        for t in rig.throws():
            self.assertEqual(t.sources, 2)
            self.assertFalse(t.uncertain, t.reason)
            self.assertEqual(t.note, "2 kamera egyezik")

    def test_fused_position_is_close_to_the_truth(self):
        rig = Rig(noise=0.6)
        rig.show([D1, D2, D3], 12)
        got = sorted((t.x, t.y) for t in rig.throws())
        want = sorted([D1, D2, D3])
        for (gx, gy), (wx, wy) in zip(got, want):
            self.assertLess(math.hypot(gx - wx, gy - wy), 3.0)

    def test_weights_favour_the_confident_and_better_calibrated_camera(self):
        hub = f.FusionHub()
        a = v.Throw(1, 20, 0.0, -100.0, 10, 0.9, False, cal_err=0.5)
        b = v.Throw(1, 20, 4.0, -100.0, 10, 0.3, False, cal_err=2.5)
        fused = hub.fuse(a, b)
        self.assertLess(abs(fused.x), 1.0)               # majdnem az a kamera, nem a 2 mm-es középérték
        self.assertEqual(fused.sources, 2)
        self.assertAlmostEqual(fused.spread, 4.0)

    def test_equal_cameras_are_averaged(self):
        hub = f.FusionHub()
        a = v.Throw(1, 20, 0.0, -100.0, 10, 0.8, False, cal_err=1.0)
        b = v.Throw(1, 20, 4.0, -100.0, 10, 0.8, False, cal_err=1.0)
        self.assertAlmostEqual(hub.fuse(a, b).x, 2.0)


class DisagreeTests(unittest.TestCase):
    def test_cameras_in_different_segments_need_confirmation(self):
        rig = Rig(shift_b=(10.0, 0.0))                   # B 10 mm-rel eltolva látja: a drót másik oldalára esik
        d = polar(135, 7.5)                              # A: S20, a drót 3,5 mm-re
        rig.show([d], 10)
        (t,) = rig.throws()
        self.assertTrue(t.uncertain)
        self.assertEqual(t.reason, "kamerák eltérnek")
        self.assertEqual(t.sources, 2)
        self.assertGreater(t.spread, 8.0)

    def test_dart_near_the_wire_is_uncertain_even_if_both_agree(self):
        rig = Rig()
        rig.show([polar(135, 9.1)], 10)
        (t,) = rig.throws()
        self.assertTrue(t.uncertain)
        self.assertEqual(t.reason, "határ közelében")

    def test_one_confident_camera_is_enough_when_both_agree(self):
        """Az egyik kamera bizonytalan (kevés kalibrációs pont), a másik biztos, és egyeznek: nem kell kézi ellenőrzés."""
        hub = f.FusionHub()
        a = v.Throw(1, 20, 0.0, -103.0, 10, 0.9, False, cal_err=0.5)
        b = v.Throw(1, 20, 1.0, -103.0, 10, 0.9, True, cal_err=5.0)
        self.assertFalse(hub.fuse(a, b).uncertain)
        b2 = v.Throw(1, 20, 1.0, -103.0, 10, 0.9, True, cal_err=5.0)
        self.assertTrue(hub.fuse(b, b2).uncertain)       # mindkettő bizonytalan: a játékos dönt


class SingleSourceTests(unittest.TestCase):
    def test_dart_seen_by_one_camera_waits_then_asks_for_confirmation(self):
        rig = Rig()
        rig.show([D1], 8, B=[])
        self.assertEqual(rig.throws(), [])               # még várunk a másik kamerára
        rig.step(12)
        (t,) = rig.throws()
        self.assertEqual(t.text, "T20")
        self.assertTrue(t.uncertain)
        self.assertEqual(t.reason, "csak 1 kamera látta")
        self.assertEqual(t.sources, 1)

    def test_unusable_second_camera_does_not_delay_or_flag(self):
        rig = Rig()
        rig.dead.add("B")
        rig.show([D1], 6)
        (t,) = rig.throws()                              # azonnal, a várakozás nélkül
        self.assertFalse(t.uncertain)
        self.assertEqual(t.sources, 1)

    def test_single_camera_behaves_like_before(self):
        rig = Rig(cams=("A",))
        rig.show([D1], 8)
        rig.show([D1, D2], 8)
        rig.show([], 10)
        self.assertEqual([getattr(e, "text", "Removed") for e in rig.log], ["T20", "S5", "Removed"])
        self.assertTrue(all(not t.uncertain for t in rig.throws()))

    def test_late_confirmation_is_not_a_new_dart(self):
        rig = Rig()
        rig.cams["A"].darts_mm = [D1]
        rig.cams["B"].darts_mm = []
        rig.step(24)                                     # A önállóan kiadta (a várakozás lejárt)
        self.assertEqual(len(rig.throws()), 1)
        rig.cams["B"].darts_mm = [D1]
        rig.step(15)                                     # B most látja meg
        self.assertEqual(len(rig.throws()), 1)

    def test_pending_throw_is_released_before_the_removal(self):
        rig = Rig()
        rig.show([D1], 6, B=[])                          # csak A látja, kihúzzák, mielőtt a várakozás lejárna
        rig.show([], 10)
        self.assertEqual(rig.kinds(), ["Throw", "Removed"])
        self.assertTrue(rig.throws()[0].uncertain)


class RemovalTests(unittest.TestCase):
    def test_removed_only_when_both_cameras_see_it(self):
        rig = Rig()
        rig.show([D1, D2], 12)
        self.assertEqual(len(rig.throws()), 2)
        rig.show([D1, D2], 4, A=[])                      # A már nem látja, B még igen
        rig.step(4)
        self.assertNotIn("Removed", rig.kinds())
        rig.show([], 10)
        self.assertEqual(rig.kinds().count("Removed"), 1)

    def test_removal_timeout_resets_the_straggler(self):
        rig = Rig()
        rig.show([D1], 10)
        rig.cams["A"].darts_mm = []
        rig.cams["B"].darts_mm = [D1]                    # B soha nem látja kihúzva
        rig.step(40)
        self.assertEqual(rig.kinds().count("Removed"), 1)
        self.assertEqual(rig.resets, ["B"])              # a hátramaradt kamera követőjét nullázni kell

    def test_next_round_after_removal(self):
        rig = Rig()
        rig.show([D1], 10)
        rig.show([], 10)
        rig.show([D2], 10)
        self.assertEqual([getattr(e, "text", "Removed") for e in rig.log], ["T20", "Removed", "S5"])

    def test_new_throw_ends_a_round_that_is_waiting_for_the_other_camera(self):
        rig = Rig()
        rig.show([D1], 10)
        rig.cams["A"].darts_mm = []                      # A kihúzva, B még látja
        rig.step(10)
        rig.cams["A"].darts_mm = [D2]                    # új dobás A-nál, mielőtt B jelezte volna a kihúzást
        rig.step(10)
        self.assertEqual(rig.kinds()[:2], ["Throw", "Removed"])


class GuardTests(unittest.TestCase):
    def test_at_most_three_darts_per_round(self):
        rig = Rig(shift_b=(60.0, 0.0))                   # a két kamera semmiben nem ért egyet (rossz kalibráció)
        rig.show([D1, D2, D3], 40)
        self.assertLessEqual(len(rig.throws()), 3)
        self.assertGreater(rig.hub.dropped, 0)
        self.assertTrue(all(t.uncertain for t in rig.throws()))

    def test_loosely_matching_cameras_are_paired_not_duplicated(self):
        rig = Rig(shift_b=(0.0, 17.0))                   # 17 mm eltérés: a gyors párosítás nem, a lazább igen fogja meg
        rig.show([D1, D2, D3], 30)
        ts = rig.throws()
        self.assertEqual(len(ts), 3)
        self.assertTrue(all(t.sources == 2 and t.uncertain for t in ts))

    def test_reset_clears_pending_state(self):
        rig = Rig()
        rig.show([D1], 6, B=[])
        rig.hub.reset()
        rig.show([], 20)
        self.assertEqual(rig.throws(), [])


class FakeChild:
    """vision.DetectionService helyett: a FusionService csak ezeket a metódusokat használja."""

    def __init__(self, events=(), healthy=True):
        self.queue, self._healthy, self.started, self.stopped, self.resets = list(events), healthy, False, False, 0
        self.error = None
        self.detector = self

    def healthy(self):
        return self._healthy

    def poll(self):
        out, self.queue = self.queue, []
        return out

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def reset_round(self):
        self.resets += 1


class ServiceTests(unittest.TestCase):
    def test_service_merges_children(self):
        th = v.Throw(1, 20, 0.0, -103.0, 10, 0.9, False)
        svc = f.FusionService(f.FusionHub())
        a, b = FakeChild([th]), FakeChild([th])
        svc.add("A", a)
        svc.add("B", b)
        self.assertTrue(a.started and b.started)
        out = svc.poll()
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].sources, 2)
        svc.reset_round()
        self.assertEqual((a.resets, b.resets), (1, 1))
        svc.remove("B")
        self.assertTrue(b.stopped)
        self.assertEqual(list(svc.children), ["A"])
        svc.stop()
        self.assertTrue(a.stopped)

    def test_error_of_any_child_is_reported(self):
        svc = f.FusionService(f.FusionHub())
        a = FakeChild()
        svc.add("A", a)
        self.assertIsNone(svc.error)
        a.error = "ValueError: x"
        self.assertEqual(svc.error, "ValueError: x")

    def test_real_threads_end_to_end(self):
        """Valódi DetectionService-szálak két szimulált kamerával: 3 nyíl -> pontosan 3 összevetett dobás."""
        cams = {"A": Cam(H_A, 0.4, 5), "B": Cam(H_B, 0.4, 6)}
        for c in cams.values():
            c.darts_mm = [D1, D2, D3]
        svc = f.FusionService()
        for n, c in cams.items():
            svc.add(n, v.DetectionService(v.Detector(c), lambda: FRAME.copy(), fps=40))
        got, t0 = [], time.time()
        try:
            while time.time() - t0 < 10 and len(got) < 3:
                got += svc.poll()
                time.sleep(0.05)
            time.sleep(0.5)
            got += svc.poll()
        finally:
            svc.stop()
        throws = [e for e in got if isinstance(e, v.Throw)]
        self.assertEqual(sorted(t.text for t in throws), ["D16", "S5", "T20"])
        self.assertTrue(all(t.sources == 2 for t in throws))


if __name__ == "__main__":
    unittest.main()
