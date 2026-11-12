"""Hangeffektek: melyik esemény melyik hangot játssza (felülettől független), és a lejátszó.

A hang a játék állapotából következik, nem a gombnyomásból, így a kézi bevitel és a kamerás felismerés ugyanúgy szól.
A visszavonás és az új játék néma."""
from pathlib import Path

import stats

HEADLESS = ("offscreen", "minimal")            # képernyő nélküli Qt platformok (tesztek, szerverek)
CUES = ("dart", "double", "triple", "bull", "next", "ton", "180", "bust", "win")
FILES = {"dart": "dart.wav", "double": "double.wav", "triple": "triple.wav", "bull": "bull.wav", "next": "next.wav",
         "ton": "ton.wav", "180": "oneeighty.wav", "bust": "bust.wav", "win": "win.wav"}
NAMES = {"dart": "🎯  Nyíl a táblán", "double": "✨  Dupla", "triple": "⚡  Tripla", "bull": "🔥  Bull",
         "next": "👉  Következő játékos", "ton": "🔔  100+ kör", "180": "🎆  180", "bust": "💥  Bust", "win": "🏆  Győzelem"}


def dart_cue(mult, num):
    """Egy nyíl hangja: a bull, a tripla és a dupla külön effektet kap, minden más a sima puffanást."""
    if num == 25 and mult == 2:
        return "bull"
    if mult == 3:
        return "triple"
    if mult == 2 and num:
        return "double"
    return "dart"


def cue_for(game):
    """Az utolsó dobás(ok) után melyik hang szóljon (None = egyik sem). A hívó azt garantálja, hogy a játék előrelépett."""
    if game.winner is not None:
        return "win"
    if game.darts:                                    # a kör közben vagyunk: egy nyíl került a táblára
        return dart_cue(*game.darts[-1])
    if hasattr(game, "thrown") and hasattr(game, "left"):              # X01: a ténylegesen levont pont számít
        rounds = stats.x01_rounds(game)
        if not rounds:
            return None
        last = rounds[-1]
        if last["bust"]:
            return "bust"
        scored = last["scored"]
    else:
        log = stats.round_log(game)
        if not log:
            return None
        scored = stats.points(log[-1][1])
    if scored == 180:
        return "180"
    if scored >= 100:
        return "ton"
    last_dart = (stats.round_log(game)[-1][1] or [None])[-1]       # a kör utolsó nyila is lehet dupla, tripla vagy bull
    special = dart_cue(*last_dart) if last_dart else "dart"
    return special if special != "dart" else "next"


class SoundBoard:
    """A hangok betöltése és lejátszása. Hiányzó fájl vagy hanglejátszó nélkül is csendben működik."""

    def __init__(self, folder, enabled=True, volume=0.7):
        self.folder = Path(folder)
        self.enabled = bool(enabled)
        self.volume = min(max(float(volume), 0.0), 1.0)
        self.effects = {}
        self.played = []                              # az utolsó lejátszott hangok (diagnosztika és tesztek)

    def _effect(self, cue):
        if cue in self.effects:
            return self.effects[cue]
        effect = None
        path = self.folder / FILES.get(cue, "")
        if path.is_file():
            try:
                from PySide6.QtCore import QCoreApplication, QUrl
                from PySide6.QtGui import QGuiApplication
                if QCoreApplication.instance() is None or QGuiApplication.platformName() in HEADLESS:
                    return None                       # alkalmazás vagy képernyő nélkül nincs hang (a hangmotor ott összeomolhat)
                from PySide6.QtMultimedia import QSoundEffect
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(str(path)))
                effect.setVolume(self.volume)
            except Exception:
                effect = None                         # nincs QtMultimedia vagy hangeszköz: a játék csendben megy tovább
        self.effects[cue] = effect
        return effect

    def preload(self):
        """Az összes hang betöltése induláskor, hogy az első lejátszás se késsen."""
        for cue in CUES:
            self._effect(cue)

    def set_volume(self, volume):
        self.volume = min(max(float(volume), 0.0), 1.0)
        for effect in self.effects.values():
            if effect is not None:
                effect.setVolume(self.volume)

    def play(self, cue, force=False):
        """Lejátssza a hangot. `force`: a némítástól függetlenül (a beállítások „Próba” gombjához)."""
        if (not self.enabled and not force) or cue not in FILES:
            return False
        self.played = (self.played + [cue])[-20:]
        effect = self._effect(cue)
        if effect is None:
            return False
        try:
            effect.play()
        except Exception:
            return False
        return True
