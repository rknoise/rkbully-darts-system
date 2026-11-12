"""Darts tábla geometriája: pontszámítás, kalibráció (homográfia) és bizonytalanság-mérés.

Koordináta-rendszer a "tábla síkjában": a közép az origó, x jobbra, y lefelé, mm-ben.
A szögeket felülről, óramutató járásával megegyező irányban mérjük (a 20-as szektor közepe 0 fok).
"""
import math

import numpy as np

try:
    import cv2
except ImportError:          # a pontszámításhoz nem kell, csak a kalibrációhoz
    cv2 = None

# Szabványos (WDF/PDC) méretek mm-ben, a tábla közepétől mérve
R_BULL = 6.35                # dupla bull (50) külső sugara
R_OUTER_BULL = 15.9          # szimpla bull (25) külső sugara
R_TRIPLE = (99.0, 107.0)     # tripla gyűrű belső és külső sugara
R_DOUBLE = (162.0, 170.0)    # dupla gyűrű belső és külső sugara

SECTORS = (20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5)  # felülről, óramutató szerint

# Kalibrációs pontok: a külső dupla gyűrű széle egy-egy szektorhatár-drótnál.
# A név az a szektor, amelyik nevével a modell az adott pontot jelöli (DeepDarts / Dart-Sense jelölés):
#   "20": 5|20 drót   "6": 13|6 drót   "3": 17|3 drót   "11": 8|11 drót   ("9": 14|9 drót   "15": 10|15 drót)
CAL_ANGLES = {"20": -9.0, "6": 81.0, "3": 171.0, "11": 261.0, "9": 297.0, "15": 117.0}

_NOTATION = {"DB": (2, 25), "BULL": (2, 25), "SB": (1, 25), "OUTER": (1, 25), "25": (1, 25), "50": (2, 25),
             "MISS": (0, 0), "-": (0, 0), "–": (0, 0)}


def cal_point_mm(name):
    """A kalibrációs pont helye a tábla síkjában (mm)."""
    a = math.radians(CAL_ANGLES[str(name)])
    return (R_DOUBLE[1] * math.sin(a), -R_DOUBLE[1] * math.cos(a))


def score_at(x, y):
    """(szorzó, szám) a tábla síkjának (x, y) pontjára. Mellé: (0, 0); Bull: (2, 25); 25-ös: (1, 25)."""
    r = math.hypot(x, y)
    if r <= R_BULL:
        return (2, 25)
    if r <= R_OUTER_BULL:
        return (1, 25)
    if r > R_DOUBLE[1]:
        return (0, 0)
    ang = math.degrees(math.atan2(x, -y)) % 360.0
    num = SECTORS[int(((ang + 9.0) % 360.0) // 18.0)]
    if r > R_DOUBLE[0]:
        return (2, num)
    if R_TRIPLE[0] <= r <= R_TRIPLE[1]:
        return (3, num)
    return (1, num)


def margin_mm(x, y):
    """Milyen messze (mm) van a pont a legközelebbi pontszám-határtól (gyűrűtől vagy szektordróttól).
    Kicsi érték = a találat bizonytalan, érdemes megerősíttetni."""
    r = math.hypot(x, y)
    m = min(abs(r - b) for b in (R_BULL, R_OUTER_BULL, *R_TRIPLE, *R_DOUBLE))
    if R_OUTER_BULL < r <= R_DOUBLE[1] + 5.0:
        ang = math.degrees(math.atan2(x, -y)) % 360.0
        off = (ang + 9.0) % 18.0
        m = min(m, math.radians(min(off, 18.0 - off)) * r)
    return m


def notation(mult, num):
    """Gépi jelölés: S20, D16, T19, DB (bull), SB (25), MISS."""
    if mult == 0:
        return "MISS"
    if num == 25:
        return "DB" if mult == 2 else "SB"
    return "SDT"[mult - 1] + str(num)


def parse_notation(text):
    """Visszafejti a jelölést (S20, D16, T19, DB/BULL, SB/25/OUTER, MISS) -> (szorzó, szám), vagy None."""
    t = str(text).strip().upper()
    if t in _NOTATION:
        return _NOTATION[t]
    if len(t) >= 2 and t[0] in "SDT" and t[1:].isdigit():
        n = int(t[1:])
        if 1 <= n <= 20:
            return ("SDT".index(t[0]) + 1, n)
    return None


# ───────────── kalibráció ─────────────
def _fit(points_px, names):
    src = np.array([points_px[n] for n in names], dtype=np.float64)
    dst = np.array([cal_point_mm(n) for n in names], dtype=np.float64)
    H, _ = cv2.findHomography(src, dst, 0)
    if H is None or not np.all(np.isfinite(H)):
        return None, None
    return H, float(np.max(np.linalg.norm(apply_h(H, src) - dst, axis=1)))


def homography(points_px, max_err_mm=2.0):
    """Kép (pixel) -> tábla síkja (mm) transzformáció a felismert kalibrációs pontokból.

    points_px: {pontnév: (x, y)} – legalább 4 pont kell. Ha 5-6 pont van és az illesztés hibája nagy
    (egy pontot rosszul ismert fel a modell), a legrosszabb pontot elhagyja. Visszatér (H, max_hiba_mm) vagy (None, None).
    """
    names = [n for n in points_px if str(n) in CAL_ANGLES]
    if cv2 is None or len(names) < 4:
        return None, None
    H, err = _fit(points_px, names)
    while H is not None and err > max_err_mm and len(names) > 4:
        best = None
        for n in names:                                       # melyik pont elhagyásától lesz a legjobb az illesztés?
            rest = [m for m in names if m != n]
            h2, e2 = _fit(points_px, rest)
            if h2 is not None and (best is None or e2 < best[2]):
                best = (rest, h2, e2)
        if best is None or best[2] >= err:
            break
        names, H, err = best
    return (H, err) if H is not None else (None, None)


def apply_h(H, pts):
    """Pontok (N×2) átvetítése a H homográfiával."""
    p = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    q = np.hstack([p, np.ones((len(p), 1))]) @ np.asarray(H).T
    return q[:, :2] / q[:, 2:3]
