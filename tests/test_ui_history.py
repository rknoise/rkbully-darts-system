"""Felület-tesztek: a befejezett játékok mentése, a visszavonás hatása, újraindítás, Statisztikák ablak."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    import options
    import rkbully
    import statsview
except Exception:                                       # pragma: no cover
    rkbully = None

import ask
import history
import profiles as pf

ORIGINAL_CONFIRM = ask.confirm                           # a tesztek ideiglenesen lecserélik, az AskTests az eredetit használja


@unittest.skipIf(rkbully is None, "PySide6 nincs telepítve")
class HistoryUiBase(unittest.TestCase):
    """Közös alap: ideiglenes beállítási mappa, három profil, segédfüggvények (nem tartalmaz tesztet)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(rkbully.QSS)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._saved = (rkbully.CFG_FILE, pf.AVATAR_DIR, QMessageBox.information, ask.confirm)
        rkbully.CFG_FILE = self.tmp / "settings.json"
        pf.AVATAR_DIR = self.tmp / "avatars"
        QMessageBox.information = staticmethod(lambda *a, **k: None)
        ask.confirm = lambda *a, **k: True
        rkbully.CFG_FILE.write_text(json.dumps({"names": ["Robi", "Dani", "Milla"]}), encoding="utf-8")
        self.wins = []
        self.win = rkbully.Main()
        self.win.set_mode("301")

    def tearDown(self):
        for w in self.wins:
            rkbully.dispose(w)
        rkbully.dispose(self.win)
        self.win = None
        (rkbully.CFG_FILE, pf.AVATAR_DIR, QMessageBox.information, ask.confirm) = self._saved

    def play(self, darts, win=None):
        w = win or self.win
        for m, n in darts:
            w.mult = m
            w.hit(n)

    def finish(self, win=None):
        """Robi 180, a többiek mellé, Robi T20 T11 D14: 301-ről pontosan nullára (121 kiszálló)."""
        self.play([(3, 20)] * 3 + [(1, 0)] * 6 + [(3, 20), (3, 11), (2, 14)], win)

    def saved_records(self):
        return json.loads((self.tmp / "history.json").read_text(encoding="utf-8"))


