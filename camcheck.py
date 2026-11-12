"""Kamera- és fényellenőrzés a kalibrációs varázslóhoz (felülettől független, tesztelhető).

Egy négyzetes kameraképre (a Detector is ezt a középső négyzetet látja) és a 4 kalibrációs pontra számolja ki, hogy a tábla
elhelyezése és a megvilágítás megfelel-e a felismerő modellnek: méret, középre állítás, látószög, élesség, fényerő,
tükröződés, egyenletes fény, a kép nyugodtsága, és ha van modell, az is, hogy valóban látja-e a négy pontot."""
import math
from dataclasses import dataclass

import numpy as np

import dartboard as db
import trainer as tr

try:
    import cv2
except ImportError:                                    # pragma: no cover
    cv2 = None

OK, WARN, BAD, NONE = "ok", "warn", "bad", "none"
ICON = {OK: "✔", WARN: "⚠", BAD: "✖", NONE: "·"}
ORDER = {BAD: 0, WARN: 1, NONE: 2, OK: 3}


@dataclass
class Check:
    key: str
    level: str
    title: str
    detail: str = ""                 # rövid utasítás, ha nem rendben
    value: float = None

    @property
    def icon(self):
        return ICON[self.level]


def overall(checks):
    """Az összkép: piros, ha valami hibás; sárga, ha csak figyelmeztetés van; zöld, ha minden rendben."""
    levels = {c.level for c in checks}
    return BAD if BAD in levels else WARN if WARN in levels else OK


def worst_first(checks):
    return sorted(checks, key=lambda c: ORDER[c.level])


def instructions(checks, limit=3):
    """A legfontosabb teendők, szövegesen (a hibásak elöl)."""
    todo = [c for c in worst_first(checks) if c.level in (BAD, WARN) and c.detail]
    return [c.detail for c in todo[:limit]]


# ───────────── a tábla geometriája a képen ─────────────
def outer_ring(cal, n=180):
    """A külső dupla gyűrű pontjai a képen (Nx2), a kalibrációból."""
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    ring = np.stack([db.R_DOUBLE[1] * np.cos(ang), db.R_DOUBLE[1] * np.sin(ang)], 1)
    return db.apply_h(cal.Hinv, ring)


def geometry(cal):
    """{"fill", "inside", "offset", "ratio"}: a tábla átmérője a kép arányában, teljesen a képen belül van-e, a középpont
    eltolódása a kép közepétől (kép arányában, x/y) és a látószög (kis/nagy tengely aránya, 1 = szemből)."""
    ring = outer_ring(cal)
    size = cal.size
    w = float(ring[:, 0].max() - ring[:, 0].min())
    h = float(ring[:, 1].max() - ring[:, 1].min())
    inside = bool((ring >= 0.01 * size).all() and (ring <= 0.99 * size).all())
    cx, cy = cal.center_px()
    c = ring - ring.mean(0)
    ev = np.linalg.eigvalsh(np.cov(c.T))
    ratio = math.sqrt(max(ev[0], 1e-9) / max(ev[1], 1e-9))
    return {"fill": max(w, h) / size, "inside": inside, "offset": ((cx - size / 2) / size, (cy - size / 2) / size),
            "ratio": ratio}


