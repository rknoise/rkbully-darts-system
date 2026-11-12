"""Meccs végi képernyő: a győztes kiemelése, konfetti és a játékosok átlagai.

A `standings` a játék állapotából számol (felülettől független, tesztelhető), a `MatchEndDialog` csak megjeleníti."""
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

import stats
from statsview import make_table
from theme import Avatar, GREEN, ORANGE, YELLOW, glow

HEAD = ["#", "Játékos", "Eredmény", "Átlag (3 nyíl)", "Nyilak", "Legjobb kör", "100+", "180", "Kiszálló"]
CONFETTI = ["#ff8a1f", "#ffd23f", "#3a9bff", "#38e07b", "#ff4d9d", "#ffffff"]


def is_x01(game):
    return hasattr(game, "thrown") and hasattr(game, "left")


def standings(game):
    """Játékosonként a meccs számai, a helyezés szerint rendezve (a győztes(ek) elöl).

    Sor: {"i", "name", "score", "avg", "darts", "best", "c100", "c180", "checkout", "winner"}. X01-nél a ténylegesen
    levont pontok számítanak (a bust nem pont); más játékoknál a dobott nyilak értéke."""
    winners = set(game.tied or ([game.winner] if game.winner is not None else []))
    rows = [{"i": i, "name": game.names[i], "score": game.score(i), "avg": 0.0, "darts": 0, "best": 0, "c100": 0,
             "c180": 0, "checkout": 0, "winner": i in winners} for i in range(game.n)]
    if is_x01(game):
        for i, s in enumerate(stats.summary(game)):
            r = rows[i]
            r.update(darts=game.thrown[i], best=s["best"], c100=s["c100"], c180=s["c180"], checkout=s["checkout"])
            r["avg"] = s["scored"] / game.thrown[i] * 3 if game.thrown[i] else 0.0
    else:
        for i, s in enumerate(stats.player_stats(game)):
            rows[i].update(darts=s["darts"], best=s["best"], avg=s["avg3"])
        for p, darts in stats.round_log(game):
            pts = stats.points(darts)
            rows[p]["c100"] += pts >= 100
            rows[p]["c180"] += pts == 180
    if is_x01(game):
        rows.sort(key=lambda r: (not r["winner"], game.left[r["i"]]))
    else:
        rows.sort(key=lambda r: (not r["winner"], -r["avg"]))
    return rows


def highlights(rows):
    """A meccs kiemelései: a legjobb átlag és a legjobb kör játékosa (csak ha volt dobás)."""
    out = {}
    played = [r for r in rows if r["darts"]]
    if played:
        out["avg"] = max(played, key=lambda r: r["avg"])["i"]
        top = max(played, key=lambda r: r["best"])
        if top["best"]:
            out["best"] = top["i"]
    return out


def fmt_avg(v):
    return f"{v:.1f}"


