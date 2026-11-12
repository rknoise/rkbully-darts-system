"""Az új játékmódok szabályai + a minden módon végigfutó véletlen-dobásos próba."""
import random
import unittest

import games as g

MISS = (0, 0)
D = lambda n: (2, n)
T = lambda n: (3, n)
S = lambda n: (1, n)


def throw_all(game, darts):
    for m, n in darts:
        game.throw(m, n)


def turn(game, darts):
    """Egy teljes kör: a hiányzó dobásokat mellével tölti ki (a kör végéig)."""
    start = (game.cur, game.round)
    for d in darts + [MISS] * 3:
        if (game.cur, game.round) != start or game.winner is not None:
            break
        game.throw(*d)


class KillerTests(unittest.TestCase):
    def test_pick_phase_one_dart_each_and_duplicates_rejected(self):
        game = g.Killer(["A", "B", "C"])
        self.assertEqual(game.turn_darts(), 1)
        game.throw(1, 7)
        self.assertEqual(game.num, [7, None, None])
        self.assertEqual(game.cur, 1)
        game.throw(1, 7)                                   # foglalt: B nem kap számot, jön C
        self.assertEqual(game.num, [7, None, None])
        self.assertEqual(game.cur, 2)
        game.throw(0, 0)                                   # mellé: C sem
        self.assertEqual(game.cur, 1)                      # A-nak már van száma, kimarad: újra B jön
        game.throw(3, 12)                                  # tripla is érvényes számválasztás
        game.throw(1, 25)                                  # Bull nem választható
        self.assertEqual(game.num, [7, 12, None])
        self.assertTrue(game.picking)
        game.throw(1, 1)
        self.assertEqual(game.num, [7, 12, 1])
        self.assertFalse(game.picking)
        self.assertEqual(game.turn_darts(), 3)

    def make(self, picks=(7, 12, 1), names=("A", "B", "C")):
        game = g.Killer(list(names))
        for n in picks:
            game.throw(1, n)
        return game

    def test_become_killer_only_with_own_double(self):
        game = self.make()
        self.assertEqual(game.cur, 0)                      # a számválasztás után újra A jön
        throw_all(game, [S(7), T(7), D(12)])               # nem a saját dupla: nem lett Gyilkos, mások életét sem vehette el
        self.assertEqual(game.killer, [False, False, False])
        self.assertEqual(game.lives, [3, 3, 3])
        turn(game, [D(7)])
        self.assertEqual(game.killer[0], False)            # ez B köre volt
        turn(game, [])
        turn(game, [D(7)])
        self.assertTrue(game.killer[0])

    def test_killer_takes_lives_and_wins(self):
        game = self.make(names=("A", "B"), picks=(7, 12))
        turn(game, [D(7)])                                 # A gyilkos
        turn(game, [])
        turn(game, [D(12), D(12), D(12)])                  # A: 3 élet B-től
        self.assertEqual(game.lives, [3, 0])
        self.assertEqual(game.winner, 0)

    def test_non_killer_cannot_hurt_others_but_can_be_hurt(self):
        game = self.make(names=("A", "B", "C"))
        turn(game, [D(12)])                                # A nem gyilkos: a B duplája nem számít
        self.assertEqual(game.lives[1], 3)
        turn(game, [D(7)])                                 # B gyilkos lett? nem: B száma 12, D7 az A-é
        self.assertEqual(game.lives[0], 3)
        turn(game, [D(1)])                                 # C gyilkos
        turn(game, [])
        turn(game, [])
        turn(game, [D(7)])                                 # C kiüti az A egyik életét
        self.assertEqual(game.lives[0], 2)

    def test_killing_yourself_ends_your_turn(self):
        game = self.make(picks=(7, 12, 1))
        game.lives[0] = 1
        game.killer[0] = True
        game.throw(2, 7)                                   # a saját duplád az utolsó életed: kiestél
        self.assertEqual(game.lives[0], 0)
        self.assertEqual(game.cur, 1)                      # a kör azonnal véget ér, B jön
        self.assertEqual(game.darts, [])
        self.assertIsNone(game.winner)

    def test_own_double_as_killer_costs_a_life(self):
        game = self.make(names=("A", "B"), picks=(7, 12))
        turn(game, [D(7), D(7)])
        self.assertTrue(game.killer[0])
        self.assertEqual(game.lives[0], 2)

    def test_eliminated_player_skipped_and_cannot_be_hit(self):
        game = self.make()
        turn(game, [D(7)])                                 # A gyilkos
        turn(game, []); turn(game, [])
        turn(game, [D(12), D(12), D(12)])                  # B kiesett
        self.assertEqual(game.lives, [3, 0, 3])
        self.assertEqual(game.cur, 2)                      # B kimarad
        turn(game, [])
        self.assertEqual(game.cur, 0)

    def test_undo(self):
        game = self.make(names=("A", "B"), picks=(7, 12))
        turn(game, [D(7), D(12)])                          # D7: Gyilkos, D12: B-től egy élet, majd egy mellé
        self.assertEqual(game.lives, [3, 2])
        game.undo()                                        # a mellé
        game.undo()                                        # a D12
        self.assertEqual(game.lives, [3, 3])
        self.assertTrue(game.killer[0])
        game.undo()                                        # a D7
        self.assertFalse(game.killer[0])
        self.assertEqual(game.cur, 0)


