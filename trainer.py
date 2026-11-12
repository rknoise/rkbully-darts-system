"""Modell-betanító logika (a felülettől független): kalibráció kattintásokból, nyílkereső képkülönbséggel,
YOLO-adatkészlet, a tanítás indítása és a kész modell ellenőrzése.

Hogyan tanul a program a saját kamerádból:
  1. Egyszer megjelölöd a tábla négy kalibrációs pontját (20, 3, 11, 6) a kamera képén. Ebből homográfia lesz.
  2. Üres tábláról referenciaképet rögzít, aztán figyeli a kamerát. Amikor a kép megnyugszik, a referenciához képest
     megjelent új foltot nyílnak veszi, és javasolja a nyílhegy helyét. Te jóváhagyod, vagy a képre kattintva javítod.
  3. Minden jóváhagyott nyílból tanítóképet készít: a kép + a nyílhegyek + a 4 kalibrációs pont helye (YOLO formátum,
     pontosan olyan osztályokkal, amiket a vision.py vár: `dart`, `20`, `3`, `11`, `6`).
  4. Az ultralytics-szel betanít egy kis YOLO modellt, és megméri, mennyire találja meg a nyilakat a saját képeiden.

A modell ugyanazt a középső négyzetet látja, mint éles használatban (vision.Detector), ezért a betanítás is azon dolgozik.
"""
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import dartboard as db
import vision

try:
    import cv2
except ImportError:                                    # pragma: no cover
    cv2 = None

CAL_NAMES = ("20", "3", "11", "6")
CLASS_NAMES = ("dart",) + CAL_NAMES                   # a vision.YoloBackend ezeket az osztályokat keresi
CAL_BOX = 0.045                                        # a kalibrációs pont dobozának oldala a kép oldalának arányában
DART_BOX = 0.035                                       # a nyílhegy dobozának oldala
MIN_AREA, MAX_AREA = 0.00025, 0.012                    # egy nyíl foltja a kép területének arányában (kicsi: zaj, nagy: kéz)
MASK_MM = 260.0                                        # a táblától ennél messzebbi részt nem figyeljük (mint a vision.py)
MIN_SAMPLES = 30                                       # ennyi tanítóképnél enged tanítani
GOOD_DARTS = 150                                       # ennyi nyíl után várható használható modell

PRESETS = {                                            # név: (epoch, képméret, leírás)
    "fast": (40, 640, "Gyors"),
    "normal": (80, 640, "Normál"),
    "thorough": (150, 800, "Alapos"),
}


# ───────────── képkivágás és kalibráció ─────────────
def square_crop(frame):
    """A kép közepének négyzete, ahogy a vision.Detector vágja. Visszaad: (kép, x0, y0)."""
    h, w = frame.shape[:2]
    if w == h:
        return frame, 0, 0
    s = min(w, h)
    x0, y0 = (w - s) // 2, (h - s) // 2
    return frame[y0:y0 + s, x0:x0 + s], x0, y0


def initial_points(size, fill=0.39):
    """Kiinduló becslés a négy kalibrációs pontra: a tábla a négyzet közepén van, szabványos állásban (a 20-as felül)."""
    c, r = size / 2.0, size * fill
    out = {}
    for n in CAL_NAMES:
        a = math.radians(db.CAL_ANGLES[n])
        out[n] = (c + r * math.sin(a), c - r * math.cos(a))
    return out


