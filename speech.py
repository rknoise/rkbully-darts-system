"""Pontszám-felolvasás: magyar számnevek, a felolvasott mondatok (felülettől független) és a hangmotorok.

A felolvasás a játék állapotából következik, mint a hangeffektek: a kör végén (és a győzelemnél) szól, a kör közbeni
nyilaknál nem. Hangmotor: a Qt beépített TTS-e (Windowson a rendszer hangja), ennek hiányában a Windows PowerShell
System.Speech-je; ha egyik sincs, a program csendben megy tovább."""
import subprocess
import sys

import stats

ONES = ["", "egy", "kettő", "három", "négy", "öt", "hat", "hét", "nyolc", "kilenc"]
TEENS = {10: "tíz", 20: "húsz"}
TENS_PREFIX = {1: "tizen", 2: "huszon"}
TENS = {3: "harminc", 4: "negyven", 5: "ötven", 6: "hatvan", 7: "hetven", 8: "nyolcvan", 9: "kilencven"}
HEADLESS = ("offscreen", "minimal")


def hu_number(n):
    """Egész szám magyarul kimondva (0–9999; negatívnál „mínusz”). Pl. 180 -> „száznyolcvan”, 22 -> „huszonkettő”."""
    n = int(n)
    if n < 0:
        return "mínusz " + hu_number(-n)
    if n == 0:
        return "nulla"
    return _below_10000(n)


def _below_100(n):
    if n < 10:
        return ONES[n]
    if n in TEENS:
        return TEENS[n]
    if n < 30:
        return TENS_PREFIX[n // 10] + ONES[n % 10]
    return TENS[n // 10] + ONES[n % 10]


def _below_1000(n):
    h, rest = divmod(n, 100)
    head = "" if h == 0 else ("száz" if h == 1 else ("két" if h == 2 else ONES[h]) + "száz")
    return head + _below_100(rest)


def _below_10000(n):
    t, rest = divmod(n, 1000)
    head = "" if t == 0 else ("ezer" if t == 1 else ("két" if t == 2 else ONES[t]) + "ezer")
    return head + _below_1000(rest)


def digits_or_words(n, hungarian):
    """Magyar hang esetén szavakkal, más nyelvű hangnál számjegyekkel (a hang a saját nyelvén olvassa)."""
    return hu_number(n) if hungarian else str(int(n))


def announcement(game, hungarian=True):
    """Mit olvasson fel a program a legutóbbi dobás után (None = semmit). Csak lezárt körnél vagy győzelemnél szól."""
    w = game.winner
    if w is None and game.darts:
        return None
    num = lambda n: digits_or_words(n, hungarian)                       # noqa: E731
    if w is not None:
        if game.tied and len(game.tied) > 1:
            return "Döntetlen: " + ", ".join(game.names[i] for i in game.tied) + "."
        return f"Játék! {game.names[w]} nyerte a meccset."
    if hasattr(game, "thrown") and hasattr(game, "left"):               # X01
        rounds = stats.x01_rounds(game)
        if not rounds:
            return None
        last = rounds[-1]
        name = game.names[last["p"]]
        if last["bust"]:
            return f"{name}, túldobta."
        left = game.left[last["p"]]
        return f"{name}: {num(last['scored'])} pont. Hátra: {num(left)}."
    log = stats.round_log(game)
    if not log:
        return None
    p, darts = log[-1]
    return f"{game.names[p]}: {num(stats.points(darts))} pont."


# ───────────── hangmotorok ─────────────
class NullEngine:
    name = "nincs"
    hungarian = False

    def say(self, text):
        return False

    def stop(self):
        pass


class RecordingEngine(NullEngine):
    """Tesztekhez: elteszi, mit kellett volna felolvasnia."""
    name = "teszt"

    def __init__(self, hungarian=True):
        self.hungarian, self.said = hungarian, []

    def say(self, text):
        self.said.append(text)
        return True


class QtEngine(NullEngine):
    name = "Qt"

    def __init__(self):
        from PySide6.QtCore import QLocale
        from PySide6.QtTextToSpeech import QTextToSpeech
        self.tts = QTextToSpeech()
        self.hungarian = False
        for voice in self.tts.availableVoices():
            if voice.locale().language() == QLocale.Hungarian:
                self.tts.setVoice(voice)
                self.hungarian = True
                break
        if not self.tts.availableVoices():
            raise RuntimeError("nincs hang")

    def say(self, text):
        self.tts.stop()                                  # egy elavult felolvasás ne torlódjon a következőre
        self.tts.say(text)
        return True

    def stop(self):
        self.tts.stop()


PS_SCRIPT = (
    "Add-Type -AssemblyName System.Speech;"
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "$hu = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'hu*' } | Select-Object -First 1;"
    "if ($hu) { $s.SelectVoice($hu.VoiceInfo.Name) };"
    "$s.Speak($env:RKBULLY_SAY)"
)


class PowerShellEngine(NullEngine):
    """Windows: a beépített System.Speech. A magyar hang meglétét induláskor egyszer kérdezi le."""
    name = "Windows"

    def __init__(self, hungarian=None):
        self.proc = None
        self.hungarian = self.has_hungarian() if hungarian is None else hungarian

    @staticmethod
    def has_hungarian():
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Add-Type -AssemblyName System.Speech;"
                 "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | "
                 "ForEach-Object { $_.VoiceInfo.Culture.Name }"],
                capture_output=True, text=True, timeout=15, creationflags=0x08000000).stdout
            return any(line.strip().lower().startswith("hu") for line in out.splitlines())
        except Exception:
            return False

    def say(self, text):
        self.stop()
        try:
            import os
            env = dict(os.environ, RKBULLY_SAY=text)
            self.proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", PS_SCRIPT], env=env,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
            return True
        except Exception:
            return False

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()


def make_engine():
    """A legjobb elérhető hangmotor; képernyő nélküli környezetben (tesztek) és hang nélkül a NullEngine."""
    try:
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtGui import QGuiApplication
        if QCoreApplication.instance() is None or QGuiApplication.platformName() in HEADLESS:
            return NullEngine()
        try:
            return QtEngine()
        except Exception:
            pass
    except Exception:
        pass
    if sys.platform == "win32":
        return PowerShellEngine()
    return NullEngine()


class Announcer:
    """Felolvasó: be/ki kapcsolható; a hangmotor lustán, az első használatkor jön létre (az indulást nem lassítja)."""

    def __init__(self, enabled=True, engine=None):
        self.enabled = bool(enabled)
        self._engine = engine
        self.said = []

    @property
    def engine(self):
        if self._engine is None:
            self._engine = make_engine()
        return self._engine

    def speak_for(self, game, force=False):
        """A játék állapota alapján felolvas valamit, ha kell. Visszaad: a felolvasott szöveg vagy None."""
        if not self.enabled and not force:
            return None
        text = announcement(game, self.engine.hungarian)
        return self.say(text, force) if text else None

    def say(self, text, force=False):
        if not text or (not self.enabled and not force):
            return None
        self.said = (self.said + [text])[-20:]
        self.engine.say(text)
        return text

    def sample(self):
        """A beállítások „Próba” gombja."""
        e = self.engine
        return self.say(f"Teszt: {digits_or_words(180, e.hungarian)} pont. Hátra: {digits_or_words(321, e.hungarian)}.", True)

