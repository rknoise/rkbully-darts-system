"""Több kamera összevetése.

Miért nem kell valódi háromszögelés: a nyílhegy a tábla síkján van, és minden kamera a *tábla saját jelöléseiből*
(20, 3, 11, 6) számol homográfiát, vagyis mindkét kamera ugyanabba a koordináta-rendszerbe (a tábla síkja, mm) vetíti
a nyílhegyet. A kamerák között ezért nincs külön kalibráció. Az összevetés három dolgot csinál:

  1. ugyanazon nyíl két észlelését egyetlen dobássá egyesíti (nincs dupla számolás),
  2. a két becslést súlyozva átlagolja (a magabiztosabb, jobban kalibrált kamera többet számít),
  3. jelzi, ha a kamerák nem értenek egyet, vagy az egyik nem látta a nyilat, akkor a játékosnak kell jóváhagynia.

A kameránkénti felismerés (vision.Detector) változatlan: minden kamerának saját dobáskövetője van, ez az egység a
már megerősített Throw / Removed eseményeket fogja össze. Egyetlen kamerával pontosan úgy viselkedik, mint korábban.
"""
import math
import time
from dataclasses import replace

import dartboard as db
from vision import Removed, Throw


class FusionHub:
    """Kamerák eseményeinek egyesítése. A felület szálából használható (nincs benne saját szál)."""

    def __init__(self, clock=time.monotonic, merge_mm=14.0, loose_mm=20.0, split_mm=8.0, wait_s=2.5,
                 remove_wait_s=3.0, max_darts=3, margin_mm=3.0):
        self.clock = clock
        self.merge_mm = merge_mm            # ennél közelebbi két észlelés ugyanaz a nyíl
        self.loose_mm = loose_mm            # a várakozás végén ennél közelebbit is párosítunk (rosszul kalibrált kamerapár)
        self.split_mm = split_mm            # ennél nagyobb eltérésnél nem átlagolunk, és kézi jóváhagyás kell
        self.wait_s = wait_s                # ennyit várunk a másik kamera megerősítésére
        self.remove_wait_s = remove_wait_s  # ennyit várunk a többi kamera "kihúzva" jelzésére
        self.max_darts = max_darts
        self.margin_mm = margin_mm          # a vision.DartTracker bizonytalansági küszöbével azonos
        self.cams = {}                      # név -> {"healthy": bool, "known": hány dobást látott ebben a körben}
        self.reset_callback = None          # f(kamera_neve): a hátramaradt kamera követőjét nullázni kell
        self.dropped = 0                    # a körönkénti maximum miatt eldobott dobások száma (diagnosztika)
        self.reset()

    # ── kamerák ──
    def add_camera(self, name, healthy=True):
        self.cams[name] = {"healthy": bool(healthy), "known": 0}

    def remove_camera(self, name):
        self.cams.pop(name, None)
        self.pending = [p for p in self.pending if p["cam"] != name]
        for e in self.emitted:
            e["cams"].discard(name)

    def set_health(self, name, ok):
        if name in self.cams:
            self.cams[name]["healthy"] = bool(ok)

    def reset(self):
        """Új kör / új játék: minden függő állapot eldobása."""
        self.pending = []                   # még nem párosított, megerősített dobások: {"cam", "throw", "t"}
        self.emitted = []                   # a körben már kiadott dobások: {"x", "y", "cams"}
        self.remove_t = None                # mikor jött az első "kihúzva" jelzés
        for c in self.cams.values():
            c["known"] = 0

    def _others_healthy(self, cam):
        return any(c["healthy"] for n, c in self.cams.items() if n != cam)

    # ── bemenet ──
    def push(self, cam, events):
        """Egy kamera új eseményei (Throw / Removed). Visszatér az összevetett eseményekkel."""
        out = []
        if cam not in self.cams:
            self.add_camera(cam)
        for ev in events:
            if isinstance(ev, Throw):
                out += self._throw(cam, ev)
            elif isinstance(ev, Removed):
                out += self._removed(cam)
        return out

    def poll(self, now=None):
        """Időzített teendők: a várakozás lejárta után egy kamera dobása önállóan is kiadódik; a kihúzás időtúllépése."""
        now = self.clock() if now is None else now
        out = []
        for p in sorted(self.pending, key=lambda p: p["t"]):
            if not self._has(p):                           # egy korábbi párosítás már elvitte
                continue
            others_ok = self._others_healthy(p["cam"])
            if others_ok and now - p["t"] < self.wait_s:
                continue
            self._drop(p)
            if others_ok:
                m = self._nearest_pending(p["cam"], p["throw"], self.loose_mm)
                if m:
                    self._drop(m)
                    out += self._emit_pair(p, m)
                    continue
            out += self._emit_single(p, expect_other=others_ok)
        if self.remove_t is not None and now - self.remove_t >= self.remove_wait_s:
            out += self._finish_round()
        return out

    # ── dobások ──
    def _throw(self, cam, th):
        out = []
        if self.remove_t is not None:                      # új dobás érkezett: az előző kör vége biztos
            out += self._finish_round()
        self.cams[cam]["known"] += 1
        entry = {"cam": cam, "throw": th, "t": self.clock()}
        if not self._others_healthy(cam):                  # egyedül vagyunk (vagy a többi kamera nem használható)
            return out + self._emit_single(entry, expect_other=False)
        m = self._nearest_pending(cam, th, self.merge_mm)
        if m:
            self._drop(m)
            return out + self._emit_pair(m, entry)
        for e in self.emitted:                             # késői megerősítés egy már kiadott dobáshoz: nem új nyíl
            if cam not in e["cams"] and math.hypot(e["x"] - th.x, e["y"] - th.y) <= self.merge_mm:
                e["cams"].add(cam)
                return out
        self.pending.append(entry)
        return out

    def _has(self, p):
        return any(q is p for q in self.pending)

    def _drop(self, p):
        self.pending = [q for q in self.pending if q is not p]

    def _nearest_pending(self, cam, th, radius):
        best, best_d = None, radius
        for p in self.pending:
            if p["cam"] == cam:
                continue
            d = math.hypot(p["throw"].x - th.x, p["throw"].y - th.y)
            if d <= best_d:
                best, best_d = p, d
        return best

    @staticmethod
    def _weight(th):
        """Heurisztikus súly: a magabiztosabb és jobban kalibrált kamera többet számít (nem mért értékekből levezetve)."""
        return max(th.conf, 0.05) / (0.8 + max(th.cal_err, 0.0)) ** 2

    def fuse(self, a, b):
        """Két kamera becslésének egyesítése egy Throw-vá."""
        wa, wb = self._weight(a), self._weight(b)
        spread = math.hypot(a.x - b.x, a.y - b.y)
        if spread > self.split_mm:                         # nagy eltérésnél az átlag semmit sem ér: a jobb becslés marad
            x, y = (a.x, a.y) if wa >= wb else (b.x, b.y)
        else:
            x, y = (a.x * wa + b.x * wb) / (wa + wb), (a.y * wa + b.y * wb) / (wa + wb)
        mult, num = db.score_at(x, y)
        margin = db.margin_mm(x, y)
        same = db.score_at(a.x, a.y) == db.score_at(b.x, b.y)
        reason = ""
        if not same or spread > self.split_mm:
            reason = "kamerák eltérnek"
        elif margin < self.margin_mm:
            reason = "határ közelében"
        elif a.uncertain and b.uncertain:
            reason = "bizonytalan felismerés"
        return Throw(mult, num, x, y, margin, (a.conf + b.conf) / 2, bool(reason), cal_err=min(a.cal_err, b.cal_err),
                     sources=2, spread=spread, reason=reason)

    def _emit(self, th, cams):
        if len(self.emitted) >= self.max_darts:            # egy körben legfeljebb ennyi nyíl lehet
            self.dropped += 1
            return []
        self.emitted.append({"x": th.x, "y": th.y, "cams": set(cams)})
        return [th]

    def _emit_pair(self, pa, pb):
        return self._emit(self.fuse(pa["throw"], pb["throw"]), {pa["cam"], pb["cam"]})

    def _emit_single(self, p, expect_other):
        th = p["throw"]
        if expect_other:                                   # a másik kamera is működik, mégsem látta: ne higgyünk neki vakon
            th = replace(th, uncertain=True, reason="csak 1 kamera látta")
        return self._emit(th, {p["cam"]})

    # ── kihúzás ──
    def _removed(self, cam):
        c = self.cams[cam]
        c["known"] = 0
        if self.remove_t is None:
            self.remove_t = self.clock()
        if all(x["known"] == 0 for x in self.cams.values()):
            return self._finish_round()
        return []                                          # a többi kamera még látja a nyilakat: várunk rájuk

    def _finish_round(self):
        out = []
        for p in sorted(self.pending, key=lambda p: p["t"]):       # előbb a függő dobások, aztán a kihúzás
            out += self._emit_single(p, expect_other=self._others_healthy(p["cam"]))
        stragglers = [n for n, c in self.cams.items() if c["known"] > 0]
        self.reset()
        if self.reset_callback:
            for n in stragglers:
                self.reset_callback(n)
        return out + [Removed()]


