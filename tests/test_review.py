import unittest

import games as g
import review as r
import vision as v


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def thr(m, n, uncertain=False):
    return v.Throw(m, n, 0.0, 0.0, 10.0, 0.9, uncertain)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.rv = r.RoundReview(countdown=60, clock=self.clock)

    def fill3(self, uncertain_second=False):
        self.rv.add_detected(thr(3, 20))
        self.rv.add_detected(thr(1, 5, uncertain_second))
        self.rv.add_detected(thr(2, 16))

    def test_countdown_starts_with_third_dart(self):
        self.rv.add_detected(thr(3, 20))
        self.rv.add_detected(thr(1, 5))
        self.assertIsNone(self.rv.seconds_left())
        self.rv.add_detected(thr(2, 16))
        self.assertEqual(self.rv.seconds_left(), 60)
        self.assertEqual(self.rv.text(), "T20 + S5 + D16 = 97")

    def test_auto_accept_when_certain(self):
        self.fill3()
        self.clock.t += 59
        self.assertFalse(self.rv.due())
        self.clock.t += 2
        self.assertTrue(self.rv.due())
        self.assertEqual(self.rv.accept(), [(3, 20), (1, 5), (2, 16)])
        self.assertFalse(self.rv.active)

    def test_uncertain_waits_for_user(self):
        self.fill3(uncertain_second=True)
        self.clock.t += 120
        self.assertEqual(self.rv.seconds_left(), 0)
        self.assertFalse(self.rv.due())
        self.assertTrue(self.rv.needs_manual())
        self.rv.edit(1, 1, 5)                       # a játékos megerősítette (ugyanazt írta be)
        self.assertFalse(self.rv.needs_manual())
        self.assertGreaterEqual(self.rv.seconds_left(), 19)   # javítás után marad idő
        self.clock.t += 21
        self.assertTrue(self.rv.due())

    def test_manual_only_mode(self):
        rv = r.RoundReview(auto=False, clock=self.clock)
        for t in (thr(1, 1), thr(1, 2), thr(1, 3)):
            rv.add_detected(t)
        self.clock.t += 500
        self.assertFalse(rv.due())

    def test_select_and_edit_marks_original(self):
        self.fill3()
        self.rv.select(2)
        self.assertEqual(self.rv.selected, 2)
        self.rv.edit(2, 3, 16)
        self.assertEqual((self.rv.items[2].mult, self.rv.items[2].num), (3, 16))
        self.assertEqual(self.rv.items[2].orig, (2, 16))
        self.assertTrue(self.rv.items[2].edited)
        self.assertIsNone(self.rv.selected)
        self.rv.select(0)
        self.rv.select(0)                           # újabb koppintás: kijelölés megszűnik
        self.assertIsNone(self.rv.selected)

    def test_manual_darts_fill_the_round_but_full_round_rejects_more(self):
        self.rv.add_detected(thr(3, 20))
        self.assertTrue(self.rv.add_manual(0, 0))   # a kamera által nem látott mellé
        self.assertTrue(self.rv.add_manual(1, 1))
        self.assertTrue(self.rv.full)
        self.assertFalse(self.rv.add_manual(1, 2))

    def test_removed_with_fewer_than_three_fills_misses(self):
        self.rv.add_detected(thr(3, 20))
        self.rv.add_detected(thr(1, 5))
        self.assertTrue(self.rv.on_removed())
        self.assertEqual(len(self.rv.items), 3)
        self.assertEqual((self.rv.items[2].mult, self.rv.items[2].source), (0, "fill"))
        self.assertTrue(self.rv.needs_manual())
        self.assertIsNotNone(self.rv.seconds_left())
        r2 = r.RoundReview(clock=self.clock)
        self.assertFalse(r2.on_removed())           # nincs felismert dobás: nincs mit kitölteni

    def test_next_players_darts_wait_in_queue(self):
        self.fill3()
        self.assertFalse(self.rv.add_detected(thr(1, 20)))      # a következő játékos dobott, a kör még nincs jóváhagyva
        self.assertEqual(len(self.rv.items), 3)
        self.rv.accept()
        self.assertEqual([(i.mult, i.num) for i in self.rv.items], [(1, 20)])
        self.assertIsNone(self.rv.seconds_left())

    def test_discard(self):
        self.fill3()
        self.rv.discard()
        self.assertFalse(self.rv.active)

    def test_undo_last_item_stops_countdown(self):
        self.fill3()
        self.rv.undo()
        self.assertEqual(len(self.rv.items), 2)
        self.assertIsNone(self.rv.seconds_left())
        self.rv.add_manual(0, 0)
        self.assertEqual(self.rv.seconds_left(), 60)
        self.assertEqual(r.show(0, 0), "Mellé")
        self.assertEqual((r.show(2, 25), r.show(1, 25), r.show(3, 1)), ("Bull", "25", "T1"))

    # ── szünet ──
    def test_pause_freezes_the_countdown_and_resume_continues_it(self):
        self.fill3()
        self.clock.t += 20
        self.rv.pause()
        self.assertTrue(self.rv.paused)
        self.assertEqual(self.rv.seconds_left(), 40)
        self.clock.t += 500                         # a szünet alatt nem telik az idő
        self.assertEqual(self.rv.seconds_left(), 40)
        self.assertFalse(self.rv.due())
        self.rv.resume()
        self.assertFalse(self.rv.paused)
        self.assertEqual(self.rv.seconds_left(), 40)
        self.clock.t += 39
        self.assertFalse(self.rv.due())
        self.clock.t += 2
        self.assertTrue(self.rv.due())

    def test_pause_before_the_round_is_full_changes_nothing(self):
        self.rv.add_detected(thr(3, 20))
        self.rv.pause()
        self.clock.t += 100
        self.rv.resume()
        self.assertIsNone(self.rv.seconds_left())
        self.rv.add_detected(thr(1, 5))
        self.rv.add_detected(thr(2, 16))
        self.assertEqual(self.rv.seconds_left(), 60)

    def test_pause_and_resume_are_idempotent(self):
        self.fill3()
        self.rv.resume()                            # szünet nélkül semmit sem csinál
        self.assertEqual(self.rv.seconds_left(), 60)
        self.rv.pause()
        self.clock.t += 10
        self.rv.pause()                             # másodszor sem indul újra a szünet
        self.clock.t += 10
        self.rv.resume()
        self.assertEqual(self.rv.seconds_left(), 60)


