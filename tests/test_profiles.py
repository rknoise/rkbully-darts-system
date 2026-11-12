"""Játékosprofilok: betöltés, régi beállításfájl átvétele, névkezelés, profilkép importálása."""
import tempfile
import unittest
from pathlib import Path

import profiles as pf

try:
    from PySide6.QtGui import QColor, QImage
except Exception:                                       # pragma: no cover
    QImage = None


def make_image(path, w, h, fmt="PNG"):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor("#3a9bff"))
    assert img.save(str(path), fmt)
    return path


class ProfileDataTests(unittest.TestCase):
    def test_stats_reset_time_survives_loading_and_bad_values_are_dropped(self):
        ok = pf.clean({"id": "a", "name": "Robi", "stats_from": 1700000000.5})
        self.assertEqual(ok["stats_from"], 1700000000.5)
        for bad in (0, -5, "tegnap", None, True, [1]):
            self.assertNotIn("stats_from", pf.clean({"id": "a", "name": "Robi", "stats_from": bad}), repr(bad))
        self.assertNotIn("stats_from", pf.make_profile("Robi"))           # új profilnál nincs nullázás
        profiles, _ = pf.load({"profiles": [{"id": "a", "name": "Robi", "stats_from": 123.0}], "players": ["a"]})
        self.assertEqual(profiles[0]["stats_from"], 123.0)

    def test_new_profile_takes_the_first_free_color(self):
        a = pf.make_profile("  Robi ", [])
        b = pf.make_profile("Dani", [a["color"]])
        self.assertEqual(a["name"], "Robi")                 # a szóközöket levágja
        self.assertNotEqual(a["color"], b["color"])
        self.assertIsNone(a["avatar"])
        self.assertNotEqual(a["id"], b["id"])

    def test_colors_wrap_around_when_all_are_used(self):
        self.assertIn(pf.make_profile("X", pf.COLORS)["color"], pf.COLORS)

    def test_clean_repairs_or_drops_broken_entries(self):
        self.assertIsNone(pf.clean({"name": "   "}))
        self.assertIsNone(pf.clean({}))
        p = pf.clean({"name": "Peti", "color": "nem-szín", "avatar": ""})
        self.assertEqual(p["color"], pf.COLORS[0])
        self.assertIsNone(p["avatar"])
        self.assertTrue(p["id"])

    def test_legacy_settings_with_names_become_profiles(self):
        profiles, players = pf.load({"names": ["Robi", "Dani", " ", "Peti"]})
        self.assertEqual([p["name"] for p in profiles], ["Robi", "Dani", "Peti"])
        self.assertEqual(players, [p["id"] for p in profiles])
        self.assertEqual(len({p["color"] for p in profiles}), 3)

    def test_empty_settings_give_two_default_players(self):
        profiles, players = pf.load({})
        self.assertEqual([p["name"] for p in profiles], ["Játékos 1", "Játékos 2"])
        self.assertEqual(len(players), 2)

    def test_load_keeps_order_and_ignores_unknown_ids(self):
        a, b, c = (pf.make_profile(n, []) for n in "ABC")
        profiles, players = pf.load({"profiles": [a, b, c], "players": [c["id"], "nincs-ilyen", a["id"]]})
        self.assertEqual(players, [c["id"], a["id"]])
        self.assertEqual(len(profiles), 3)

    def test_load_without_valid_players_takes_the_first_two(self):
        a, b, c = (pf.make_profile(n, []) for n in "ABC")
        _, players = pf.load({"profiles": [a, b, c], "players": ["x"]})
        self.assertEqual(players, [a["id"], b["id"]])

    def test_load_drops_duplicate_ids_and_non_dicts(self):
        a = pf.make_profile("A", [])
        profiles, _ = pf.load({"profiles": [a, dict(a), "szemét", 5]})
        self.assertEqual(len(profiles), 1)

    def test_at_most_eight_players(self):
        profiles = [pf.make_profile(f"J{i}", []) for i in range(10)]
        _, players = pf.load({"profiles": profiles, "players": [p["id"] for p in profiles]})
        self.assertEqual(len(players), pf.MAX_PLAYERS)

    def test_names_are_unique_ignoring_case(self):
        a, b = pf.make_profile("Robi", []), pf.make_profile("Dani", [])
        profiles = [a, b]
        self.assertTrue(pf.name_taken(profiles, " robi "))
        self.assertFalse(pf.name_taken(profiles, "robi", except_id=a["id"]))     # a saját nevét megtarthatja
        self.assertTrue(pf.name_taken(profiles, "Dani", except_id=a["id"]))
        n = pf.unique_name(profiles, "Játékos")
        self.assertFalse(pf.name_taken(profiles, n))

    def test_dump_round_trips(self):
        a, b = pf.make_profile("A", []), pf.make_profile("B", [])
        again = pf.load(pf.dump([a, b], [b["id"]]))
        self.assertEqual(again, ([a, b], [b["id"]]))


@unittest.skipIf(QImage is None, "PySide6 nincs telepítve")
class AvatarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_import_makes_a_small_square_jpg(self):
        src = make_image(self.tmp / "nagy.png", 1200, 700)
        name = pf.import_avatar(src, "abc123", self.tmp / "av")
        out = self.tmp / "av" / name
        self.assertTrue(out.is_file())
        self.assertTrue(name.endswith(".jpg"))
        img = QImage(str(out))
        self.assertEqual((img.width(), img.height()), (pf.AVATAR_PX, pf.AVATAR_PX))
        self.assertLess(out.stat().st_size, 60_000)             # a nagy fotó sem terheli a felületet

    def test_import_accepts_a_jpg_and_a_portrait_image(self):
        for w, h, fmt, ext in ((300, 900, "JPG", "jpg"), (50, 50, "PNG", "png")):
            src = make_image(self.tmp / f"k.{ext}", w, h, fmt)
            name = pf.import_avatar(src, "x", self.tmp / "av")
            self.assertEqual(QImage(str(self.tmp / "av" / name)).width(), pf.AVATAR_PX)

    def test_import_rejects_files_that_are_not_images(self):
        bad = self.tmp / "szoveg.jpg"
        bad.write_text("ez nem kép", encoding="utf-8")
        with self.assertRaises(ValueError):
            pf.import_avatar(bad, "x", self.tmp / "av")
        with self.assertRaises(ValueError):
            pf.import_avatar(self.tmp / "nincs.png", "x", self.tmp / "av")

    def test_every_import_gets_a_new_file_name(self):
        src = make_image(self.tmp / "a.png", 100, 100)
        names = {pf.import_avatar(src, "x", self.tmp / "av") for _ in range(5)}
        self.assertEqual(len(names), 5)                          # így a régi kép gyorsítótára nem ragad be

    def test_avatar_path_and_delete(self):
        p = pf.make_profile("Robi", [])
        self.assertIsNone(pf.avatar_path(p, self.tmp))
        p["avatar"] = pf.import_avatar(make_image(self.tmp / "a.png", 80, 80), p["id"], self.tmp / "av")
        path = pf.avatar_path(p, self.tmp / "av")
        self.assertTrue(path.is_file())
        pf.delete_avatar(p, self.tmp / "av")
        self.assertFalse(path.exists())
        self.assertIsNone(p["avatar"])
        pf.delete_avatar(p, self.tmp / "av")                     # másodszor sem dob hibát

    def test_missing_avatar_file_is_not_an_error(self):
        p = {"id": "x", "name": "A", "avatar": "eltunt.jpg", "color": pf.COLORS[0]}
        self.assertIsNone(pf.avatar_path(p, self.tmp))


if __name__ == "__main__":
    unittest.main()