@unittest.skipIf(rkbully is None, "PySide6 nincs telepítve")
class HistoryUiTests(HistoryUiBase):
    def test_an_unfinished_game_is_not_saved(self):
        self.play([(3, 20)] * 3)
        self.assertEqual(self.win.history, [])
        self.assertFalse((self.tmp / "history.json").exists())

    def test_a_finished_game_is_saved_once_with_the_profiles(self):
        w = self.win
        self.finish()
        self.assertIsNotNone(w.game.winner)
        for _ in range(3):
            w.refresh()                                  # többszöri frissítés nem ment újra
        recs = self.saved_records()
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual((rec["mode"], rec["winners"], rec["x01"]), ("301", [0], True))
        self.assertEqual([p["pid"] for p in rec["players"]], w.pids[:3])
        self.assertEqual([p["name"] for p in rec["players"]], ["Robi", "Dani", "Milla"])
        self.assertEqual((rec["players"][0]["checkout"], rec["players"][0]["c180"]), (121, 1))

    def test_undoing_the_winning_dart_removes_the_record_and_finishing_again_adds_it_back(self):
        w = self.win
        self.finish()
        self.assertEqual(len(w.history), 1)
        w.undo()
        self.assertIsNone(w.game.winner)
        self.assertEqual(w.history, [])
        self.assertEqual(self.saved_records(), [])
        self.play([(2, 14)])
        self.assertEqual(len(w.history), 1)
        self.assertEqual(len(self.saved_records()), 1)

    def test_starting_a_new_game_keeps_the_record(self):
        w = self.win
        self.finish()
        w.new_game()
        self.assertEqual(len(w.history), 1)
        self.finish()
        self.assertEqual(len(w.history), 2)

    def test_the_history_survives_a_restart(self):
        self.finish()
        w2 = rkbully.Main()
        self.wins.append(w2)
        self.assertEqual(len(w2.history), 1)
        self.assertEqual(w2.history[0]["players"][0]["name"], "Robi")

    def test_stats_tab_opens_the_dialog_with_history_and_current_names(self):
        w = self.win
        self.finish()
        w.rename_profile(w.pids[0], "Robert")             # átnevezés után az összesítés az új nevet mutatja
        seen = []
        self._exec = statsview.StatsDialog.exec
        statsview.StatsDialog.exec = lambda dlg: seen.append(dlg)
        try:
            w.show_stats()
        finally:
            statsview.StatsDialog.exec = self._exec
        dlg = seen[0]
        self.assertEqual(dlg.pages.currentIndex(), 0)
        self.assertEqual(dlg.totals.item(0, 0).text(), "Robert")
        self.assertEqual(dlg.totals.item(0, 2).text(), "1")           # győzelem
        self.assertEqual(dlg.totals.item(0, 3).text(), "100%")
        self.assertEqual(dlg.totals.item(0, 8).text(), "121")         # legjobb kiszálló
        self.assertIn("Robert", dlg.log.item(0, 2).text())
        self.assertTrue(dlg.log.item(0, 2).text().startswith("👑 Robert"))

    def test_dialog_without_history_explains_itself(self):
        dlg = statsview.StatsDialog(self.win, self.win.game, [], {})
        self.assertFalse(dlg.totals_empty.isHidden())
        self.assertTrue(dlg.totals.isHidden())
        self.assertFalse(dlg.clear_btn.isEnabled())
        self.assertEqual(dlg.current.rowCount(), 3)                   # a folyó játék oldala ettől még működik

    def test_mode_filter_changes_the_totals(self):
        w = self.win
        self.finish()
        w.set_mode("501")
        self.play([(3, 20)] * 3)
        w.set_mode("301")
        self.finish()
        dlg = statsview.StatsDialog(w, w.game, w.history, {p["id"]: p["name"] for p in w.profiles})
        self.assertEqual(dlg.totals.item(0, 1).text(), "2")           # Robi: 2 játék
        self.assertEqual(dlg.mode_box.itemText(0), "Minden játékmód")
        self.assertEqual(dlg.mode_box.count(), 2)                     # csak a 301 szerepel az előzményben (+ az „összes”)
        dlg.mode_box.setCurrentIndex(1)
        self.assertEqual(dlg.totals.item(0, 1).text(), "2")

    def test_zero_wins_shows_zero_percent_not_a_dash(self):
        w = self.win
        self.finish()
        dlg = statsview.StatsDialog(w, w.game, w.history, {p["id"]: p["name"] for p in w.profiles})
        rows = {dlg.totals.item(r, 0).text(): [dlg.totals.item(r, c).text() for c in range(9)] for r in range(3)}
        self.assertEqual(rows["Dani"][3], "0%")                       # játszott, de nem nyert
        self.assertEqual(rows["Dani"][2], "0")
        self.assertEqual(rows["Dani"][4], "0.0")                      # 3 mellé dobott nyíl: átlag 0.0, nem hiányzó adat
        self.assertEqual(rows["Dani"][8], "–")                        # nem volt kiszállója

    def test_clear_asks_and_empties_everything(self):
        w = self.win
        self.finish()
        ask.confirm = lambda *a, **k: False
        dlg = statsview.StatsDialog(w, w.game, w.history, {}, w.clear_history)
        dlg.clear()
        self.assertEqual(len(w.history), 1)                           # nemmel nem törlődik
        ask.confirm = lambda *a, **k: True
        dlg.clear()
        self.assertEqual(w.history, [])
        self.assertEqual(self.saved_records(), [])
        self.assertEqual(dlg.log.rowCount(), 0)
        self.assertTrue(dlg.totals.isHidden())
        self.assertFalse(dlg.clear_btn.isEnabled())
        self.finish()                                                 # törlés után az új játékok megint mentődnek
        w.new_game()
        self.finish()
        self.assertEqual(len(w.history), 1)

    def test_every_mode_can_finish_and_be_summarised(self):
        """Minden játékmód befejezett játéka mentődik, és az összesítés nem dől el rajta (a motorral dobunk, a felület a végén frissül)."""
        import games as g
        import random
        w = self.win
        rnd = random.Random(11)
        finished = 0
        for mode in g.MODES:
            w.names = ["A", "B", "C"]
            w.set_mode(mode.id)
            for _ in range(1500):
                if w.game.winner is not None:
                    break
                m = rnd.choice((1, 2, 3))
                w.game.throw(m, rnd.choice([0, 25] + list(range(1, 21))))
            w.refresh()
            finished += w.game.winner is not None
        self.assertGreater(finished, 5)
        self.assertEqual(len(w.history), finished)
        statsview.StatsDialog(w, w.game, w.history, {})
        self.assertEqual(len(history.load(self.tmp / "history.json")), finished)


