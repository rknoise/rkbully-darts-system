"""Hangeffektek: melyik esemény melyik hangot szólaltatja meg, a hangfájlok épsége, ki/be kapcsolás, hangerő, felületi bekötés."""
import json
import os
import struct
import tempfile
import unittest
import wave
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    import options
    import rkbully
except Exception:                                       # pragma: no cover
    rkbully = None

import games as g
import sounds

ROOT = Path(__file__).resolve().parent.parent
T20 = (3, 20)
MISS = (1, 0)


def cues_while_playing(game, darts):
    """A játék dobásonként: melyik hang szólna (a felület ugyanígy hívja a cue_for-t minden új dobás után)."""
    out = []
    for m, n in darts:
        game.throw(m, n)
        out.append(sounds.cue_for(game))
    return out


class CueTests(unittest.TestCase):
    def test_darts_inside_a_round_and_the_round_end(self):
        game = g.X01(["A", "B"], 501, True)
        self.assertEqual(cues_while_playing(game, [(1, 5), (1, 5), (1, 5)]), ["dart", "dart", "next"])

    def test_one_hundred_plus_and_one_eighty(self):
        game = g.X01(["A", "B"], 501, True)
        self.assertEqual(cues_while_playing(game, [T20, T20, T20]), ["triple", "triple", "180"])
        self.assertEqual(cues_while_playing(game, [(3, 20), (1, 20), (1, 20)]), ["triple", "dart", "ton"])

    def test_bust_ends_the_round_early_with_the_bust_sound(self):
        game = g.X01(["A", "B"], 301, True)
        cues = cues_while_playing(game, [T20] * 3 + [MISS] * 3 + [T20, T20])      # 121 - 60 - 60 = 1: bust
        self.assertEqual(cues, ["triple", "triple", "180", "dart", "dart", "next", "triple", "bust"])

    def test_a_busting_round_is_never_a_ton_even_with_big_darts(self):
        game = g.X01(["A", "B"], 170, True)
        cues = cues_while_playing(game, [T20, T20, T20])                           # 170 - 60 - 60 - 60 < 0
        self.assertEqual(cues[-1], "bust")

    def test_the_winning_dart_plays_the_fanfare(self):
        game = g.X01(["A"], 40, True)
        self.assertEqual(cues_while_playing(game, [(2, 20)]), ["win"])

    def test_other_modes_use_the_round_points(self):
        game = g.HighScore(["A", "B"])
        self.assertEqual(cues_while_playing(game, [T20, T20, T20]), ["triple", "triple", "180"])
        self.assertEqual(cues_while_playing(game, [(1, 1)] * 3), ["dart", "dart", "next"])

    def test_double_triple_and_bull_have_their_own_effects(self):
        game = g.X01(["A", "B"], 501, True)
        self.assertEqual(cues_while_playing(game, [(2, 16), (3, 5), (2, 25)]), ["double", "triple", "bull"])

    def test_single_bull_and_misses_are_plain_darts(self):
        self.assertEqual([sounds.dart_cue(*d) for d in [(1, 25), (1, 0), (0, 0), (1, 20)]], ["dart"] * 4)

    def test_the_last_dart_of_a_round_can_still_be_special(self):
        game = g.X01(["A", "B"], 501, True)
        self.assertEqual(cues_while_playing(game, [(1, 5), (1, 5), (2, 10)]), ["dart", "dart", "double"])
        self.assertEqual(cues_while_playing(game, [(1, 5), (1, 5), (1, 5)]), ["dart", "dart", "next"])

    def test_ton_and_180_beat_the_last_dart_effect(self):
        game = g.X01(["A", "B"], 501, True)
        self.assertEqual(cues_while_playing(game, [(3, 20), (3, 20), (2, 20)])[-1], "ton")

    def test_every_cue_has_a_file_and_a_name(self):
        for cue in sounds.CUES:
            self.assertIn(cue, sounds.FILES)
            self.assertIn(cue, sounds.NAMES)
            self.assertTrue((ROOT / "assets" / "sounds" / sounds.FILES[cue]).is_file(), cue)


class WavTests(unittest.TestCase):
    def test_files_are_valid_short_audible_and_not_clipping(self):
        for cue, name in sounds.FILES.items():
            with wave.open(str(ROOT / "assets" / "sounds" / name)) as w:
                self.assertEqual((w.getsampwidth(), w.getnchannels()), (2, 1), name)
                seconds = w.getnframes() / w.getframerate()
                self.assertTrue(0.05 < seconds < 3.0, f"{name}: {seconds:.2f} s")
                data = struct.unpack(f"<{w.getnframes()}h", w.readframes(w.getnframes()))
            peak = max(abs(x) for x in data) / 32767
            self.assertTrue(0.15 < peak <= 0.9, f"{name}: csúcs {peak:.2f}")


