"""Játékstatisztika a játékmotor előzményeiből (a felülettől független).

A `Game.hist` minden dobás előtti állapotot őriz, ebből visszaállítható, ki mit dobott. Így a visszavonás is
automatikusan helyes: a visszavont dobás kikerül az előzményekből, és vele a statisztikából is.
"""
from games import label


def _closed_rounds(game):
    """A befejezett körök időrendben: (játékos_index, [(szorzó, szám), ...], kör eleji állapot, kör utáni állapot)."""
    states = list(game.hist) + [game.__dict__]
    out, first = [], None
    for i, before in enumerate(game.hist):
        after = states[i + 1]
        if not before["darts"]:                      # a kör első nyila előtti állapot
            first = before
        if not after["darts"]:                       # a dobás lezárta a kört: az utolsó nyíl is a `prev`-ben van
            if after["prev"]:
                out.append((before["cur"], list(after["prev"][1]), first, after))
        elif after["winner"] is not None:            # a győztes utolsó, félbemaradt köre
            out.append((after["cur"], list(after["darts"]), first, after))
    return out


def round_log(game):
    """A befejezett körök időrendben: [(játékos_index, [(szorzó, szám), ...]), ...]."""
    return [(p, darts) for p, darts, _, _ in _closed_rounds(game)]


def points(darts):
    return sum(m * n for m, n in darts)


def player_stats(game):
    """Játékosonként: körök, nyilak, dobott pont, legjobb kör, 3 nyilas átlag (a folyamatban lévő kör nyilaival együtt)."""
    rows = [{"rounds": 0, "darts": 0, "points": 0, "best": 0, "avg3": 0.0} for _ in range(game.n)]
    for p, darts in round_log(game):
        r = rows[p]
        r["rounds"] += 1
        r["darts"] += len(darts)
        r["points"] += points(darts)
        r["best"] = max(r["best"], points(darts))
    if game.winner is None and game.darts:
        r = rows[game.cur]
        r["darts"] += len(game.darts)
        r["points"] += points(game.darts)
    for r in rows:
        r["avg3"] = r["points"] / r["darts"] * 3 if r["darts"] else 0.0
    return rows


def recent(game, limit=4):
    """A legutóbbi körök, legfrissebb elöl: [(név, [feliratok], összeg), ...]."""
    log = round_log(game)[-limit:][::-1]
    return [(game.names[p], [("S" + str(n)) if m == 1 and n != 25 else label(m, n) for m, n in darts], points(darts))
            for p, darts in log]


def x01_rounds(game):
    """X01 körök a ténylegesen levont pontokkal: bustnál a kör 0-t ér, bár a nyilak értéke nem 0.
    [{"p", "darts", "scored", "bust", "won"}, ...]"""
    out = []
    for p, darts, first, last in _closed_rounds(game):
        scored = first["left"][p] - last["left"][p]
        out.append({"p": p, "darts": darts, "scored": scored, "bust": scored != points(darts), "won": last["winner"] == p})
    return out


def summary(game):
    """A tartós előzményhez: játékosonként körök és nyilak; X01-nél a ténylegesen számított pontok, a legjobb kör,
    a 100+ és 180-as körök és a kiszálló értéke is (bust nem számít pontnak)."""
    rows = [{"rounds": 0, "darts": 0} for _ in range(game.n)]
    if hasattr(game, "thrown") and hasattr(game, "left"):                    # X01
        for r in rows:
            r.update(scored=0, best=0, c100=0, c180=0, checkout=0)
        for rd in x01_rounds(game):
            r = rows[rd["p"]]
            r["rounds"] += 1
            r["best"] = max(r["best"], rd["scored"])
            r["c100"] += rd["scored"] >= 100
            r["c180"] += rd["scored"] == 180
            if rd["won"]:
                r["checkout"] = rd["scored"]
        for i, r in enumerate(rows):
            r["darts"] = game.thrown[i]
            r["scored"] = game.start - game.left[i]
    else:
        for p, darts in round_log(game):
            rows[p]["rounds"] += 1
            rows[p]["darts"] += len(darts)
    return rows
