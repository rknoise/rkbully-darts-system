"""Névjegy és név, kör-óra szünet, legutóbbi meccs, meccs végi képernyő (képernyő nélkül)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel
    import appinfo
    import finish
    import options
    import rkbully
    import speech
except Exception:                                       # pragma: no cover
    rkbully = None

import games as g


def played_game(*darts_by_player):
    game = g.X01(["A", "B"], 100, True)
    for m, n in darts_by_player:
        game.throw(m, n)
    return game


@unittest.skipIf(rkbully is None, "PySide6 nincs telepítve")
class FeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(rkbully.QSS)

    def setUp(self):
        self._cfg = rkbully.CFG_FILE
        self.tmp = Path(tempfile.mkdtemp())
        rkbully.CFG_FILE = self.tmp / "settings.json"
        self.win = rkbully.Main()
        self.win.sound.effects = {c: None for c in rkbully.sounds.CUES}
        self.win.speaker = speech.Announcer(True, speech.RecordingEngine())
        self.win.set_mode("501")

    def tearDown(self):
        rkbully.dispose(self.win)
        self.win = None
        rkbully.CFG_FILE = self._cfg

    def play(self, darts):
        for m, n in darts:
            self.win.mult = m
            self.win.hit(n)

    def saved(self):
        return json.loads(rkbully.CFG_FILE.read_text(encoding="utf-8"))

    # ── név és névjegy ──
    def test_the_program_is_called_rkbully_darts_system(self):
        self.assertEqual(appinfo.APP_NAME, "RKBully Darts System")
        self.assertEqual(self.win.windowTitle(), "RKBully Darts System")
        self.assertEqual(self.win.logo_sub.text(), "DARTS SYSTEM")
        self.assertIn("Bully", self.win.findChild(QLabel, "logo").text())

    def test_about_page_names_the_author(self):
        dlg = options.OptionsDialog(self.win, 5)
        page = dlg.pages.currentWidget()
        self.assertIsInstance(page, options.AboutPage)
        self.assertIn("RKNOISE", page.author.text())
        text = " ".join(lb.text() for lb in page.findChildren(QLabel))
        self.assertIn("RKBully Darts System", text)
        self.assertIn(appinfo.GITHUB_URL, text)

    # ── szünet ──
    def clock(self, now):
        return mock.patch.object(rkbully.time, "monotonic", lambda: now[0])

    def test_pause_freezes_the_turn_clock_and_resume_continues_from_there(self):
        w = self.win
        now = [1000.0]
        with self.clock(now):
            w.turn_t0 = 1000.0
            now[0] = 1030.0
            w.update_timer()
            self.assertEqual(w.timer_lbl.text(), "⏱  00:30")
            w.set_paused(True)
            now[0] = 1200.0                                   # 170 mp szünet
            w.update_timer()
            self.assertEqual(w.timer_lbl.text(), "⏸  SZÜNET  00:30")
            w.set_paused(False)
            now[0] = 1210.0
            w.update_timer()
            self.assertEqual(w.timer_lbl.text(), "⏱  00:40")

    def test_the_pause_button_in_the_status_bar_toggles_it(self):
        w = self.win
        w.pause_top.click()
        self.assertTrue(w.paused)
        self.assertEqual(w.pause_top.text(), "▶")
        self.assertEqual(w.pause_btn.text(), "▶  Folytatás")
        w.pause_top.click()
        self.assertFalse(w.paused)
        self.assertEqual(w.pause_top.text(), "⏸")

    def test_nothing_can_be_thrown_while_paused(self):
        w = self.win
        w.toggle_pause()
        self.play([(1, 20)])
        self.assertEqual(len(w.game.hist), 0)
        w.toggle_pause()
        self.play([(1, 20)])
        self.assertEqual(len(w.game.hist), 1)

    def test_a_new_game_ends_the_pause(self):
        w = self.win
        w.toggle_pause()
        w.new_game()
        self.assertFalse(w.paused)
        self.assertIsNone(w.pause_t)

    def test_pause_shortcut_exists(self):
        from PySide6.QtGui import QShortcut
        keys = {sc.key().toString() for sc in self.win.findChildren(QShortcut)}
        self.assertIn("P", keys)

    # ── legutóbbi meccs ──
    def test_no_last_match_before_the_first_throw(self):
        self.assertIsNone(self.win.last_match())
        self.assertFalse(self.win.last_btn.isEnabled())

    def test_switching_games_remembers_the_played_one(self):
        w = self.win
        pids = list(w.game_pids)
        w.out.setCurrentIndex(1)                              # Straight Out
        w.new_game()
        self.play([(1, 20)])
        w.set_mode("301")
        lm = w.last_match()
        self.assertEqual((lm["mode_id"], lm["pids"], lm["out"]), ("501", pids, False))
        self.assertTrue(w.last_btn.isEnabled())
        self.assertIn("501", w.last_btn.toolTip())
        self.assertEqual(self.saved()["last_match"]["mode_id"], "501")

    def test_restart_restores_players_mode_and_checkout_rule(self):
        w = self.win
        w.out.setCurrentIndex(1)
        w.new_game()
        self.play([(1, 20)])
        pids = list(w.game_pids)
        w.set_mode("301")
        w.out.setCurrentIndex(0)
        w.restart_last_match()
        self.assertEqual(w.mode_id, "501")
        self.assertEqual(w.out.currentIndex(), 1)
        self.assertEqual(w.pids[:len(w.names)], pids)
        self.assertEqual(len(w.game.hist), 0)                 # tiszta, új játék
        self.assertEqual(w.game.title, "501 STRAIGHT OUT")

    def test_restart_asks_before_dropping_a_running_game(self):
        w = self.win
        self.play([(1, 20)])
        w.set_mode("301")
        self.play([(1, 5)])
        with mock.patch.object(rkbully.ask, "confirm", return_value=False) as c:
            w.restart_last_match()
        self.assertTrue(c.called)
        self.assertEqual(w.mode_id, "301")
        self.assertEqual(len(w.game.hist), 1)

    def test_last_match_survives_a_restart(self):
        w = self.win
        self.play([(1, 20)])
        w.set_mode("301")
        w.save_state()
        w2 = rkbully.Main()
        try:
            self.assertEqual(w2.last_match()["mode_id"], "501")
            self.assertTrue(w2.last_btn.isEnabled())
        finally:
            rkbully.dispose(w2)

    def test_a_deleted_profile_is_dropped_from_the_last_match(self):
        w = self.win
        self.play([(1, 20)])
        w.set_mode("301")
        w.cfg["last_match"]["pids"].append("nincs-ilyen")
        self.assertNotIn("nincs-ilyen", w.last_match()["pids"])
        w.cfg["last_match"] = {"mode_id": "nincs-ilyen", "pids": ["x"], "out": True}
        self.assertIsNone(w.last_match())

    # ── hang és felolvasás a felületen ──
    def test_round_end_is_read_aloud_and_mute_silences_it(self):
        w = self.win
        w.speaker.engine.said.clear()
        self.play([(1, 20)] * 3)
        self.assertEqual(len(w.speaker.engine.said), 1)
        self.assertIn("hatvan pont", w.speaker.engine.said[0])
        w.set_sound(False)
        self.play([(1, 20)] * 3)
        self.assertEqual(len(w.speaker.engine.said), 1)       # a némított program nem beszél

    def test_speech_setting_is_saved_and_has_a_checkbox(self):
        w = self.win
        page = options.OptionsDialog(w, 3).pages.currentWidget()
        self.assertTrue(page.speech.isChecked())
        page.speech.setChecked(False)
        self.assertFalse(w.speaker.enabled)
        self.assertFalse(self.saved()["speech"])
        w.speaker.engine.said.clear()
        page.speech_test.click()
        self.assertEqual(len(w.speaker.engine.said), 1)       # a próba némítva is megszólal

    # ── meccs végi képernyő ──
    def test_standings_rank_the_winner_first_with_real_averages(self):
        game = played_game((3, 20), (1, 0), (1, 0), (1, 1), (1, 1), (1, 1), (2, 20))
        rows = finish.standings(game)
        self.assertEqual([r["name"] for r in rows], ["A", "B"])
        a, b = rows
        self.assertTrue(a["winner"] and not b["winner"])
        self.assertEqual((a["darts"], a["checkout"], a["best"]), (4, 40, 60))
        self.assertAlmostEqual(a["avg"], 75.0)
        self.assertAlmostEqual(b["avg"], 3.0)
        self.assertEqual(finish.highlights(rows), {"avg": a["i"], "best": a["i"]})

    def test_standings_count_one_eighties_and_tons(self):
        game = g.X01(["A", "B"], 501, True)
        for d in [(3, 20)] * 3 + [(1, 1)] * 3 + [(3, 20), (3, 20), (1, 20)]:
            game.throw(*d)
        rows = {r["name"]: r for r in finish.standings(game)}
        self.assertEqual((rows["A"]["c180"], rows["A"]["c100"]), (1, 2))

    def test_standings_for_other_modes_use_dart_values(self):
        game = g.HighScore(["A", "B"])
        for d in [(3, 20)] * 3 + [(1, 1)] * 3:
            game.throw(*d)
        rows = {r["name"]: r for r in finish.standings(game)}
        self.assertEqual((rows["A"]["best"], rows["A"]["c180"]), (180, 1))
        self.assertAlmostEqual(rows["B"]["avg"], 3.0)

    def test_the_win_triggers_the_end_screen_once(self):
        w = self.win
        w.end_force = True
        w.set_mode("301")
        w.out.setCurrentIndex(1)
        calls = []
        with mock.patch.object(rkbully.QTimer, "singleShot", lambda ms, fn: calls.append(ms)):
            for _ in range(5):
                self.play([(1, 20)] * 3 + [(0, 0)] * 9)
            self.play([(1, 1)])
            self.assertIsNotNone(w.game.winner)
            self.assertEqual(len(calls), 1)
            w.refresh()
            self.assertEqual(len(calls), 1)                   # ugyanannál a játéknál nem ismétlődik
            w.undo()                                          # visszavonás után az újabb győzelem megint megjelenik
            self.play([(1, 1)])
            self.assertEqual(len(calls), 2)

    def test_the_end_screen_is_not_scheduled_without_a_screen_or_when_turned_off(self):
        w = self.win
        calls = []
        with mock.patch.object(rkbully.QTimer, "singleShot", lambda ms, fn: calls.append(ms)):
            w.schedule_match_end()                            # offscreen: nem nyílik ablak
            w.end_force = True
            w.cfg["end_screen"] = False
            w.schedule_match_end()
        self.assertEqual(calls, [])

    def finish_game(self):
        w = self.win
        w.set_mode("301")
        w.out.setCurrentIndex(1)
        for _ in range(5):
            self.play([(1, 20)] * 3 + [(0, 0)] * 9)
        self.play([(1, 1)])

    def test_dialog_shows_the_winner_and_all_players(self):
        w = self.win
        self.finish_game()
        dlg = finish.MatchEndDialog(w, w.game, {}, animate=False)
        try:
            winner = w.game.names[w.game.winner]
            self.assertIn(winner, dlg.name.text())
            self.assertEqual(dlg.table.rowCount(), w.game.n)
            self.assertEqual(dlg.table.item(0, 1).text(), winner)
            self.assertIn("🥇", dlg.table.item(0, 0).text())
            self.assertIn("átlag", dlg.tagline([dlg.rows[0]]))
        finally:
            dlg.deleteLater()

    def test_dialog_buttons_set_the_choice(self):
        w = self.win
        self.finish_game()
        for btn, choice in (("rematch", "rematch"), ("stats_btn", "stats"), ("close_btn", "close")):
            dlg = finish.MatchEndDialog(w, w.game, {}, animate=False)
            getattr(dlg, btn).click()
            self.assertEqual(dlg.choice, choice)
            dlg.deleteLater()

    def test_confetti_runs_and_stops(self):
        w = self.win
        self.finish_game()
        dlg = finish.MatchEndDialog(w, w.game, {}, animate=True)
        try:
            self.assertTrue(dlg.particles)
            for _ in range(1500):
                dlg.step()
            self.assertFalse(dlg.timer.isActive())
        finally:
            dlg.deleteLater()

    def test_rematch_choice_starts_a_fresh_game(self):
        w = self.win
        w.end_force = True
        self.finish_game()
        old = w.game
        with mock.patch.object(finish.MatchEndDialog, "exec", lambda dlg: dlg.rematch.click()):
            w.show_match_end()
        self.assertIsNot(w.game, old)
        self.assertEqual(len(w.game.hist), 0)
        self.assertEqual(w.mode_id, "301")

    def test_stale_end_screen_does_not_open_after_undo(self):
        w = self.win
        w.end_force = True
        self.finish_game()
        w.undo()
        opened = []
        with mock.patch.object(finish.MatchEndDialog, "exec", lambda dlg: opened.append(1)):
            w.show_match_end()
        self.assertEqual(opened, [])


if __name__ == "__main__":
    unittest.main()
