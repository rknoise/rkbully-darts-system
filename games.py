"""RKBully játékmotor: pontszámítás és szabályok (a felülettől és a kameráktól független).

Egy dobás = (szorzó, szám); szorzó 0 = mellé, szám 25 = Bull (2 = belső Bull = 50).
Minden játék körökre épül: egy kör (turn) legfeljebb `turn_darts()` nyíl, a kör idő előtt is véget érhet.
"""
import copy
import itertools
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable


# ───────────── segédek ─────────────
def label(m, n):
    if m == 0: return "–"
    if n == 25: return "Bull" if m == 2 else "25"
    return ("", "", "D", "T")[m] + str(n)


ORDER = ([(3, n) for n in range(20, 0, -1)] + [(2, 25)] + [(2, n) for n in range(20, 0, -1)]
         + [(1, 25)] + [(1, n) for n in range(20, 0, -1)])
FIN_D = {m * n: (m, n) for m, n in reversed(ORDER) if m == 2}   # kiszálló dupla
FIN_S = {m * n: (m, n) for m, n in reversed(ORDER)}             # bármi


@lru_cache(None)
def checkout_routes(left, k, dbl, limit=3):
    """Kiszálló útvonalak legfeljebb k nyílból, a legkevesebb nyíllal kezdve: [((szorzó, szám), ...), ...]."""
    fin, out = (FIN_D if dbl else FIN_S), []
    for r in range(1, k + 1):
        for c in itertools.product(ORDER, repeat=r - 1):
            rest = left - sum(m * n for m, n in c)
            if rest in fin: out.append(c + (fin[rest],))
        if out: break
    return out[:limit]


def checkout(left, k, dbl):
    """Ugyanez szövegesen: ["T20 → T17 → D18", ...]."""
    return [" → ".join(label(*t) for t in c) for c in checkout_routes(left, k, dbl)]


def target_name(n):
    return "Bull" if n == 25 else str(n)


# ───────────── alap ─────────────
class Game:
    rounds = None           # körök száma (None = a játék a győztesig tart)
    max_rounds = None       # holtverseny esetén eddig hosszabbítható (None = nincs hosszabbítás, döntetlen)
    title = ""
    unit = "KÖR"            # a fejlécben: "3/10. KÖR", baseballnál "INNING", golfnál "LYUK"

    def __init__(self, names):
        self.names, self.n = names, len(names)
        self.cur, self.round, self.darts, self.winner, self.prev, self.hist = 0, 1, [], None, None, []
        self.tied = []                          # döntetlen esetén a holtversenyben álló játékosok
        self.rounds = self.rounds               # példányszintű érték: a hosszabbítás és a visszavonás így együtt működik
        self.base_rounds = self.rounds
        self.setup()

    # ── kiterjeszthető részek ──
    def setup(self): pass
    def apply(self, p, m, n): """A p játékos egy dobása. True = a kör idő előtt véget ért."""
    def end_turn(self, p): pass                 # a kör végén fut (3 nyíl vagy idő előtti vég), még a következő játékos előtt
    def skip(self, p): return False             # True = a p játékos kimarad (kiesett / végzett)
    def turn_darts(self): return 3              # ebben a körben hány nyilat dob a játékos
    def value(self, p): return 0                # összehasonlítható eredmény (nagyobb = jobb)
    def score(self, p): return str(self.value(p))   # a játékoslistában
    def big(self, p): return self.score(p)      # a nagy számként
    def stats(self, p): return ""
    def hint(self): return ""

    # ── közös működés ──
    def snap(self): return copy.deepcopy({k: v for k, v in self.__dict__.items() if k != "hist"})

    def throw(self, m, n):
        if self.winner is not None: return
        self.hist.append(self.snap())
        self.darts.append((m, n))
        end = self.apply(self.cur, m, n)
        if self.winner is None and (end or len(self.darts) >= self.turn_darts()):
            self.end_turn(self.cur)
            if self.winner is None: self.next()

    def undo(self):
        if self.hist: self.__dict__.update(self.hist.pop())

    def next(self):
        self.prev = (self.names[self.cur], self.darts)
        self.darts = []
        for _ in range(self.n):
            self.cur = (self.cur + 1) % self.n
            if self.cur == 0:
                self.round += 1
                if self.rounds and self.round > self.rounds and self.finish(): return
            if not self.skip(self.cur): return
        self.finish()                           # mindenki kiesett vagy végzett

    def finish(self):
        """A játék vége pontok szerint. Holtversenynél hosszabbít (ha a mód engedi), különben döntetlen.
        True = vége van, False = hosszabbítás."""
        best = max(self.value(p) for p in range(self.n))
        top = [p for p in range(self.n) if self.value(p) == best]
        if len(top) > 1 and self.max_rounds and self.rounds < self.max_rounds:
            self.rounds += 1
            return False
        self.winner, self.tied = top[0], top
        return True

    def round_text(self):
        if self.base_rounds and self.round > self.base_rounds: return f"{self.round}. (hosszabbítás)"
        return f"{self.round}{'/%d' % self.rounds if self.rounds else ''}."