class Bobs27Tests(unittest.TestCase):
    def test_hits_and_misses(self):
        game = g.Bobs27(["A"])
        throw_all(game, [D(1), D(1), MISS])                # +2 +2
        self.assertEqual(game.pts[0], 31)
        throw_all(game, [S(2), MISS, MISS])                # D2 mellé: -4
        self.assertEqual(game.pts[0], 27)
        self.assertEqual(game.round, 3)

    def test_bull_round_is_double_bull(self):
        game = g.Bobs27(["A"])
        game.round = 21
        game.throw(2, 25)
        self.assertEqual(game.pts[0], 77)
        self.assertIn("Bull", game.hint())

    def test_elimination_below_zero_and_skip(self):
        game = g.Bobs27(["A", "B"])
        game.pts = [1, 27]
        throw_all(game, [MISS] * 3)                        # A: -2 -> -1: kiesett
        self.assertTrue(game.out[0])
        self.assertEqual(game.winner, 1)                   # B az egyetlen, aki bent maradt

    def test_zero_survives(self):
        game = g.Bobs27(["A", "B"])
        game.pts = [2, 27]
        throw_all(game, [MISS] * 3)                        # 2 - 2 = 0: még bent
        self.assertFalse(game.out[0])
        self.assertIsNone(game.winner)

    def test_solo_ends_when_eliminated(self):
        game = g.Bobs27(["A"])
        game.pts = [1]
        throw_all(game, [MISS] * 3)
        self.assertEqual(game.winner, 0)

    def test_full_game_highest_wins(self):
        game = g.Bobs27(["A", "B"])
        for r in range(1, 22):
            t = r if r <= 20 else 25
            turn(game, [D(t)])
            turn(game, [D(t), D(t)] if r % 2 == 0 else [])
            if game.winner is not None:
                break
        self.assertIsNotNone(game.winner)


