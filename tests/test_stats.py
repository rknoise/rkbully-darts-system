"""Statisztika a játékmotor előzményeiből, és a kiszálló útvonalak."""
import unittest

import games as g
import stats


def play(game, rounds):
    """rounds: [[(szorzó, szám), ...], ...] sorban a játékosoknak."""
    for darts in rounds:
        for m, n in darts:
            game.throw(m, n)


class StatsTests(unittest.TestCase):
    def setUp(self):
        self.game = g.MODES[[m.id for m in g.MODES].index("501")].make(["A", "B"], True)

    def test_empty_game_has_empty_stats(self):
        rows = stats.player_stats(self.game)
        self.assertEqual([r["rounds"] for r in rows], [0, 0])
        self.assertEqual(stats.recent(self.game), [])
        self.assertEqual(stats.round_log(self.game), [])

    def test_rounds_darts_points_best_and_average(self):
        play(self.game, [[(3, 20), (3, 20), (3, 20)], [(1, 1), (1, 1), (1, 1)], [(1, 20), (1, 20), (1, 20)]])
        a, b = stats.player_stats(self.game)
        self.assertEqual((a["rounds"], a["darts"], a["points"], a["best"]), (2, 6, 240, 180))
        self.assertAlmostEqual(a["avg3"], 120.0)
        self.assertEqual((b["rounds"], b["darts"], b["points"], b["best"]), (1, 3, 3, 3))

    def test_the_round_in_progress_counts_for_darts_and_points(self):
        play(self.game, [[(3, 20), (1, 5)]])
        a, b = stats.player_stats(self.game)
        self.assertEqual((a["rounds"], a["darts"], a["points"]), (0, 2, 65))
        self.assertEqual(b["darts"], 0)

    def test_recent_lists_newest_first_with_short_names(self):
        play(self.game, [[(3, 20), (1, 5), (2, 25)], [(0, 0), (1, 1), (3, 19)]])
        rows = stats.recent(self.game, 4)
        self.assertEqual(rows[0], ("B", ["–", "S1", "T19"], 58))
        self.assertEqual(rows[1], ("A", ["T20", "S5", "Bull"], 115))
        self.assertEqual(len(stats.recent(self.game, 1)), 1)

    def test_undo_removes_the_dart_from_the_stats(self):
        play(self.game, [[(3, 20), (3, 20), (3, 20)]])
        self.assertEqual(len(stats.recent(self.game)), 1)
        self.game.undo()
        self.assertEqual(stats.recent(self.game), [])
        a, _ = stats.player_stats(self.game)
        self.assertEqual((a["darts"], a["points"]), (2, 120))

    def test_winners_last_round_is_included(self):
        game = g.MODES[[m.id for m in g.MODES].index("301")].make(["A", "B"], False)
        for _ in range(5):
            play(game, [[(1, 20), (1, 20), (1, 20)], [(0, 0), (0, 0), (0, 0)]])
        play(game, [[(1, 1)]])
        self.assertIsNotNone(game.winner)
        a, _ = stats.player_stats(game)
        self.assertEqual(a["rounds"], 6)
        self.assertEqual(a["points"], 301)

    def test_every_mode_gives_consistent_stats(self):
        import random
        rnd = random.Random(3)
        for mode in g.MODES:
            game = mode.make(["A", "B", "C"], True)
            for _ in range(70):
                if game.winner is not None:
                    break
                game.throw(rnd.choice((1, 2, 3)), rnd.choice([0, 25] + list(range(1, 21))))
            rows = stats.player_stats(game)
            self.assertEqual(len(rows), 3, mode.name)
            for r in rows:
                self.assertGreaterEqual(r["darts"], 0)
                self.assertGreaterEqual(r["best"], 0)
            for _, darts, total in stats.recent(game, 5):
                self.assertTrue(darts and isinstance(total, int), mode.name)


class CheckoutRouteTests(unittest.TestCase):
    def names(self, left, k, dbl):
        return [[g.label(*d) for d in route] for route in g.checkout_routes(left, k, dbl)]

    def test_classic_finishes(self):
        self.assertEqual(self.names(170, 3, True)[0], ["T20", "T20", "Bull"])
        self.assertEqual(self.names(40, 1, True), [["D20"]])
        self.assertEqual(self.names(50, 1, True), [["Bull"]])
        self.assertEqual(self.names(61, 2, True)[0][-1][0], "D")
        routes = g.checkout_routes(147, 3, True)
        self.assertTrue(routes and all(len(r) == 3 and sum(m * n for m, n in r) == 147 for r in routes))

    def test_double_out_always_ends_on_a_double(self):
        for left in range(2, 171):
            for route in g.checkout_routes(left, 3, True):
                self.assertEqual(route[-1][0], 2, (left, route))
                self.assertEqual(sum(m * n for m, n in route), left)

    def test_straight_out_may_finish_on_anything(self):
        self.assertEqual(self.names(19, 1, False), [["19"]])             # páratlan szám: sima mező is jó
        self.assertEqual(self.names(60, 1, False), [["T20"]])
        self.assertEqual(self.names(20, 1, False), [["D10"]])            # több lehetőségnél a dupla/tripla az elsődleges

    def test_impossible_finishes_are_empty(self):
        self.assertEqual(g.checkout_routes(1, 3, True), [])
        self.assertEqual(g.checkout_routes(0, 3, True), [])
        self.assertEqual(g.checkout_routes(171, 3, True), [])
        self.assertEqual(g.checkout_routes(159, 3, True), [])           # a klasszikus bogey szám
        self.assertEqual(g.checkout_routes(100, 1, True), [])           # egy nyílból nem megy

    def test_fewest_darts_first_and_limit(self):
        routes = g.checkout_routes(100, 3, True)
        self.assertLessEqual(len(routes), 3)
        self.assertEqual(len({len(r) for r in routes}), 1)              # csak a legkevesebb nyilas útvonalak
        self.assertEqual(self.names(40, 3, True), [["D20"]])             # egy nyíl elég: nem ajánl hosszabbat
        self.assertEqual(len(g.checkout_routes(100, 3, True, limit=1)), 1)

    def test_text_wrapper(self):
        self.assertEqual(g.checkout(170, 3, True)[0], "T20 → T20 → Bull")


if __name__ == "__main__":
    unittest.main()