class MatchEndDialog(QDialog):
    """A győztes képernyője. Az eredmény (`choice`): "rematch" (visszavágó), "stats" vagy "close"."""

    def __init__(self, parent, game, avatars, animate=True):
        super().__init__(parent)
        self.setWindowTitle("Meccs vége")
        self.choice = "close"
        self.rows = standings(game)
        self.marks = highlights(self.rows)
        self.draw = bool(game.tied and len(game.tied) > 1)
        winners = [r for r in self.rows if r["winner"]]
        self.particles = []
        self._rnd = random.Random()
        self._ticks = 0
        self.resize(940, 700)

        kicker = QLabel("🤝  DÖNTETLEN" if self.draw else "🏆  GYŐZTES")
        kicker.setAlignment(Qt.AlignCenter)
        kicker.setStyleSheet(f"font-size: 22px; font-weight: 900; letter-spacing: 6px; color: {YELLOW};")
        names = " · ".join(r["name"] for r in winners) or "–"
        self.name = QLabel(names)
        self.name.setAlignment(Qt.AlignCenter)
        self.name.setStyleSheet("font-size: 58px; font-weight: 900; font-style: italic; color: #ff9d2e;")
        glow(self.name, ORANGE, 46, 190)
        sub = QLabel(f"{game.title}  ·  {game.round_text()} {game.unit}")
        sub.setAlignment(Qt.AlignCenter)
        sub.setObjectName("muted")
        row = QHBoxLayout()
        row.addStretch()
        self.avatars = []
        for r in winners[:4]:
            av = Avatar(120)
            info = avatars.get(r["i"], {})
            av.set_player(r["name"], info.get("path"), info.get("color", ORANGE), YELLOW)
            glow(av, YELLOW, 36, 200)
            self.avatars.append(av)
            row.addWidget(av)
        row.addStretch()
        tip = QLabel(self.tagline(winners))
        tip.setAlignment(Qt.AlignCenter)
        tip.setStyleSheet(f"font-size: 17px; color: {GREEN}; font-weight: 700;")

        rows = []
        for place, r in enumerate(self.rows, 1):
            rows.append(["🥇" if place == 1 and r["winner"] and not self.draw else place, r["name"],
                         r["score"], fmt_avg(r["avg"]) + (" ⭐" if self.marks.get("avg") == r["i"] else ""), r["darts"],
                         (str(r["best"]) + (" ⭐" if self.marks.get("best") == r["i"] else "")) if r["best"] else "–",
                         r["c100"] or "–", r["c180"] or "–", r["checkout"] or "–"])
        self.table = make_table(HEAD, rows, left_cols=(1,), stretch=1)
        self.table.setFixedHeight(min(52 + 42 * len(rows), 400))

        self.rematch = QPushButton("↻  Visszavágó (ugyanazok, ugyanez a játék)")
        self.rematch.setObjectName("go")
        self.rematch.clicked.connect(lambda: self.finish("rematch"))
        self.stats_btn = QPushButton("📊  Statisztikák")
        self.stats_btn.clicked.connect(lambda: self.finish("stats"))
        self.close_btn = QPushButton("Bezárás")
        self.close_btn.clicked.connect(lambda: self.finish("close"))
        buttons = QHBoxLayout()
        buttons.addWidget(self.rematch, 3)
        buttons.addWidget(self.stats_btn, 1)
        buttons.addWidget(self.close_btn, 1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 18, 26, 18)
        lay.setSpacing(8)
        lay.addWidget(kicker)
        lay.addLayout(row)
        lay.addWidget(self.name)
        lay.addWidget(sub)
        lay.addWidget(tip)
        lay.addWidget(self.table)
        lay.addStretch(1)
        lay.addLayout(buttons)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.step)
        if animate:
            self.burst(140)
            self.timer.start(33)

    def tagline(self, winners):
        """Egy mondat a győztesről: átlag és legjobb kör."""
        if self.draw or not winners:
            return "Mindenki ugyanannyit ért: döntetlen."
        w = winners[0]
        parts = [f"átlag {fmt_avg(w['avg'])}", f"{w['darts']} nyíl"]
        if w["best"]:
            parts.append(f"legjobb kör: {w['best']}")
        if w["c180"]:
            parts.append(f"{w['c180']}× 180")
        return "  ·  ".join(parts)

    def finish(self, choice):
        self.choice = choice
        self.timer.stop()
        self.accept()

    def done(self, result):
        self.timer.stop()
        super().done(result)

    # ── konfetti ──
    def burst(self, n):
        w = max(self.width(), 200)
        for _ in range(n):
            self.particles.append({"x": self._rnd.uniform(0, w), "y": self._rnd.uniform(-self.height(), 0),
                                   "vx": self._rnd.uniform(-1.2, 1.2), "vy": self._rnd.uniform(2.0, 5.5),
                                   "rot": self._rnd.uniform(0, math.tau), "vr": self._rnd.uniform(-0.25, 0.25),
                                   "s": self._rnd.uniform(5, 11), "c": QColor(self._rnd.choice(CONFETTI))})

    def step(self):
        self._ticks += 1
        for p in self.particles:
            p["x"] += p["vx"] + math.sin(self._ticks / 9 + p["rot"]) * 0.6
            p["y"] += p["vy"]
            p["rot"] += p["vr"]
        self.particles = [p for p in self.particles if p["y"] < self.height() + 20]
        if self._ticks % 70 == 0 and self._ticks < 300:
            self.burst(60)                              # néhány hullám, utána elcsendesedik
        if not self.particles and self._ticks >= 300:
            self.timer.stop()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#070a14"))
        for cx, cy, rad, col in ((w / 2, h * 0.18, h * 0.75, QColor(255, 140, 30, 95)), (0, h, h * 0.7, QColor(255, 120, 20, 60)),
                                 (w, h * 0.3, h * 0.8, QColor(40, 120, 255, 70))):
            g = QRadialGradient(QPointF(cx, cy), rad)
            g.setColorAt(0, col)
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.fillRect(self.rect(), QBrush(g))
        edge = QLinearGradient(0, 0, w, h)
        edge.setColorAt(0, QColor(ORANGE))
        edge.setColorAt(1, QColor("#3a9bff"))
        p.setPen(QPen(QBrush(edge), 3))
        p.drawRoundedRect(QRectF(3, 3, w - 6, h - 6), 14, 14)
        p.setPen(Qt.NoPen)
        for q in self.particles:
            p.save()
            p.translate(q["x"], q["y"])
            p.rotate(math.degrees(q["rot"]))
            p.setBrush(q["c"])
            p.drawRect(QRectF(-q["s"] / 2, -q["s"] / 4, q["s"], q["s"] / 2))
            p.restore()

