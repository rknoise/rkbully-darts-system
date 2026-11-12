"""A befejezett játékok tartós előzménye és a profilonkénti összesítés (a felülettől független).

Egy játék a végén egyetlen bejegyzésként mentődik a `history.json` fájlba. A játékosok azonosítója a profil azonosítója,
így az átnevezés az összesítést nem szakítja szét; a bejegyzésben a név is megmarad, hogy törölt profilnál is olvasható legyen.
"""
import json
import time
import uuid
from pathlib import Path

import stats

MAX_RECORDS = 1000


def history_path(cfg_file):
    """Az előzményfájl a beállításfájl mellett van."""
    return Path(cfg_file).with_name("history.json")


def load(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return []
    return [r for r in data if isinstance(r, dict) and isinstance(r.get("players"), list)] if isinstance(data, list) else []


def save(records, path):
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(records[-MAX_RECORDS:], ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass                                  # az előzmény mentése sosem állíthatja meg a játékot


def make_record(game, pids, mode, now=None):
    """Egy befejezett játék bejegyzése. `pids`: a játékosok profilazonosítói a játék sorrendjében."""
    rows = stats.summary(game)
    players = []
    for i in range(game.n):
        players.append({"pid": pids[i] if i < len(pids) else None, "name": game.names[i], "score": game.score(i), **rows[i]})
    winners = list(game.tied or [game.winner]) if game.winner is not None else []
    return {"id": uuid.uuid4().hex[:10], "t": round(float(time.time() if now is None else now), 3), "mode": mode.id,
            "title": game.title, "x01": hasattr(game, "thrown") and hasattr(game, "left"), "players": players,
            "winners": winners}


def aggregate(records, mode_id=None, since=None):
    """Profilonkénti összesítés, a legtöbbet győzőtől a legkevesebbig. `mode_id`: csak az a játékmód (None = mind).
    `since`: {profilazonosító: időpont}, a profil statisztikájának nullázása: az ennél régebbi játékok nála nem számítanak.
    Egyedül játszott játék csak a „Játékok” számot növeli: ott nincs kivel nyerni."""
    rows, since = {}, since or {}
    for rec in records:
        if mode_id and rec.get("mode") != mode_id:
            continue
        versus = len(rec["players"]) > 1
        winners = rec.get("winners") or []
        for i, p in enumerate(rec["players"]):
            if p.get("pid") and rec.get("t", 0) <= since.get(p["pid"], 0):
                continue                                     # nullázás előtti játék: ennek a profilnak nem számít
            key = p.get("pid") or "n:" + str(p.get("name", "")).casefold()
            r = rows.setdefault(key, {"pid": p.get("pid"), "name": p.get("name", "?"), "games": 0, "versus": 0, "wins": 0,
                                      "draws": 0, "x01_games": 0, "darts": 0, "scored": 0, "best": 0, "c100": 0,
                                      "c180": 0, "checkout": 0})
            r["name"] = p.get("name", r["name"])             # a legutóbbi név
            r["games"] += 1
            if versus:
                r["versus"] += 1
                if i in winners:
                    r["wins" if len(winners) == 1 else "draws"] += 1
            if rec.get("x01"):
                r["x01_games"] += 1
                r["darts"] += p.get("darts", 0)
                r["scored"] += p.get("scored", 0)
                r["best"] = max(r["best"], p.get("best", 0))
                r["c100"] += p.get("c100", 0)
                r["c180"] += p.get("c180", 0)
                r["checkout"] = max(r["checkout"], p.get("checkout", 0))
    out = list(rows.values())
    for r in out:
        r["avg3"] = r["scored"] / r["darts"] * 3 if r["darts"] else None
        r["win_pct"] = r["wins"] / r["versus"] * 100 if r["versus"] else None
    out.sort(key=lambda r: (-r["wins"], -r["games"], r["name"].casefold()))
    return out


def modes_in(records):
    """A játékmódok azonosítói, amikből van bejegyzés (a szűrőhöz), előfordulás szerint rendezve."""
    counts = {}
    for rec in records:
        counts[rec.get("mode")] = counts.get(rec.get("mode"), 0) + 1
    return [m for m, _ in sorted(counts.items(), key=lambda kv: -kv[1]) if m]