class RoundSizeTests(unittest.TestCase):
    """Nem minden kör 3 nyilas (pl. Killer számválasztás, a „100 nyíl” utolsó köre)."""

    def setUp(self):
        self.clock = Clock()
        self.rv = r.RoundReview(countdown=60, clock=self.clock)

    def test_one_dart_round_starts_countdown_immediately(self):
        self.rv.set_size(1)
        self.rv.add_detected(thr(1, 7))
        self.assertTrue(self.rv.full)
        self.assertEqual(self.rv.seconds_left(), 60)
        self.assertEqual(self.rv.accept(), [(1, 7)])

    def test_extra_darts_wait_for_the_next_round(self):
        self.rv.set_size(1)
        self.rv.add_detected(thr(1, 7))
        self.assertFalse(self.rv.add_detected(thr(2, 12)))      # a következő játékos nyila
        self.assertEqual(self.rv.accept(), [(1, 7)])
        self.assertEqual([(i.mult, i.num) for i in self.rv.items], [(2, 12)])   # ez a következő kör 1. nyila
        self.rv.set_size(3)
        self.assertIsNone(self.rv.seconds_left())               # a 3 nyilas kör még nem teljes

    def test_removed_fills_only_up_to_size(self):
        self.rv.set_size(2)
        self.rv.add_detected(thr(1, 7))
        self.assertTrue(self.rv.on_removed())
        self.assertEqual(len(self.rv.items), 2)

    def test_size_change_while_items_waiting(self):
        for t in (thr(1, 1), thr(1, 2), thr(1, 3)):
            self.rv.add_detected(t)
        self.assertIsNotNone(self.rv.seconds_left())
        self.rv.set_size(1)                                     # a játék közli: ez a kör csak 1 nyilas
        self.assertEqual(len(self.rv.items), 1)
        self.assertEqual(len(self.rv.queue), 2)                 # a többi a következő körhöz tartozik
        self.assertEqual(self.rv.seconds_left(), 60)
        self.rv.set_size(3)
        self.assertIsNone(self.rv.seconds_left())


class ApplyRoundTests(unittest.TestCase):
    def test_normal_round(self):
        game = g.X01(["A", "B"], 301, True)
        g.apply_round(game, [(3, 20), (1, 5), (2, 16)])
        self.assertEqual(game.left[0], 301 - 97)
        self.assertEqual(game.cur, 1)

    def test_bust_does_not_leak_into_next_player(self):
        game = g.X01(["A", "B"], 301, True)
        game.left[0] = 50
        g.apply_round(game, [(3, 20), (1, 5), (2, 16)])         # az első dobás bust
        self.assertEqual(game.left[0], 50)
        self.assertEqual((game.cur, game.left[1]), (1, 301))    # B pontja érintetlen

    def test_win_stops_round(self):
        game = g.X01(["A", "B"], 301, True)
        game.left[0] = 40
        g.apply_round(game, [(2, 20), (3, 20), (3, 20)])
        self.assertEqual(game.winner, 0)


if __name__ == "__main__":
    unittest.main()
