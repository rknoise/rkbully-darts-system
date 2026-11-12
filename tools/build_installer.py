"""A telepítők összeállítása (futtatás:  python tools/build_installer.py [--offline <offline_mappa>]).

* dist/RKBully_Darts_System_<verzió>_Telepito_online.bat – kis (néhány MB) egyfájlos telepítő, a csomagokat az internetről tölti.
* --offline megadásakor: dist/RKBully_Darts_System_<verzió>_Teljes_Telepito/ – Telepites.bat + offline\\ mappa (Python 3.12.8 telepítő
  és az összes wheel): internet nélkül telepíthető. Az offline mappát a tools/build_offline.py állítja elő.

A telepítő egyetlen .bat fájl: az elején egy kis batch betöltő, utána a PowerShell telepítő (installer/install.ps1), a végén a
program fájljai base64-es zip-ként. A zip tartalmazza a forráskódot, a teszteket, a fejlesztői eszközöket és a dokumentációt is,
így a telepített program mappája egyben fejlesztői környezet (lásd docs/FEJLESZTOI_ADATLAP.md)."""
import base64
import hashlib
import io
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from appinfo import APP_NAME, VERSION  # noqa: E402

DIST = ROOT / "dist"
OUT = DIST / f"RKBully_Darts_System_{VERSION}_Telepito_online.bat"
FULL_DIR = DIST / f"RKBully_Darts_System_{VERSION}_Teljes_Telepito"
TOP_FILES = ["requirements.txt", "requirements-felismeres.txt", "requirements-lock.txt", "README.md", ".gitignore"]
SKIP_ASSETS = set()                      # a logó forrásképe is bekerül: a tools/make_icons.py ebből gyártja az ikonokat
EXTRA = {"Inditas.bat": ROOT / "installer" / "Inditas.bat", "Eltavolitas.bat": ROOT / "installer" / "Eltavolitas.bat"}
LAUNCHERS = ["RKBully_indit.bat", "Felismeres_telepitese.bat", "Parancsikon_letrehozasa.bat"]


def payload_files():
    """[(archívum-útvonal, fájl)] – a program futtatásához ÉS módosításához kellő fájlok (régi verziók, modellek nélkül)."""
    files = [(p.name, p) for p in sorted(ROOT.glob("*.py"))]
    files += [(n, ROOT / n) for n in TOP_FILES + LAUNCHERS if (ROOT / n).is_file()]
    files += [(f"assets/{p.relative_to(ROOT / 'assets').as_posix()}", p)
              for p in sorted((ROOT / "assets").rglob("*")) if p.is_file() and p.name not in SKIP_ASSETS]
    files += [(f"tools/{p.name}", p) for p in sorted((ROOT / "tools").iterdir()) if p.is_file() and p.suffix in (".py", ".ps1")]
    files += [(f"tests/{p.name}", p) for p in sorted((ROOT / "tests").glob("*.py"))]
    files += [(f"installer/{p.name}", p) for p in sorted((ROOT / "installer").iterdir()) if p.is_file()]
    files += [(f"docs/{p.relative_to(ROOT / 'docs').as_posix()}", p) for p in sorted((ROOT / "docs").rglob("*")) if p.is_file()]
    files += list(EXTRA.items())
    return files


def build_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, path in payload_files():
            data = path.read_bytes()
            if path.suffix in (".bat", ".ps1"):
                data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            z.writestr(zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0)), data, zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def crlf(text):
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def installer_text():
    loader = (ROOT / "installer" / "loader.bat").read_text(encoding="ascii")
    script = (ROOT / "installer" / "install.ps1").read_text(encoding="utf-8").replace("@VERSION@", VERSION)
    assert all(ord(c) < 128 for c in loader + script), "a telepítő szövege csak ASCII lehet"
    b64 = base64.b64encode(build_zip()).decode("ascii")
    lines = [b64[i:i + 120] for i in range(0, len(b64), 120)]
    return (crlf(loader.rstrip() + f"\n\nrem {APP_NAME} {VERSION}\nexit /b 1\n") + "#__PS__\r\n" + crlf(script.rstrip()) + "\r\n"
            + "#__ZIP__\r\n" + "\r\n".join(lines) + "\r\n")