# ───────────── klasszikus játékok ─────────────
class X01(Game):
    def __init__(self, names, start=501, dbl=True):
        self.start, self.dbl = start, dbl
        self.title = f"{start} {'DOUBLE OUT' if dbl else 'STRAIGHT OUT'}"
        super().__init__(names)
    def setup(self): self.left, self.thrown, self.t0 = [self.start] * self.n, [0] * self.n, self.start
    def apply(self, p, m, n):
        if len(self.darts) == 1: self.t0 = self.left[p]
        self.thrown[p] += 1
        s = self.left[p] - m * n
        if s < 0 or (self.dbl and (s == 1 or (s == 0 and m != 2))):   # bust: vissza a kör eleji állásra
            self.left[p] = self.t0
            return True
        self.left[p] = s
        if s == 0: self.winner = p
    def value(self, p): return -self.left[p]
    def score(self, p): return str(self.left[p])
    def stats(self, p):
        a = (self.start - self.left[p]) / self.thrown[p] * 3 if self.thrown[p] else 0
        return f"3 darts átlag: {a:.1f}"
    def hint(self):
        left = self.left[self.cur]
        if not 2 <= left <= 170: return ""
        opts = checkout(left, 3 - len(self.darts), self.dbl)
        return "Kiszálló: " + "   |   ".join(opts) if opts else "Ebből a nyílszámból nincs kiszálló"


class Cricket(Game):
    title, T = "CRICKET", (20, 19, 18, 17, 16, 15, 25)
    def setup(self): self.marks, self.pts = [dict.fromkeys(self.T, 0) for _ in range(self.n)], [0] * self.n
    def apply(self, p, m, n):
        if n in self.T:
            for _ in range(m):
                if self.marks[p][n] < 3: self.marks[p][n] += 1
                elif any(self.marks[q][n] < 3 for q in range(self.n) if q != p): self.pts[p] += n
        if all(v == 3 for v in self.marks[p].values()) and self.pts[p] >= max(self.pts): self.winner = p
    def value(self, p): return self.pts[p]
    def hint(self):
        return "   ".join(f"{'Bull' if t == 25 else t}: {'●' * v}{'○' * (3 - v)}" for t, v in self.marks[self.cur].items())


class Clock(Game):
    title = "AROUND THE CLOCK"
    def setup(self): self.pos = [1] * self.n                       # 1–20, majd 21 = Bull
    def target(self, p): return 25 if self.pos[p] == 21 else self.pos[p]
    def apply(self, p, m, n):
        if m and n == self.target(p):
            self.pos[p] += 1
            if self.pos[p] > 21: self.winner = p
    def value(self, p): return self.pos[p]
    def score(self, p): return "✔" if self.pos[p] > 21 else ("Bull" if self.pos[p] == 21 else str(self.pos[p]))
    def hint(self): return f"Következő cél: {self.score(self.cur)}"


class Shanghai(Game):
    title, rounds = "SHANGHAI", 7
    def setup(self): self.pts, self.seen = [0] * self.n, set()
    def apply(self, p, m, n):
        if len(self.darts) == 1: self.seen = set()
        if m and n == self.round:
            self.pts[p] += m * n
            self.seen.add(m)
            if self.seen == {1, 2, 3}: self.winner = p              # szingli + dupla + tripla = Shanghai
    def value(self, p): return self.pts[p]
    def hint(self): return f"Ebben a körben a(z) {self.round}-es szám ér pontot"


class HighScore(Game):
    title, rounds = "HIGH SCORE", 10
    def setup(self): self.pts = [0] * self.n
    def apply(self, p, m, n): self.pts[p] += m * n
    def value(self, p): return self.pts[p]


# ───────────── party játékok ─────────────
class Killer(Game):
    """Mindenkinek van egy száma és 3 élete. Aki a saját duplájába dob, Gyilkos lesz, és az ellenfelek duplájával
    életet vesz el. Az nyer, aki utolsónak életben marad."""
    title, LIVES = "KILLER", 3

    def setup(self):
        self.num, self.lives, self.killer = [None] * self.n, [self.LIVES] * self.n, [False] * self.n
        self.picking = True                     # számválasztás: mindenki egy nyilat dob a gyengébbik kezével
    def skip(self, p): return self.lives[p] <= 0 or (self.picking and self.num[p] is not None)
    def turn_darts(self): return 1 if self.picking else 3
    def alive(self): return [p for p in range(self.n) if self.lives[p] > 0]
    def hurt(self, q): self.lives[q] = max(0, self.lives[q] - 1)

    def apply(self, p, m, n):
        if self.picking:
            if m and 1 <= n <= 20 and n not in self.num:            # foglalt szám vagy mellé: a következő körben újra
                self.num[p] = n
                if all(x is not None for x in self.num): self.picking = False
                return True
            return
        if m != 2: return
        if n == self.num[p]:
            if not self.killer[p]: self.killer[p] = True            # a saját dupla: Gyilkos lett
            else: self.hurt(p)                                      # Gyilkosként a saját dupla életbe kerül
        elif self.killer[p]:
            for q in range(self.n):
                if q != p and self.lives[q] > 0 and self.num[q] == n: self.hurt(q)
        alive = self.alive()
        if self.n > 1 and len(alive) == 1: self.winner = alive[0]
        return self.lives[p] <= 0                                   # aki a saját duplájával esett ki, annak vége a körének

    def value(self, p): return self.lives[p]
    def score(self, p):
        if self.lives[p] <= 0: return "✖"
        head = "?" if self.num[p] is None else f"#{self.num[p]}"
        return f"{'⚔ ' if self.killer[p] else ''}{head} {'♥' * self.lives[p]}"
    def big(self, p):
        if self.lives[p] <= 0: return "✖"
        return "?" if self.num[p] is None else f"D{self.num[p]}"
    def stats(self, p):
        if self.picking: return "Számválasztás: dobj egy nyilat a gyengébbik kezeddel"
        return ("⚔ Gyilkos" if self.killer[p] else "Még nem Gyilkos") + "  ·  " + "♥" * self.lives[p]
    def hint(self):
        p = self.cur
        if self.picking:
            taken = sorted(x for x in self.num if x is not None)
            return "Dobj egy nyilat a GYENGÉBBIK kezeddel: a talált szám (1–20) lesz a tiéd." + (
                f" Foglalt: {', '.join(map(str, taken))}." if taken else "")
        if not self.killer[p]:
            return f"Találd el a saját duplád (D{self.num[p]}), hogy Gyilkos legyél!"
        prey = ", ".join(f"D{self.num[q]} ({self.names[q]})" for q in range(self.n) if q != p and self.lives[q] > 0)
        return f"⚔ Gyilkos vagy! Célpont: {prey}.  A saját duplád (D{self.num[p]}) életet vesz el tőled!"


