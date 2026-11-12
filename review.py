"""A kamerával felismert, még el nem fogadott kör: összegyűjtés, javítás, visszaszámlálás, jóváhagyás.

A felismert dobások nem kerülnek azonnal a játékba. Amikor megvan a 3 nyíl, elindul egy visszaszámlálás;
a játékos jóváhagyhatja a kört, vagy kijelölheti és átírhatja bármelyik nyilat. A felülettől független, tesztelhető.
"""
import time
from dataclasses import dataclass


@dataclass
class Item:
    mult: int
    num: int
    uncertain: bool = False      # a program nem biztos benne: kézi jóváhagyás kell
    source: str = "cam"          # cam = kamera, man = kézzel beütött, fill = hiányzó dobás (mellé)
    orig: tuple = None           # az eredetileg felismert (szorzó, szám), ha javították
    note: str = ""               # rövid megjegyzés a kamerákról (pl. "2 kamera egyezik", "csak 1 kamera látta")

    @property
    def points(self):
        return self.mult * self.num

    @property
    def edited(self):
        return self.orig is not None


class RoundReview:
    def __init__(self, countdown=60.0, auto=True, min_after_edit=20.0, clock=time.monotonic):
        self.countdown, self.auto, self.min_after_edit, self.clock = countdown, auto, min_after_edit, clock
        self.items, self.queue = [], []     # queue: a következő kör első dobásai, amik a jóváhagyás alatt érkeztek
        self.deadline = None
        self.selected = None
        self.size = 3                       # ennyi nyíl alkot egy kört (a játék dönti el: pl. Killer számválasztás = 1)
        self.paused_at = None               # szünet alatt a visszaszámlálás áll

    def set_size(self, size):
        """A játék közli, hány nyilas a soron következő kör. A felesleges dobások a következő körbe kerülnek."""
        size = max(1, int(size))
        if size == self.size:
            return
        self.size = size
        if len(self.items) > size:
            self.queue = self.items[size:] + self.queue
            self.items = self.items[:size]
            self.selected = None if self.selected is not None and self.selected >= size else self.selected
        if self.full:
            self._start_if_full()
        else:
            self.deadline = None

    # ── állapot ──
    @property
    def active(self):
        return bool(self.items)

    @property
    def full(self):
        return len(self.items) >= self.size

    def total(self):
        return sum(i.points for i in self.items)

    def seconds_left(self):
        now = self.clock() if self.paused_at is None else self.paused_at
        return None if self.deadline is None else max(0.0, self.deadline - now)

    # ── szünet ──
    @property
    def paused(self):
        return self.paused_at is not None

    def pause(self):
        if self.paused_at is None:
            self.paused_at = self.clock()

    def resume(self):
        """A szünet alatt eltelt idővel kitolja a határidőt: a visszaszámlálás ott folytatódik, ahol megállt."""
        if self.paused_at is not None:
            if self.deadline is not None:
                self.deadline += self.clock() - self.paused_at
            self.paused_at = None

    def needs_manual(self):
        """Van olyan dobás, amit a játékosnak kell jóváhagynia."""
        return any(i.uncertain for i in self.items)

    def due(self):
        """Lejárt a visszaszámlálás, és automatikusan elfogadható (nincs bizonytalan dobás)."""
        return bool(self.auto and not self.paused and self.deadline is not None and self.clock() >= self.deadline
                    and not self.needs_manual())

    # ── bemenet ──
    def add_detected(self, throw):
        """Kamera által felismert dobás (vision.Throw). Ha a kör már teljes, a következő körbe várakozik."""
        item = Item(throw.mult, throw.num, throw.uncertain, "cam", note=getattr(throw, "note", ""))
        if self.full:
            if len(self.queue) < 3:
                self.queue.append(item)
            return False
        self.items.append(item)
        self._start_if_full()
        return True

    def add_manual(self, mult, num):
        """Kézzel beütött dobás (pl. a kamera által nem látott "mellé"). Teljes körnél nem fogad el újat."""
        if self.full:
            return False
        self.items.append(Item(mult, num, False, "man"))
        self._start_if_full()
        return True

    def select(self, idx):
        if 0 <= idx < len(self.items):
            self.selected = None if self.selected == idx else idx
            self._touch()

    def edit(self, idx, mult, num):
        it = self.items[idx]
        if it.source == "cam" and it.orig is None and (it.mult, it.num) != (mult, num):
            it.orig = (it.mult, it.num)
        it.mult, it.num, it.uncertain = mult, num, False
        self.selected = None
        self._touch()

    def on_removed(self):
        """A nyilakat kihúzták. Ha kevesebb dobást láttunk, mint a kör nyílszáma, a hiányzókat "mellé"-nek vesszük (megerősítést kérve)."""
        if 0 < len(self.items) < self.size:
            while len(self.items) < self.size:
                self.items.append(Item(0, 0, True, "fill"))
            self._start_if_full()
            return True
        return False

    # ── lezárás ──
    def accept(self):
        """Elfogadja a kört: visszaadja a dobásokat [(szorzó, szám), ...], és a várakozó dobások lesznek az új kör."""
        darts = [(i.mult, i.num) for i in self.items]
        self._next_round()
        return darts

    def discard(self):
        self._next_round()

    def _next_round(self):
        self.items, self.queue = self.queue[:self.size], self.queue[self.size:]
        self.deadline, self.selected = None, None
        self._start_if_full()

    def _start_if_full(self):
        if self.full and self.deadline is None:
            self.deadline = self.clock() + self.countdown

    def _touch(self):
        """Javítás közben ne járjon le az idő: legalább min_after_edit másodperc marad."""
        if self.deadline is not None:
            self.deadline = max(self.deadline, self.clock() + self.min_after_edit)

    def undo(self):
        """Az utolsó még el nem fogadott dobás törlése."""
        if self.items:
            self.items.pop()
            self.selected = None
            if not self.full:
                self.deadline = None

    def text(self):
        return " + ".join(show(i.mult, i.num) + ("?" if i.uncertain else "") for i in self.items) + f" = {self.total()}"


def show(mult, num):
    """Megjelenített név: S5 / D16 / T20 / Bull / 25 / Mellé."""
    if mult == 0:
        return "Mellé"
    if num == 25:
        return "Bull" if mult == 2 else "25"
    return "SDT"[mult - 1] + str(num)
