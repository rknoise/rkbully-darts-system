"""Statisztika-ablak: összesítés profilonként, a folyó játék és a befejezett játékok előzménye."""
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

import ask
import history
import stats
from games import MODES

MODE_NAMES = {m.id: m.name for m in MODES}
LOG_LIMIT = 200


def dash(value, fmt="{}"):
    """Üres érték (None, 0) helyett gondolatjel."""
    return "–" if value in (None, 0, 0.0) else fmt.format(value)


def num(value, fmt):
    """Mint a dash, de a 0 valódi érték (0% győzelem, 0.0 átlag), csak a hiányzó (None) lesz gondolatjel."""
    return "–" if value is None else fmt.format(value)


def fill_table(table, rows, left_cols=(0,)):
    """A táblázat tartalmának cseréje (a fejléc és a méretezés marad)."""
    table.setRowCount(len(rows))
    for r, cells in enumerate(rows):
        for c, v in enumerate(cells):
            it = QTableWidgetItem(str(v))
            it.setTextAlignment(Qt.AlignVCenter | (Qt.AlignLeft if c in left_cols else Qt.AlignCenter))
            table.setItem(r, c, it)


def make_table(head, rows, left_cols=(0,), stretch=None):
    """Egyszerű, csak olvasható táblázat a program stílusával. `stretch`: a kitöltő oszlop sorszáma (a többi a tartalomhoz
    igazodik); nélküle minden oszlop egyformán széles."""
    table = QTableWidget(0, len(head))
    table.setHorizontalHeaderLabels(head)
    table.verticalHeader().hide()
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionMode(QTableWidget.NoSelection)
    table.setShowGrid(False)
    table.setFocusPolicy(Qt.NoFocus)
    table.verticalHeader().setDefaultSectionSize(40)
    header = table.horizontalHeader()
    if stretch is None:
        header.setSectionResizeMode(QHeaderView.Stretch)
    else:
        for c in range(len(head)):
            header.setSectionResizeMode(c, QHeaderView.Stretch if c == stretch else QHeaderView.ResizeToContents)
    fill_table(table, rows, left_cols)
    return table


def muted(text):
    lb = QLabel(text)
    lb.setObjectName("muted")
    lb.setWordWrap(True)
    return lb


