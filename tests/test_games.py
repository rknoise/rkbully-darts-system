import unittest

import games as g

MISS = (0, 0)


def throw_all(game, darts):
    for m, n in darts:
        game.throw(m, n)


class X01Tests(unittest.TestCase):
    def test_turn_flow_and_score(self):
        game = g.X01(["A", "B"], 301, True)
        throw_all(game, [(3, 20)] * 3)
        self.assertEqual(game.left[0], 121)
        self.assertEqual((game.cur, game.round), (1, 1))
        self.assertEqual(game.prev[0], "A")
        throw_all(game, [MISS] * 3)
        self.assertEqual((game.cur, game.round), (0, 2))

    def test_bust_restores_turn_start_and_ends_turn(self):
        game = g.X01(["A", "B"], 301, True)
        throw_all(game, [(3, 20)] * 3 + [MISS] * 3)      # A: 121
        throw_all(game, [(3, 20), (3, 20)])               # 61, majd 1 -> bust (dupla kiszálló)
        self.assertEqual(game.left[0], 121)
        self.assertEqual(game.cur, 1)

    def test_overshoot_is_bust(self):
        game = g.X01(["A", "B"], 301, True)
        game.left[0] = 30
        throw_all(game, [(3, 20)])
        self.assertEqual(game.left[0], 30)
        self.assertEqual(game.cur, 1)

    def test_must_finish_on_double(self):
        game = g.X01(["A", "B"], 301, True)
        game.left[0] = 20
        game.throw(1, 20)                                  # szimpla 20 -> bust
        self.assertEqual(game.left[0], 20)
        self.assertIsNone(game.winner)
        game2 = g.X01(["A", "B"], 301, True)
        game2.left[0] = 20
        game2.throw(2, 10)
        self.assertEqual(game2.winner, 0)

    def test_finish_with_bull_after_two_darts(self):
        game = g.X01(["A", "B"], 301, True)
        game.left[0] = 121
        throw_all(game, [(3, 20), (1, 11), (2, 25)])
        self.assertEqual(game.winner, 0)

    def test_straight_out(self):
        game = g.X01(["A", "B"], 301, False)
        game.left[0] = 20
        game.throw(1, 20)
        self.assertEqual(game.winner, 0)

    def test_throws_ignored_after_win(self):
        game = g.X01(["A"], 301, False)
        game.left[0] = 5
        game.throw(1, 5)
        game.throw(3, 20)
        self.assertEqual(game.left[0], 0)

    def test_undo(self):
        game = g.X01(["A", "B"], 301, True)
        game.throw(3, 20)
        game.undo()
        self.assertEqual((game.left[0], game.darts), (301, []))
        throw_all(game, [(3, 20)] * 3)
        self.assertEqual(game.cur, 1)
        game.undo()                                         # vissza a kör közepére
        self.assertEqual((game.cur, len(game.darts), game.left[0]), (0, 2, 181))
        game.undo(); game.undo(); game.undo()               # üres előzménynél nem hibázik
        self.assertEqual(game.left[0], 301)

    def test_average(self):
        game = g.X01(["A", "B"], 501, True)
        throw_all(game, [(3, 20)] * 3)
        self.assertIn("180.0", game.stats(0))

    def test_checkout_hints(self):
        self.assertEqual(g.checkout(170, 3, True), ["T20 → T20 → Bull"])
        self.assertEqual(g.checkout(40, 3, True), ["D20"])
        self.assertEqual(g.checkout(100, 2, True)[0], "T20 → D20")        # a Bull → Bull is érvényes, de nem ez az első javaslat
        self.assertEqual(g.checkout(171, 3, True), [])
        self.assertEqual(g.checkout(3, 1, True), [])
        game = g.X01(["A", "B"], 301, True)
        game.left[0] = 40
        self.assertIn("D20", game.hint())


class CricketTests(unittest.TestCase):
    def test_scoring_only_while_opponent_open(self):
        game = g.Cricket(["A", "B"])
        throw_all(game, [(3, 20), MISS, MISS])             # A lezárta a 20-ast
        throw_all(game, [MISS] * 3)
        game.throw(1, 20)                                  # B még nyitva -> A pontot kap
        self.assertEqual(game.pts[0], 20)
        throw_all(game, [MISS] * 2)
        throw_all(game, [(3, 20), MISS, MISS])             # B is lezárta
        game.throw(1, 20)                                  # már senki sem pontozhat
        self.assertEqual(game.pts[0], 20)

    def test_win_by_closing_everything_with_most_points(self):
        game = g.Cricket(["A", "B"])
        throw_all(game, [(3, 20), (3, 19), (3, 18)] + [MISS] * 3)
        throw_all(game, [(3, 17), (3, 16), (3, 15)] + [MISS] * 3)
        throw_all(game, [(2, 25), (2, 25)])
        self.assertEqual(game.winner, 0)
        self.assertEqual(game.pts[0], 25)


class ClockTests(unittest.TestCase):
    def test_full_round(self):
        game = g.Clock(["A"])
        game.throw(1, 5)                                   # nem a soron következő
        self.assertEqual(game.pos[0], 1)
        for n in range(1, 21):
            game.throw(1, n)
        self.assertEqual(game.score(0), "Bull")
        game.throw(2, 25)
        self.assertEqual(game.winner, 0)
        self.assertEqual(game.score(0), "✔")


class ShanghaiTests(unittest.TestCase):
    def test_instant_win(self):
        game = g.Shanghai(["A", "B"])
        throw_all(game, [(1, 1), (2, 1), (3, 1)])
        self.assertEqual(game.winner, 0)

    def test_win_on_points_after_seven_rounds(self):
        game = g.Shanghai(["A", "B"])
        for rnd in range(1, 8):
            throw_all(game, [(1, rnd), MISS, MISS] + [MISS] * 3)
        self.assertEqual(game.winner, 0)
        self.assertEqual(game.pts[0], sum(range(1, 8)))


class HighScoreTests(unittest.TestCase):
    def test_ten_rounds(self):
        game = g.HighScore(["A", "B"])
        for _ in range(10):
            throw_all(game, [(3, 20)] * 3 + [(1, 1)] * 3)
        self.assertEqual(game.winner, 0)
        self.assertEqual(game.pts, [1800, 30])


class HelperTests(unittest.TestCase):
    def test_label(self):
        self.assertEqual(g.label(3, 20), "T20")
        self.assertEqual(g.label(2, 25), "Bull")
        self.assertEqual(g.label(1, 25), "25")
        self.assertEqual(g.label(0, 0), "–")

    def test_all_modes_start(self):
        for mode in g.MODES:
            game = mode.make(["A", "B", "C"], True)
            game.throw(1, 20)
            self.assertEqual(game.n, 3, mode.name)

    def test_tie_is_a_draw_not_a_silent_win(self):
        game = g.HighScore(["A", "B"])
        for _ in range(10):
            throw_all(game, [(1, 20)] * 3 + [(1, 20)] * 3)
        self.assertEqual(game.tied, [0, 1])
        self.assertEqual(game.winner, 0)


if __name__ == "__main__":
    unittest.main()
