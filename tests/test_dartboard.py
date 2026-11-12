import math
import random
import unittest

import numpy as np

import dartboard as db


def polar(r, ang_deg):
    a = math.radians(ang_deg)
    return r * math.sin(a), -r * math.cos(a)


class ScoreTests(unittest.TestCase):
    def test_sector_order_and_single_area(self):
        for i, num in enumerate(db.SECTORS):
            self.assertEqual(db.score_at(*polar(135, i * 18)), (1, num))
            self.assertEqual(db.score_at(*polar(135, i * 18 + 8.5)), (1, num))
            self.assertEqual(db.score_at(*polar(135, i * 18 - 8.5)), (1, num))

    def test_compass_points(self):
        self.assertEqual(db.score_at(0, -135)[1], 20)   # fent
        self.assertEqual(db.score_at(135, 0)[1], 6)     # jobbra
        self.assertEqual(db.score_at(0, 135)[1], 3)     # lent
        self.assertEqual(db.score_at(-135, 0)[1], 11)   # balra

    def test_rings(self):
        self.assertEqual(db.score_at(0, 0), (2, 25))
        self.assertEqual(db.score_at(*polar(10, 40)), (1, 25))
        self.assertEqual(db.score_at(*polar(50, 0)), (1, 20))
        self.assertEqual(db.score_at(*polar(103, 0)), (3, 20))
        self.assertEqual(db.score_at(*polar(135, 0)), (1, 20))
        self.assertEqual(db.score_at(*polar(166, 0)), (2, 20))
        self.assertEqual(db.score_at(*polar(175, 0)), (0, 0))

    def test_margin(self):
        self.assertAlmostEqual(db.margin_mm(*polar(103, 0)), 4.0, places=3)         # tripla közepe
        self.assertLess(db.margin_mm(*polar(135, 9.0)), 0.01)                        # szektordrót
        self.assertAlmostEqual(db.margin_mm(*polar(135, 0)), math.radians(9) * 135, places=2)   # a drót közelebb van, mint a gyűrű
        self.assertLess(db.margin_mm(*polar(107.5, 0)), 1.0)                         # tripla külső széle

    def test_notation_roundtrip(self):
        for m in (1, 2, 3):
            for n in range(1, 21):
                self.assertEqual(db.parse_notation(db.notation(m, n)), (m, n))
        self.assertEqual(db.parse_notation("DB"), (2, 25))
        self.assertEqual(db.parse_notation("bull"), (2, 25))
        self.assertEqual(db.parse_notation("SB"), (1, 25))
        self.assertEqual(db.parse_notation("OUTER"), (1, 25))
        self.assertEqual(db.parse_notation("miss"), (0, 0))
        self.assertIsNone(db.parse_notation("T21"))
        self.assertIsNone(db.parse_notation("xyz"))
        self.assertEqual(db.notation(0, 0), "MISS")


class CalibrationTests(unittest.TestCase):
    # egy ferdén nézett tábla "kamerája": mm -> pixel
    H_CAM = np.array([[2.1, 0.35, 400.0], [-0.20, 1.9, 380.0], [0.0004, 0.0006, 1.0]])

    def to_px(self, pts_mm):
        return db.apply_h(self.H_CAM, pts_mm)

    def test_cal_points_match_dartsense_convention(self):
        # a 20 és a 3 pontja egymás tükörképe a középpontra, ugyanígy a 11 és a 6
        for a, b in (("20", "3"), ("11", "6"), ("9", "15")):
            pa, pb = db.cal_point_mm(a), db.cal_point_mm(b)
            self.assertAlmostEqual(pa[0], -pb[0], places=6)
            self.assertAlmostEqual(pa[1], -pb[1], places=6)
        x, y = db.cal_point_mm("20")
        self.assertLess(x, 0)
        self.assertLess(y, -165)          # a 20-as dupla bal felső sarka
        self.assertAlmostEqual(math.hypot(x, y), 170.0, places=6)

    def test_homography_recovers_scores(self):
        names = ("20", "3", "11", "6")
        px = {n: tuple(self.to_px([db.cal_point_mm(n)])[0]) for n in names}
        H, err = db.homography(px)
        self.assertIsNotNone(H)
        self.assertLess(err, 1e-3)        # numerikus pontosság: ezredmilliméter alatt
        rnd = random.Random(1)
        for _ in range(300):
            x, y = polar(rnd.uniform(0, 168), rnd.uniform(0, 360))
            p = self.to_px([(x, y)])[0]
            bx, by = db.apply_h(H, [p])[0]
            self.assertAlmostEqual(bx, x, places=4)
            self.assertAlmostEqual(by, y, places=4)
            self.assertEqual(db.score_at(bx, by), db.score_at(x, y))

    def test_homography_with_noise_and_extra_points(self):
        rnd = random.Random(2)
        names = tuple(db.CAL_ANGLES)
        px = {n: tuple(np.array(self.to_px([db.cal_point_mm(n)])[0]) + [rnd.gauss(0, 0.5), rnd.gauss(0, 0.5)]) for n in names}
        H, err = db.homography(px)
        self.assertLess(err, 2.0)         # fél pixeles zajnál 2 mm-nél kisebb hiba

    def test_outlier_calibration_point_is_dropped(self):
        px = {n: tuple(self.to_px([db.cal_point_mm(n)])[0]) for n in db.CAL_ANGLES}
        px["9"] = (px["9"][0] + 40, px["9"][1] - 25)          # a modell egy pontot rosszul talált meg
        H, err = db.homography(px)
        self.assertLess(err, 0.01)                            # a kiugró pont nélkül tökéletes az illesztés
        x, y = db.apply_h(H, [self.to_px([polar(103, 0)])[0]])[0]
        self.assertEqual(db.score_at(x, y), (3, 20))

    def test_needs_four_points(self):
        px = {n: tuple(self.to_px([db.cal_point_mm(n)])[0]) for n in ("20", "3", "11")}
        self.assertEqual(db.homography(px), (None, None))


if __name__ == "__main__":
    unittest.main()