class Calibration:
    """A kamera képe (pixel) és a tábla síkja (mm) közti megfeleltetés a négy megjelölt pontból."""

    def __init__(self, points, size):
        self.size = int(size)
        self.points = {n: (float(x), float(y)) for n, (x, y) in points.items() if n in CAL_NAMES}
        self.H = self.Hinv = None
        if len(self.points) == 4:
            H, _ = db.homography(self.points)
            if H is not None and np.all(np.isfinite(H)) and abs(np.linalg.det(H)) > 1e-12:
                self.H, self.Hinv = H, np.linalg.inv(H)

    def problem(self):
        """Miért nem használható a kalibráció (None = rendben)."""
        if self.H is None:
            return "A négy pontból nem számítható a tábla síkja: ne legyenek egy vonalban vagy egymás mellett."
        pts = np.array([self.points[n] for n in CAL_NAMES], dtype=np.float32)
        if (pts < -0.05 * self.size).any() or (pts > 1.05 * self.size).any():
            return "Egy pont a képen kívül van."
        center = pts.mean(0)
        order = np.argsort(np.arctan2(pts[:, 1] - center[1], pts[:, 0] - center[0]))
        if cv2.contourArea(pts[order]) < 0.04 * self.size ** 2:
            return "A négy pont túl közel van egymáshoz: a tábla kitölti a képet?"
        if not cv2.isContourConvex(pts[order].reshape(-1, 1, 2)):
            return "A négy pont nem alkot kiterjedt négyszöget: ellenőrizd, melyik pont melyik drótnál van."
        return None

    def to_mm(self, x, y):
        return tuple(float(v) for v in db.apply_h(self.H, [(x, y)])[0])

    def to_px(self, mx, my):
        return tuple(float(v) for v in db.apply_h(self.Hinv, [(mx, my)])[0])

    def board_mask(self, margin_mm=MASK_MM):
        """Fehér folt a képen ott, ahol a tábla (és a nyilak repülési tere) van; máshol fekete."""
        mask = np.zeros((self.size, self.size), np.uint8)
        if self.Hinv is None:
            mask[:] = 255
            return mask
        ang = np.linspace(0, 2 * math.pi, 120, endpoint=False)
        ring = np.stack([margin_mm * np.cos(ang), margin_mm * np.sin(ang)], 1)
        poly = db.apply_h(self.Hinv, ring)
        cv2.fillPoly(mask, [np.round(poly).astype(np.int32)], 255)
        return mask

    def center_px(self):
        return self.to_px(0.0, 0.0) if self.Hinv is not None else (self.size / 2.0, self.size / 2.0)

    def shapes(self, n=180):
        """A tábla rajza a képre vetítve (ellenőrzéshez): gyűrűk és szektordrótok, pixelben."""
        if self.Hinv is None:
            return [], []
        ang = np.linspace(0, 2 * math.pi, n)
        rings = []
        for r in (db.R_BULL, db.R_OUTER_BULL, db.R_TRIPLE[0], db.R_TRIPLE[1], db.R_DOUBLE[0], db.R_DOUBLE[1]):
            rings.append(db.apply_h(self.Hinv, np.stack([r * np.cos(ang), r * np.sin(ang)], 1)))
        wires = []
        for k in range(20):
            a = math.radians(-9.0 + 18.0 * k)
            p = [(r * math.sin(a), -r * math.cos(a)) for r in (db.R_OUTER_BULL, db.R_DOUBLE[1])]
            wires.append(db.apply_h(self.Hinv, p))
        return rings, wires

    def dump(self):
        return {"size": self.size, "points": {n: list(p) for n, p in self.points.items()}}

    @classmethod
    def load(cls, data):
        return cls({n: tuple(p) for n, p in data["points"].items()}, data["size"])