class Baseball(Game):
    """9 inning: az inning számát kell dobni; szimpla 1, dupla 2, tripla 3 futás."""
    title, rounds, max_rounds, unit = "BASEBALL", 9, 20, "INNING"
    def setup(self): self.runs = [0] * self.n
    def apply(self, p, m, n):
        if m and n == self.round: self.runs[p] += m
    def value(self, p): return self.runs[p]
    def hint(self):
        return f"{self.round}. inning: a(z) {self.round}-es szám a cél  ·  szimpla 1, dupla 2, tripla 3 futás"


class Golf(Game):
    """18 lyuk (1–18), lyukanként 3 nyíl, a legjobb nyíl számít; kevesebb ütés a jobb. Döntetlennél a 19., 20. lyuk, majd a Bull."""
    title, rounds, max_rounds, unit = "GOLF", 18, 21, "LYUK"
    def setup(self): self.strokes, self.best = [0] * self.n, 5
    def hole(self): return self.round if self.round <= 20 else 25
    def cost(self, m, n):
        h = self.hole()
        if h == 25: return 2 if (n == 25 and m == 2) else (3 if n == 25 and m == 1 else 4)
        return {3: 2, 2: 3, 1: 4}[m] if m and n == h else 5
    def apply(self, p, m, n):
        if len(self.darts) == 1: self.best = 5
        self.best = min(self.best, self.cost(m, n))
    def end_turn(self, p): self.strokes[p] += self.best
    def value(self, p): return -self.strokes[p]
    def score(self, p): return str(self.strokes[p])
    def hint(self):
        h = self.hole()
        if h == 25: return "Bull-lyuk: belső Bull 2, külső Bull 3, mellé 4 ütés (a legjobb nyíl számít)"
        return f"{h}. lyuk: cél a(z) {h}-es szám  ·  tripla 2, dupla 3, szimpla 4, mellé 5 ütés (a legjobb nyíl számít)"


class Bermuda(Game):
    """13 kör, körönként más cél; ha mind a 3 nyíl mellé megy, a pontszám felére esik."""
    title, rounds = "BERMUDA TRIANGLE", 13
    TARGETS = (("n", 12), ("n", 13), ("n", 14), ("d", 0), ("n", 15), ("n", 16), ("n", 17), ("t", 0),
               ("n", 18), ("n", 19), ("n", 20), ("b", 25), ("B", 50))
    NAMES = {"d": "bármelyik DUPLA", "t": "bármelyik TRIPLA", "b": "Bull (külső vagy belső, 25 pont)",
             "B": "belső Bull (50 pont)"}
    def setup(self): self.pts, self.hit = [0] * self.n, False
    def target(self): return self.TARGETS[min(self.round, len(self.TARGETS)) - 1]
    def points(self, m, n):
        kind, arg = self.target()
        if not m: return 0
        if kind == "n": return m * n if n == arg else 0
        if kind == "d": return m * n if m == 2 else 0
        if kind == "t": return m * n if m == 3 else 0
        if kind == "b": return 25 if n == 25 else 0
        return 50 if (n == 25 and m == 2) else 0
    def apply(self, p, m, n):
        if len(self.darts) == 1: self.hit = False
        pts = self.points(m, n)
        self.pts[p] += pts
        if pts: self.hit = True
    def end_turn(self, p):
        if not self.hit: self.pts[p] //= 2                  # mind a 3 nyíl mellé: felezés (lefelé kerekítve)
    def value(self, p): return self.pts[p]
    def hint(self):
        kind, arg = self.target()
        return f"{self.round}. kör: cél: {arg if kind == 'n' else self.NAMES[kind]}  ·  ha mind a 3 nyíl mellé megy, a pontod a felére esik"