class BoardTests(unittest.TestCase):
    def test_disabled_board_plays_nothing_but_force_still_works(self):
        board = sounds.SoundBoard(ROOT / "assets" / "sounds", enabled=False)
        board.effects = {c: None for c in sounds.CUES}                 # a tesztben ne nyúljon hangeszközhöz
        board.play("win")
        self.assertEqual(board.played, [])
        board.play("win", force=True)
        self.assertEqual(board.played, ["win"])

    def test_missing_files_never_raise(self):
        board = sounds.SoundBoard(Path(tempfile.mkdtemp()))
        self.assertFalse(board.play("dart"))
        self.assertFalse(board.play("nincs-ilyen-hang"))

    def test_without_an_application_nothing_is_created_and_nothing_crashes(self):
        board = sounds.SoundBoard(ROOT / "assets" / "sounds")
        if rkbully is None or QApplication.instance() is None:
            self.assertFalse(board.play("dart"))                       # nincs QApplication: csendben kihagyja
            self.assertEqual(board.effects, {})                        # és nem jegyzi fel, hogy a hang „nem létezik”

    def test_volume_is_clamped(self):
        board = sounds.SoundBoard(ROOT / "assets" / "sounds", volume=7)
        self.assertEqual(board.volume, 1.0)
        board.set_volume(-3)
        self.assertEqual(board.volume, 0.0)


@unittest.skipIf(rkbully is None, "PySide6 nincs telepítve")
class SoundUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(rkbully.QSS)

    def setUp(self):
        self._cfg = rkbully.CFG_FILE
        self.tmp = Path(tempfile.mkdtemp())
        rkbully.CFG_FILE = self.tmp / "settings.json"
        self.win = rkbully.Main()
        self.win.sound.effects = {c: None for c in sounds.CUES}        # a tesztben ne nyúljon hangeszközhöz
        self.win.set_mode("501")

    def tearDown(self):
        rkbully.dispose(self.win)
        self.win = None
        rkbully.CFG_FILE = self._cfg

    def play(self, darts):
        for m, n in darts:
            self.win.mult = m
            self.win.hit(n)

    def test_throws_play_the_matching_sounds_in_order(self):
        w = self.win
        w.sound.played = []
        self.play([T20, T20, T20, (1, 5), (1, 5), (1, 5)])
        self.assertEqual(w.sound.played, ["triple", "triple", "180", "dart", "dart", "next"])

    def test_undo_and_a_new_game_are_silent(self):
        w = self.win
        self.play([T20, T20])
        w.sound.played = []
        w.undo()
        w.new_game()
        w.refresh()
        self.assertEqual(w.sound.played, [])

    def test_muting_silences_everything_and_is_saved(self):
        w = self.win
        w.set_sound(False)
        w.sound.played = []
        self.play([T20, T20, T20])
        self.assertEqual(w.sound.played, [])
        self.assertEqual(w.snd_btn.text(), "🔇")
        self.assertFalse(json.loads(rkbully.CFG_FILE.read_text(encoding="utf-8"))["sound"])
        w.snd_btn.click()                                              # a fejléc gombja visszakapcsolja
        self.assertTrue(w.sound.enabled)
        self.assertEqual(w.snd_btn.text(), "🔊")
        self.assertTrue(w.snd_btn.toolTip())

    def test_settings_survive_a_restart(self):
        w = self.win
        w.set_sound(False)
        w.set_volume(35)
        w2 = rkbully.Main()
        try:
            self.assertFalse(w2.sound.enabled)
            self.assertAlmostEqual(w2.sound.volume, 0.35)
            self.assertEqual(w2.snd_btn.text(), "🔇")
        finally:
            rkbully.dispose(w2)

    def test_options_page_controls_the_board(self):
        w = self.win
        page = options.OptionsDialog(w, 3).pages.currentWidget()       # a főablak gyermekeként (parentless ablak leállási hibát okozhat)
        self.assertIsInstance(page, options.SoundPage)
        self.assertTrue(page.on.isChecked())
        self.assertEqual(page.slider.value(), 70)
        page.slider.setValue(20)
        self.assertEqual(page.value.text(), "20%")
        self.assertAlmostEqual(w.sound.volume, 0.2)
        page.on.setChecked(False)
        self.assertFalse(w.sound.enabled)
        w.sound.played = []
        page.tests["win"].click()                                      # a próbagomb némítva is szól
        self.assertEqual(w.sound.played, ["win"])
        self.assertEqual(len(page.tests), len(sounds.CUES))

    def test_the_options_dialog_has_a_sound_page(self):
        dlg = options.OptionsDialog(self.win, 3)
        self.assertIn("Hang", dlg.nav.item(3).text())
        self.assertIsInstance(dlg.pages.currentWidget(), options.SoundPage)


if __name__ == "__main__":
    unittest.main()