# ───────────── nyílkeresés képkülönbséggel ─────────────
def prep(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return cv2.GaussianBlur(gray, (5, 5), 0)


def diff_binary(ref, cur, mask=None, thr=30):
    """Fehér pontok, ahol a mostani kép érdemben eltér az üres tábla képétől. A fényerő-eltolódást kiegyenlíti."""
    cur_f = cur.astype(np.float32)
    if mask is not None:
        m = mask > 0
        if m.any():
            rm, cm = float(ref[m].mean()), float(cur_f[m].mean())
            if cm > 1.0:
                cur_f *= rm / cm
    out = (cv2.absdiff(ref.astype(np.float32), cur_f) > thr).astype(np.uint8) * 255
    if mask is not None:
        out = cv2.bitwise_and(out, mask)
    out = cv2.morphologyEx(out, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return cv2.morphologyEx(out, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))


def find_blobs(binary, size):
    """A zajnál nagyobb foltok: [{"centroid", "area", "pts", "too_big"}]."""
    n, labels, stats, cents = cv2.connectedComponentsWithStats(binary, connectivity=8)
    lo, hi = MIN_AREA * size * size, MAX_AREA * size * size
    out = []
    for i in range(1, n):
        a = int(stats[i, cv2.CC_STAT_AREA])
        if a < lo:
            continue
        ys, xs = np.nonzero(labels == i)
        out.append({"centroid": (float(cents[i][0]), float(cents[i][1])), "area": a,
                    "pts": np.stack([xs, ys], 1).astype(np.float32), "too_big": a > hi})
    return out


def propose_tip(pts, center, mean_dir=None):
    """A nyílfolt két végpontja közül a nyílhegy. Ha már tudjuk, merre áll a hegy a folt közepéhez képest (a korábbi
    jóváhagyásokból), azt követi; addig a tábla közepéhez közelebbi véget választja."""
    c = pts.mean(0)
    if len(pts) < 3:
        return float(c[0]), float(c[1])
    w, v = np.linalg.eigh(np.cov((pts - c).T))
    proj = (pts - c) @ v[:, int(np.argmax(w))]
    a, b = pts[int(np.argmin(proj))], pts[int(np.argmax(proj))]
    if mean_dir is not None:
        pick = a if float(np.dot(a - c, mean_dir)) > float(np.dot(b - c, mean_dir)) else b
    else:
        pick = a if np.linalg.norm(a - np.asarray(center)) < np.linalg.norm(b - np.asarray(center)) else b
    return float(pick[0]), float(pick[1])


@dataclass
class Candidate:
    """Egy új, még el nem bírált folt: a javasolt nyílhegy helye és a kép, amelyen látszik."""
    image: np.ndarray
    tip: tuple
    centroid: tuple
    area: int
    unresolved: int = 0               # még hány további új folt van ugyanezen a képen
    pts: np.ndarray = None


@dataclass
class Sample:
    """Egy tanítókép: a kép, a nyílhegyek és a kalibrációs pontok pixelben (a négyzetes képen)."""
    image: np.ndarray
    darts: list
    cal: dict
    round_id: int = 0


class Collector:
    """A kamera figyelése: üres tábla referencia + nyugodt képnél új foltok keresése. Az idő kívülről jön (tesztelhető)."""

    def __init__(self, calibration, stable_s=0.8, stable_diff=3.0, thr=30, recheck_s=0.5):
        self.cal, self.size = calibration, calibration.size
        self.stable_s, self.stable_diff, self.thr, self.recheck_s = stable_s, stable_diff, thr, recheck_s
        self.mask = calibration.board_mask()
        self.center = calibration.center_px()
        self.empty = None
        self.known, self.ignored, self.tip_dirs = [], [], []
        self.candidate, self.round_id = None, 0
        self.tainted = False                           # összeért nyilak a körben: ebből a körből nem készül tanítókép
        self.state, self.message = "no_reference", ""
        self._prev, self._still, self._last = None, None, None

    # ── referencia ──
    def set_empty(self, img):
        """Az üres tábla képe. Új referenciánál a körben lévő nyilak listája kiürül."""
        self.empty = prep(img)
        self.known, self.ignored, self.candidate = [], [], None
        self.tainted = False
        self._prev, self._still, self._last = None, None, None
        self.state, self.message = "watching", ""

    def mean_dir(self):
        """Merre áll a nyílhegy a folt közepéhez képest (egységvektor), ha a jóváhagyások elég egyirányúak."""
        if len(self.tip_dirs) < 3:
            return None
        m = np.mean(self.tip_dirs, axis=0)
        n = float(np.linalg.norm(m))
        return m / n if n > 0.5 else None

    # ── képfolyam ──
    def feed(self, img, t):
        """Egy új képkocka. Visszaad: események [("candidate", Candidate) | ("removed",) | ("busy", szöveg)].
        Az állapot (`state`) mindig lekérdezhető: no_reference, watching, moving, candidate, busy, tainted."""
        if self.empty is None:
            return []
        gray = prep(img)
        small = cv2.resize(gray, (96, 96), interpolation=cv2.INTER_AREA).astype(np.float32)
        moved = self._prev is None or float(np.mean(np.abs(small - self._prev))) > self.stable_diff
        self._prev = small
        if moved:
            self._still, self._last = None, None
            self.candidate = None                     # a jelenet megváltozott: a függő javaslat elavult
            self.state, self.message = "moving", ""
            return []
        if self._still is None:
            self._still = t
        if t - self._still < self.stable_s:
            return []
        if self._last is not None and t - self._last < self.recheck_s:
            return []
        self._last = t                                # nyugodt képnél rendszeresen újraelemzünk: a lassan érkező nyilat is látjuk
        return self._analyze(img, gray)

    def _set_busy(self, state, text):
        changed = self.state != state
        self.state, self.message, self.candidate = state, text, None
        return [("busy", text)] if changed else []

    def _analyze(self, img, gray):
        blobs = find_blobs(diff_binary(self.empty, gray, self.mask, self.thr), self.size)
        r = 0.04 * self.size

        def near(a, b):
            return math.hypot(a[0] - b[0], a[1] - b[1]) <= r

        had = bool(self.known)
        self.known = [k for k in self.known if any(near(b["centroid"], k["centroid"]) for b in blobs)]
        self.ignored = [e for e in self.ignored if any(near(b["centroid"], e["centroid"]) for b in blobs)]
        if had and not self.known and not blobs:
            self.round_id += 1
            self.tainted = False
            self.state, self.message, self.candidate = "watching", "", None
            return [("removed",)]
        if any(b["too_big"] for b in blobs):
            return self._set_busy("busy", "Nagy tárgy van a táblán (kéz?). Várok, amíg elvonul.")
        typical = float(np.median([k["area"] for k in self.known])) if self.known else None
        if typical is not None and any(b["area"] > 1.9 * typical for b in blobs):
            self.tainted = True                       # két nyíl összeért: a címkék nem lennének megbízhatóak
        if self.tainted:
            return self._set_busy("tainted", "Két nyíl összeért, ebből a körből nem készül tanítókép. "
                                             "Húzd ki a nyilakat, és dobj újra.")
        new = [b for b in blobs if not any(near(b["centroid"], k["centroid"]) for k in self.known)
               and not any(near(b["centroid"], e["centroid"]) for e in self.ignored)]
        if not new:
            self.state, self.message, self.candidate = "watching", "", None
            return []
        new.sort(key=lambda b: -b["area"])
        b = new[0]
        c = self.candidate
        if c is not None and near(b["centroid"], c.centroid):     # ugyanaz a jelölt: a felhasználó kijelölését nem írjuk felül
            c.unresolved = len(new) - 1
            self.state, self.message = "candidate", ""
            return []
        tip = propose_tip(b["pts"], self.center, self.mean_dir())
        self.candidate = Candidate(img.copy(), tip, b["centroid"], b["area"], len(new) - 1, b["pts"])
        self.state, self.message = "candidate", ""
        return [("candidate", self.candidate)]

    # ── döntés ──
    def accept(self, tip=None):
        """Jóváhagyja a függő jelöltet. A javasolt helyett `tip` (kattintással javított hely) is megadható.
        Visszaad egy Sample-t, ha a képen minden folt el van intézve (különben None, mert lenne címkézetlen nyíl)."""
        c = self.candidate
        if c is None:
            return None
        tip = (float(tip[0]), float(tip[1])) if tip is not None else c.tip
        self.known.append({"tip": tip, "centroid": c.centroid, "area": c.area})
        v = np.array(tip, dtype=np.float64) - np.array(c.centroid)
        if float(np.linalg.norm(v)) > 3.0:
            self.tip_dirs.append(v / np.linalg.norm(v))
        self.candidate = None
        self._last = None                              # ha van még új folt ugyanezen a képen, a következő képkocka újra elemzi
        if c.unresolved > 0:
            return None
        return Sample(c.image, [k["tip"] for k in self.known], dict(self.cal.points), self.round_id)

    def reject(self):
        """„Nem nyíl” (árnyék, kéz, fényvisszaverődés): a folt többé nem jelölt."""
        c = self.candidate
        if c is None:
            return
        self.ignored.append({"centroid": c.centroid})
        self.candidate = None
        self._last = None

    def undo(self):
        """Az utolsó jóváhagyott nyíl visszavonása: a nyíl újra jelölt lesz."""
        if self.known:
            self.known.pop()
            if self.tip_dirs:
                self.tip_dirs.pop()
            self._last = None


def coverage(darts_mm):
    """A nyilak eloszlása 12 zónában (4 negyed × 3 sugársáv): {(negyed, sáv): darab}. A gyenge zónák keresésére."""
    grid = {(q, b): 0 for q in range(4) for b in range(3)}
    for x, y in darts_mm:
        r = math.hypot(x, y)
        if r > db.R_DOUBLE[1] + 5:
            continue
        q = int((math.degrees(math.atan2(x, -y)) % 360) // 90)
        grid[(q, 0 if r < 60 else 1 if r < 120 else 2)] += 1
    return grid


ZONE_NAMES = {0: "jobb felső", 1: "jobb alsó", 2: "bal alsó", 3: "bal felső"}
RING_NAMES = {0: "belső", 1: "középső", 2: "külső"}


def coverage_hint(darts_mm, minimum=4, start=20):
    """Szöveges tanács: hová dobj még. Az első `start` nyílig nem szól."""
    if len(darts_mm) < start:
        return ""
    grid = coverage(darts_mm)
    thin = [f"{ZONE_NAMES[q]} negyed, {RING_NAMES[b]} sáv" for (q, b), n in sorted(grid.items()) if n < minimum]
    return ("Dobj még ide: " + "; ".join(thin[:4])) if thin else "Szép az eloszlás."


# ───────────── tanítókészlet ─────────────
class DatasetStore:
    """A jóváhagyott tanítóképek mappája. Minden kép azonnal lemezre kerül, így megszakadás után is megvan, és egy
    későbbi alkalommal tovább gyűjthető. Mappa: images/*.jpg, labels/*.txt (YOLO), meta/*.json."""

    def __init__(self, folder):
        self.folder = Path(folder)
        for sub in ("images", "labels", "meta"):
            (self.folder / sub).mkdir(parents=True, exist_ok=True)

    def ids(self):
        return sorted(p.stem for p in (self.folder / "meta").glob("s*.json"))

    def _next_id(self):
        ids = self.ids()
        return f"s{int(ids[-1][1:]) + 1:05d}" if ids else "s00001"

    def label_lines(self, darts, cal, size):
        lines = []
        for x, y in darts:
            lines.append(f"0 {x / size:.6f} {y / size:.6f} {DART_BOX:.6f} {DART_BOX:.6f}")
        for n in CAL_NAMES:
            if n in cal:
                x, y = cal[n]
                lines.append(f"{CLASS_NAMES.index(n)} {x / size:.6f} {y / size:.6f} {CAL_BOX:.6f} {CAL_BOX:.6f}")
        return lines

    def add(self, sample, session=""):
        h, w = sample.image.shape[:2]
        sid = self._next_id()
        ok, buf = cv2.imencode(".jpg", sample.image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise ValueError("A kép mentése nem sikerült.")
        (self.folder / "images" / f"{sid}.jpg").write_bytes(buf.tobytes())
        (self.folder / "labels" / f"{sid}.txt").write_text("\n".join(self.label_lines(sample.darts, sample.cal, w)) + "\n", encoding="utf-8")
        meta = {"id": sid, "size": int(w), "round": f"{session}:{sample.round_id}", "darts": [list(d) for d in sample.darts],
                "cal": {n: list(p) for n, p in sample.cal.items()}, "t": time.time()}
        (self.folder / "meta" / f"{sid}.json").write_text(json.dumps(meta), encoding="utf-8")
        return sid

    def remove(self, sid):
        for sub, ext in (("images", ".jpg"), ("labels", ".txt"), ("meta", ".json")):
            try:
                (self.folder / sub / f"{sid}{ext}").unlink()
            except OSError:
                pass

    def remove_last(self):
        ids = self.ids()
        if ids:
            self.remove(ids[-1])
            return ids[-1]
        return None

    def meta(self, sid):
        return json.loads((self.folder / "meta" / f"{sid}.json").read_text(encoding="utf-8"))

    def all_meta(self):
        return [self.meta(i) for i in self.ids()]

    def count(self):
        return len(self.ids())

    def n_darts(self):
        """Hány nyílhegy-címke van összesen. (A körönként növekvő mintákban ugyanaz a nyíl többször szerepel, ezért a
        legtöbb nyilat tartalmazó mintákat számoljuk köreként.)"""
        best = {}
        for m in self.all_meta():
            best[m["round"]] = max(best.get(m["round"], 0), len(m["darts"]))
        return sum(best.values())

    def build(self, out_dir=None):
        """A tanítás bemenete: train.txt / val.txt (képlisták) és data.yaml. A validáció körönként van elkülönítve
        (minden 5. kör), így a modell nem a már látott képen ellenőrződik. Visszaad: (data.yaml útvonal, tanító, validációs db)."""
        out = Path(out_dir or self.folder)
        metas = self.all_meta()
        if not metas:
            raise ValueError("Nincs tanítókép.")
        rounds = []
        for m in metas:
            if m["round"] not in rounds:
                rounds.append(m["round"])
        val_rounds = {r for i, r in enumerate(rounds) if i % 5 == 4} or {rounds[-1]}
        if len(rounds) == 1:
            val_rounds = set()
        train, val = [], []
        for m in metas:
            path = (self.folder / "images" / f"{m['id']}.jpg").resolve().as_posix()
            (val if m["round"] in val_rounds else train).append(path)
        if not val:                                                  # egyetlen kör: ugyanaz a készlet ellenőriz is
            val = list(train)
        (out / "train.txt").write_text("\n".join(train) + "\n", encoding="utf-8")
        (out / "val.txt").write_text("\n".join(val) + "\n", encoding="utf-8")
        names = "\n".join(f"  {i}: '{n}'" for i, n in enumerate(CLASS_NAMES))
        yaml = (f"path: {out.resolve().as_posix()}\ntrain: {(out / 'train.txt').resolve().as_posix()}\n"
                f"val: {(out / 'val.txt').resolve().as_posix()}\nnames:\n{names}\n")
        (out / "data.yaml").write_text(yaml, encoding="utf-8")
        return out / "data.yaml", len(train), len(val)


# ───────────── tanítás ─────────────
def python_exe(exe=None):
    """A konzolos Python (a parancsikon pythonw.exe-je nem ír ki semmit, így a tanítás üzeneteit nem látnánk)."""
    exe = str(exe or sys.executable)
    return exe[:-len("pythonw.exe")] + "python.exe" if exe.lower().endswith("pythonw.exe") else exe


def ultralytics_available():
    import importlib.util
    return importlib.util.find_spec("ultralytics") is not None


BASE_WEIGHTS = "yolov8n.pt"                                      # a tanítás kiinduló súlyai (COCO-n előtanított, ~6 MB)


def base_weights(app_dir=None):
    """A kiinduló súlyfájl útvonala: ha az offline telepítő a `base` mappába tette (internet nélküli tanításhoz), azt használja;
    különben a fájlnevet adja, amit az ultralytics az első tanításkor magától letölt."""
    if app_dir:
        local = Path(app_dir) / "base" / BASE_WEIGHTS
        if local.is_file():
            return str(local)
    return BASE_WEIGHTS


def job_config(data_yaml, preset, project, name="rkbully", base=BASE_WEIGHTS):
    epochs, imgsz, _ = PRESETS[preset]
    return {"base": base, "data": str(data_yaml), "epochs": epochs, "imgsz": imgsz, "batch": 8, "project": str(project),
            "name": name, "patience": 30}


def parse_line(line):
    """A tanító script üzeneteinek értelmezése: ("epoch", n, összes, mAP) | ("done", útvonal) | ("error", szöveg) | None."""
    line = line.strip()
    if line.startswith("RKBULLY_EPOCH|"):
        parts = line.split("|")
        try:
            return ("epoch", int(parts[1]), int(parts[2]), float(parts[3]) if len(parts) > 3 and parts[3] else None)
        except (ValueError, IndexError):
            return None
    if line.startswith("RKBULLY_DONE|"):
        return ("done", line.split("|", 1)[1])
    if line.startswith("RKBULLY_ERROR|"):
        return ("error", line.split("|", 1)[1])
    return None


class TrainJob:
    """A tanítás külön folyamatban fut (a felület közben él, és megszakítható). A kimenet sorait a `poll` adja vissza."""

    def __init__(self, command, cwd=None):
        self.command, self.cwd = list(command), cwd
        self.proc, self.lines, self._thread = None, queue.Queue(), None
        self.returncode = None

    def start(self):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        flags = 0x08000000 if sys.platform == "win32" else 0            # CREATE_NO_WINDOW: ne villanjon fel konzolablak
        self.proc = subprocess.Popen(self.command, cwd=self.cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=flags)
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self):
        # a tqdm folyamatjelzője kocsivissza-jelekkel frissül: azokat is sortörésnek vesszük
        buf = ""
        while True:
            ch = self.proc.stdout.read(1)
            if ch == "":
                break
            if ch in "\r\n":
                if buf.strip():
                    self.lines.put(buf)
                buf = ""
            else:
                buf += ch
        if buf.strip():
            self.lines.put(buf)
        try:
            self.proc.stdout.close()
        except OSError:
            pass

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.lines.get_nowait())
            except queue.Empty:
                break
        if self.proc is not None and self.returncode is None:
            self.returncode = self.proc.poll()
        return out

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def finished(self):
        """Lejárt a folyamat, és az utolsó sorokat is elolvastuk."""
        return self.proc is not None and self.proc.poll() is not None and not self._thread.is_alive() and self.lines.empty()

    def cancel(self):
        if self.running:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# ───────────── a kész modell ellenőrzése ─────────────
def evaluate(backend, items, match_frac=0.02):
    """A modell megméri magát a címkézett képeken. items: [(kép, [nyílhegyek px], {pont: (x, y)})].
    Visszaad: {"darts": hány címke, "found": hányat talált meg, "false": hány felesleges találat, "err_px": átlagos hiba,
    "err_mm": átlagos hiba mm-ben (a kalibrációból), "cal_ok": hány képen látta mind a 4 pontot}."""
    total = found = false = cal_ok = 0
    errs, errs_mm = [], []
    for img, tips, cal in items:
        size = img.shape[0]
        det = backend.detect(img)
        total += len(tips)
        c = Calibration(cal, size)
        have = [n for n in CAL_NAMES if n in det.cal]
        cal_ok += len(have) == 4
        used = set()
        for tx, ty in tips:
            best, best_d = None, match_frac * size
            for i, (x, y, _) in enumerate(det.darts):
                d = math.hypot(x - tx, y - ty)
                if i not in used and d <= best_d:
                    best, best_d = i, d
            if best is not None:
                used.add(best)
                found += 1
                errs.append(best_d)
                if c.H is not None:
                    px, py = det.darts[best][0], det.darts[best][1]
                    a, b = c.to_mm(px, py), c.to_mm(tx, ty)
                    errs_mm.append(math.hypot(a[0] - b[0], a[1] - b[1]))
        false += len(det.darts) - len(used)
    return {"darts": total, "found": found, "false": false, "cal_ok": cal_ok, "images": len(items),
            "err_px": float(np.mean(errs)) if errs else None, "err_mm": float(np.mean(errs_mm)) if errs_mm else None}


def verdict(result):
    """Rövid, érthető értékelés a mérésből."""
    if not result["darts"]:
        return "Nincs mivel összehasonlítani."
    rate = result["found"] / result["darts"]
    cal = result["cal_ok"] / max(result["images"], 1)
    mm = result["err_mm"]
    text = (f"A {result['darts']} nyílból {result['found']}-t megtalált ({rate:.0%}), a kalibrációs pontokat "
            f"{cal:.0%}-ban látta mind a négyet" + (f", a nyílhegy átlagos hibája {mm:.1f} mm." if mm is not None else "."))
    if rate >= 0.9 and cal >= 0.9 and (mm is None or mm <= 3.0):
        return "Jó modell. " + text
    if rate >= 0.7 and cal >= 0.7:
        return "Használható, de több gyűjtéssel javulna. " + text
    return "Még gyenge: gyűjts több képet, és tanítsd újra. " + text


def estimate_remaining(epoch_times, done, total):
    """Hátralévő idő másodpercben a már lefutott epochok átlagából (None, ha még nincs adat)."""
    if not epoch_times or done >= total:
        return 0.0 if done >= total else None
    recent = epoch_times[-5:]
    return (total - done) * sum(recent) / len(recent)


# ───────────── kamerakép a betanítóhoz ─────────────
class FrameSource:
    """Saját kamera-kapcsolat (ha a főablakban még nincs ilyen kamera): háttérszál olvassa a képet."""

    def __init__(self, text):
        self.src = vision.normalize_source(text)
        self.frame, self.alive = None, True
        threading.Thread(target=self._run, daemon=True).start()

    def _open(self):
        if isinstance(self.src, int) and sys.platform == "win32":
            cap = cv2.VideoCapture(self.src, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(self.src)
        if isinstance(self.src, int):
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        return cap

    def _run(self):
        cap, fails = self._open(), 0
        while self.alive:
            ok, f = cap.read() if cap.isOpened() else (False, None)
            if ok:
                self.frame, fails = f, 0
            else:
                self.frame, fails = None, fails + 1
                time.sleep(0.3)
                if fails % 10 == 0:
                    cap.release()
                    cap = self._open()
        cap.release()

    def stop(self):
        self.alive = False