# ───────────── gyakorló játékok ─────────────
class Bobs27(Game):
    """27 ponttal indulsz, D1–D20, majd Bull. Találatonként +a dupla értéke; ha mind a 3 mellé megy, −a dupla értéke.
    Aki 0 alá kerül, kiesik."""
    title, rounds, unit = "BOB'S 27", 21, "DUPLA"
    def setup(self): self.pts, self.out, self.hits = [27] * self.n, [False] * self.n, 0
    def target(self): return self.round if self.round <= 20 else 25
    def skip(self, p): return self.out[p]
    def apply(self, p, m, n):
        if len(self.darts) == 1: self.hits = 0
        if m == 2 and n == self.target():
            self.hits += 1
            self.pts[p] += 2 * n
    def end_turn(self, p):
        if not self.hits:
            self.pts[p] -= 2 * self.target()
            if self.pts[p] < 0: self.out[p] = True
        if self.n > 1 and sum(not o for o in self.out) <= 1: self.finish()   # már senki sem érheti utol
    def value(self, p): return self.pts[p]
    def stats(self, p): return "Kiesett ✖" if self.out[p] else ""
    def hint(self):
        t = self.target()
        return (f"Cél: {'Bull (dupla)' if t == 25 else 'D' + str(t)}  ·  találatonként +{2 * t}, "
                f"ha mind a 3 nyíl mellé megy: −{2 * t}")


class Doubles(Game):
    """D1–D20, majd Bull; mindegyikre 3 nyíl, minden találat 1 pont."""
    title, rounds, unit = "DUPLÁK", 21, "DUPLA"
    def setup(self): self.pts = [0] * self.n
    def target(self): return self.round if self.round <= 20 else 25
    def apply(self, p, m, n):
        if m == 2 and n == self.target(): self.pts[p] += 1
    def value(self, p): return self.pts[p]
    def hint(self):
        t = self.target()
        return f"Cél: {'Bull (dupla)' if t == 25 else 'D' + str(t)}  ·  3 nyíl, minden találat 1 pont"


class BullPractice(Game):
    """10 kör a Bullra: külső Bull 1 pont, belső Bull 2 pont."""
    title, rounds = "BULL", 10
    def setup(self): self.pts = [0] * self.n
    def apply(self, p, m, n):
        if m and n == 25: self.pts[p] += m
    def value(self, p): return self.pts[p]
    def hint(self): return "Cél: Bull  ·  külső Bull 1 pont, belső Bull (50) 2 pont"


class Hundred(Game):
    """Pontszerző gyakorlat: pontosan 100 nyíl (33 kör × 3 + 1), bárhová dobhatsz, az összpont számít."""
    title, rounds = "100 NYÍL", 34
    def setup(self): self.pts, self.thrown = [0] * self.n, [0] * self.n
    def turn_darts(self): return 1 if self.round == self.rounds else 3
    def apply(self, p, m, n):
        self.pts[p] += m * n
        self.thrown[p] += 1
    def value(self, p): return self.pts[p]
    def stats(self, p):
        a = self.pts[p] / self.thrown[p] * 3 if self.thrown[p] else 0
        return f"{self.thrown[p]}/100 nyíl  ·  3 darts átlag: {a:.1f}"
    def hint(self):
        return "Utolsó nyíl!" if self.round == self.rounds else "Bárhová dobhatsz: a nyilak pontértéke összeadódik"


class Scoring(Game):
    """10 kör; egy kör akkor sikeres, ha a 3 nyíl összege eléri a célpontot (99 vagy 121)."""
    rounds = 10
    def __init__(self, names, goal=99):
        self.goal, self.title = goal, f"SCORING {goal}"
        super().__init__(names)
    def setup(self): self.ok, self.total, self.turn = [0] * self.n, [0] * self.n, 0
    def apply(self, p, m, n):
        if len(self.darts) == 1: self.turn = 0
        self.turn += m * n
        self.total[p] += m * n
    def end_turn(self, p):
        if self.turn >= self.goal: self.ok[p] += 1
    def value(self, p): return self.ok[p] * 100000 + self.total[p]      # azonos sikeres körszámnál az összpont dönt
    def score(self, p): return str(self.ok[p])
    def stats(self, p): return f"Sikeres körök: {self.ok[p]}  ·  összpont: {self.total[p]}"
    def hint(self):
        return f"Cél: legalább {self.goal} pont a 3 nyílból" + (f"  ·  most: {self.turn}" if self.darts else "")


class A1(Game):
    """A1 gyakorlat: 20, 19, …, 13 és Bull. Egy szám akkor kap jelzést, ha a 3 nyílból legalább 2 a számra esik;
    5 jelzés után a szám lezárul. Az nyer, aki kevesebb kör alatt zár le mindent."""
    title = "A1 GYAKORLÓ"
    TARGETS, NEED, MARKS = (20, 19, 18, 17, 16, 15, 14, 13, 25), 2, 5
    def setup(self):
        self.marks = [dict.fromkeys(self.TARGETS, 0) for _ in range(self.n)]
        self.pos, self.visits, self.done, self.cnt = [-1] * self.n, [0] * self.n, [False] * self.n, 0
    def current(self, p):
        for k in range(1, len(self.TARGETS) + 1):
            t = self.TARGETS[(self.pos[p] + k) % len(self.TARGETS)]
            if self.marks[p][t] < self.MARKS: return t
    def skip(self, p): return self.done[p]
    def apply(self, p, m, n):
        if len(self.darts) == 1: self.cnt = 0
        if m and n == self.current(p): self.cnt += 1
    def end_turn(self, p):
        t = self.current(p)
        self.visits[p] += 1
        if self.cnt >= self.NEED: self.marks[p][t] += 1
        self.pos[p] = self.TARGETS.index(t)
        if all(v >= self.MARKS for v in self.marks[p].values()): self.done[p] = True
    def closed(self, p): return sum(v >= self.MARKS for v in self.marks[p].values())
    def value(self, p): return -self.visits[p]
    def score(self, p): return f"{self.closed(p)}/{len(self.TARGETS)}"
    def big(self, p): return "✔" if self.done[p] else target_name(self.current(p))
    def stats(self, p):
        marks = " ".join(f"{target_name(t)}:{v}{'✔' if v >= self.MARKS else ''}" for t, v in self.marks[p].items())
        return f"Körök: {self.visits[p]}  ·  {marks}"
    def hint(self):
        t = self.current(self.cur)
        return (f"Cél: {target_name(t)}  ·  legalább {self.NEED} nyíl kell a számra a 3-ból egy jelzéshez "
                f"({self.marks[self.cur][t]}/{self.MARKS})")


