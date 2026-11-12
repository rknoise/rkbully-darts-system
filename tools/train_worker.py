"""A modell betanítása külön folyamatban (a betanító ablak indítja: python tools/train_worker.py beallitas.json).

A felület ennek a kimenetét olvassa: RKBULLY_EPOCH|n|összes|mAP, RKBULLY_DONE|útvonal, RKBULLY_ERROR|szöveg."""
import json
import shutil
import sys
import traceback
from pathlib import Path


def main(cfg_path):
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    try:
        from ultralytics import YOLO
    except ImportError:
        print("RKBULLY_ERROR|Az ultralytics csomag nincs telepítve. Futtasd a Felismeres_telepitese.bat fájlt.", flush=True)
        return 2
    try:
        import torch
        gpu = bool(torch.cuda.is_available())
    except Exception:
        gpu = False
    try:
        print("RKBULLY_INFO|" + ("Videokártyás (CUDA) tanítás" if gpu else "Processzoros tanítás (lassabb)"), flush=True)
        model = YOLO(cfg["base"])
        total = int(cfg["epochs"])

        def on_epoch_end(trainer):
            metrics = getattr(trainer, "metrics", None) or {}
            m = metrics.get("metrics/mAP50(B)")
            print(f"RKBULLY_EPOCH|{min(int(trainer.epoch) + 1, total)}|{total}|{'' if m is None else f'{float(m):.4f}'}", flush=True)

        model.add_callback("on_fit_epoch_end", on_epoch_end)
        model.train(
            data=cfg["data"], epochs=total, imgsz=int(cfg["imgsz"]), batch=int(cfg.get("batch", 8)),
            project=cfg["project"], name=cfg.get("name", "rkbully"), exist_ok=True,
            patience=int(cfg.get("patience", 30)), workers=2 if gpu else 0, device=0 if gpu else "cpu",
            # a kamera fix, ezért nincs tükrözés/forgatás/mozaik: a kalibrációs pontok helye a kép egészében számít
            fliplr=0.0, flipud=0.0, degrees=0.0, mosaic=0.0, mixup=0.0, scale=0.2, translate=0.05, shear=0.0,
            hsv_h=0.01, hsv_s=0.4, hsv_v=0.4, plots=False, verbose=False, amp=gpu,
        )
        best = Path(cfg["project"]) / cfg.get("name", "rkbully") / "weights" / "best.pt"
        if not best.is_file():
            last = best.with_name("last.pt")
            if last.is_file():
                shutil.copyfile(last, best)
        if not best.is_file():
            print("RKBULLY_ERROR|A tanítás nem hozott létre modellfájlt.", flush=True)
            return 3
        print(f"RKBULLY_DONE|{best}", flush=True)
        return 0
    except Exception as e:
        traceback.print_exc()
        print(f"RKBULLY_ERROR|{type(e).__name__}: {e}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
