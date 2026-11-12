"""Kamerás dobásfelismerés.

Folyamat:  kamerakép -> YOLO-modell (nyílhegyek + kalibrációs pontok) -> homográfia (kép -> tábla síkja, mm)
           -> pontszám -> dobáskövető (új nyíl észlelése, a nyilak kihúzásának észlelése).

A modell: DeepDarts / Dart-Sense típusú YOLO (.pt). Osztályok: 'dart' és kalibrációs pontok ('20', '3', '11', '6', ...).
Az `ultralytics` csomag csak a modell betöltésekor kell (késői import), nélküle is indul az alkalmazás.
A modell-fájlt NEM tartalmazza a program: a letöltés és a használat feltételeit a README írja le.
"""
import math
import os
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

import dartboard as db

BOARD_LIMIT_MM = 260.0       # ennél messzebb a tábla közepétől talált "nyilat" figyelmen kívül hagyjuk
FAR_MISS_MM = 240.0          # a dupla gyűrűn kívül, de ennél közelebb (a számgyűrű széléig) leszúrt nyíl: biztos "mellé"; távolabb: megerősítést kér


# ───────────── adatok ─────────────
@dataclass
class Detections:
    """Egy képkocka nyers felismerése, a bemeneti kép pixelkoordinátáiban."""
    cal: dict = field(default_factory=dict)     # pontnév -> (x, y, biztonság)
    darts: list = field(default_factory=list)   # [(x, y, biztonság)] – a nyílhegy helye


@dataclass
class Throw:
    mult: int
    num: int
    x: float                  # a tábla síkjában, mm
    y: float
    margin: float             # távolság a legközelebbi pontszám-határtól, mm
    conf: float
    uncertain: bool           # érdemes megerősíttetni (határ közeli, gyenge felismerés vagy pontatlan kalibráció)
    cal_err: float = 0.0      # a kalibráció visszavetítési hibája (mm), az összevetés súlyozásához
    sources: int = 1          # hány kamera látta (két kamera összevetése után 2)
    spread: float = 0.0       # a két kamera becslése közti eltérés (mm)
    reason: str = ""          # rövid indok, ha az összevetés miatt bizonytalan

    @property
    def text(self):
        return db.notation(self.mult, self.num)

    @property
    def note(self):
        """Rövid megjegyzés a jóváhagyó panelnek."""
        if self.reason:
            return self.reason
        return f"{self.sources} kamera egyezik" if self.sources >= 2 else ""


@dataclass
class Removed:
    """A nyilakat kihúzták a táblából."""


# ───────────── modell ─────────────
class YoloBackend:
    """Ultralytics YOLO (.pt) modell DeepDarts / Dart-Sense osztályokkal."""

    def __init__(self, path, imgsz=None):
        from ultralytics import YOLO            # késői import: a program enélkül is elindul
        self.model = YOLO(str(path))
        names = {int(i): str(n) for i, n in self.model.names.items()}
        self.cal_ids = {i: n for i, n in names.items() if n in db.CAL_ANGLES}
        self.dart_ids = {i for i, n in names.items() if n.lower() == "dart"}
        if not self.dart_ids or len(self.cal_ids) < 4:
            raise ValueError("A modell osztályai nem megfelelőek: kell egy 'dart' és legalább 4 kalibrációs pont "
                             "(20, 3, 11, 6). A modell osztályai: " + ", ".join(names.values()))
        self.imgsz = int(imgsz or (getattr(self.model, "overrides", {}) or {}).get("imgsz") or 800)
        self.lock = threading.Lock()            # több kamera is használhatja ugyanazt a modellt

    def detect(self, image):
        with self.lock:
            res = self.model.predict(image, imgsz=self.imgsz, conf=0.25, verbose=False)[0]
        det = Detections()
        if res.boxes is None or len(res.boxes) == 0:
            return det
        xywh = res.boxes.xywh.cpu().numpy()
        cls = res.boxes.cls.cpu().numpy().astype(int)
        conf = res.boxes.conf.cpu().numpy()
        for (x, y, _, _), c, p in zip(xywh, cls, conf):
            if c in self.dart_ids:
                det.darts.append((float(x), float(y), float(p)))
            elif c in self.cal_ids:
                name = self.cal_ids[c]
                if name not in det.cal or p > det.cal[name][2]:
                    det.cal[name] = (float(x), float(y), float(p))
        return det