class Finisher(Game):
    """Közös alap a kiszállást gyakorló módokhoz: játékosonként külön feladat (Double Out), egy feladatra `visits` kör jut."""
    visits = 3

    def setup(self):
        self.target = [self.first()] * self.n
        self.left = list(self.target)
        self.visit, self.done, self.pts = [0] * self.n, [False] * self.n, [0] * self.n
        self.t0, self.res = 0, None
        self.extra()
    def first(self): return 0
    def extra(self): pass
    def skip(self, p): return self.done[p]
    def set_target(self, p, t):
        self.target[p], self.left[p], self.visit[p] = t, t, 0

    def apply(self, p, m, n):
        if len(self.darts) == 1: self.t0, self.res = self.left[p], None
        s = self.left[p] - m * n
        if s < 0 or s == 1 or (s == 0 and m != 2):          # bust: a kör elveszett, vissza a kör eleji állásra
            self.left[p], self.res = self.t0, "bust"
            return True
        self.left[p] = s
        if s == 0:
            self.res = "ok"
            return True

    def end_turn(self, p):
        if self.res == "ok":
            self.solved(p, self.visit[p] * 3 + len(self.darts))       # ennyi nyílból sikerült
            return
        self.visit[p] += 1
        if self.visit[p] >= self.visits: self.failed(p)

    def big(self, p): return "✔" if self.done[p] else str(self.left[p])
    def hint(self):
        p, left = self.cur, self.left[self.cur]
        text = f"Feladat: {self.target[p]}  ·  {self.visit[p] + 1}/{self.visits}. kör"
        if 2 <= left <= 170:
            opts = checkout(left, 3 - len(self.darts), True)
            text += "  ·  Kiszálló: " + (" | ".join(opts) if opts else "ebből a nyílszámból nincs")
        return text


class Checkout121(Finisher):
    """121-től indulsz; 9 nyíl (3 kör) alatt kell kiszállni dupla zárással. Siker: a következő szám (egészen 170-ig),
    kudarc: vissza a kezdőszámra vagy az utolsó „bankerre” (3 nyílból sikerült kiszálló)."""
    title, START, END, ATTEMPTS = "121–170 CHECKOUT", 121, 170, 10
    def first(self): return self.START
    def extra(self): self.tries, self.best, self.bank, self.streak = [0] * self.n, [0] * self.n, [0] * self.n, [0] * self.n
    def advance(self, p, t):
        self.tries[p] += 1
        if self.tries[p] >= self.ATTEMPTS or t > self.END: self.done[p] = True
        self.set_target(p, min(t, self.END))
    def solved(self, p, used):
        t = self.target[p]
        self.best[p] = max(self.best[p], t)
        self.streak[p] += 1
        if used <= 3: self.bank[p] = t
        self.advance(p, t + 1)
    def failed(self, p):
        self.streak[p] = 0
        self.advance(p, self.bank[p] or self.START)
    def value(self, p): return self.best[p]
    def score(self, p): return str(self.best[p] or "–")
    def stats(self, p):
        return (f"Kísérlet: {min(self.tries[p] + 1, self.ATTEMPTS)}/{self.ATTEMPTS}  ·  legjobb kiszálló: "
                f"{self.best[p] or '–'}  ·  sorozat: {self.streak[p]}")


class Catch40(Finisher):
    """40 kiszálló (61–100), egyenként legfeljebb 6 nyíl (2 kör). 2 nyílból 3 pont, 3-ból 2 pont, 4–6-ból 1 pont
    (a 99 három nyílból 3 pont). Legfeljebb 120 pont."""
    title, visits, FIRST, COUNT = "CATCH 40", 2, 61, 40
    def first(self): return self.FIRST
    def extra(self): self.idx = [0] * self.n
    def advance(self, p):
        self.idx[p] += 1
        if self.idx[p] >= self.COUNT: self.done[p] = True
        else: self.set_target(p, self.FIRST + self.idx[p])
    def solved(self, p, used):
        pts = 3 if used <= 2 else (2 if used == 3 else 1)
        if self.target[p] == 99 and used <= 3: pts = 3
        self.pts[p] += pts
        self.advance(p)
    def failed(self, p): self.advance(p)
    def value(self, p): return self.pts[p]
    def score(self, p): return str(self.pts[p])
    def stats(self, p): return f"Pont: {self.pts[p]}  ·  feladat: {min(self.idx[p] + 1, self.COUNT)}/{self.COUNT}"


