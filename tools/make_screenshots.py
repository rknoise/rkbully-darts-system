"""A README képernyőképeinek elkészítése (képernyő nélkül, offscreen). Futtatás:  python tools/make_screenshots.py

A képek a valódi felületet mutatják szintetikus (generált) játékadatokkal és tesztképpel; a program nem igényel kamerát."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

import rkbully  # noqa: E402
import sounds  # noqa: E402
import speech  # noqa: E402
import trainer_ui  # noqa: E402
import wizard  # noqa: E402
from tests import synth  # noqa: E402

OUT = ROOT / "docs" / "images"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(rkbully.QSS)
    tmp = Path(tempfile.mkdtemp())
    rkbully.CFG_FILE = tmp / "settings.json"
    win = rkbully.Main()
    win.sound.effects = {c: None for c in sounds.CUES}
    win.speaker = speech.Announcer(False)
    win.names = ["RK", "Dani", "Milla"]
    win.set_mode("501")
    win.resize(1912, 1027)
    win.show()
    app.processEvents()
    for m, n in ((3, 20), (3, 20), (2, 20), (1, 19), (3, 19), (1, 5), (2, 16), (3, 18), (1, 1)):
        win.mult = m
        win.hit(n)
    app.processEvents()
    win.grab().save(str(OUT / "foablak.png"))

    quick = rkbully.Main()
    quick.names = ["RK", "Dani"]
    quick.set_mode("301")
    quick.end_force = True
    quick.resize(1000, 760)
    for m, n in ((3, 20), (3, 20), (3, 19), (3, 20), (3, 20), (3, 20), (3, 20), (3, 20), (2, 2)):
        quick.mult = m
        quick.hit(n)
    dlg = rkbully.finish.MatchEndDialog(quick, quick.game, {}, animate=False)
    dlg.burst(160)
    for _ in range(90):
        dlg.step()
    dlg.grab().save(str(OUT / "meccs-vege.png"))
    dlg.deleteLater()
    rkbully.dispose(quick)                                   # a függő meccs végi ablak ne nyíljon meg később

    img = synth.render(640, tilt=0.03, noise=1.0)[0]
    w = wizard.CalibrationWizard(None, [{"label": "Webkamera 0", "text": "0", "get": lambda: img}], tmp / "calibration.json")
    w.resize(1180, 760)
    w.show()
    w.tick()
    w.auto_find()
    for _ in range(4):
        w._last_check = -1.0
        w.tick()
        app.processEvents()
    w.grab().save(str(OUT / "kalibracios-varazslo.png"))
    w.timer.stop()
    w.deleteLater()
    wizard.save_calibration(tmp / "calibration.json", "0", synth.render(640, tilt=0.03)[2], 640)
    state = {"img": synth.render(640, tilt=0.03)[0]}
    clock = [0.0]
    t = trainer_ui.TrainerDialog(None, [{"label": "Webkamera 0", "text": "0", "get": lambda: state["img"]}], tmp / "calibration.json",
                                 tmp / "training", tmp / "models", clock=lambda: clock[0])
    t.resize(1180, 780)
    t.show()
    t.tabs.setCurrentIndex(1)

    def spin(seconds):
        for _ in range(int(seconds / 0.1)):
            clock[0] += 0.1
            t.tick()
        app.processEvents()

    spin(0.3)
    t.empty_btn.click()
    for i, (mm, empty_after) in enumerate((((30, -100), True), ((-60, 40), True), ((70, 90), False))):
        state["img"] = synth.render(640, tilt=0.03, darts_mm=[mm])[0]
        spin(2.5)
        if empty_after:
            t.accept_candidate()
            state["img"] = synth.render(640, tilt=0.03)[0]
            spin(3.0)
    t.grab().save(str(OUT / "betanito.png"))
    t.timer.stop()
    t.deleteLater()
    rkbully.dispose(win)
    print("kész:", ", ".join(sorted(p.name for p in OUT.glob("*.png"))))


if __name__ == "__main__":
    main()