def find_model(app_dir, saved=None):
    """Megkeresi a modellfájlt: RKBULLY_MODEL környezeti változó, mentett útvonal, majd a models mappa."""
    cands = [os.environ.get("RKBULLY_MODEL"), saved]
    for c in cands:
        if c and Path(c).is_file():
            return Path(c)
    folder = Path(app_dir) / "models"
    if folder.is_dir():
        found = sorted(folder.glob("*.pt"))
        if found:
            return found[0]
    return None


def normalize_source(text):
    """A beírt szövegből kamera-forrás: szám = USB webkamera, cím = telefon IP-kamera.

    '0' -> 0;  '192.168.0.56:8080' -> 'http://192.168.0.56:8080/video';  'http://...' -> változatlan.
    """
    t = str(text).strip()
    if t.isdigit():
        return int(t)
    if "://" not in t:
        t = "http://" + t
    rest = t.split("://", 1)[1]
    if "/" not in rest:                         # csak cím, útvonal nélkül: az IP Webcam alkalmazás /video címe
        t += "/video"
    return t


# ───────────── kalibráció követése ─────────────
class CalibrationTracker:
    """A kalibrációs pontok helyét több képkockán át mediánnal simítja, és belőle homográfiát számol.
    Rögzített kamerát feltételez: ha egy pont egy ideig nem látszik, az utolsó jó kalibrációt használja tovább."""

    def __init__(self, history=10, min_hits=3):
        self.hist = {n: deque(maxlen=history) for n in db.CAL_ANGLES}
        self.min_hits = min_hits
        self.H = None
        self.err = None             # legnagyobb visszavetítési hiba (mm)
        self.points = {}            # a most használt (simított) pontok, kép pixelben

    def update(self, cal):
        for name, d in self.hist.items():
            d.append((cal[name][0], cal[name][1]) if name in cal else None)
        pts = {}
        for name, d in self.hist.items():
            obs = [p for p in d if p is not None]
            if len(obs) >= self.min_hits:
                pts[name] = tuple(float(v) for v in np.median(np.array(obs), axis=0))
        self.points = pts
        H, err = db.homography(pts)
        if H is not None:
            self.H, self.err = H, err
        return self.H, self.err