def apply_round(game, darts):
    """Egy kör dobásait (szorzó, szám) viszi be a játékba. Megáll, ha a kör idő előtt véget ér
    (pl. bust vagy kiszálló), így a megmaradt dobások nem kerülnek a következő játékoshoz."""
    start = (game.cur, game.round)
    for m, n in darts:
        if game.winner is not None or (game.cur, game.round) != start:
            break
        game.throw(m, n)


# ───────────── játékmódok: választó, játékosszám, szabályleírás ─────────────
GROUPS = ("Klasszikus", "Party", "Gyakorló")
MAX_PLAYERS = 8


@dataclass(frozen=True)
class Mode:
    id: str
    name: str
    group: str
    desc: str                       # egy sor a választóban
    make: Callable                  # make(nevek, double_out) -> Game
    min_players: int = 1
    max_players: int = MAX_PLAYERS
    uses_out: bool = False          # számít-e a Double/Straight Out beállítás
    rules: tuple = ()               # ((cím, szöveg), ...) az infóablakhoz
    players_note: str = ""

    def players_text(self):
        span = f"{self.min_players}–{self.max_players}" if self.min_players != self.max_players else str(self.min_players)
        return f"{span} játékos" + (f" ({self.players_note})" if self.players_note else "")


_X01_RULES = (
    ("Cél", "Elsőként érj pontosan nullára a kezdőpontról."),
    ("Menet", "Felváltva dobtok, körönként 3 nyíl. Minden nyíl pontértéke levonódik a pontszámodból: a szimpla a szám értéke, "
              "a dupla kétszerese, a tripla háromszorosa; a külső Bull 25, a belső Bull 50."),
    ("Kiszállás", "Double Out beállításnál az utolsó nyílnak dupla (vagy belső Bull) mezőbe kell esnie. "
                  "Straight Outnál bármilyen mező jó."),
    ("Bust", "Ha túllősz, vagy Double Outnál 1 pont marad, vagy nem duplával érsz nullára, a kör érvénytelen: "
             "a pontszámod visszaáll a kör eleji értékre, és a következő játékos jön."),
    ("Segítség", "170 pont alatt a program kiszálló-javaslatot ír ki. A 3 darts átlag a pontszám alatt látszik."),
)