class StatsDialog(QDialog):
    """Három oldal: Összesítés (profilonként, játékmód szerint szűrhető), Folyó játék, Előzmények.

    records: a history.py bejegyzései · names: profilazonosító -> a profil mostani neve · on_clear: az előzmény törlése."""

    HEAD = ("Játékos", "Állás", "Körök", "Nyilak", "Dobott pont", "Legjobb kör", "3 nyilas átlag")
    TOTAL_HEAD = ("Játékos", "Játékok", "Győzelem", "Győzelem %", "3 nyilas átlag", "Legjobb kör", "100+", "180",
                  "Legjobb kiszálló")
    LOG_HEAD = ("Dátum", "Játék", "Eredmény")
    PAGES = ("🏆  Összesítés", "🎯  Folyó játék", "📜  Előzmények")

    def __init__(self, parent, game, records=None, names=None, on_clear=None, since=None):
        super().__init__(parent)
        self.setWindowTitle("Statisztikák")
        self.resize(980, 560)
        self.game, self.records, self.names, self.on_clear = game, list(records or []), dict(names or {}), on_clear
        self.since = dict(since or {})                   # profilonkénti statisztika-nullázás időpontja
        self.pages = QStackedWidget()
        self.tabs = []
        group = QButtonGroup(self)
        bar = QHBoxLayout()
        for i, text in enumerate(self.PAGES):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setMinimumHeight(38)
            group.addButton(b, i)
            b.clicked.connect(lambda _=False, i=i: self.show_page(i))
            bar.addWidget(b)
            self.tabs.append(b)
        bar.addStretch()
        self.pages.addWidget(self.build_totals())
        self.pages.addWidget(self.build_current())
        self.pages.addWidget(self.build_log())
        close = QPushButton("Rendben")
        close.setObjectName("go")
        close.clicked.connect(self.accept)
        lay = QVBoxLayout(self)
        lay.addLayout(bar)
        lay.addWidget(self.pages, 1)
        lay.addWidget(close)
        self.show_page(0)

    def show_page(self, i):
        self.pages.setCurrentIndex(i)
        self.tabs[i].setChecked(True)

    def name(self, pid, fallback):
        return self.names.get(pid, fallback) if pid else fallback

    # ── összesítés ──
    def build_totals(self):
        page = QWidget()
        self.mode_box = QComboBox()
        self.mode_box.addItem("Minden játékmód", None)
        for mid in history.modes_in(self.records):
            self.mode_box.addItem(MODE_NAMES.get(mid, mid), mid)
        self.mode_box.currentIndexChanged.connect(self.fill_totals)
        top = QHBoxLayout()
        top.addWidget(QLabel("Szűrés:"))
        top.addWidget(self.mode_box)
        top.addStretch()
        self.totals_box = QVBoxLayout()
        self.totals = make_table(self.TOTAL_HEAD, [], stretch=0)
        self.totals_empty = muted("Még nincs befejezett játék. Az eredmények a játék végén automatikusan mentődnek, "
                                  "és a program újraindítása után is megmaradnak.")
        note = muted("A győzelem százalék a legalább két játékos által játszott játékokból számolódik. A 3 nyilas átlag, "
                     "a legjobb kör, a 100+ és 180 körök és a legjobb kiszálló csak a 301/501/701 játékokból jön; a bust kör nem ér pontot.")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.addLayout(top)
        lay.addWidget(self.totals, 1)
        lay.addWidget(self.totals_empty)
        lay.addWidget(note)
        self.fill_totals()
        return page

    def total_rows(self):
        rows = history.aggregate(self.records, self.mode_box.currentData(), self.since)
        out = []
        for r in rows:
            out.append((self.name(r["pid"], r["name"]), r["games"], r["wins"] if r["versus"] else "–",
                        num(r["win_pct"], "{:.0f}%"), num(r["avg3"], "{:.1f}"), dash(r["best"]), dash(r["c100"]),
                        dash(r["c180"]), dash(r["checkout"])))
        return out

    def fill_totals(self, *_):
        rows = self.total_rows()
        fill_table(self.totals, rows)
        self.totals.setVisible(bool(rows))
        self.totals_empty.setVisible(not rows)

    # ── folyó játék ──
    def build_current(self):
        game = self.game
        rows = stats.player_stats(game)
        cells = [(game.names[i], game.score(i), r["rounds"], r["darts"], r["points"], r["best"], f"{r['avg3']:.1f}")
                 for i, r in enumerate(rows)]
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.addWidget(muted(f"🎯 {game.title}  ·  {game.round_text()} {game.unit}. A statisztika az aktuális játékra vonatkozik; "
                            "visszavonásnál a visszavont dobás is kikerül belőle."))
        self.current = make_table(self.HEAD, cells)
        lay.addWidget(self.current, 1)
        return page

    # ── előzmény ──
    def result_text(self, rec):
        crown = "🤝" if len(rec.get("winners") or []) > 1 else "👑"
        parts = []
        for i, p in enumerate(rec["players"]):
            nm = self.name(p.get("pid"), p.get("name", "?"))
            parts.append(f"{crown + ' ' if i in (rec.get('winners') or []) else ''}{nm} {p.get('score', '')}")
        return "   ·   ".join(parts)

    def log_rows(self):
        out = []
        for rec in self.records[::-1][:LOG_LIMIT]:
            when = time.strftime("%Y.%m.%d %H:%M", time.localtime(rec.get("t", 0)))
            out.append((when, rec.get("title", ""), self.result_text(rec)))
        return out

    def build_log(self):
        page = QWidget()
        self.log = make_table(self.LOG_HEAD, self.log_rows(), left_cols=(0, 1, 2), stretch=2)
        self.clear_btn = QPushButton("🗑  Előzmények törlése")
        self.clear_btn.clicked.connect(self.clear)
        self.clear_btn.setEnabled(bool(self.records))
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.addWidget(muted(f"A legutóbbi befejezett játékok, legfrissebb elöl (legfeljebb {LOG_LIMIT}). A 👑 a győztest, "
                            "a 🤝 a döntetlent jelöli."))
        lay.addWidget(self.log, 1)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.clear_btn)
        lay.addLayout(row)
        return page

    def clear(self):
        if not ask.confirm(self, "Előzmények törlése", "Biztosan törlöd az összes mentett játékot és a belőlük számolt "
                                                       "összesítést?\nEz nem vonható vissza."):
            return
        if self.on_clear:
            self.on_clear()
        self.records = []
        self.fill_totals()
        fill_table(self.log, [])
        self.clear_btn.setEnabled(False)