# ───────────── dobáskövetés ─────────────
class DartTracker:
    """A tábla síkjában talált nyílhegyekből eseményeket készít: új dobás, nyilak kihúzva.

    Egy nyíl akkor számít leszállt dobásnak, ha több egymás utáni képkockán ugyanott látszik
    (így a repülő nyíl és az egyszeri téves felismerés nem számít). A már leírt nyilakat helyük alapján
    ismeri fel, így egy nyíl csak egyszer ad dobást. Ha a nyilak eltűnnek a tábláról, új kör kezdődik.
    """

    def __init__(self, match_mm=6.0, confirm_hits=4, window=6, clear_frames=6, max_darts=3,
                 uncertain_margin_mm=3.0, low_conf=0.4, max_cal_err_mm=3.0, twin_mm=10.0):
        self.match_mm, self.confirm_hits, self.window = match_mm, confirm_hits, window
        self.twin_mm = twin_mm      # egymáshoz ennél közelebbi felismerésekből csak a legbiztosabbat tartjuk meg
        self.clear_frames, self.max_darts = clear_frames, max_darts
        self.uncertain_margin_mm, self.low_conf, self.max_cal_err_mm = uncertain_margin_mm, low_conf, max_cal_err_mm
        self.reset()

    def reset(self):
        self.tracks, self.known, self.empty = [], [], 0

    def update(self, dets, cal_err=0.0, n_cal=4):
        """dets: [(x_mm, y_mm, biztonság)] ebben a képkockában. Visszatér: események listája."""
        events = []
        for t in self.tracks:
            t["seen"] = False
        kept = []                    # a modell néha ugyanahhoz a nyílhoz két, közeli találatot ad (pl. tollszár): az ikreket elhagyjuk
        for d in sorted(dets, key=lambda d: -d[2]):
            if all(math.hypot(d[0] - k[0], d[1] - k[1]) > self.twin_mm for k in kept):
                kept.append(d)
        dets = kept
        for x, y, c in sorted(dets, key=lambda d: -d[2]):
            best, best_d = None, self.match_mm
            for t in self.tracks:
                d = math.hypot(t["x"] - x, t["y"] - y)
                if not t["seen"] and d <= best_d:
                    best, best_d = t, d
            if best is None:
                best = {"x": x, "y": y, "hist": deque(maxlen=self.window), "conf": deque(maxlen=self.window)}
                self.tracks.append(best)
            else:
                best["x"] += 0.5 * (x - best["x"])
                best["y"] += 0.5 * (y - best["y"])
            best["seen"] = True
            best["hist"].append(1)
            best["conf"].append(c)
        for t in self.tracks:
            if not t.get("seen"):
                t["hist"].append(0)
        self.tracks = [t for t in self.tracks if any(t["hist"])]

        stable = [t for t in self.tracks if sum(t["hist"]) >= self.confirm_hits]
        for t in stable:
            if len(self.known) >= self.max_darts:
                break
            if any(math.hypot(t["x"] - kx, t["y"] - ky) <= self.match_mm for kx, ky in self.known):
                continue
            self.known.append((t["x"], t["y"]))
            mult, num = db.score_at(t["x"], t["y"])
            margin = db.margin_mm(t["x"], t["y"])
            conf = float(np.mean(t["conf"]))
            unsure = (margin < self.uncertain_margin_mm or conf < self.low_conf
                      or math.hypot(t["x"], t["y"]) > FAR_MISS_MM
                      or (cal_err is not None and cal_err > self.max_cal_err_mm) or n_cal < 4)
            events.append(Throw(mult, num, t["x"], t["y"], margin, conf, unsure, cal_err=float(cal_err or 0.0)))

        # kihúzás: a leírt nyilak közül egyik sem látszik egymás utáni sok képkockán át
        seen_known = any(math.hypot(x - kx, y - ky) <= self.match_mm for x, y, _ in dets for kx, ky in self.known)
        self.empty = 0 if (not self.known or seen_known) else self.empty + 1
        if self.known and self.empty >= self.clear_frames:
            self.reset()
            events.append(Removed())
        return events


# ───────────── egy kamera feldolgozása ─────────────
class Detector:
    """Egy kamera teljes feldolgozása: kép -> felismerés -> kalibráció -> dobáskövetés."""

    def __init__(self, backend, crop_square=True, cal_conf=0.6, dart_conf=0.35):
        self.backend, self.crop_square = backend, crop_square
        self.cal_conf, self.dart_conf = cal_conf, dart_conf
        self.cal = CalibrationTracker()
        self.tracker = DartTracker()
        self.overlay = {"cal": [], "darts": [], "status": "Indul…", "square": None}

    def reset_round(self):
        """A nyilak kihúzva (kézi jelzés): a következő nyilak új dobásnak számítanak."""
        self.tracker.reset()

    @property
    def healthy(self):
        """Megbízható-e most a kamera: van kalibráció, mind a 4 pont látszik, és a visszavetítési hiba kicsi."""
        return (self.cal.H is not None and len(self.cal.points) >= 4
                and (self.cal.err or 0.0) <= self.tracker.max_cal_err_mm)

    def process(self, frame):
        """Feldolgoz egy BGR képkockát; visszatér az új események listájával (Throw / Removed)."""
        h, w = frame.shape[:2]
        x0 = y0 = 0
        img, square = frame, None
        if self.crop_square and w != h:         # a modell négyzetes, tábla-központú képeken tanult
            s = min(w, h)
            x0, y0 = (w - s) // 2, (h - s) // 2
            img, square = frame[y0:y0 + s, x0:x0 + s], (x0, y0, s)
        det = self.backend.detect(img)
        cal = {n: (x + x0, y + y0, c) for n, (x, y, c) in det.cal.items() if c >= self.cal_conf}
        darts = [(x + x0, y + y0, c) for x, y, c in det.darts if c >= self.dart_conf]
        return self.step(cal, darts, square)

    def step(self, cal, darts, square=None):
        """A felismert pontokból (kép pixelben) eseményeket és megjelenítési adatot készít."""
        H, err = self.cal.update(cal)
        events, labels = [], []
        n_cal = len(self.cal.points)
        if H is not None:
            on_board = []
            if darts:
                mm = db.apply_h(H, [(x, y) for x, y, _ in darts])
                for (x, y, c), (mx, my) in zip(darts, mm):
                    if math.hypot(mx, my) <= BOARD_LIMIT_MM:
                        on_board.append((mx, my, c))
                        labels.append((x, y, db.notation(*db.score_at(mx, my))))
            events = self.tracker.update(on_board, cal_err=err, n_cal=n_cal)
        if H is None:
            status = f"Kalibrálás… {n_cal}/4 pont látszik – a tábla legyen jól látható, és töltse ki a kép közepét"
        elif n_cal < 4:
            status = f"Kalibrálva (elavult: most {n_cal} pont látszik)"
        elif err > self.tracker.max_cal_err_mm:
            status = f"Kalibráció pontatlan ({err:.1f} mm) – igazítsd a kamerát"
        else:
            status = f"Kalibrálva ({n_cal} pont, {err:.1f} mm)"
        self.overlay = {"cal": [(x, y, n) for n, (x, y) in self.cal.points.items()], "darts": labels,
                        "status": status, "square": square}
        return events