def gray_of(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def analyze(sq, cal):
    """A képkocka ellenőrzése. Visszaad: [Check, ...] (a kalibrációnak érvényesnek kell lennie)."""
    checks = []
    geo = geometry(cal)
    fill = geo["fill"]
    if not geo["inside"]:
        checks.append(Check("fill", BAD, "A tábla teljesen látszik", "A tábla széle kilóg a képből: menj távolabb vagy "
                                                                    "csökkentsd a nagyítást, hogy az egész tábla belefférjen.", fill))
    elif fill < 0.5:
        checks.append(Check("fill", BAD, "A tábla kitölti a képet", "Túl kicsi a tábla a képen: menj közelebb, vagy nagyítsd "
                                                                    "(a tábla a kép szélességének ~70-90%-át töltse ki).", fill))
    elif fill < 0.62:
        checks.append(Check("fill", WARN, "A tábla kitölti a képet", "Kicsit kicsi a tábla: közelebb vagy nagyítással "
                                                                    "pontosabb lesz a felismerés.", fill))
    elif fill > 0.95:
        checks.append(Check("fill", WARN, "A tábla kitölti a képet", "A tábla majdnem kilóg a képből: kicsit távolabb.", fill))
    else:
        checks.append(Check("fill", OK, "A tábla kitölti a képet", value=fill))

    dx, dy = geo["offset"]
    off = math.hypot(dx, dy)
    if off > 0.12:
        level = BAD
    elif off > 0.06:
        level = WARN
    else:
        level = OK
    hint = ""
    if level != OK:
        side = ("jobbra" if dx > 0 else "balra") if abs(dx) >= abs(dy) else ("lefelé" if dy > 0 else "felfelé")
        hint = f"A tábla a kép közepéhez képest {side} tolódott: fordítsd a kamerát egy kicsit {side}."
    checks.append(Check("center", level, "A tábla a kép közepén van", hint, off))

    ratio = geo["ratio"]
    if ratio < 0.6:
        checks.append(Check("angle", BAD, "A kamera szemből nézi a táblát",
                            "Túl ferdén látja a kamera a táblát: állítsd a tábla közepe elé, a szemmagasságához közelebb.", ratio))
    elif ratio < 0.78:
        checks.append(Check("angle", WARN, "A kamera szemből nézi a táblát",
                            "Eléggé ferde a látószög: két kameránál ez még jó, de szemből pontosabb a felismerés.", ratio))
    else:
        checks.append(Check("angle", OK, "A kamera szemből nézi a táblát", value=ratio))

    side = 512
    small = cv2.resize(sq, (side, side), interpolation=cv2.INTER_AREA)
    gray = gray_of(small)
    mask = cv2.resize(cal.board_mask(db.R_DOUBLE[1] + 10), (side, side), interpolation=cv2.INTER_NEAREST) > 0
    if not mask.any():
        return checks
    vals = gray[mask].astype(np.float32)

    lap = cv2.Laplacian(gray, cv2.CV_32F)
    sharp = float(lap[mask].var())
    if sharp < 20:
        checks.append(Check("sharp", BAD, "A kép éles", "Életlen a kép: élesíts rá a táblára (koppints a telefon képernyőjén), "
                                                        "tisztítsd meg a lencsét, és ne mozogjon a kamera.", sharp))
    elif sharp < 50:
        checks.append(Check("sharp", WARN, "A kép éles", "Kicsit életlen a kép: élesíts rá a táblára, vagy válassz nagyobb "
                                                         "felbontást.", sharp))
    else:
        checks.append(Check("sharp", OK, "A kép éles", value=sharp))

    mean = float(vals.mean())
    if mean < 55:
        checks.append(Check("light", BAD, "Megfelelő a fényerő", "Túl sötét a tábla: kapcsolj fel több lámpát, vagy világítsd meg "
                                                                 "a táblát szemből.", mean))
    elif mean < 80:
        checks.append(Check("light", WARN, "Megfelelő a fényerő", "Kicsit sötét: több fény pontosabb felismerést ad.", mean))
    elif mean > 210:
        checks.append(Check("light", BAD, "Megfelelő a fényerő", "Túl világos, kiég a kép: csökkentsd a fényt vagy az "
                                                                 "expozíciót.", mean))
    elif mean > 190:
        checks.append(Check("light", WARN, "Megfelelő a fényerő", "Kicsit túl világos: vegyél vissza a fényből.", mean))
    else:
        checks.append(Check("light", OK, "Megfelelő a fényerő", value=mean))

    glare = float((vals >= 250).mean())
    if glare > 0.03:
        checks.append(Check("glare", BAD, "Nincs tükröződés", "Fényvisszaverődés (villanó folt) van a táblán: fordítsd el vagy "
                                                              "takard le a lámpát, ami a táblára süt, ne használj vakut.", glare))
    elif glare > 0.01:
        checks.append(Check("glare", WARN, "Nincs tükröződés", "Kis fényvisszaverődés látszik: igazíts a lámpán.", glare))
    else:
        checks.append(Check("glare", OK, "Nincs tükröződés", value=glare))

    ys, xs = np.nonzero(mask)
    cx, cy = float(xs.mean()), float(ys.mean())
    parts = {"bal": gray[mask & (np.arange(side)[None, :] < cx)], "jobb": gray[mask & (np.arange(side)[None, :] >= cx)],
             "felső": gray[mask & (np.arange(side)[:, None] < cy)], "alsó": gray[mask & (np.arange(side)[:, None] >= cy)]}
    means = {k: float(v.mean()) for k, v in parts.items() if v.size}
    spread = max(abs(means["bal"] - means["jobb"]), abs(means["felső"] - means["alsó"])) / max(mean, 1.0)
    if spread > 0.4:
        checks.append(Check("even", BAD, "Egyenletes a fény", "Nagyon egyenetlen a megvilágítás (erős árnyék vagy oldalfény): "
                                                              "világítsd meg a táblát szemből, egyenletesen.", spread))
    elif spread > 0.25:
        checks.append(Check("even", WARN, "Egyenletes a fény", "Kicsit egyenetlen a fény: a tábla egyik oldala sötétebb.", spread))
    else:
        checks.append(Check("even", OK, "Egyenletes a fény", value=spread))
    return checks


# ───────────── a kép nyugodtsága ─────────────
class ShakeMeter:
    """A képkockák közti változásból ítéli meg, hogy a kamera rögzített-e (kézben tartott telefon remeg)."""

    def __init__(self, window=12):
        self.diffs, self.prev, self.window = [], None, window

    def feed(self, sq):
        small = cv2.resize(gray_of(sq), (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)
        if self.prev is not None:
            self.diffs = (self.diffs + [float(np.mean(np.abs(small - self.prev)))])[-self.window:]
        self.prev = small

    def check(self):
        if len(self.diffs) < 4:
            return Check("steady", NONE, "A kamera nem mozog")
        d = float(np.median(self.diffs))
        if d > 4.0:
            return Check("steady", BAD, "A kamera nem mozog", "A kép mozog: tedd állványra vagy támaszd meg a telefont/kamerát, "
                                                                "és ne tartsd kézben.", d)
        if d > 2.0:
            return Check("steady", WARN, "A kamera nem mozog", "A kép kissé remeg vagy villog: rögzítsd stabilabban.", d)
        return Check("steady", OK, "A kamera nem mozog", value=d)


# ───────────── a modell ellenőrzése ─────────────
def model_check(det, cal, conf=0.6, max_dev=0.025):
    """A modell látja-e a 4 kalibrációs pontot, és ott, ahol a felhasználó megjelölte. det: vision.Detections vagy None."""
    title = "A modell látja a 4 kalibrációs pontot"
    if det is None:
        return Check("model", NONE, title)
    seen = {n: p for n, p in det.cal.items() if p[2] >= conf and n in tr.CAL_NAMES}
    if len(seen) < 4:
        missing = ", ".join(n for n in tr.CAL_NAMES if n not in seen)
        return Check("model", BAD, title, f"A modell most nem látja ezeket a pontokat: {missing}. Javíts a fényen és a kamera "
                                          "állásán; ha így is marad, tanítsd be a modellt a saját kameraképeden.", len(seen))
    dev = max(math.hypot(seen[n][0] - cal.points[n][0], seen[n][1] - cal.points[n][1]) for n in tr.CAL_NAMES) / cal.size
    if dev > max_dev:
        return Check("model", WARN, title, "A modell és a kézzel megjelölt pontok eltérnek: ellenőrizd, hogy a négy jelet a "
                                           "megfelelő drótokhoz húztad-e.", dev)
    return Check("model", OK, title, value=dev)


# ───────────── a tábla automatikus megkeresése ─────────────
def estimate_points(sq):
    """A tábla megkeresése a piros-zöld dupla gyűrű alapján (a 20-as legyen felül). Visszaad: {pont: (x, y)} vagy None.
    Kiindulási becslés a kézi finomításhoz; a kalibráció érvényességét ellenőrzi."""
    size = sq.shape[0]
    hsv = cv2.cvtColor(sq, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    red = ((h < 10) | (h > 170)) & (s > 110) & (v > 70)
    green = (h > 38) & (h < 90) & (s > 70) & (v > 50)
    mask = ((red | green).astype(np.uint8)) * 255
    k = max(3, size // 80)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, labels, stat, cent = cv2.connectedComponentsWithStats(mask, connectivity=8)
    best, best_score = None, 0.0
    for i in range(1, n):
        bw, bh = stat[i, cv2.CC_STAT_WIDTH], stat[i, cv2.CC_STAT_HEIGHT]
        if min(bw, bh) < 0.3 * size or max(bw, bh) > 1.05 * size:
            continue
        roundness = min(bw, bh) / max(bw, bh)
        dist = math.hypot(cent[i][0] - size / 2, cent[i][1] - size / 2) / size
        score = roundness * (1.0 - min(dist, 0.9)) * stat[i, cv2.CC_STAT_AREA]
        if roundness > 0.5 and score > best_score:
            best, best_score = i, score
    if best is None:
        return None
    pts = np.column_stack(np.nonzero(labels == best))[:, ::-1].astype(np.float32)
    hull = cv2.convexHull(pts)
    if len(hull) < 5:
        return None
    (cx, cy), (w, hh), angle = cv2.fitEllipse(hull)
    th = math.radians(angle)
    u = np.array([math.cos(th), math.sin(th)]) * (w / 2)           # a „szélesség” tengely fél hossza, kép irányban
    v_ = np.array([-math.sin(th), math.cos(th)]) * (hh / 2)
    horiz, vert = (u, v_) if abs(u[0]) >= abs(v_[0]) else (v_, u)
    if horiz[0] < 0:
        horiz = -horiz
    if vert[1] < 0:
        vert = -vert
    out = {}
    for name in tr.CAL_NAMES:
        a = math.radians(db.CAL_ANGLES[name])
        p = np.array([cx, cy]) + math.sin(a) * horiz - math.cos(a) * vert
        out[name] = (float(p[0]), float(p[1]))
    gray = cv2.GaussianBlur(gray_of(sq), (5, 5), 0)
    out = refine_points(out, mask > 0, gray, size)
    return out if tr.Calibration(out, size).problem() is None else None


def ring_score(points, colored, size):
    """Mennyire fedi a kalibrációból vetített dupla gyűrű a kép piros-zöld sávját: a sáv közepén sok színes pont, a
    szélén kívül és belül kevés kell legyen."""
    cal = tr.Calibration(points, size)
    if cal.Hinv is None:
        return -1.0
    ang = np.linspace(0, 2 * math.pi, 120, endpoint=False)
    total = 0.0
    for r, w in ((166.0, 1.0), (176.0, -0.6), (156.0, -0.6)):
        px = db.apply_h(cal.Hinv, np.stack([r * np.cos(ang), r * np.sin(ang)], 1))
        x = np.clip(np.round(px[:, 0]).astype(int), 0, size - 1)
        y = np.clip(np.round(px[:, 1]).astype(int), 0, size - 1)
        total += w * float(colored[y, x].mean())
    return total


def wire_score(points, gray, size):
    """A szektorhatár-drótoknál mennyire vált a fényerő (0..1): jó kalibrációnál a drót két oldalán eltérő a szektor színe."""
    cal = tr.Calibration(points, size)
    if cal.Hinv is None:
        return 0.0
    pts = []
    for r in (135.0, 70.0):
        for k in range(20):
            for off in (-3.0, 3.0):
                a = math.radians(-9.0 + 18.0 * k + off)
                pts.append((r * math.sin(a), -r * math.cos(a)))
    px = db.apply_h(cal.Hinv, pts)
    x = np.clip(np.round(px[:, 0]).astype(int), 0, size - 1)
    y = np.clip(np.round(px[:, 1]).astype(int), 0, size - 1)
    g = gray[y, x].astype(np.float32).reshape(-1, 2)
    return float(np.mean(np.abs(g[:, 0] - g[:, 1]))) / 255.0


def _refine(points, colored, gray, size, seed):
    """A kezdeti (ellipszis-alapú) becslés finomítása véletlen kereséssel, durvától a finomig: először elmosott képen (nagy
    tűrés, hogy a távoli kezdőpont is a jó irányba húzzon), majd egyre élesebben. Mindig a legjobb rázást tartja meg, amelyben
    a vetített gyűrű a piros-zöld sávra, a szektordrótok pedig a fényerő-váltásokra esnek; a kiinduló helytől való
    eltávolodást kis büntetés mérsékli."""
    rng = np.random.default_rng(seed)
    start = dict(points)
    names = tr.CAL_NAMES
    best = dict(points)
    for blur, sigma, n in ((10.0, 0.03, 220), (5.0, 0.015, 220), (2.0, 0.006, 160), (0.0, 0.003, 120)):
        if blur:
            col_f = cv2.GaussianBlur(colored.astype(np.float32), (0, 0), blur * size / 640.0)
            gray_f = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), blur * size / 640.0)
        else:
            col_f, gray_f = colored.astype(np.float32), gray

        def value(pts):
            drift = sum(math.hypot(pts[nm][0] - start[nm][0], pts[nm][1] - start[nm][1]) for nm in names) / size
            return ring_score(pts, col_f, size) + 1.5 * wire_score(pts, gray_f, size) - 0.1 * drift

        cur = value(best)
        base = best
        for _ in range(n):
            jitter = rng.normal(0, sigma * size, (4, 2))
            trial = {nm: (base[nm][0] + jitter[i][0], base[nm][1] + jitter[i][1]) for i, nm in enumerate(names)}
            v = value(trial)
            if v > cur:
                best, cur = trial, v
    return best


def refine_points(points, colored, gray, size, seeds=(1, 2, 3)):
    """Több véletlen indítás közül a legjobb illeszkedésű (éles képen mért) eredményt adja."""
    gray_f = gray.astype(np.float32)
    col_f = colored.astype(np.float32)
    best, best_v = points, -1e9
    for seed in seeds:
        cand = _refine(points, colored, gray, size, seed)
        v = ring_score(cand, col_f, size) + 1.5 * wire_score(cand, gray_f, size)
        if v > best_v:
            best, best_v = cand, v
    return best