@unittest.skipIf(rkbully is None, "PySide6 nincs telepítve")
class StatsResetTests(HistoryUiBase):
    """A profil szerkesztőben a statisztika nullázása (megerősítéssel)."""

    def setUp(self):
        super().setUp()
        self.questions = []
        self.answer = True
        ask.confirm = lambda parent, title, text, *a, **k: self.questions.append((title, text)) or self.answer
        self.page = options.OptionsDialog(self.win).profiles_page      # a főablak gyermeke: azzal együtt bomlik le
        self.page.list.setCurrentRow(0)                                # Robi

    def select(self, name):
        for row in range(self.page.list.count()):
            if self.page.list.item(row).text().startswith(name):
                self.page.list.setCurrentRow(row)
                return
        raise AssertionError(name)

    def test_page_says_there_is_nothing_to_reset_yet(self):
        self.assertIn("Még nincs mentett játék", self.page.stats.text())
        self.assertFalse(self.page.reset_stats.isEnabled())

    def test_page_summarises_the_profiles_games(self):
        self.finish()
        self.page.reload()
        text = self.page.stats.text()
        self.assertIn("1 játék", text)
        self.assertIn("1 győzelem (100%)", text)
        self.assertIn("legjobb kiszálló 121", text)
        self.assertIn("1× 180", text)
        self.assertTrue(self.page.reset_stats.isEnabled())
        self.select("Dani")
        self.assertIn("0 győzelem (0%)", self.page.stats.text())

    def test_no_answer_changes_nothing(self):
        self.finish()
        self.page.reload()
        self.answer = False
        self.page.reset_stats.click()
        self.assertEqual(len(self.questions), 1)
        title, text = self.questions[0]
        self.assertEqual(title, "Statisztika nullázása")
        self.assertIn("Robi", text)
        self.assertIn("1 játék", self.page.stats.text())
        self.assertNotIn("stats_from", self.win.profiles[0])
        self.assertTrue(self.page.reset_stats.isEnabled())

    def test_yes_answer_resets_only_this_profile_and_keeps_the_game_list(self):
        w = self.win
        self.finish()
        self.page.reload()
        self.page.reset_stats.click()
        self.assertIn("Még nincs mentett játék", self.page.stats.text())
        self.assertFalse(self.page.reset_stats.isEnabled())
        self.assertIn("nullázva", self.page.msg.text())
        self.assertGreater(w.profiles[0]["stats_from"], 0)
        saved = json.loads(rkbully.CFG_FILE.read_text(encoding="utf-8"))
        self.assertGreater(saved["profiles"][0]["stats_from"], 0)       # a beállításfájlba is bekerült
        self.assertNotIn("stats_from", w.profiles[1])                    # Dani statisztikája érintetlen
        self.select("Dani")
        self.assertIn("1 játék", self.page.stats.text())
        self.assertEqual(len(w.history), 1)                              # a játékok listája megmarad
        seen = []
        self._exec = statsview.StatsDialog.exec
        statsview.StatsDialog.exec = lambda dlg: seen.append(dlg)
        try:
            w.show_stats()
        finally:
            statsview.StatsDialog.exec = self._exec
        dlg = seen[0]
        self.assertEqual([dlg.totals.item(r, 0).text() for r in range(dlg.totals.rowCount())], ["Dani", "Milla"])
        self.assertEqual(dlg.log.rowCount(), 1)

    def test_games_finished_after_the_reset_count_again_and_it_survives_a_restart(self):
        w = self.win
        self.finish()
        self.page.reload()
        self.page.reset_stats.click()
        time.sleep(0.02)
        w.new_game()
        self.finish()
        self.page.reload()
        self.assertIn("1 játék", self.page.stats.text())
        self.assertIn("1 győzelem", self.page.stats.text())
        w2 = rkbully.Main()
        self.wins.append(w2)
        self.assertEqual(w2.stats_since().keys(), {w.pids[0]})
        self.assertEqual(options.OptionsDialog(w2).profiles_page.stats_row(w2.profiles[0])["games"], 1)

    def test_nothing_to_reset_means_no_question(self):
        self.page.reset_profile_stats()
        self.assertEqual(self.questions, [])


class AskTests(unittest.TestCase):
    """A magyar Igen/Nem kérdés (a valódi ablakkal, képernyő nélkül)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._confirm = ask.confirm
        ask.confirm = ORIGINAL_CONFIRM

    def tearDown(self):
        ask.confirm = self._confirm

    def click_later(self, text):
        def click():
            box = QApplication.activeModalWidget()
            self.buttons = [b.text() for b in box.buttons()]
            self.default = box.defaultButton().text()
            if text is None:
                box.close()
            else:
                next(b for b in box.buttons() if b.text() == text).click()
        QTimer.singleShot(80, click)

    def test_buttons_are_hungarian_and_yes_returns_true(self):
        self.click_later("Igen")
        self.assertTrue(ask.confirm(None, "Cím", "Biztos?"))
        self.assertEqual(self.buttons, ["Igen", "Nem"])
        self.assertEqual(self.default, "Nem")                            # az Enter a biztonságos választ adja

    def test_no_and_closing_the_window_both_mean_no(self):
        self.click_later("Nem")
        self.assertFalse(ask.confirm(None, "Cím", "Biztos?"))
        self.click_later(None)
        self.assertFalse(ask.confirm(None, "Cím", "Biztos?"))


if __name__ == "__main__":
    unittest.main()
