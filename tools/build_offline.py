"""Az offline telepítő "offline" mappájának előállítása: a Python 3.12.8 telepítője + az összes csomag wheel-je.

Futtatás (internet kell, Windows/Linux/macOS bármelyiken működik – a wheel-eket Windows-ra tölti le):
    python tools/build_offline.py [kimeneti_mappa]          (alapértelmezés: dist/offline)

A csomagok a requirements-lock.txt rögzített verziói (win_amd64, cp312). Ezután:
    python tools/build_installer.py --offline dist/offline  → dist/RKBully_Darts_System_<verzió>_Teljes_Telepito/
"""
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_VERSION = "3.12.8"
PY_FILE = f"python-{PY_VERSION}-amd64.exe"
PY_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/{PY_FILE}"
PY_MIN_BYTES = 20_000_000            # a valódi telepítő ~27 MB: ennél kisebb fájl hibás letöltés
BASE_FILE = "yolov8n.pt"             # a modell betanításának kiinduló súlyai (~6,5 MB, Ultralytics, AGPL-3.0)
BASE_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/" + BASE_FILE
BASE_MIN_BYTES = 5_000_000


def download_wheels(dest: Path):
    """pip download a rögzített listához; --no-deps, mert a lista már a teljes (feloldott) függőségfa."""
    dest.mkdir(parents=True, exist_ok=True)
    common = [sys.executable, "-m", "pip", "download", "--no-deps", "-d", str(dest), "--platform", "win_amd64",
              "--python-version", "3.12", "--implementation", "cp", "--only-binary=:all:"]
    subprocess.run(common + ["-r", str(ROOT / "requirements-lock.txt")], check=True)
    subprocess.run(common + ["pip", "wheel"], check=True)            # a venv pip-jének frissítéséhez


def download_python(dest: Path):
    target = dest / PY_FILE
    if target.exists() and target.stat().st_size >= PY_MIN_BYTES:
        return target
    print(f"Python {PY_VERSION} letöltése: {PY_URL}")
    urllib.request.urlretrieve(PY_URL, target)
    if target.stat().st_size < PY_MIN_BYTES:
        target.unlink()
        raise SystemExit("A Python telepítő letöltése hibás (túl kicsi fájl).")
    return target


def download_base(dest: Path):
    """Az alap-súlyfájl a betanításhoz. Ha nem sikerül, a csomag akkor is jó: a betanítás az első indításkor maga tölti le."""
    target = dest / BASE_FILE
    if target.exists() and target.stat().st_size >= BASE_MIN_BYTES:
        return target
    try:
        print(f"Alap-súlyfájl letöltése: {BASE_URL}")
        urllib.request.urlretrieve(BASE_URL, target)
        if target.stat().st_size < BASE_MIN_BYTES:
            raise OSError("túl kicsi fájl")
        return target
    except OSError as e:
        target.unlink(missing_ok=True)
        print(f"Figyelem: a {BASE_FILE} letöltése nem sikerült ({e}); a betanításhoz az első alkalommal internet kell.")
        return None


def build(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    download_wheels(out / "wheels")
    download_python(out)
    download_base(out)
    wheels = list((out / "wheels").glob("*.whl"))
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"Kész: {out}  ({len(wheels)} wheel, {size / 1e6:.0f} MB)")
    return out


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "offline")