def analyze_image(backend, frame, crop_square=False, cal_conf=0.6, dart_conf=0.35):
    """Egyetlen képet elemez (kalibráció + pontszámok) – a beállítás ellenőrzéséhez és teszteléséhez."""
    h, w = frame.shape[:2]
    x0 = y0 = 0
    img = frame
    if crop_square and w != h:
        s = min(w, h)
        x0, y0 = (w - s) // 2, (h - s) // 2
        img = frame[y0:y0 + s, x0:x0 + s]
    det = backend.detect(img)
    cal = {n: (x + x0, y + y0) for n, (x, y, c) in det.cal.items() if c >= cal_conf}
    H, err = db.homography(cal)
    out = {"cal": cal, "err": err, "darts": []}
    if H is None:
        return out
    for x, y, c in det.darts:
        if c < dart_conf:
            continue
        mx, my = db.apply_h(H, [(x + x0, y + y0)])[0]
        if math.hypot(mx, my) <= BOARD_LIMIT_MM:
            m, n = db.score_at(mx, my)
            out["darts"].append({"px": (x + x0, y + y0), "mm": (float(mx), float(my)), "mult": m, "num": n,
                                 "margin": db.margin_mm(mx, my), "conf": c})
    return out


# ───────────── háttérszál ─────────────
class DetectionService:
    """Háttérszál: egy kamera képét dolgozza fel, az eseményeket sorba teszi a felületnek."""

    def __init__(self, detector, get_frame, fps=6.0):
        self.detector, self.get_frame, self.period = detector, get_frame, 1.0 / fps
        self.events = queue.Queue()
        self.error = None
        self.last_frame_t = None               # mikor dolgoztunk fel utoljára új képkockát
        self._stop = threading.Event()
        self._thread = None

    @property
    def overlay(self):
        return self.detector.overlay

    def healthy(self, max_age=3.0):
        """A kamera használható az összevetéshez: képet kapunk, és a kalibráció jó."""
        fresh = self.last_frame_t is not None and time.monotonic() - self.last_frame_t <= max_age
        return bool(fresh and self.detector.healthy)

    def poll(self):
        """Kiveszi a sorban várakozó eseményeket (Throw / Removed), a felület szálából hívható."""
        out = []
        while True:
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                return out

    def reset_round(self):
        """Új játék / kézi nullázás: a követő elfelejti a leírt nyilakat, a még le nem kért események eldobódnak."""
        self.detector.reset_round()
        self.poll()

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        last = None
        while not self._stop.is_set():
            t0 = time.time()
            frame = self.get_frame()
            if frame is not None and frame is not last:
                last = frame
                try:
                    for ev in self.detector.process(frame):
                        self.events.put(ev)
                    self.error = None
                    self.last_frame_t = time.monotonic()
                except Exception as e:           # egy rossz kép ne állítsa le a szálat
                    self.error = f"{type(e).__name__}: {e}"
            time.sleep(max(0.01, self.period - (time.time() - t0)))