class BaseballTests(unittest.TestCase):
    def test_runs_and_innings(self):
        game = g.Baseball(["A", "B"])
        throw_all(game, [S(1), D(1), T(1)])                # 1+2+3 = 6
        self.assertEqual(game.runs[0], 6)
        throw_all(game, [S(2), MISS, MISS])                # a 2-es nem ér az 1. inningben
        self.assertEqual(game.runs[1], 0)
        self.assertEqual(game.round, 2)

    def test_nine_innings_winner(self):
        game = g.Baseball(["A", "B"])
        for i in range(1, 10):
            turn(game, [T(i)])
            turn(game, [])
        self.assertEqual(game.winner, 0)
        self.assertEqual(game.tied, [0])

    def test_extra_innings_on_tie(self):
        game = g.Baseball(["A", "B"])
        for i in range(1, 10):
            turn(game, [S(i)])
            turn(game, [S(i)])
        self.assertIsNone(game.winner)
        self.assertEqual((game.round, game.rounds), (10, 10))
        self.assertIn("hosszabbítás", game.round_text())
        turn(game, [D(10)])                                # a 10. inning száma a 10-es
        turn(game, [S(10)])
        self.assertEqual(game.winner, 0)


class GolfTests(unittest.TestCase):
    def test_best_dart_counts(self):
        game = g.Golf(["A", "B", "C", "D"])
        turn(game, [S(1), T(1), MISS])                     # tripla: 2
        turn(game, [S(1), D(1), S(1)])                     # dupla: 3
        turn(game, [S(1)])                                 # szimpla: 4 (a 2 mellé 5-öt nem rontja)
        turn(game, [S(5), S(5), S(5)])                     # mind más szám: 5
        self.assertEqual(game.strokes, [2, 3, 4, 5])

    def test_lowest_wins_and_18_holes(self):
        game = g.Golf(["A", "B"])
        for h in range(1, 19):
            turn(game, [T(h)])
            turn(game, [S(h)])
        self.assertEqual(game.winner, 0)
        self.assertEqual(game.strokes, [36, 72])

    def test_tie_goes_to_extra_holes_then_bull(self):
        game = g.Golf(["A", "B"])
        for h in range(1, 19):
            turn(game, [S(h)])
            turn(game, [S(h)])
        self.assertIsNone(game.winner)
        self.assertEqual(game.hole(), 19)
        turn(game, [S(19)]); turn(game, [S(19)])
        self.assertEqual(game.hole(), 20)
        turn(game, [S(20)]); turn(game, [S(20)])
        self.assertEqual(game.hole(), 25)
        turn(game, [(1, 25)])                              # külső Bull: 3
        turn(game, [MISS])                                 # 4
        self.assertEqual(game.winner, 0)

    def test_inner_bull_hole(self):
        game = g.Golf(["A"])
        game.round = 21
        game.base_rounds = 18
        turn(game, [(2, 25), MISS, MISS])
        self.assertEqual(game.strokes[0], 2)