class FusionService:
    """A felület ezzel beszél: kamerák háttérszálai (vision.DetectionService) + az összevető egység."""

    def __init__(self, hub=None):
        self.hub = hub or FusionHub()
        self.hub.reset_callback = self._reset_cam
        self.children = {}                  # név -> DetectionService

    def add(self, name, service):
        self.children[name] = service
        self.hub.add_camera(name, service.healthy())
        service.start()

    def remove(self, name):
        svc = self.children.pop(name, None)
        if svc:
            svc.stop()
        self.hub.remove_camera(name)

    def stop(self):
        for svc in self.children.values():
            svc.stop()

    def reset_round(self):
        for svc in self.children.values():
            svc.reset_round()
        self.hub.reset()

    def _reset_cam(self, name):
        if name in self.children:
            self.children[name].detector.reset_round()

    @property
    def error(self):
        return next((s.error for s in self.children.values() if s.error), None)

    def poll(self):
        """A felület időzítőjéből hívva: összegyűjti a kamerák eseményeit, és visszaadja az összevetett eseményeket."""
        out = []
        for name, svc in list(self.children.items()):
            self.hub.set_health(name, svc.healthy())
        for name, svc in list(self.children.items()):
            out += self.hub.push(name, svc.poll())
        return out + self.hub.poll()