MODES = [
    Mode("301", "301", "Klasszikus", "Gyors lejátszású, 301-ről nullára", lambda n, d: X01(n, 301, d),
         uses_out=True, rules=_X01_RULES, players_note="egyedül gyakorlásra is"),
    Mode("501", "501", "Klasszikus", "A klasszikus: 501-ről nullára", lambda n, d: X01(n, 501, d),
         uses_out=True, rules=_X01_RULES, players_note="egyedül gyakorlásra is"),
    Mode("701", "701", "Klasszikus", "Hosszú meccs, 701-ről nullára", lambda n, d: X01(n, 701, d),
         uses_out=True, rules=_X01_RULES, players_note="egyedül gyakorlásra is"),
    Mode("cricket", "Cricket", "Klasszikus", "Zárd le a 15–20-at és a Bullt, pontot a nyitott számokon gyűjthetsz",
         lambda n, d: Cricket(n), min_players=2, rules=(
             ("Cél", "Zárd le a 20, 19, 18, 17, 16, 15 és a Bull mezőt, és legyen legalább annyi pontod, mint bárki másnak."),
             ("Menet", "Csak ezekre a számokra dobsz, körönként 3 nyíl. Szimpla találat 1, dupla 2, tripla 3 jelölés "
                       "(a belső Bull 2 jelölés). 3 jelölés = a szám lezárva."),
             ("Pontozás", "Ha egy számot már lezártál, de valamelyik ellenfél még nem, minden további találatod a szám értékét "
                          "hozza pontként (Bull: 25). Ha mindenki lezárta, a szám már nem ér pontot."),
             ("Vége", "Az nyer, aki minden számot lezárt, és pontban nem marad le senki mögött."))),
    Mode("clock", "Around the Clock", "Party", "Sorban 1-től 20-ig, a végén Bull", lambda n, d: Clock(n), rules=(
        ("Cél", "Elsőként találd el sorban az 1, 2, 3 … 20 számot, majd a Bullt."),
        ("Menet", "Körönként 3 nyíl. Csak a soron következő szám számít (bármelyik gyűrűje: szimpla, dupla, tripla). "
                  "Találat után azonnal a következő szám a cél, még ugyanabban a körben is."),
        ("Vége", "Az nyer, aki először eltalálja a Bullt (külső vagy belső)."))),
    Mode("shanghai", "Shanghai", "Party", "7 kör, minden körben más szám ér pontot", lambda n, d: Shanghai(n), rules=(
        ("Cél", "Gyűjts minél több pontot a 7 körben, vagy dobj Shanghait."),
        ("Menet", "Az 1. körben az 1-es, a 2. körben a 2-es … a 7. körben a 7-es szám ér pontot. Körönként 3 nyíl, "
                  "más számokra dobott nyíl nem ér semmit."),
        ("Pontozás", "Szimpla = a szám, dupla = 2×, tripla = 3×."),
        ("Shanghai", "Ha egy körben a körszám szimplájába, duplájába és triplájába is eltalálsz, azonnal nyersz."),
        ("Vége", "7 kör után a legtöbb pont nyer; azonos pontszámnál döntetlen."))),
    Mode("highscore", "High Score", "Klasszikus", "10 kör, a legtöbb pont nyer", lambda n, d: HighScore(n), rules=(
        ("Cél", "Gyűjts minél több pontot 10 kör alatt."),
        ("Menet", "Körönként 3 nyíl, bárhová dobhatsz. A pontok összeadódnak (szimpla, dupla 2×, tripla 3×, Bull 25/50)."),
        ("Vége", "10 kör után a legtöbb pont nyer; azonos pontszámnál döntetlen."))),
    Mode("killer", "Killer", "Party", "Mindenkinek van egy száma és 3 élete, az utolsó él nyer",
         lambda n, d: Killer(n), min_players=2, rules=(
             ("Cél", "Utolsónak maradj életben."),
             ("1. Számválasztás", "Mindenki egyetlen nyilat dob a GYENGÉBBIK kezével. A talált szám (1–20) lesz a tiéd. "
                                  "Ha foglalt számot vagy mellé dobsz, a következő körben újra próbálkozol."),
             ("2. Gyilkossá válás", "Mindenkinek 3 élete van. Találd el a saját számod DUPLÁJÁT, így Gyilkos leszel."),
             ("3. Vadászat", "Gyilkosként az ellenfelek duplájába dobva életet veszel el tőlük (találatonként egyet). "
                             "Vigyázz: a saját duplád Gyilkosként életet vesz el TŐLED. Gyilkossá válás előtt is elveszíthetsz életet."),
             ("Vége", "Akinek elfogy az élete, kiesik. Az nyer, aki utolsónak életben marad."))),
    Mode("bobs27", "Bob's 27", "Gyakorló", "Duplák 27 pontról, egy mellé dobás pontba kerül",
         lambda n, d: Bobs27(n), rules=(
             ("Cél", "Minél magasabb pontszámmal érj a végére, és ne essél 0 alá."),
             ("Menet", "27 ponttal indulsz. A célok sorban: D1, D2 … D20, majd a Bull (dupla). Mindegyikre 3 nyilat dobsz."),
             ("Pontozás", "Minden eltalált dupla annak értékét adja hozzá (D6 = +12, a Bull = +50). Ha mind a 3 nyíl mellé megy, "
                          "ugyanennyit levonunk a pontodból. Ha a pontod 0 alá csökken, kiesel."),
             ("Vége", "21 kör után a legmagasabb pontszám nyer. Ha mindenki más kiesett, az utolsó játékos azonnal nyer."))),
    Mode("baseball", "Baseball", "Party", "9 inning, az inning számát kell dobni", lambda n, d: Baseball(n), rules=(
        ("Cél", "Szerezz több futást, mint a többiek, 9 inning alatt."),
        ("Menet", "Az 1. inningben az 1-es, a 2.-ban a 2-es … a 9.-ben a 9-es szám a cél. Inningenként 3 nyíl."),
        ("Pontozás", "Szimpla = 1 futás, dupla = 2, tripla = 3. Más számra dobott nyíl nem ér semmit."),
        ("Vége", "9 inning után a legtöbb futás nyer. Holtversenynél hosszabbítás jön (10., 11. … inning, a 10-es, 11-es … számmal), "
                 "amíg el nem dől."))),
    Mode("golf", "Golf", "Party", "18 lyuk, a legkevesebb ütés nyer", lambda n, d: Golf(n), rules=(
        ("Cél", "Zárd a 18 lyukat a lehető legkevesebb ütéssel."),
        ("Menet", "Az 1. lyuk az 1-es szám, a 2. lyuk a 2-es … a 18. lyuk a 18-as. Lyukanként mind a 3 nyilat dobod, "
                  "és a LEGJOBB nyíl számít."),
        ("Ütések", "Tripla: 2 ütés, dupla: 3, szimpla: 4, mellé (vagy más számra dobva): 5 ütés."),
        ("Vége", "Az nyer, aki a 18 lyuk után a legkevesebb ütést gyűjtötte. Holtversenynél hosszabbítás: 19., 20. lyuk, majd a "
                 "Bull-lyuk (belső Bull 2, külső Bull 3, mellé 4 ütés), amíg el nem dől."))),
    Mode("bermuda", "Bermuda Triangle", "Party", "13 kör különböző célokkal, mellé = felezés",
         lambda n, d: Bermuda(n), rules=(
             ("Cél", "Gyűjts minél több pontot a 13 körben, és kerüld a felezést."),
             ("Célok sorban", "12, 13, 14, bármelyik dupla, 15, 16, 17, bármelyik tripla, 18, 19, 20, Bull (külső vagy belső: 25 pont), "
                              "belső Bull (50 pont)."),
             ("Pontozás", "A találatok a mező értékét adják (a tripla 20 = 60). A célon kívüli nyíl nem ér semmit."),
             ("Felezés", "Ha egy körben mind a 3 nyíl mellé megy, a teljes pontszámod a felére esik (lefelé kerekítve). 0 pontról indulsz."),
             ("Vége", "13 kör után a legtöbb pont nyer; azonos pontszámnál döntetlen."))),
    Mode("121", "121–170 Checkout", "Gyakorló", "Nagy kiszállók gyakorlása 121-től 170-ig",
         lambda n, d: Checkout121(n), rules=(
             ("Cél", "Érd el minél magasabb kiszálló számot."),
             ("Menet", "121-ről indulsz. Egy feladatra 3 kör (9 nyíl) jut, Double Out szabállyal: dupla (vagy belső Bull) zárással kell "
                       "pontosan nullára érni. Bust esetén a kör elvész, és az állás visszaáll a kör elejére."),
             ("Siker", "A következő feladat a következő szám (122, 123 …), legfeljebb 170-ig."),
             ("Kudarc", "Vissza a 121-re, vagy az utolsó „bankerre”: az a kiszálló, ami az első 3 nyílból sikerült."),
             ("Vége", "Játékosonként 10 kísérlet. A legmagasabb teljesített kiszálló nyer; azonos eredménynél döntetlen."))),
    Mode("catch40", "Catch 40", "Gyakorló", "40 kiszálló 61-től 100-ig, pont a nyílszám után",
         lambda n, d: Catch40(n), rules=(
             ("Cél", "Szállj ki mind a 40 számból (61–100), minél kevesebb nyílból."),
             ("Menet", "Mindegyik kiszállóra legfeljebb 6 nyíl (2 kör) jut, Double Out szabállyal. Ha nem sikerül, a következő szám jön."),
             ("Pontozás", "Kiszállás 2 nyílból: 3 pont, 3 nyílból: 2 pont, 4–6 nyílból: 1 pont. Kivétel: a 99-et 3 nyílból 3 pont éri. "
                          "Maximum 120 pont."),
             ("Vége", "A 100 után vége; a legtöbb pont nyer, azonos pontszámnál döntetlen."))),
    Mode("doubles", "Duplák", "Gyakorló", "D1–D20 és Bull, találatonként 1 pont", lambda n, d: Doubles(n), rules=(
        ("Cél", "Gyakorold a dupla mezők eltalálását."),
        ("Menet", "Sorban D1, D2 … D20, majd a Bull (dupla). Mindegyik célra 3 nyilat dobsz."),
        ("Pontozás", "Minden eltalált dupla 1 pont (legfeljebb 3 célonként, összesen 63)."),
        ("Vége", "21 kör után a legtöbb pont nyer; azonos pontszámnál döntetlen."))),
    Mode("bull", "Bull", "Gyakorló", "10 kör a Bullra", lambda n, d: BullPractice(n), rules=(
        ("Cél", "Gyakorold a Bull eltalálását."),
        ("Menet", "10 kör, körönként 3 nyíl, mind a Bullra."),
        ("Pontozás", "Külső Bull: 1 pont, belső Bull (50): 2 pont. Legfeljebb 60 pont."),
        ("Vége", "10 kör után a legtöbb pont nyer; azonos pontszámnál döntetlen."))),
    Mode("a1", "A1 gyakorló", "Gyakorló", "20–13 és Bull, számonként 5 jelzés", lambda n, d: A1(n), rules=(
        ("Cél", "Zárj le mind a 9 célt (20, 19, 18, 17, 16, 15, 14, 13, Bull) a lehető legkevesebb kör alatt."),
        ("Menet", "Egy körben (3 nyíl) egyetlen számra dobsz. Ha legalább 2 nyíl a számra esik (bármelyik gyűrűjére), "
                  "a szám 1 jelzést kap. Utána a következő megnyitott szám jön."),
        ("Lezárás", "5 jelzés után a szám lezárul, és kimarad."),
        ("Vége", "Aki minden számot lezárt, végzett. Több játékosnál az nyer, aki kevesebb kör alatt végzett; azonos körszámnál döntetlen."))),
    Mode("hundred", "100 nyíl", "Gyakorló", "Pontosan 100 nyíl, az összpont számít", lambda n, d: Hundred(n), rules=(
        ("Cél", "Szerezz minél több pontot 100 nyílból."),
        ("Menet", "33 kör 3 nyíllal, majd 1 záró nyíl: pontosan 100 nyíl. Bárhová dobhatsz."),
        ("Pontozás", "A nyilak pontértéke összeadódik (szimpla, dupla 2×, tripla 3×, Bull 25/50). A program kiírja a 3 darts átlagot is."),
        ("Vége", "A 100. nyíl után a legtöbb pont nyer; azonos pontszámnál döntetlen."))),
    Mode("scoring99", "Scoring 99", "Gyakorló", "10 kör, a cél körönként legalább 99 pont",
         lambda n, d: Scoring(n, 99), rules=(
             ("Cél", "Minél több körben dobj legalább 99 pontot a 3 nyílból."),
             ("Menet", "10 kör, körönként 3 nyíl, bárhová dobhatsz."),
             ("Pontozás", "Egy kör akkor sikeres, ha a 3 nyíl összege eléri a 99-et. Azonos sikeres körszámnál az összpont dönt."),
             ("Vége", "10 kör után a legtöbb sikeres kör nyer."))),
    Mode("scoring121", "Scoring 121", "Gyakorló", "10 kör, a cél körönként legalább 121 pont",
         lambda n, d: Scoring(n, 121), rules=(
             ("Cél", "Minél több körben dobj legalább 121 pontot a 3 nyílból."),
             ("Menet", "10 kör, körönként 3 nyíl, bárhová dobhatsz."),
             ("Pontozás", "Egy kör akkor sikeres, ha a 3 nyíl összege eléri a 121-et. Azonos sikeres körszámnál az összpont dönt."),
             ("Vége", "10 kör után a legtöbb sikeres kör nyer."))),
]
MODE_IDS = [m.id for m in MODES]
