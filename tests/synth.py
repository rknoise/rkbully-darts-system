"""Szintetikus tábla- és nyílképek a betanító teszteléséhez (valódi kamera nélkül).

A tábla a saját síkjában (mm) készül, és egy perspektivikus vetítéssel kerül a „kamera” képére, így a kalibráció,
a nyílkeresés és a tanítókészlet ugyanúgy ellenőrizhető, mint egy valódi, ferdén nézett táblánál."""
import math

import cv2
import numpy as np

import dartboard as db

SPAN = 220.0                                   # a síkrajz fél szélessége mm-ben
PLANE = 880                                    # a síkrajz képpontjai


def plane_to_px(size, tilt=0.0, shift=(0.0, 0.0), fill=0.39):
    """A tábla síkja (mm) -> kamerakép (pixel) homográfia. tilt: enyhe perspektíva; shift: a tábla eltolása a kép arányában."""
    scale = size * fill / db.R_DOUBLE[1]
    c = size / 2.0
    src = np.array([[-100, -100], [100, -100], [100, 100], [-100, 100]], np.float32)
    dst = src * scale + c
    dst[:, 0] += shift[0] * size
    dst[:, 1] += shift[1] * size
    dst[0] += (-tilt * size, 0)
    dst[1] += (tilt * size, 0)
    H = cv2.getPerspectiveTransform(src, dst)
    return H


def board_plane():
    """A tábla felülnézeti rajza (szürkeárnyalatos háttér + színes szektorok)."""
    img = np.full((PLANE, PLANE, 3), (30, 30, 30), np.uint8)
    k = PLANE / (2 * SPAN)
    c = PLANE / 2.0

    def pt(r, deg):
        a = math.radians(deg)
        return (c + r * k * math.sin(a), c - r * k * math.cos(a))

    for i in range(20):
        a0 = -9 + 18 * i
        for r0, r1, col_a, col_b in ((db.R_OUTER_BULL, db.R_TRIPLE[0], (200, 230, 240), (40, 40, 40)),
                                     (db.R_TRIPLE[0], db.R_TRIPLE[1], (60, 60, 200), (70, 160, 60)),
                                     (db.R_TRIPLE[1], db.R_DOUBLE[0], (200, 230, 240), (40, 40, 40)),
                                     (db.R_DOUBLE[0], db.R_DOUBLE[1], (60, 60, 200), (70, 160, 60))):
            col = col_a if i % 2 == 0 else col_b
            poly = [pt(r1, a0 + t) for t in np.linspace(0, 18, 8)] + [pt(r0, a0 + t) for t in np.linspace(18, 0, 8)]
            cv2.fillPoly(img, [np.round(np.array(poly)).astype(np.int32)], col, cv2.LINE_AA)
        p = pt(db.R_OUTER_BULL, a0)
        q = pt(db.R_DOUBLE[1], a0)
        cv2.line(img, tuple(int(v) for v in p), tuple(int(v) for v in q), (190, 190, 190), 1, cv2.LINE_AA)
    cv2.circle(img, (int(c), int(c)), int(db.R_OUTER_BULL * k), (70, 160, 60), -1, cv2.LINE_AA)
    cv2.circle(img, (int(c), int(c)), int(db.R_BULL * k), (60, 60, 200), -1, cv2.LINE_AA)
    return img


_PLANE = None


def render(size=640, tilt=0.03, shift=(0.0, 0.0), darts_mm=(), brightness=1.0, noise=0.0, seed=0, width=None, fill=0.39):
    """Egy kamerakép a táblával és a megadott nyilakkal (a nyílhegyek helye mm-ben).
    Visszaad: (kép, a nyílhegyek pixelben, a 4 kalibrációs pont pixelben, H). width: téglalap alakú (nem négyzetes) kép."""
    global _PLANE
    if _PLANE is None:
        _PLANE = board_plane()
    H0 = plane_to_px(size, tilt, shift, fill)
    k = PLANE / (2 * SPAN)
    to_plane = np.array([[k, 0, PLANE / 2.0], [0, k, PLANE / 2.0], [0, 0, 1]], np.float64)   # mm -> síkrajz pixel
    M = H0 @ np.linalg.inv(to_plane)                                                       # síkrajz pixel -> kamera
    img = cv2.warpPerspective(_PLANE, M, (size, size), flags=cv2.INTER_LINEAR, borderValue=(55, 50, 45))
    tips = []
    for x, y in darts_mm:
        tx, ty = db.apply_h(H0, [(x, y)])[0]
        tips.append((float(tx), float(ty)))
        # a nyíl: fémes szár a hegytől felfelé-balra, a végén színes toll
        ex, ey = tx - 0.055 * size, ty - 0.075 * size
        cv2.line(img, (int(tx), int(ty)), (int(ex), int(ey)), (185, 185, 185), max(3, size // 120), cv2.LINE_AA)
        cv2.circle(img, (int(ex), int(ey)), max(5, size // 70), (230, 200, 40), -1, cv2.LINE_AA)
    if brightness != 1.0:
        img = np.clip(img.astype(np.float32) * brightness, 0, 255).astype(np.uint8)
    if noise > 0:
        rng = np.random.default_rng(seed)
        img = np.clip(img.astype(np.float32) + rng.normal(0, noise, img.shape), 0, 255).astype(np.uint8)
    cal = {n: tuple(float(v) for v in db.apply_h(H0, [db.cal_point_mm(n)])[0]) for n in ("20", "3", "11", "6")}
    if width and width > size:
        pad = (width - size) // 2
        img = cv2.copyMakeBorder(img, 0, 0, pad, width - size - pad, cv2.BORDER_CONSTANT, value=(40, 40, 40))
    return img, tips, cal, H0
