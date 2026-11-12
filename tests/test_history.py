"""A tartós előzmény és az összesítés (Qt nélkül): X01 pontozás bustokkal, bejegyzések, profilonkénti összesítés, fájlkezelés."""
import json
import tempfile
import unittest
from pathlib import Path

import games as g
import history
import stats

T20 = (3, 20)
MISS = (1, 0)


def play(game, darts):
    for m, n in darts:
        game.throw(m, n)


def finished_301(names=("A", "B")):
    """A: 180, B: három mellé, A: T20 T11 D14 (121 kiszálló)."""
    game = g.X01(list(names), 301, True)
    play(game, [T20] * 3)
    play(game, [MISS] * 3 * (len(names) - 1))
    play(game, [T20, (3, 11), (2, 14)])
    return game


class SummaryTests(unittest.TestCase):
    def test_x01_bust_round_scores_nothing(self):
        game = g.X01(["A", "B"], 301, True)
        play(game, [T20] * 3 + [MISS] * 3)               # A 180, B semmi
        play(game, [T20, T20])                           # 121 - 60 - 60 = 1: Double Outnál bust, a kör 2 nyílnál véget ér
        rows = stats.summary(game)
        self.assertEqual(game.left[0], 121)
        self.assertEqual(rows[0]["scored"], 180)
        self.assertEqual(rows[0]["darts"], 5)
        self.assertEqual((rows[0]["best"], rows[0]["c180"], rows[0]["c100"]), (180, 1, 1))
        rounds = stats.x01_rounds(game)
        self.assertEqual([(r["p"], r["scored"], r["bust"]) for r in rounds], [(0, 180, False), (1, 0, False), (0, 0, True)])

    def test_x01_checkout_is_the_value_of_the_finishing_round(self):
        game = finished_301()
        self.assertEqual(game.winner, 0)
        a, b = stats.summary(game)
        self.assertEqual((a["scored"], a["darts"], a["rounds"]), (301, 6, 2))
        self.assertEqual((a["checkout"], a["best"], a["c180"]), (121, 180, 1))
        self.assertEqual((b["scored"], b["darts"], b["checkout"]), (0, 3, 0))

    def test_other_modes_only_count_rounds_and_darts(self):
        game = g.HighScore(["A", "B"])
        play(game, [T20, (1, 5), (2, 7)] + [MISS] * 3)
        rows = stats.summary(game)
        self.assertEqual(rows[0], {"rounds": 1, "darts": 3})
        self.assertEqual(rows[1], {"rounds": 1, "darts": 3})

    def test_undo_changes_the_summary_too(self):
        game = finished_301()
        game.undo()
        self.assertIsNone(game.winner)
        self.assertEqual(stats.summary(game)[0]["checkout"], 0)


class RecordTests(unittest.TestCase):
    def test_record_holds_pids_winner_and_scores(self):
        game = finished_301()
        mode = next(m for m in g.MODES if m.id == "301")
        rec = history.make_record(game, ["p1", "p2"], mode, now=1000)
        self.assertEqual((rec["mode"], rec["t"], rec["winners"], rec["x01"]), ("301", 1000, [0], True))
        self.assertEqual([p["pid"] for p in rec["players"]], ["p1", "p2"])
        self.assertEqual([p["score"] for p in rec["players"]], ["0", "301"])
        self.assertTrue(rec["id"])
        json.dumps(rec)                                  # fájlba írható

    def test_a_tie_lists_every_tied_player(self):
        game = g.HighScore(["A", "B"])
        play(game, [(1, 5)] * 3 + [(1, 5)] * 3)
        for _ in range(9):
            play(game, [(1, 5)] * 6)
            if game.winner is not None:
                break
        self.assertIsNotNone(game.winner)
        rec = history.make_record(game, ["p1", "p2"], next(m for m in g.MODES if m.id == "highscore"))
        self.assertEqual(rec["winners"], [0, 1])
        self.assertFalse(rec["x01"])


def rec(mode, players, winners, x01=True, t=1):
    return {"id": f"r{t}", "t": t, "mode": mode, "title": mode, "x01": x01, "winners": winners, "players": players}


def pl(pid, name, score="0", **kw):
    return {"pid": pid, "name": name, "score": score, **kw}


class AggregateTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            rec("501", [pl("a", "Robi", darts=9, scored=501, best=180, c100=2, c180=1, checkout=60),
                        pl("b", "Dani", darts=9, scored=300, best=100, c100=1, c180=0, checkout=0)], [0], t=1),
            rec("501", [pl("a", "Robi", darts=9, scored=200, best=80, c100=0, c180=0, checkout=0),
                        pl("b", "Dani", darts=6, scored=501, best=140, c100=1, c180=0, checkout=40)], [1], t=2),
            rec("cricket", [pl("a", "Robi"), pl("b", "Dani")], [0, 1], x01=False, t=3),
            rec("301", [pl("a", "Robi", darts=6, scored=301, best=121, c100=1, c180=0, checkout=121)], [0], t=4),
        ]

    def by_pid(self, rows):
        return {r["pid"]: r for r in rows}

    def test_wins_draws_games_and_percentages(self):
        r = self.by_pid(history.aggregate(self.records))
        self.assertEqual((r["a"]["games"], r["a"]["versus"], r["a"]["wins"], r["a"]["draws"]), (4, 3, 1, 1))
        self.assertEqual((r["b"]["games"], r["b"]["wins"], r["b"]["draws"]), (3, 1, 1))
        self.assertAlmostEqual(r["a"]["win_pct"], 100 / 3)

    def test_a_solo_game_is_played_but_never_won(self):
        solo = history.aggregate([self.records[3]])
        self.assertEqual((solo[0]["games"], solo[0]["wins"], solo[0]["versus"]), (1, 0, 0))
        self.assertIsNone(solo[0]["win_pct"])

    def test_x01_numbers_only_come_from_x01_games(self):
        r = self.by_pid(history.aggregate(self.records))["a"]
        self.assertEqual((r["darts"], r["scored"]), (24, 1002))
        self.assertAlmostEqual(r["avg3"], 1002 / 24 * 3)
        self.assertEqual((r["best"], r["c100"], r["c180"], r["checkout"]), (180, 3, 1, 121))

    def test_mode_filter_and_order(self):
        rows = history.aggregate(self.records, "501")
        self.assertEqual([r["pid"] for r in rows], ["b", "a"])          # 1-1 győzelem, azonos játékszám: név szerint (Dani, Robi)
        self.assertEqual(rows[0]["games"], 2)
        cricket = history.aggregate(self.records, "cricket")
        self.assertEqual((cricket[0]["draws"], cricket[0]["avg3"]), (1, None))

    def test_the_latest_name_wins_and_unknown_profiles_group_by_name(self):
        records = [rec("501", [pl("a", "Régi"), pl(None, "Vendég")], [0]), rec("501", [pl("a", "Új"), pl(None, "vendég")], [1], t=2)]
        rows = {r["pid"] or r["name"].casefold(): r for r in history.aggregate(records)}
        self.assertEqual(rows["a"]["name"], "Új")
        self.assertEqual(rows["a"]["games"], 2)
        self.assertEqual(rows["vendég"]["games"], 2)

    def test_a_reset_hides_older_games_for_that_profile_only(self):
        since = {"a": 2}                                           # Robi nullázta: az 1-es és 2-es játék nem számít neki
        rows = self.by_pid(history.aggregate(self.records, since=since))
        self.assertEqual((rows["a"]["games"], rows["a"]["wins"], rows["a"]["draws"]), (2, 0, 1))
        self.assertEqual(rows["a"]["scored"], 301)                 # csak a 301-es solo játék X01-értékei maradnak
        self.assertEqual((rows["b"]["games"], rows["b"]["wins"], rows["b"]["draws"]), (3, 1, 1))   # Daninak minden megmaradt
        self.assertEqual(rows["b"]["versus"], 3)

    def test_games_after_the_reset_count_again(self):
        self.assertEqual(self.by_pid(history.aggregate(self.records, since={"a": 0.5}))["a"]["games"], 4)     # mind újabb
        self.assertEqual(self.by_pid(history.aggregate(self.records, since={"a": 3.5}))["a"]["games"], 1)     # csak a 4-es
        self.assertNotIn("a", self.by_pid(history.aggregate(self.records, since={"a": 4})))                   # t == since: még nem számít

    def test_a_reset_never_touches_guests_without_a_profile(self):
        records = [rec("501", [pl(None, "Vendég"), pl("a", "Robi")], [0], t=1)]
        rows = history.aggregate(records, since={"a": 10})
        self.assertEqual([r["name"] for r in rows], ["Vendég"])

    def test_the_timestamp_has_millisecond_precision(self):
        game = finished_301()
        record = history.make_record(game, ["p1", "p2"], next(m for m in g.MODES if m.id == "301"), now=1000.12345)
        self.assertEqual(record["t"], 1000.123)

    def test_modes_in_orders_by_frequency(self):
        self.assertEqual(history.modes_in(self.records), ["501", "cricket", "301"])


class FileTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "sub" / "history.json"

    def test_round_trip_creates_the_folder(self):
        history.save([rec("501", [pl("a", "A")], [0])], self.path)
        self.assertEqual(history.load(self.path)[0]["mode"], "501")

    def test_damaged_files_give_an_empty_history(self):
        self.assertEqual(history.load(self.path), [])                   # nincs fájl
        self.path.parent.mkdir(parents=True)
        for text in ("nem json", "{}", '"szöveg"', "[1, 2, {\"players\": 5}]"):
            self.path.write_text(text, encoding="utf-8")
            self.assertEqual(history.load(self.path), [], text)

    def test_only_the_newest_records_are_kept(self):
        many = [rec("501", [pl("a", "A")], [0], t=i) for i in range(history.MAX_RECORDS + 5)]
        history.save(many, self.path)
        saved = history.load(self.path)
        self.assertEqual(len(saved), history.MAX_RECORDS)
        self.assertEqual(saved[-1]["t"], history.MAX_RECORDS + 4)

    def test_path_is_next_to_the_settings_file(self):
        self.assertEqual(history.history_path(Path("x") / ".rkbully" / "settings.json"), Path("x") / ".rkbully" / "history.json")


if __name__ == "__main__":
    unittest.main()
