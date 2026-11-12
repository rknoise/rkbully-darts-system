"""Pontszám-felolvasás: magyar számnevek, a mondatok és a be/ki kapcsolás (hangmotor nélkül, felvevő motorral)."""
import unittest

import games as g
import speech


def play(game, darts):
    for m, n in darts:
        game.throw(m, n)


class NumberTests(unittest.TestCase):
    def test_hungarian_numbers(self):
        cases = {0: "nulla", 1: "egy", 2: "kettő", 7: "hét", 10: "tíz", 11: "tizenegy", 12: "tizenkettő", 19: "tizenkilenc",
                 20: "húsz", 21: "huszonegy", 22: "huszonkettő", 30: "harminc", 32: "harminckettő", 45: "negyvenöt",
                 60: "hatvan", 99: "kilencvenkilenc", 100: "száz", 101: "százegy", 112: "száztizenkettő", 180: "száznyolcvan",
                 200: "kétszáz", 222: "kétszázhuszonkettő", 301: "háromszázegy", 501: "ötszázegy", 701: "hétszázegy",
                 1000: "ezer", 2000: "kétezer", 1501: "ezerötszázegy"}
        for n, text in cases.items():
            self.assertEqual(speech.hu_number(n), text, n)

    def test_negative_and_float_input(self):
        self.assertEqual(speech.hu_number(-5), "mínusz öt")
        self.assertEqual(speech.hu_number(60.0), "hatvan")

    def test_every_score_up_to_a_thousand_has_a_clean_reading(self):
        for n in range(0, 1000):
            text = speech.hu_number(n)
            self.assertTrue(text and text.islower() and " " not in text, (n, text))


class AnnouncementTests(unittest.TestCase):
    def test_nothing_is_read_in_the_middle_of_a_round(self):
        game = g.X01(["Anna", "Béla"], 501, True)
        self.assertIsNone(speech.announcement(game))
        play(game, [(3, 20), (3, 20)])
        self.assertIsNone(speech.announcement(game))

    def test_round_end_reads_the_score_and_the_rest(self):
        game = g.X01(["Anna", "Béla"], 501, True)
        play(game, [(3, 20), (3, 20), (3, 20)])
        self.assertEqual(speech.announcement(game), "Anna: száznyolcvan pont. Hátra: háromszázhuszonegy.")

    def test_digits_are_used_when_the_voice_is_not_hungarian(self):
        game = g.X01(["Anna", "Béla"], 501, True)
        play(game, [(3, 20), (3, 20), (3, 20)])
        self.assertEqual(speech.announcement(game, hungarian=False), "Anna: 180 pont. Hátra: 321.")

    def test_bust_is_announced_without_a_score(self):
        game = g.X01(["Anna", "Béla"], 40, True)
        play(game, [(3, 20)])                                  # 40 - 60: bust
        self.assertEqual(speech.announcement(game), "Anna, túldobta.")

    def test_win_is_announced(self):
        game = g.X01(["Anna", "Béla"], 40, True)
        play(game, [(2, 20)])
        self.assertEqual(speech.announcement(game), "Játék! Anna nyerte a meccset.")

    def test_other_modes_read_the_round_points(self):
        game = g.HighScore(["Anna", "Béla"])
        play(game, [(3, 20), (1, 20), (1, 20)])
        self.assertEqual(speech.announcement(game), "Anna: száz pont.")


class AnnouncerTests(unittest.TestCase):
    def setUp(self):
        self.engine = speech.RecordingEngine(hungarian=True)
        self.game = g.X01(["Anna", "Béla"], 501, True)
        play(self.game, [(1, 20)] * 3)

    def test_speaks_through_the_engine(self):
        a = speech.Announcer(True, self.engine)
        text = a.speak_for(self.game)
        self.assertEqual(self.engine.said, [text])
        self.assertIn("hatvan pont", text)

    def test_disabled_is_silent_but_force_works(self):
        a = speech.Announcer(False, self.engine)
        self.assertIsNone(a.speak_for(self.game))
        self.assertEqual(self.engine.said, [])
        self.assertIsNotNone(a.speak_for(self.game, force=True))

    def test_nothing_to_say_mid_round(self):
        a = speech.Announcer(True, self.engine)
        play(self.game, [(1, 5)])
        self.assertIsNone(a.speak_for(self.game))

    def test_sample_always_speaks(self):
        a = speech.Announcer(False, self.engine)
        self.assertIn("száznyolcvan", a.sample())
        english = speech.RecordingEngine(hungarian=False)
        self.assertIn("180", speech.Announcer(False, english).sample())

    def test_null_engine_never_raises(self):
        a = speech.Announcer(True, speech.NullEngine())
        self.assertIsNotNone(a.speak_for(self.game))

    def test_headless_environment_gets_the_null_engine(self):
        self.assertIsInstance(speech.make_engine(), speech.NullEngine)


if __name__ == "__main__":
    unittest.main()
