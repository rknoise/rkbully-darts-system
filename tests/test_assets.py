"""Az ikonfájlok és a parancsikon-készítő scriptek ellenőrzése (Pillow és PySide6 nélkül is futnak)."""
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def ico_sizes(path):
    data = path.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind) == (0, 1), "nem .ico fájl"
    sizes = set()
    for i in range(count):
        w, h = struct.unpack("<BB", data[6 + 16 * i:8 + 16 * i])
        sizes.add((w or 256, h or 256))
    return sizes


class IconTests(unittest.TestCase):
    def test_ico_has_the_sizes_windows_needs(self):
        sizes = ico_sizes(ROOT / "assets" / "rkbully.ico")
        for s in (16, 24, 32, 48, 64, 128, 256):
            self.assertIn((s, s), sizes)

    def test_png_is_a_512_square(self):
        data = (ROOT / "assets" / "rkbully.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (512, 512))

    def test_source_image_exists_for_regeneration(self):
        self.assertTrue((ROOT / "assets" / "rkbully_forras.png").exists())
        self.assertTrue((ROOT / "tools" / "make_icons.py").exists())


class ShortcutScriptTests(unittest.TestCase):
    FILES = ("Parancsikon_letrehozasa.bat", "tools/make_shortcut.ps1", "RKBully_indit.bat", "Felismeres_telepitese.bat")

    def test_scripts_are_ascii_only(self):
        """Ékezetes karakter a .bat/.ps1 fájlban a Windows kodlapján elromlik, ezért csak ASCII lehet."""
        for name in self.FILES:
            (ROOT / name).read_bytes().decode("ascii")

    def test_ultralytics_is_installed_by_the_launchers_but_never_required_to_start(self):
        """A dobásfelismerés csomagja külön fájlban van: ha a telepítése nem sikerül, a program akkor is elindul."""
        base = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        det = (ROOT / "requirements-felismeres.txt").read_text(encoding="utf-8")
        self.assertNotIn("\nultralytics", "\n" + base)                 # a kötelező csomagok között nincs
        self.assertIn("\nultralytics", "\n" + det)
        bat = (ROOT / "RKBully_indit.bat").read_text(encoding="ascii")
        self.assertIn("requirements-felismeres.txt", bat)
        first = bat.index("requirements.txt")
        self.assertLess(first, bat.index("requirements-felismeres.txt"))       # előbb az alap, utána a nagy csomag
        self.assertLess(bat.index("requirements-felismeres.txt"), bat.rindex("rkbully.py"))
        self.assertEqual(bat.count("exit /b 1"), 2)                              # csak a hiányzó Python és az alapcsomagok hibája állítja meg az indítást
        ps = (ROOT / "tools" / "make_shortcut.ps1").read_text(encoding="ascii")
        self.assertIn("requirements-felismeres.txt", ps)
        self.assertIn("pip show ultralytics", ps)
        repair = (ROOT / "Felismeres_telepitese.bat").read_text(encoding="ascii")
        self.assertIn("requirements-felismeres.txt", repair)

    def test_bat_calls_the_powershell_script_that_exists(self):
        bat = (ROOT / "Parancsikon_letrehozasa.bat").read_text(encoding="ascii")
        self.assertIn(r"tools\make_shortcut.ps1", bat)
        self.assertTrue((ROOT / "tools" / "make_shortcut.ps1").exists())

    def test_powershell_script_targets_real_files(self):
        ps = (ROOT / "tools" / "make_shortcut.ps1").read_text(encoding="ascii")
        for rel in re.findall(r"Join-Path \$root '([^']+)'", ps):
            self.assertTrue((ROOT / rel.replace("\\", "/")).exists(), rel)
        self.assertIn("rkbully.ico", ps)
        self.assertIn("WScript.Shell", ps)
        self.assertIn("pythonw.exe", ps)

    def test_installer_is_ascii_and_builds_a_valid_self_extracting_file(self):
        import base64
        import io
        import sys
        import zipfile
        sys.path.insert(0, str(ROOT / "tools"))
        import build_installer
        for name in ("loader.bat", "install.ps1", "Inditas.bat", "Eltavolitas.bat"):
            (ROOT / "installer" / name).read_text(encoding="ascii")          # csak ASCII: a konzol kódlapja nem ronthatja el
        out = build_installer.build()
        text = out.read_bytes().decode("ascii")
        head, rest = text.split("#__PS__\r\n", 1)
        script, payload = rest.split("#__ZIP__\r\n", 1)
        self.assertIn("RK_SELF", head)
        self.assertNotIn("\n", text.replace("\r\n", ""))                    # végig CRLF
        names = zipfile.ZipFile(io.BytesIO(base64.b64decode("".join(payload.split())))).namelist()
        for need in ("rkbully.py", "wizard.py", "camcheck.py", "requirements.txt", "requirements-felismeres.txt",
                     "assets/rkbully.ico", "assets/sounds/triple.wav", "tools/train_worker.py", "Inditas.bat", "Eltavolitas.bat"):
            self.assertIn(need, names)
        # a telepített mappa egyben fejlesztői környezet is: forrás, tesztek, eszközök, dokumentáció, rögzített csomaglista
        for need in ("tests/test_games.py", "tests/synth.py", "tools/build_installer.py", "tools/build_offline.py",
                     "installer/install.ps1", "requirements-lock.txt", "docs/FEJLESZTOI_ADATLAP.md", "docs/images/foablak.png"):
            self.assertIn(need, names)
        self.assertFalse([n for n in names if n.startswith(("old/", "dist/", "models/")) or "__pycache__" in n
                          or n.endswith((".pt", ".onnx", ".pyc"))])
        for word in ("venv", "winget", "RKNOISE", "kalibracios", "RK_EXTRACT_ONLY", "offline", "--no-index", "--find-links"):
            self.assertIn(word, script)
        self.assertNotIn("@VERSION@", script)                                # a build behelyettesítette a verziót
        import appinfo
        self.assertIn("'" + appinfo.VERSION + "'", script)
        self.assertIn(appinfo.VERSION, build_installer.OUT.name)

    def test_version_is_1_0_and_names_match(self):
        import appinfo
        self.assertEqual(appinfo.VERSION, "1.0")
        self.assertEqual(appinfo.APP_NAME, "RKBully Darts System")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("RKBully Darts System 1.0", readme)

    def test_lock_file_pins_everything_and_matches_the_requirements(self):
        lock = [l.strip() for l in (ROOT / "requirements-lock.txt").read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")]
        self.assertTrue(all("==" in l for l in lock), "minden csomagnak rögzített verziója van")
        names = {l.split("==")[0].lower().replace("_", "-") for l in lock}
        for req in ("requirements.txt", "requirements-felismeres.txt"):
            for line in (ROOT / req).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    pkg = re.split(r"[<>=!~ ]", line)[0].lower().replace("_", "-")
                    self.assertIn(pkg, names, f"{req}: {pkg} hiányzik a requirements-lock.txt-ből")
        self.assertFalse(any(n in names for n in ("pyside6", "pyside6-webengine")))          # a nagy, nem használt csomagok nélkül

    def test_offline_mode_is_wired_in_the_installer_script(self):
        ps = (ROOT / "installer" / "install.ps1").read_text(encoding="ascii")
        self.assertIn("'--no-index', '--find-links', $Wheels", ps)
        self.assertIn("python-3.12*-amd64.exe", ps)
        self.assertIn("RK_FORCE_ONLINE", ps)
        self.assertIn("TELEPITES_INFO.txt", ps)
        self.assertIn("calcsize('P') == 8", ps)                              # csak 64 bites Python jó a win_amd64 csomagokhoz
        # offline csomagnál a pip-hívások mindegyike a helyi forrást használja
        self.assertEqual(ps.count("+ $pipSrc"), 3)

    def test_full_package_builder_requires_python_and_wheels(self):
        import sys
        import tempfile
        sys.path.insert(0, str(ROOT / "tools"))
        import build_installer
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                build_installer.build_full(Path(tmp))                         # üres mappa: nincs wheels/ és Python telepítő

    def test_windows_scripts_use_crlf(self):
        for name in self.FILES:
            data = (ROOT / name).read_bytes()
            self.assertNotIn(b"\n", data.replace(b"\r\n", b""), name)


if __name__ == "__main__":
    unittest.main()