class BermudaTests(unittest.TestCase):
    def test_targets_and_scoring(self):
        game = g.Bermuda(["A"])
        turn(game, [T(12), S(12), S(20)])                  # 36 + 12; a 20 nem a cél
        self.assertEqual(game.pts[0], 48)
        turn(game, [D(13), MISS, MISS])                    # 26
        self.assertEqual(game.pts[0], 74)
        turn(game, [S(14), S(14), S(14)])                  # 42 -> 116
        turn(game, [S(20), D(8), T(9)])                    # bármely dupla: D8 = 16 -> 132
        self.assertEqual(game.pts[0], 132)

    def test_halving_when_all_miss(self):
        game = g.Bermuda(["A"])
        turn(game, [T(12), T(12), T(12)])                  # 108
        turn(game, [MISS, S(1), S(2)])                     # a 13-as mellé: felezés
        self.assertEqual(game.pts[0], 54)
        turn(game, [S(14)])
        turn(game, [S(1), S(2), S(3)])                     # bármely dupla: nincs: felezés
        self.assertEqual(game.pts[0], (54 + 14) // 2)

    def test_odd_total_rounds_down(self):
        game = g.Bermuda(["A"])
        game.pts = [15]
        game.round = 2
        turn(game, [])
        self.assertEqual(game.pts[0], 7)

    def test_triple_and_bull_rounds(self):
        game = g.Bermuda(["A"])
        game.round = 8                                     # bármely tripla
        turn(game, [S(20), T(7), D(20)])
        self.assertEqual(game.pts[0], 21)
        game.round = 12                                    # Bull: külső vagy belső = 25
        turn(game, [(1, 25), (2, 25), S(5)])
        self.assertEqual(game.pts[0], 21 + 50)
        game.round = 13                                    # csak belső Bull, 50
        turn(game, [(1, 25), (2, 25), S(5)])
        self.assertEqual(game.pts[0], 21 + 50 + 50)

    def test_double_bull_counts_as_any_double(self):
        game = g.Bermuda(["A"])
        game.round = 4
        turn(game, [(2, 25)])
        self.assertEqual(game.pts[0], 50)

    def test_thirteen_rounds(self):
        game = g.Bermuda(["A", "B"])
        for _ in range(13):
            turn(game, [S(12)] * 3)
            turn(game, [])
        self.assertIsNotNone(game.winner)


class Checkout121Tests(unittest.TestCase):
    def test_success_moves_up_and_banker(self):
        game = g.Checkout121(["A"])
        throw_all(game, [T(20), S(11), (2, 25)])           # 60 + 11 + 50 = 121
        self.assertEqual(game.best[0], 121)
        self.assertEqual(game.target[0], 122)
        self.assertEqual(game.bank[0], 121)                # 3 nyílból sikerült: banker
        self.assertEqual(game.left[0], 122)

    def test_failure_returns_to_banker_after_three_visits(self):
        game = g.Checkout121(["A"])
        throw_all(game, [T(20), S(11), (2, 25)])           # 121 kész (banker)
        for _ in range(3):
            throw_all(game, [S(1)] * 3)                    # 122: három kör sikertelen
        self.assertEqual(game.target[0], 121)
        self.assertEqual(game.streak[0], 0)
        self.assertEqual(game.tries[0], 2)

    def test_failure_without_banker_goes_back_to_start(self):
        game = g.Checkout121(["A"])
        game.target[0] = game.left[0] = 130
        for _ in range(3):
            throw_all(game, [S(1)] * 3)
        self.assertEqual(game.target[0], 121)

    def test_checkout_in_second_visit_is_not_a_banker(self):
        game = g.Checkout121(["A"])
        throw_all(game, [T(20), S(20), S(20)])             # 21 marad
        throw_all(game, [S(5), D(8), MISS])                # 5 -> 16; D8 -> 0
        self.assertEqual(game.best[0], 121)
        self.assertEqual(game.bank[0], 0)

    def test_bust_costs_the_visit_not_the_task(self):
        game = g.Checkout121(["A"])
        throw_all(game, [T(20), T(20)])                    # 61, majd 1 marad: bust, a kör véget ér
        self.assertEqual(game.left[0], 121)
        self.assertEqual(game.visit[0], 1)
        self.assertEqual(game.target[0], 121)
        self.assertEqual(game.darts, [])

    def test_must_finish_on_double(self):
        game = g.Checkout121(["A"])
        game.target[0] = game.left[0] = 20
        game.throw(1, 20)                                  # nullára, de nem duplával: bust
        self.assertEqual(game.left[0], 20)
        self.assertEqual(game.best[0], 0)
        self.assertEqual(game.visit[0], 1)
        game.throw(2, 10)                                  # dupla: kész
        self.assertEqual(game.best[0], 20)

    def test_stops_after_attempts_and_at_170(self):
        game = g.Checkout121(["A", "B"])
        game.target[0] = game.left[0] = 170
        throw_all(game, [T(20), T(20), (2, 25)])
        self.assertTrue(game.done[0])
        self.assertEqual(game.best[0], 170)
        self.assertEqual(game.cur, 1)                      # A végzett, B jön, és A kimarad
        turn(game, [])
        self.assertEqual(game.cur, 1)

    def test_attempt_limit_ends_the_game(self):
        game = g.Checkout121(["A"])
        for _ in range(game.ATTEMPTS):
            for _ in range(3):
                throw_all(game, [S(1)] * 3)
        self.assertEqual(game.winner, 0)

    def test_players_are_independent_and_highest_wins(self):
        game = g.Checkout121(["A", "B"])
        game.tries = [game.ATTEMPTS - 1] * 2
        throw_all(game, [T(20), S(11), (2, 25)])           # A: 121
        throw_all(game, [S(1)] * 3)
        throw_all(game, [S(1)] * 3)
        throw_all(game, [S(1)] * 3)                        # B: 3 kör, nincs kiszálló
        self.assertEqual(game.best, [121, 0])
        self.assertEqual(game.winner, 0)


class Catch40Tests(unittest.TestCase):
    def test_points_by_darts_used(self):
        game = g.Catch40(["A"])
        throw_all(game, [T(7), D(20)])                     # 61 = 21 + 40: két nyíl: 3 pont
        self.assertEqual(game.pts[0], 3)
        self.assertEqual(game.target[0], 62)
        throw_all(game, [S(10), S(12), D(20)])             # 62 = 10 + 12 + 40: három nyíl: 2 pont
        self.assertEqual(game.pts[0], 5)

    def test_four_to_six_darts_one_point(self):
        game = g.Catch40(["A"])
        game.target[0] = game.left[0] = 63
        throw_all(game, [S(1), S(1), S(1)])                # 60 marad
        throw_all(game, [S(20), D(20)])                    # 20 + 40: ez az 5. nyíl
        self.assertEqual(game.pts[0], 1)

    def test_99_in_three_darts_is_three_points(self):
        game = g.Catch40(["A"])
        game.target[0] = game.left[0] = 99
        throw_all(game, [T(19), S(10), D(16)])             # 57 + 10 + 32
        self.assertEqual(game.pts[0], 3)

    def test_fail_after_two_visits_moves_on(self):
        game = g.Catch40(["A"])
        throw_all(game, [S(1)] * 3)
        throw_all(game, [S(1)] * 3)
        self.assertEqual(game.pts[0], 0)
        self.assertEqual(game.target[0], 62)
        self.assertEqual(game.visit[0], 0)

    def test_all_forty_then_game_ends(self):
        game = g.Catch40(["A"])
        for _ in range(40):
            throw_all(game, [S(1)] * 3)
            throw_all(game, [S(1)] * 3)
        self.assertEqual(game.winner, 0)
        self.assertEqual(game.target[0], 100)


class SimpleDrillTests(unittest.TestCase):
    def test_doubles(self):
        game = g.Doubles(["A"])
        throw_all(game, [D(1), D(1), S(1)])
        throw_all(game, [D(2), D(3), MISS])                # a D3 nem a cél
        self.assertEqual(game.pts[0], 3)
        self.assertEqual(game.round, 3)

    def test_doubles_end_with_bull(self):
        game = g.Doubles(["A"])
        game.round = 21
        throw_all(game, [(2, 25), (1, 25), MISS])
        self.assertEqual(game.pts[0], 1)
        self.assertEqual(game.winner, 0)

    def test_bull_practice(self):
        game = g.BullPractice(["A", "B"])
        throw_all(game, [(2, 25), (1, 25), S(20)])
        self.assertEqual(game.pts[0], 3)

    def test_hundred_darts_exactly(self):
        game = g.Hundred(["A"])
        n = 0
        while game.winner is None:
            game.throw(*T(20))
            n += 1
        self.assertEqual(n, 100)
        self.assertEqual(game.pts[0], 6000)
        self.assertEqual(game.thrown[0], 100)

    def test_hundred_last_turn_is_one_dart(self):
        game = g.Hundred(["A", "B"])
        self.assertEqual(game.turn_darts(), 3)
        game.round = 34
        self.assertEqual(game.turn_darts(), 1)

    def test_scoring_goal_and_tiebreak(self):
        game = g.Scoring(["A", "B"], 99)
        throw_all(game, [T(20), T(19), S(5)])              # 122: sikeres
        throw_all(game, [T(20), T(19), MISS])              # 117: sikeres, kevesebb összpont
        throw_all(game, [T(20), MISS, MISS])               # A: 60, nem sikeres
        self.assertEqual(game.ok, [1, 1])
        self.assertGreater(game.value(0), game.value(1))
        for _ in range(10):
            turn(game, [])
            turn(game, [])
        self.assertEqual(game.winner, 0)
        self.assertEqual(game.tied, [0])

    def test_scoring_121_threshold(self):
        game = g.Scoring(["A"], 121)
        throw_all(game, [T(20), T(20), S(1)])              # 121
        self.assertEqual(game.ok[0], 1)
        throw_all(game, [T(20), T(20), MISS])              # 120
        self.assertEqual(game.ok[0], 1)
        self.assertEqual(game.title, "SCORING 121")


class A1Tests(unittest.TestCase):
    def test_two_hits_give_a_mark_one_does_not(self):
        game = g.A1(["A"])
        self.assertEqual(game.current(0), 20)
        throw_all(game, [S(20), T(20), MISS])
        self.assertEqual(game.marks[0][20], 1)
        self.assertEqual(game.current(0), 19)
        throw_all(game, [S(19), MISS, MISS])
        self.assertEqual(game.marks[0][19], 0)
        self.assertEqual(game.current(0), 18)

    def test_closed_numbers_are_skipped_and_game_ends(self):
        game = g.A1(["A"])
        guard = 0
        while game.winner is None and guard < 200:
            t = game.current(0)
            throw_all(game, [(1, t), (1, t), (1, t)])
            guard += 1
        self.assertEqual(game.winner, 0)
        self.assertEqual(game.visits[0], 45)               # 9 szám × 5 jelzés
        self.assertTrue(all(v == 5 for v in game.marks[0].values()))

    def test_bull_is_a_target(self):
        game = g.A1(["A"])
        game.pos[0] = 6                                    # a 14 után a 13, majd Bull
        self.assertEqual(game.current(0), 13)
        game.pos[0] = 7
        self.assertEqual(game.current(0), 25)
        throw_all(game, [(1, 25), (2, 25), MISS])
        self.assertEqual(game.marks[0][25], 1)

    def test_fewer_visits_wins_and_finished_player_is_skipped(self):
        game = g.A1(["A", "B"])
        game.marks[0] = {t: 5 for t in game.TARGETS}
        game.marks[0][20] = 4
        game.marks[1] = {t: 5 for t in game.TARGETS}
        game.marks[1][20] = 4
        game.visits = [10, 11]
        throw_all(game, [S(20)] * 3)                       # A kész
        self.assertTrue(game.done[0])
        throw_all(game, [MISS] * 3)                        # B nem sikerült, A kimarad
        self.assertEqual(game.cur, 1)
        throw_all(game, [S(20)] * 3)
        self.assertEqual(game.winner, 0)                   # A: 11 kör, B: 13 kör


class ModeInfoTests(unittest.TestCase):
    def test_every_mode_has_rules_and_player_text(self):
        ids = set()
        for m in g.MODES:
            self.assertNotIn(m.id, ids)
            ids.add(m.id)
            self.assertIn(m.group, g.GROUPS, m.name)
            self.assertTrue(m.desc, m.name)
            self.assertGreaterEqual(len(m.rules), 3, m.name)
            for head, body in m.rules:
                self.assertTrue(head and body, m.name)
            self.assertTrue(1 <= m.min_players <= m.max_players <= 8, m.name)
            self.assertRegex(m.players_text(), r"\d")

    def test_player_counts(self):
        by = {m.id: m for m in g.MODES}
        self.assertEqual(by["killer"].players_text(), "2–8 játékos")
        self.assertEqual(by["cricket"].min_players, 2)
        self.assertEqual(by["a1"].min_players, 1)
        self.assertIn("egyedül", by["501"].players_text())

    def test_legacy_mode_order_is_kept(self):
        self.assertEqual([m.name for m in g.MODES[:7]],
                         ["301", "501", "701", "Cricket", "Around the Clock", "Shanghai", "High Score"])

    def test_minimum_players_are_really_needed(self):
        for m in g.MODES:
            if m.min_players > 1:
                game = m.make(["Egyedül"], True)           # nem szabad kivételt dobnia akkor sem, ha a felület engedné
                game.throw(1, 20)


class SkipAndTurnTests(unittest.TestCase):
    def test_apply_round_stops_when_turn_ends(self):
        game = g.Killer(["A", "B"])
        g.apply_round(game, [(1, 7), (1, 12), (1, 3)])     # a számválasztás 1 nyilas: a többi nem kerülhet B-hez
        self.assertEqual(game.num, [7, None])
        self.assertEqual(game.cur, 1)

    def test_all_players_done_finishes_game(self):
        game = g.A1(["A", "B"])
        game.done = [True, False]
        game.cur = 1
        game.marks[1] = {t: 5 for t in game.TARGETS}
        game.marks[1][20] = 4
        throw_all(game, [S(20)] * 3)
        self.assertIsNotNone(game.winner)


class FuzzTests(unittest.TestCase):
    """Véletlen dobások minden módon: nincs kivétel, a lépés mindig halad, és a visszavonás pontosan visszaállít."""
    DARTS = [(0, 0)] + [(m, n) for m in (1, 2, 3) for n in range(1, 21)] + [(1, 25), (2, 25)]

    def test_random_play_and_full_undo(self):
        for mode in g.MODES:
            for players in (1, 2, 5, 8):
                if players < mode.min_players:
                    continue
                for seed in range(2):
                    rnd = random.Random(f"{mode.id}-{players}-{seed}")
                    game = mode.make([f"P{i}" for i in range(players)], seed % 2 == 0)
                    first = game.snap()
                    count = 0
                    while game.winner is None and count < 1500:
                        # a kiszálló módokban néha érdemes pontosan célozni, hogy a sikerek ágát is bejárjuk
                        if hasattr(game, "left") and rnd.random() < 0.4:
                            left = game.left[game.cur] if isinstance(game.left, list) else game.left
                            fin = g.FIN_D.get(left)
                            dart = fin if fin else rnd.choice(self.DARTS)
                        elif hasattr(game, "current") and rnd.random() < 0.5 and not getattr(game, "done", [False] * 9)[game.cur]:
                            dart = (rnd.choice((1, 2, 3)), game.current(game.cur))
                        else:
                            dart = rnd.choice(self.DARTS)
                        game.throw(*dart)
                        count += 1
                        self.assertTrue(0 <= game.cur < game.n, mode.id)
                        self.assertLessEqual(len(game.darts), 3, mode.id)
                        if game.winner is None:
                            self.assertFalse(game.skip(game.cur), f"{mode.id}: kimaradó játékos kerül sorra")
                    for _ in range(count):
                        game.undo()
                    self.assertEqual(game.snap(), first, f"{mode.id} {players} játékos: a visszavonás nem állít vissza mindent")

    def test_every_mode_can_finish(self):
        """Szándékosan gyenge játékosokkal is véget ér minden korlátos játék."""
        for mode in g.MODES:
            game = mode.make(["A", "B"], True)
            n = 0
            while game.winner is None and n < 20000:
                game.throw(0, 0)
                n += 1
            if mode.id in {"301", "501", "701", "cricket", "clock", "killer", "a1"}:
                continue                                    # ezek csak találatokkal érnek véget (nem is kell másképp)
            self.assertIsNotNone(game.winner, mode.id)


if __name__ == "__main__":
    unittest.main()
