"""A dobásfelismerő modell és a kamera-beállítás ellenőrzése egy-egy képen.

Használat:   python check_model.py models/dart.pt kep1.jpg [kep2.jpg ...]
Kiírja a felismert kalibrációs pontokat és nyilakat pontszámmal, és az eredményt képként a
check_output mappába menti (zöld kör = kalibrációs pont, piros kör = nyílhegy a pontszámmal).
Ha a 4 zöld pont a tábla dupla gyűrűjének külső szélén, a szektorhatár-drótoknál van, jó a beállítás.
"""
import sys
from pathlib import Path

import cv2

import dartboard as db
import vision as v


def annotate(img, res):
    out = img.copy()
    for name, (x, y) in res["cal"].items():
        cv2.circle(out, (int(x), int(y)), 9, (0, 220, 0), 2)
        cv2.putText(out, name, (int(x) + 10, int(y) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 0), 2)
    for d in res["darts"]:
        x, y = d["px"]
        cv2.circle(out, (int(x), int(y)), 9, (0, 0, 255), 2)
        txt = db.notation(d["mult"], d["num"]) + ("?" if d["margin"] < 3.0 else "")
        cv2.putText(out, txt, (int(x) + 10, int(y) + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    return out


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    backend = v.YoloBackend(argv[1])
    out_dir = Path("check_output")
    out_dir.mkdir(exist_ok=True)
    for path in argv[2:]:
        img = cv2.imread(path)
        if img is None:
            print(f"{path}: nem olvasható kép")
            continue
        res = v.analyze_image(backend, img, crop_square=True)
        print(f"\n{path}")
        print(f"  kalibrációs pontok: {len(res['cal'])} ({', '.join(res['cal'])})"
              + (f", visszavetítési hiba {res['err']:.1f} mm" if res["err"] is not None else " – kevés a pont, nincs kalibráció"))
        for d in res["darts"]:
            print(f"  nyíl: {db.notation(d['mult'], d['num']):4s} biztonság {d['conf']:.2f}, "
                  f"határtól {d['margin']:.1f} mm" + ("  (bizonytalan)" if d["margin"] < 3.0 else ""))
        cv2.imwrite(str(out_dir / (Path(path).stem + "_eredmeny.jpg")), annotate(img, res))
    print(f"\nA képek a(z) {out_dir} mappában vannak.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
