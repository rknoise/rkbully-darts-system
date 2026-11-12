"""Felület-tesztek: profilok és profilképek, beállítások (fogaskerék), játékos hozzáadása, szünet, statisztika, ablakillesztés."""
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton
    import options
    import rkbully
except Exception:                                       # pragma: no cover
    rkbully = None

import ask
import games as g
import profiles as pf


def make_png(path, w=320, h=200):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor("#e05aff"))
    assert img.save(str(path), "PNG")
    return path


@unittest.skipIf(rkbully is None, "PySide6 nincs telepítve")
class ProfileUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(rkbully.QSS)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._saved = (rkbully.CFG_FILE, pf.AVATAR_DIR, QMessageBox.information, ask.confirm,
                       options.QInputDialog.getText, options.QFileDialog.getOpenFileName)
        rkbully.CFG_FILE = self.tmp / "settings.json"
        pf.AVATAR_DIR = self.tmp / "avatars"
        self.messages = []
        QMessageBox.information = staticmethod(lambda *a, **k: self.messages.append(a))
        self.questions = []
        ask.confirm = lambda parent, title, text, *a, **k: self.questions.append((title, text)) or self.answer
        self.answer = True
        rkbully.CFG_FILE.write_text(json.dumps({"names": ["Robi", "Dani", "Milla", "Petya"]}), encoding="utf-8")
        self.win = rkbully.Main()

    def tearDown(self):
        rkbully.dispose(self.win)
        self.win = None
        (rkbully.CFG_FILE, pf.AVATAR_DIR, QMessageBox.information, ask.confirm,
         options.QInputDialog.getText, options.QFileDialog.getOpenFileName) = self._saved

    def play(self, darts):
        for m, n in darts:
            self.win.mult = m
            self.win.hit(n)

    # ── profilok a főablakban ──
    def test_legacy_names_become_profiles_and_players(self):
        w = self.win
        self.assertEqual(w.names, ["Robi", "Dani", "Milla", "Petya"])
        self.assertEqual([p["name"] for p in w.profiles], w.names)
        self.assertEqual(w.game.names, w.names)
        self.assertEqual(w.profile_at(2)["name"], "Milla")

    def test_settings_are_saved_as_profiles_not_names(self):
        w = self.win
        w.new_game()
        data = json.loads(rkbully.CFG_FILE.read_text(encoding="utf-8"))
        self.assertEqual([p["name"] for p in data["profiles"]], w.names)
        self.assertEqual(data["players"], w.pids)
        self.assertNotIn("names", data)

    def test_profiles_survive_a_restart(self):
        w = self.win
        w.rename_profile(w.pids[0], "Robi bá")
        w.profiles[1]["color"] = pf.COLORS[5]
        w.profiles_changed()
        again = rkbully.Main()
        try:
            self.assertEqual(again.names[0], "Robi bá")
            self.assertEqual(again.profiles[1]["color"], pf.COLORS[5])
            self.assertEqual(again.pids, w.pids)
        finally:
            rkbully.dispose(again)

    def test_rename_updates_the_running_game_and_its_history(self):
        w = self.win
        self.play([(3, 20), (1, 5), (2, 7)])            # Robi köre lezárult, Dani jön
        self.play([(1, 1)])
        w.rename_profile(w.pids[0], "Roberto")
        self.assertEqual(w.names[0], "Roberto")
        self.assertEqual(w.game.names[0], "Roberto")
        self.assertEqual(w.game.prev[0], "Roberto")
        self.assertTrue(all(s["names"][0] == "Roberto" for s in w.game.hist))
        w.undo()
        self.assertEqual(w.game.names[0], "Roberto")    # a visszavonás sem hozza vissza a régi nevet

    def test_the_big_name_and_the_player_list_follow_the_profile(self):
        w = self.win
        w.rename_profile(w.pids[0], "Roberto")
        self.assertIn("Roberto", w.who.text())
        labels = [lb.text() for lb in w.players_card.findChildren(QLabel)]
        self.assertTrue(any("Roberto" in t for t in labels))

    def test_player_list_always_shows_eight_slots(self):
        w = self.win
        slots = [b for b in w.players_card.findChildren(QPushButton) if b.objectName() == "slot"]
        self.assertEqual(len(slots), 4)                 # 4 játékos + 4 üres hely
        self.assertIn("Játékosok (4/8)", w.pcount.text())

    def test_the_active_player_gets_the_badge(self):
        w = self.win
        badges = [lb for lb in w.players_card.findChildren(QLabel) if lb.objectName() == "badge"]
        self.assertEqual(len(badges), 1)

    # ── játékos hozzáadása / kivétele ──
    def test_add_player_dialog_lists_only_profiles_that_are_not_playing(self):
        w = self.win
        extra = pf.make_profile("Zsolt", [p["color"] for p in w.profiles])
        w.profiles.append(extra)
        dlg = options.AddPlayerDialog(w)
        names = [dlg.list.item(i).text() for i in range(dlg.list.count())]
        self.assertEqual(names, ["Zsolt"])
        dlg.accept_pick()
        self.assertEqual(dlg.picked, extra["id"])

    def test_add_player_puts_the_chosen_profile_into_a_new_game(self):
        w = self.win
        extra = pf.make_profile("Zsolt", [p["color"] for p in w.profiles])
        w.profiles.append(extra)

        class Stub:
            picked = extra["id"]

            def __init__(self, main): pass

            def exec(self): return True
        real, options.AddPlayerDialog = options.AddPlayerDialog, Stub
        try:
            self.play([(3, 20)])
            w.add_player()
        finally:
            options.AddPlayerDialog = real
        self.assertEqual(w.names[-1], "Zsolt")
        self.assertEqual(w.game.n, 5)
        self.assertEqual(w.game.darts, [])              # új játék indult
        self.assertEqual(len(w.pids), 5)

    def test_cancelled_add_player_changes_nothing(self):
        w = self.win

        class Stub:
            picked = None

            def __init__(self, main): pass

            def exec(self): return False
        real, options.AddPlayerDialog = options.AddPlayerDialog, Stub
        try:
            w.add_player()
        finally:
            options.AddPlayerDialog = real
        self.assertEqual(w.game.n, 4)

    def test_new_profile_from_the_add_dialog(self):
        w = self.win
        options.QInputDialog.getText = staticmethod(lambda *a, **k: ("Zsolt", True))
        dlg = options.AddPlayerDialog(w)
        dlg.new_profile()
        self.assertTrue(w.profile_by_id(dlg.picked))
        self.assertEqual(w.profile_by_id(dlg.picked)["name"], "Zsolt")
        options.QInputDialog.getText = staticmethod(lambda *a, **k: ("robi", True))     # a név már foglalt (kis/nagybetű nélkül)
        before = len(w.profiles)
        options.AddPlayerDialog(w).new_profile()
        self.assertEqual(len(w.profiles), before)
        self.assertTrue(self.messages)

    def test_no_more_than_eight_players(self):
        w = self.win
        for i in range(6):
            w.profiles.append(pf.make_profile(f"Extra {i}", [p["color"] for p in w.profiles]))
        picks = [p["id"] for p in w.profiles if p["id"] not in w.pids]

        class Stub:
            def __init__(self, main): self.picked = picks.pop(0) if picks else None
            def exec(self): return True
        real, options.AddPlayerDialog = options.AddPlayerDialog, Stub
        try:
            for _ in range(6):
                w.add_player()
        finally:
            options.AddPlayerDialog = real
        self.assertEqual(w.game.n, 8)
        self.assertEqual(len(w.names), 8)
        self.assertEqual(len(w.pids), 8)

    def test_removing_a_player_keeps_the_profile(self):
        w = self.win
        w.del_player()
        self.assertEqual(w.game.n, 3)
        self.assertEqual(len(w.profiles), 4)
        self.assertEqual(len(w.pids), 3)

    # ── beállítások (fogaskerék) ──
    def test_gear_opens_the_options_dialog_with_all_pages(self):
        w = self.win
        dlg = options.OptionsDialog(w)
        self.assertEqual(dlg.nav.count(), 6)
        self.assertEqual(dlg.pages.count(), 6)
        for row in range(dlg.nav.count()):
            dlg.nav.setCurrentRow(row)
            self.assertEqual(dlg.pages.currentIndex(), row)
        self.assertTrue(w.gear.toolTip())
        self.assertEqual(dlg.profiles_page.list.count(), 4)
        self.assertEqual(options.OptionsDialog(w, 2).pages.currentIndex(), 2)

    def test_profile_page_renames_and_rejects_duplicates_and_empty_names(self):
        w = self.win
        page = options.OptionsDialog(w).profiles_page
        page.list.setCurrentRow(1)
        page.name.setText("Dániel")
        page.rename()
        self.assertEqual(w.names[1], "Dániel")
        self.assertEqual(w.game.names[1], "Dániel")
        page.name.setText("ROBI")
        page.rename()
        self.assertEqual(w.names[1], "Dániel")
        self.assertIn("már van", page.msg.text())
        self.assertEqual(page.name.text(), "Dániel")
        page.name.setText("   ")
        page.rename()
        self.assertEqual(w.names[1], "Dániel")
        self.assertIn("üres", page.msg.text())

    def test_profile_page_changes_color_and_persists(self):
        w = self.win
        page = options.OptionsDialog(w).profiles_page
        page.list.setCurrentRow(0)
        page.set_color(pf.COLORS[6])
        self.assertEqual(w.profiles[0]["color"], pf.COLORS[6])
        self.assertEqual(json.loads(rkbully.CFG_FILE.read_text(encoding="utf-8"))["profiles"][0]["color"], pf.COLORS[6])

    def test_profile_page_adds_and_deletes_profiles(self):
        w = self.win
        page = options.OptionsDialog(w).profiles_page
        options.QInputDialog.getText = staticmethod(lambda *a, **k: ("Zsolt", True))
        page.add_profile()
        self.assertEqual(len(w.profiles), 5)
        self.assertEqual(page.profile()["name"], "Zsolt")
        self.assertIn("Nincs a játékban", page.state.text())
        page.delete_profile()                           # nem játszik: törölhető
        self.assertEqual(len(w.profiles), 4)
        page.list.setCurrentRow(0)
        page.delete_profile()                           # játszik: nem törölhető
        self.assertEqual(len(w.profiles), 4)
        self.assertIn("játszik", page.msg.text())

    def test_the_last_profile_cannot_be_deleted(self):
        w = self.win
        while len(w.names) > 1:
            w.del_player()
        w.profiles[:] = [p for p in w.profiles if p["id"] == w.pids[0]] + []
        page = options.OptionsDialog(w).profiles_page
        w.pids.clear()                                  # (nem játszik, de az egyetlen profil)
        page.reload()
        page.delete_profile()
        self.assertEqual(len(w.profiles), 1)
        self.assertIn("Legalább egy", page.msg.text())

    # ── profilkép ──
    def test_uploading_a_picture_sets_the_avatar(self):
        w = self.win
        src = make_png(self.tmp / "foto.png", 640, 400)
        options.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(src), ""))
        page = options.OptionsDialog(w).profiles_page
        page.list.setCurrentRow(0)
        page.choose_image()
        p = w.profiles[0]
        path = pf.avatar_path(p, w.avatar_dir)
        self.assertIsNotNone(path)
        self.assertEqual(path.parent, self.tmp / "avatars")
        self.assertIsNotNone(page.avatar.pm)            # az előnézet is a képet mutatja
        self.assertIsNotNone(w.main_avatar.pm)          # Robi az aktív játékos: a nagy képen is látszik
        self.assertTrue(page.remove_img.isEnabled())

    def test_replacing_a_picture_deletes_the_old_file(self):
        w = self.win
        page = options.OptionsDialog(w).profiles_page
        page.list.setCurrentRow(0)
        files = []
        for i in range(2):
            src = make_png(self.tmp / f"f{i}.png")
            options.QFileDialog.getOpenFileName = staticmethod(lambda *a, s=src, **k: (str(s), ""))
            page.choose_image()
            files.append(pf.avatar_path(w.profiles[0], w.avatar_dir))
        self.assertFalse(files[0].exists())
        self.assertTrue(files[1].exists())
        self.assertEqual(len(list((self.tmp / "avatars").iterdir())), 1)

    def test_removing_a_picture_falls_back_to_the_initial(self):
        w = self.win
        src = make_png(self.tmp / "foto.png")
        options.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(src), ""))
        page = options.OptionsDialog(w).profiles_page
        page.list.setCurrentRow(0)
        page.choose_image()
        page.clear_image()
        self.assertIsNone(w.profiles[0]["avatar"])
        self.assertIsNone(w.main_avatar.pm)
        self.assertFalse(page.remove_img.isEnabled())
        self.assertEqual(list((self.tmp / "avatars").iterdir()), [])

    def test_a_broken_picture_shows_an_error_and_changes_nothing(self):
        w = self.win
        bad = self.tmp / "szoveg.jpg"
        bad.write_text("nem kép", encoding="utf-8")
        options.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(bad), ""))
        page = options.OptionsDialog(w).profiles_page
        page.list.setCurrentRow(0)
        page.choose_image()
        self.assertIsNone(w.profiles[0]["avatar"])
        self.assertIn("nem olvasható", page.msg.text())

    def test_missing_avatar_file_does_not_break_the_screen(self):
        w = self.win
        w.profiles[0]["avatar"] = "eltunt.jpg"
        w.refresh()
        self.assertIsNone(w.main_avatar.pm)

    def test_deleting_a_profile_removes_its_picture_file(self):
        w = self.win
        extra = pf.make_profile("Zsolt", [p["color"] for p in w.profiles])
        extra["avatar"] = pf.import_avatar(make_png(self.tmp / "z.png"), extra["id"], w.avatar_dir)
        w.profiles.append(extra)
        page = options.OptionsDialog(w).profiles_page
        page.reload(extra["id"])
        page.delete_profile()
        self.assertEqual(list((self.tmp / "avatars").iterdir()), [])

    # ── játék-beállítások az options ablakban ──
    def test_approval_and_countdown_settings_are_applied_and_saved(self):
        w = self.win
        dlg = options.OptionsDialog(w, 1)
        page = dlg.pages.widget(1)
        self.assertTrue(w.review.auto)
        page.approval.setCurrentIndex(1)
        self.assertFalse(w.review.auto)
        page.countdown.setValue(25)
        self.assertEqual(w.review.countdown, 25)
        data = json.loads(rkbully.CFG_FILE.read_text(encoding="utf-8"))
        self.assertEqual((data["approval"], data["countdown"]), (1, 25))
        w.new_game()
        self.assertFalse(w.review.auto)                 # az új körök is a beállítást használják
        self.assertEqual(w.review.countdown, 25)

    # ── szünet ──
    def test_pause_blocks_input_and_shows_the_banner(self):
        w = self.win
        w.toggle_pause()
        self.assertTrue(w.paused)
        self.assertIn("SZÜNET", w.banner.text())
        self.assertIn("SZÜNET", w.timer_lbl.text())
        w.hit(20)
        self.assertEqual(w.game.darts, [])
        w.toggle_pause()
        self.assertFalse(w.paused)
        w.hit(20)
        self.assertEqual(len(w.game.darts), 1)

    def test_a_new_game_ends_the_pause(self):
        w = self.win
        w.toggle_pause()
        w.new_game()
        self.assertFalse(w.paused)
        self.assertFalse(w.review.paused)

    # ── statisztika ──
    def test_stats_dialog_has_a_row_per_player(self):
        w = self.win
        self.play([(3, 20), (3, 20), (3, 20)])
        dlg = rkbully.StatsDialog(w, w.game)
        table = dlg.current                                      # a „Folyó játék” oldal táblázata
        self.assertEqual(table.rowCount(), 4)
        self.assertEqual(table.item(0, 0).text(), "Robi")
        self.assertEqual(table.item(0, 4).text(), "180")        # dobott pont
        self.assertEqual(table.item(0, 5).text(), "180")        # legjobb kör

    def test_recent_throws_card_lists_finished_rounds(self):
        w = self.win
        self.assertTrue(any("Még nem" in lb.text() for lb in w.recent_card.findChildren(QLabel)))
        self.play([(3, 20), (1, 5), (2, 7)])
        texts = [lb.text() for lb in w.recent_card.findChildren(QLabel)]
        self.assertIn("Robi", texts)
        self.assertIn("T20", texts)
        self.assertIn("S5", texts)
        self.assertIn("D7", texts)
        self.assertIn("79", texts)               # 60 + 5 + 14

    # ── kiszállási segédlet ──
    def test_checkout_helper_shows_routes_for_x01(self):
        w = self.win
        w.show()
        w.resize(1600, 900)
        w.fit()
        w.set_mode("301")
        for _ in range(4):
            self.play([(3, 20)] * 3)                    # mindenki lejjebb megy: 121 maradt, Robi jön
        self.assertEqual(w.game.left[0], 121)
        self.assertTrue(w.help_card.isVisibleTo(w))
        self.assertIn("nyíllal", w.help_badge.text())
        text = " ".join(lb.text() for lb in w.help_card.findChildren(QLabel))
        self.assertIn("AJÁNLOTT", text)
        self.assertIn("= 121", text)

    def test_checkout_helper_explains_when_there_is_no_finish_yet(self):
        w = self.win
        w.show()
        w.resize(1600, 900)
        w.fit()
        w.set_mode("501")
        self.assertTrue(w.help_card.isVisibleTo(w))
        self.assertEqual(w.help_badge.text(), "")
        text = " ".join(lb.text() for lb in w.help_card.findChildren(QLabel))
        self.assertIn("170", text)

    def test_helper_is_hidden_after_the_win(self):
        w = self.win
        w.set_mode("301")
        w.out.setCurrentIndex(1)                        # Straight Out
        for _ in range(5):
            self.play([(1, 20)] * 3 + [(0, 0)] * 3 + [(0, 0)] * 3 + [(0, 0)] * 3)
        self.play([(1, 1)])
        self.assertIsNotNone(w.game.winner)
        self.assertFalse(w.help_card.isVisibleTo(w))
        self.assertIn("GYŐZTES", w.banner.text())

    # ── ablakillesztés ──
    def test_the_layout_fits_every_common_screen_size(self):
        w = self.win
        w.show()
        for size in ((800, 600), (1280, 680), (1366, 728), (1536, 824), (1600, 900), (1920, 1040), (2560, 1380)):
            w.resize(*size)
            w.fit()
            self.assertTrue(w.fits(), f"{size}: a tartalom nem fér az ablakba (k={w.k:.2f})")
            self.assertGreaterEqual(w.k, 0.55)
            self.assertLessEqual(w.k, 1.6)

    def test_scale_follows_the_window_size(self):
        w = self.win
        w.show()
        w.resize(1280, 720)
        w.fit()
        small = w.k
        w.resize(2400, 1350)
        w.fit()
        self.assertGreater(w.k, small)

    def test_window_never_opens_larger_than_the_screen(self):
        avail = rkbully.QGuiApplication.primaryScreen().availableGeometry()
        self.assertLessEqual(self.win.width(), avail.width())
        self.assertLessEqual(self.win.height(), avail.height())

    def test_manual_pad_collapses_on_small_windows_and_can_be_reopened(self):
        w = self.win
        w.show()
        w.resize(800, 450)
        w.fit()
        self.assertTrue(w.fits())
        self.assertTrue(w.cramped)
        self.assertFalse(w.pad_box.isVisibleTo(w))
        self.assertFalse(w.pad_btn.isChecked())
        w.pad_btn.setChecked(True)                      # kérésre kinyílik, a segédlet átadja a helyét
        self.assertTrue(w.pad_box.isVisibleTo(w))
        w.fit()
        self.assertTrue(w.fits())
        self.assertTrue(w.pad_box.isVisibleTo(w))
        self.assertTrue(json.loads(rkbully.CFG_FILE.read_text(encoding="utf-8")).get("pad", True))   # a mentett beállítás nem változott

    def test_pad_toggle_is_saved_on_a_big_window(self):
        w = self.win
        w.show()
        w.resize(1920, 1040)
        w.fit()
        self.assertTrue(w.pad_box.isVisibleTo(w))
        w.pad_btn.setChecked(False)
        self.assertFalse(w.pad_box.isVisibleTo(w))
        self.assertFalse(json.loads(rkbully.CFG_FILE.read_text(encoding="utf-8"))["pad"])
        again = rkbully.Main()
        try:
            self.assertFalse(again.pad_visible)
        finally:
            rkbully.dispose(again)

    def test_every_mode_still_plays_with_profiles(self):
        w = self.win
        for mode in g.MODES:
            w.set_mode(mode.id)
            self.assertEqual(w.game.names, w.names, mode.name)
            self.assertTrue(w.who.text(), mode.name)


if __name__ == "__main__":
    unittest.main()