def build():
    """Az online (kis) telepítő."""
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes(installer_text().encode("ascii"))
    return OUT


OLVASSEL = """RKBully Darts System {version} - TELJES (OFFLINE) TELEPITO
=========================================================

Dupla kattintas a  Telepites.bat  fajlra. Internet NEM kell: a Python 3.12 es az osszes csomag
(PySide6, OpenCV, NumPy, PyTorch, ultralytics) az "offline" mappaban van.

FONTOS: a Telepites.bat es az "offline" mappa egymas mellett legyen (a mappat ne bontsd szet).
Telepitesi hely: %LOCALAPPDATA%\\RKBully Darts System  (nem kell rendszergazda).
A telepites vegen parancsikon kerul az Asztalra es a Start menube; a program ujra elindul.

Ha a Telepites.bat melle nem teszed az offline mappat, a telepito az internetrol tolti le, amit kell.
Reszletes fejlesztoi leiras: docs\\FEJLESZTOI_ADATLAP.md (telepites utan a telepitesi mappaban).
"""


def build_full(offline_src: Path):
    """Teljes (offline) csomag: dist/..._Teljes_Telepito/Telepites.bat + offline/ (Python + wheel-ek)."""
    offline_src = Path(offline_src)
    if not (offline_src / "wheels").is_dir() or not list(offline_src.glob("python-3.12*-amd64.exe")):
        raise SystemExit(f"Az offline mappából hiányzik a wheels\\ vagy a python-3.12*-amd64.exe: {offline_src}")
    if FULL_DIR.exists():
        shutil.rmtree(FULL_DIR)
    FULL_DIR.mkdir(parents=True)
    (FULL_DIR / "Telepites.bat").write_bytes(installer_text().encode("ascii"))
    (FULL_DIR / "OLVASSEL.txt").write_bytes(crlf(OLVASSEL.format(version=VERSION)).encode("ascii"))
    shutil.copytree(offline_src, FULL_DIR / "offline")
    return FULL_DIR


def write_checksums(paths):
    """SHA256 ellenőrzőösszegek a kiadás fájljaihoz (dist/SHA256SUMS.txt)."""
    lines = []
    for p in paths:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        lines.append(f"{h.hexdigest()}  {p.relative_to(DIST).as_posix()}")
    (DIST / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="ascii")


def make_zip(full: Path):
    """A teljes csomag mappájából kiadási zip (a GitHub Releases-hez): dist/<mappa>.zip."""
    return Path(shutil.make_archive(str(full), "zip", root_dir=full.parent, base_dir=full.name))


if __name__ == "__main__":
    out = build()
    print(f"{out}  ({out.stat().st_size / 1e6:.1f} MB, {len(payload_files())} fájl)")
    release = [out]
    if "--offline" in sys.argv:
        full = build_full(Path(sys.argv[sys.argv.index("--offline") + 1]))
        for extra in ("docs/LICENCEK.md", "LICENSE"):                       # a licencek a csomag mellett is látszanak
            shutil.copy2(ROOT / extra, full / (Path(extra).name + (".txt" if extra == "LICENSE" else "")))
        size = sum(p.stat().st_size for p in full.rglob("*") if p.is_file())
        print(f"{full}  ({size / 1e6:.0f} MB)")
        if "--zip" in sys.argv:
            z = make_zip(full)
            release.append(z)
            print(f"{z}  ({z.stat().st_size / 1e6:.0f} MB)")
    write_checksums(release)
    print("SHA256SUMS.txt kész (" + ", ".join(p.name for p in release) + ")")
