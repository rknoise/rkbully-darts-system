# RKBully Darts System 1.0 – Fejlesztői adatlap

**Cél:** ha a programot valahol egy másik gépen telepíted, ebből a leírásból és a telepített fájlokból pontosan lásd, hogyan épül fel,
hol mi van, és hogyan módosíthatod – anélkül, hogy az eredeti fejlesztőgépre vagy a beszélgetésre szükség lenne.

> Kapcsolódó fájlok (mind a telepítési mappában, a `docs\` alatt is megvannak):
> **`KODTERKEP.md`** – a teljes kód modulonként, osztályonként, függvényenként (a forrásból generált, mindig pontos),
> **`jatekmodok.md`** – a 20 játékmód szabályai és forrásai, **`LICENCEK.md`** – harmadik felek csomagjai és licencei,
> **`KIADAS_1.0.md`** – a kiadás jegyzéke, **`../README.md`** – felhasználói leírás.

---

## 1. Egy oldalon

| | |
|---|---|
| Név / verzió | **RKBully Darts System 1.0** (`appinfo.py`: `APP_NAME`, `VERSION`) |
| Szerző | RKNOISE |
| Nyelv / keretrendszer | Python 3.12 (3.10–3.13 fut), **PySide6** (Qt 6) felület, **OpenCV**, **NumPy**; dobásfelismeréshez **ultralytics (YOLO) + PyTorch** |
| Platform | Windows 10/11 64 bit (a felület és a játékmotor Linuxon/macOS-en is futtatható, a telepítő és a parancsikonok Windows-specifikusak) |
| Játékosok | 1–8 (`profiles.MAX_PLAYERS`, `games.MAX_PLAYERS`) |
| Játékmódok | 20 (`games.MODES`) |
| Kamerák | legfeljebb 3 (`rkbully.MAX_CAMS`): USB webkamera (szám) vagy telefon IP-kamera (cím) |
| Tesztek | 490 automatikus teszt (`tests/`), képernyő nélkül futnak (offscreen Qt) |
| Beállítások helye | `%USERPROFILE%\.rkbully\` (a felhasználó mappájában, **nem** a telepítési mappában) |
| Telepítési mappa | `%LOCALAPPDATA%\RKBully Darts System\` (a telepítő `RK_DIR` környezeti változóval felülbírálható) |

Fontos tulajdonság: **nincs fordítás, nincs build lépés** – a telepített mappa a futó forráskód. Szerkeszd a `.py` fájlt, indítsd újra a programot, kész.

---

## 2. A telepített mappa szerkezete

A telepítő (`Telepites.bat` / `…_Telepito_online.bat`) a következőt hozza létre a telepítési mappában:

```
RKBully Darts System\
├── rkbully.py              ← belépési pont (főablak, fő logika)        indítás: venv\Scripts\python.exe rkbully.py
├── appinfo.py              ← név, verzió, szerző (egy helyen)
├── games.py                ← játékmotor: 20 mód, pontszámítás (felülettől független)
├── dartboard.py            ← tábla geometria, pontszám a (x, y) mm-ből, homográfia
├── vision.py               ← kamerás felismerés: YOLO háttér, dobáskövető, háttérszál
├── fusion.py               ← több kamera eseményeinek egyesítése
├── review.py               ← kamerás kör jóváhagyása (visszaszámlálás, javítás)
├── camcheck.py             ← kamera/fény ellenőrzés a varázslóhoz
├── wizard.py               ← kalibrációs varázsló (UI)
├── trainer.py              ← modell-betanító logika (UI nélkül)
├── trainer_ui.py           ← modell-betanító ablak
├── options.py, profiles.py, stats.py, statsview.py, history.py, finish.py, welcome.py, ask.py
├── sounds.py, speech.py    ← hangeffektek, pontszám-felolvasás (magyar)
├── theme.py                ← neon-HUD stíluslap, Card, Avatar
├── check_model.py          ← parancssori modell-ellenőrző (képek elemzése)
├── assets\                 ← rkbully.ico/png (logó), sounds\*.wav (hangok), bemutató kép
├── base\yolov8n.pt         ← (csak offline telepítéskor) a betanítás kiinduló súlyfájlja
├── docs\                   ← ez a dokumentáció + images\
├── tests\                  ← az összes automatikus teszt (unittest)
├── tools\                  ← train_worker.py (a betanítás külön folyamata!), build_installer.py, build_offline.py,
│                              make_codemap.py, make_icons.py, make_sounds.py, make_screenshots.py, make_shortcut.ps1
├── installer\              ← install.ps1, loader.bat, Inditas.bat, Eltavolitas.bat (a telepítő forrásai)
├── requirements.txt        ← kötelező csomagok (PySide6-Essentials, PySide6-Addons, opencv-python, numpy)
├── requirements-felismeres.txt ← ultralytics (dobásfelismerés, betanítás) – nagy, a PyTorch-ot is behúzza
├── requirements-lock.txt   ← az 1.0-ban tesztelt, pontos verziók (Windows, Python 3.12)
├── RKBully_indit.bat, Felismeres_telepitese.bat, Parancsikon_letrehozasa.bat ← kézi telepítés/javítás segédek
├── Inditas.bat             ← a telepített venv-es indító; Eltavolitas.bat – eltávolító
├── venv\                   ← a program saját Python környezete (a telepítő hozza létre)
├── telepites.log           ← a telepítés naplója
└── TELEPITES_INFO.txt      ← verzió, telepítési mód (online/offline), Python, pontos csomagverziók (pip freeze)
```

**Mit nézz meg elsőként egy másik gépen:** `TELEPITES_INFO.txt` (milyen verzió és csomagok vannak fent), `telepites.log` (mi történt
telepítéskor), majd `docs\KODTERKEP.md` (hol mi van a kódban).

### Felhasználói adatok (`%USERPROFILE%\.rkbully\`)

Újratelepítéskor/frissítéskor ezek **megmaradnak** (a telepítő csak a programfájlokat írja felül).

| Fájl / mappa | Tartalom | Írja |
|---|---|---|
| `settings.json` | beállítások és profilok (lásd 3. fejezet) | `rkbully.save_cfg` |
| `history.json` | befejezett játékok előzménye (legfeljebb 1000) | `history.save` |
| `calibration.json` | kamerák kalibrációja (lásd 5. fejezet) | `wizard.save_calibration` |
| `avatars\*.jpg` | profilképek, 256×256 | `profiles.import_avatar` |
| `training\` | a betanítás adatai: `images\`, `labels\`, `meta\` (kamerás mintaképek), munkamappa, `runs` | `trainer.DatasetStore`, `trainer_ui` |

A modellfájlok a telepítési mappa `models\` almappájába kerülnek (`rkbully_YYYYMMDD_HHMMSS.pt`). A `.gitignore` kizárja a `models\`, `*.pt`, `*.onnx` fájlokat.

---

## 3. Beállítások: `settings.json`

Egyetlen JSON objektum. A betöltés tűrő (`load_cfg` hibánál üres szótárt ad), a mentés `save_cfg`; az UI a `Main.cfg` szótárban tartja.
Kézzel is szerkeszthető (a program zárt állapotában); a hibás profilbejegyzést a `profiles.clean` javítja/eldobja.

| Kulcs | Típus / értékek | Alapérték | Jelentés |
|---|---|---|---|
| `profiles` | lista: `{id, name, avatar, color, stats_from?}` | – | játékosprofilok (`profiles.py`); `avatar` fájlnév az `avatars\` alatt; `color` a `profiles.COLORS` egyike; `stats_from` Unix-idő: ennél régebbi játékok nem számítanak a statisztikába |
| `players` | lista: profil-azonosítók | – | ki játszik éppen, sorrendben |
| `cameras` | lista: szöveg | – | kamera-források, ahogy beírták: `0`, `1` (USB) vagy `192.168.0.56:8080` (telefon); `vision.normalize_source` alakítja URL-lé (`http://…/video`) |
| `mode_id` | szöveg | – | az utoljára választott játékmód (`games.MODES[i].id`) |
| `out` | 0 / 1 | 0 | 0 = Double Out, 1 = Straight Out |
| `approval` | 0 / 1 | 0 | kamerás kör jóváhagyása: 0 = automatikus (lejáró visszaszámlálással), 1 = kézi (`review.RoundReview.auto`) |
| `countdown` | egész, másodperc | 60 | a jóváhagyó visszaszámlálás hossza |
| `pad` | bool | true | a kézi bevitel (számlap) látszik-e |
| `last_match` | `{mode_id, pids, out}` | – | az „Utolsó meccs” gombhoz |
| `sound` | bool | true | hangeffektek |
| `speech` | bool | true | pontszám-felolvasás |
| `volume` | 0–100 | 70 | hangerő |
| `end_screen` | bool | true | meccs végi képernyő |
| `model` | szöveg (útvonal) | – | a használt YOLO modell (`.pt`); egyébként `vision.find_model` keres |
| `maximized` | bool | true | teljes méretben induljon |
| `welcome_hidden` | bool | false | ne jelenjen meg a bemutató kép |
| `wizard_done` / `wizard_hidden` | bool | false | a kalibrációs varázsló már lefutott / ne ajánlja fel induláskor |

Modell-keresés sorrendje (`vision.find_model`): `RKBULLY_MODEL` környezeti változó → `cfg["model"]` → első `*.pt` a `models\` mappában.

---

## 4. Architektúra

```
                         ┌────────────────────────────── rkbully.Main (főablak, egyetlen UI szál) ───────────────────────────────┐
 kamera (USB/IP) ──► Cam.grab szál ──► legutóbbi képkocka                                                                        │
                                          │                                                                                      │
                          vision.DetectionService (kamerán egy háttérszál)                                                       │
                          kép ─► Detector.process: YoloBackend.detect ─► CalibrationTracker (4 kalibrációs pont → homográfia)   │
                                   ─► DartTracker (mm-ben követi a nyílhegyeket) ─► események: Throw / Removed                  │
                                          │ (sor / queue)                                                                      │
                          fusion.FusionService.poll() ◄── 40 ms-os QTimer (Main.tick → poll_detection)                           │
                          FusionHub: több kamera ugyanazon nyilát EGY dobássá egyesíti, bizonytalanságot jelez                    │
                                          ▼                                                                                      │
                          review.RoundReview  (3 nyíl → visszaszámlálás, javítás, jóváhagyás)  ◄── kézi bevitel (számlap) ──────┤
                                          ▼ accept()                                                                             │
                          games.Game.throw(mult, num)  ─►  stats / history.save / sounds.cue_for / speech.speak_for / finish      │
                                          ▼                                                                                      │
                          refresh*() → játékoslista, nagy pontszám, kiszálló javaslat, utolsó körök                              │
                         └───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Alapelvek (a kód ezekre épül, módosításkor tartsd be):

1. **A játékmotor (`games.py`) nem ismer UI-t és kamerát.** Egy dobás mindig `(szorzó, szám)`: szorzó 0 = mellé, 1/2/3 = szimpla/dupla/tripla;
   szám 25 = Bull (2×25 = belső Bull, 50 pont). Minden modul (`stats`, `history`, `sounds`, `speech`, `finish`) a **játék állapotából** számol,
   nem a gombnyomásból – ezért a kézi bevitel és a kamera ugyanazt az utat járja.
2. **Visszavonás = állapot-visszaállítás.** `Game.hist` minden dobás előtt elmenti a teljes állapotot (`snap()` = `deepcopy`). Ezért a játékosztályokban
   **minden állapotot a példányon (`self.…`) tarts**, ne globálisan/osztályszinten, és csak másolható (deepcopy-zható) típusokat.
3. **A kamerás felismerés mindig a „tábla síkjában, mm-ben” dolgozik** (`dartboard.py`). Minden kamera a tábla saját 4 jelöléséből (20, 3, 11, 6) számol
   homográfiát, ezért a kamerák között nincs külön kalibráció (`fusion.py` docstring).
4. **Az `ultralytics` késői import**: csak modell betöltésekor kell (`vision.YoloBackend`). Nélküle a program elindul, csak a felismerés nem elérhető.
5. **A UI szál nem blokkolhat**: kamera-olvasás (`Cam.grab`), felismerés (`DetectionService`), betanítás (külön *folyamat*: `tools/train_worker.py`) mind háttérben fut.
6. **Tesztelhetőség**: a logikai modulok UI nélkül tesztelhetők; a UI-tesztek `QT_QPA_PLATFORM=offscreen` alatt futnak. `HEADLESS = ('offscreen', 'minimal')`
   (`sounds.py`, `speech.py`) – ilyenkor nincs hang, nincs felolvasás, nincs induláskori párbeszédablak, nincs meccs végi ablak (hacsak `end_force`).

### Koordináták és tábla (`dartboard.py`)

* Origó a tábla közepe, x jobbra, y lefelé, **mm**. A szögeket felülről, óramutató járásával megegyezően mérjük (a 20-as szektor közepe 0°).
* Méretek (mm): `R_BULL = 6.35`, `R_OUTER_BULL = 15.9`, `R_TRIPLE = (99, 107)`, `R_DOUBLE = (162, 170)`; `SECTORS` a szabványos szektorsorrend.
* `score_at(x, y)` → `(szorzó, szám)`; `margin_mm(x, y)` = a legközelebbi pontszám-határtól való távolság (a bizonytalanság mérésére).
* Jelölés: `S20, D16, T19, DB` (belső Bull), `SB` (25), `MISS` (`notation` / `parse_notation`).
* **Kalibrációs pontok:** `CAL_ANGLES` – a négy pont a külső dupla gyűrű és a szektorhatár-drótok metszése: `20` (felül), `6` (jobbra), `3` (alul), `11` (balra).
  `cal_point_mm(név)` a pont helye mm-ben. `homography(points_px)` a kép (pixel) → tábla (mm) transzformációt adja (visszavetítési hibával).

---

## 5. Kamera → pont: a felismerő lánc részletesen

**Modell (YOLO `.pt`)**: osztályok `dart` és a négy kalibrációs pont `20`, `3`, `11`, `6` (`trainer.CLASS_NAMES`). A modellt **NEM** tartalmazza a program;
a saját kamerádból betaníthatod (7. fejezet), vagy egy kompatibilis DeepDarts/Dart-Sense típusú modellt is használhatsz.

**Bemenet:** a kamerakép **középső négyzete** (`trainer.square_crop` / `Detector.crop_square=True`) – a betanítás és az éles használat ugyanazt vágja. Ezért a táblának a kép közepén kell lennie.

| Egység | Feladat | Fontos paraméterek (alapértékek) |
|---|---|---|
| `vision.Detector` | kép → felismerés → kalibráció → követés | `cal_conf=0.6`, `dart_conf=0.35` |
| `vision.CalibrationTracker` | a 4 pont helyét több képkockán át mediánnal simítja, homográfiát számol | – |
| `vision.DartTracker` | mm-ben követi a nyilakat; új dobás = több egymás utáni képkockán ugyanott | `match_mm=6`, `confirm_hits=4`, `window=6`, `clear_frames=6`, `max_darts=3`, `uncertain_margin_mm=3`, `low_conf=0.4`, `max_cal_err_mm=3`, `twin_mm=10` |
| `vision.BOARD_LIMIT_MM` | ennél messzebbi „nyilat” figyelmen kívül hagy | 260 |
| `vision.FAR_MISS_MM` | a dupla gyűrűn kívül, ennél közelebb: biztos mellé; távolabb: megerősítést kér | 240 |
| `vision.Throw` / `vision.Removed` | események: új dobás (`mult`, `num`, `x`/`y` mm-ben, `margin`, `conf`, `uncertain`, `cal_err`, `sources`, `spread`, `reason`) / a nyilak kihúzva | – |
| `vision.DetectionService` | egy kamera háttérszála; `poll()` a UI szálból veszi ki az eseményeket | – |
| `fusion.FusionHub` | több kamera dobásának egyesítése; súlyozott átlag; egyet nem értés → jóváhagyás | – |
| `review.RoundReview` | a felismert kör összegyűjtése, javítása, visszaszámlálás, `accept()` | `countdown`, `auto` |

**Finomhangolás:** ha a program túl sok téves dobást ad, a `DartTracker.confirm_hits`/`window` növelése stabilabbá teszi (lassabban reagál); ha kihagy
nyilakat, a `dart_conf` csökkentése segít. A paraméterek a `Detector`/`DartTracker` konstruktorában vannak; a `Main.toggle_detect`
hozza létre (keresd: `vision.Detector(backend)` az `rkbully.py`-ban; a `DartTracker` paramétereit a `Detector.__init__` nem adja át, ott a `DartTracker()` alapértékei élnek).

**Kalibrációs fájl** (`~/.rkbully/calibration.json`, a varázsló írja):
```json
{ "cameras": { "<kamera neve>": { "points": { "20": [0.5, 0.06], "3": [0.5, 0.94], "11": [0.06, 0.5], "6": [0.94, 0.5] },
                                    "saved": 1760000000.0 } } }
```
A pontok a négyzetes kép méretére **normalizáltak** (0–1), ezért felbontásváltásnál is érvényesek (`wizard.save_calibration` / `saved_points`).

**Kamera- és fényellenőrzés** (`camcheck.py`): `analyze(sq, cal)` → `Check` lista (OK/WARN/BAD): méret, középre állítás, élesség, fényerő,
tükröződés, egyenletes fény, a kép nyugodtsága (`ShakeMeter`), és modellel a 4 pont láthatósága (`model_check`). `overall()` adja a zöld/sárga/piros összképet.
A küszöbök szintetikus képeken hangoltak – valós kamerával finomhangolásra szorulhatnak (a `camcheck.py` elején és az `analyze`-ban találod).
`estimate_points` / `refine_points` a tábla automatikus megkeresése a piros-zöld dupla gyűrű alapján.

---

## 6. Játékmotor (`games.py`)

`Game` alaposztály, a kiterjeszthető részek:

| Metódus | Szerep |
|---|---|
| `setup()` | állapot létrehozása (példányszinten!) |
| `apply(p, m, n)` | a *p*-edik játékos dobása; `True` = a kör idő előtt véget ért (pl. bust) |
| `end_turn(p)` | a kör végén fut, a következő játékos előtt |
| `skip(p)` | `True` = a játékos kimarad (kiesett/végzett) |
| `turn_darts()` | ebben a körben hány nyilat dob (alap 3) |
| `value(p)` | összehasonlítható eredmény (nagyobb = jobb) – ebből lesz a végeredmény |
| `score(p)` / `big(p)` | a játékoslistában / a nagy számként megjelenő szöveg |
| `stats(p)`, `hint()` | kisebb kiírások, tipp |
| osztályattribútumok | `title`, `rounds` (None = győztesig), `max_rounds` (holtverseny-hosszabbítás), `unit` ("KÖR", "INNING", "LYUK") |

A `throw()`, `undo()`, `next()`, `finish()` az alaposztályban van – ne írd felül, ha nem muszáj.

### Új játékmód hozzáadása (lépésről lépésre)

1. `games.py`: írj egy `Game` utódot. A legegyszerűbb példa a **HighScore**:
   ```python
   class HighScore(Game):
       title, rounds = "HIGH SCORE", 10
       def setup(self): self.pts = [0] * self.n
       def apply(self, p, m, n): self.pts[p] += m * n
       def value(self, p): return self.pts[p]
   ```
2. Vedd fel a `MODES` listába egy `Mode(id, név, csoport, leírás, make, min_players=…, max_players=…, uses_out=…, rules=((cím, szöveg), …))` bejegyzéssel
   (`make` = `lambda nevek, double_out: UjJatek(nevek)`). A csoport a `GROUPS` egyike: `Klasszikus`, `Party`, `Gyakorló`. A `rules` adja az ℹ ablak szövegét.
3. Mást nem kell csinálni: a módválasztó, az infóablak, az előzmény és a statisztika a `MODES` listából dolgozik (`MODE_BY_ID`). A `stats.summary` általános
   játékoknál a körök/nyilak számát menti; ha egyedi összegzés kell, az ott bővíthető.
4. Írj tesztet a `tests/test_games.py` / `tests/test_modes.py` mintájára, és futtasd az összeset (9. fejezet).
5. Futtasd újra a `tools/make_codemap.py`-t (a kódtérkép frissítéséhez), és egészítsd ki a `docs/jatekmodok.md`-t.

X01-nél (`301/501/701`) a kiszálló javaslatot `games.checkout_routes(left, k, dbl)` adja (`FIN_D`/`FIN_S` táblák).

---

## 7. Modell betanítása a saját kamerából (`trainer.py`, `trainer_ui.py`, `tools/train_worker.py`)

1. A felhasználó megjelöli a 4 kalibrációs pontot (a varázsló kalibrációját használja) → `trainer.Calibration` (homográfia).
2. `Collector`: üres táblán referencia, utána a képkülönbségből (`diff_binary`, `find_blobs`) új foltot keres, `propose_tip` javasolja a nyílhegyet; a felhasználó
   jóváhagyja/javítja (`accept` / `reject` / `undo`).
3. `DatasetStore` lemezre menti: `images\*.jpg`, `labels\*.txt` (YOLO: `dart`, `20`, `3`, `11`, `6`), `meta\*.json`; `build(out_dir)` írja a `train.txt`/`val.txt`/`data.yaml`
   fájlokat (a validáció körönként elkülönített).
4. `TrainJob` **külön folyamatban** indítja a `tools/train_worker.py`-t a `job_config(...)` JSON-nal. A worker soronként ír a kimenetére:
   `RKBULLY_EPOCH|n|összes|mAP`, `RKBULLY_DONE|útvonal`, `RKBULLY_ERROR|szöveg`, `RKBULLY_INFO|…` (a `trainer.parse_line` értelmezi).
5. Az eredmény `evaluate`/`verdict` szerint értékelt; a „Használatba” gomb a modellt a `models\` mappába másolja, és beállítja a `cfg["model"]`-t.

Presetek (`trainer.PRESETS`): név → (epoch, képméret): `fast` (40 epoch, 640 px), `normal` (80, 640), `thorough` (150, 800). Minimum `MIN_SAMPLES = 30` kép, ajánlott `GOOD_DARTS = 150` nyíl.
A tanítási augmentáció szándékosan tiltja a tükrözést/forgatást/mozaikot (a kamera fix, a pontok helye számít) – lásd `tools/train_worker.py`.

**Kiinduló súlyok:** `yolov8n.pt`. Offline telepítésnél a `base\yolov8n.pt`-ből használja (`trainer.base_weights`), egyébként az ultralytics az első tanításkor letölti (internet kell).
CPU-n a tanítás lassú; NVIDIA kártyával (CUDA) sokkal gyorsabb – de a csomagolt PyTorch CPU-s, CUDA-hoz külön PyTorch-verzió kell (lásd 10. fejezet).

---

## 8. Felület (`rkbully.py` + társai)

* **`Main`** (QWidget) a főablak; a fejléc-gombok: Játékmód, Statisztikák, Beállítások (fogaskerék), hang, szünet, stb. Minden méret egy `k` skálázó szorzóval számolódik
  (`set_scale`, `fit`); a `theme.build_qss(k)` adja a stíluslapot. Az újraépítés ütemezett (`fit_timer`), húzás közben nem számol minden pixelnél.
* **Időzítő:** 40 ms (`QTimer` → `tick`): kamerák, felismerés (`poll_detection`), visszaszámlálás, kapcsolat-állapot.
* **Kamera-kártya `Cam`** (`MAX_CAMS = 3`): saját szál olvassa a képet (`cv2.VideoCapture(src, cv2.CAP_DSHOW)` Windowson), `draw_overlay` rajzolja rá a felismerést.
* **Párbeszédablakok:** `ModeDialog`/`InfoDialog` (játékmód), `options.OptionsDialog` (Játékosok, Játék, Kamerák, Hang, Megjelenés, Névjegy), `statsview.StatsDialog`,
  `finish.MatchEndDialog`, `welcome.WelcomeDialog`, `wizard.CalibrationWizard`, `trainer_ui.TrainerDialog`.
* **Megjelenés:** `theme.py`: `ORANGE #ff8a1f`, `BLUE #3a9bff`, `GREEN #38e07b`, `RED #ff4d4d`, `YELLOW #ffd23f`, `BG #070a14`, `TEXT #eef1ff`, `MUTED #8f9bd1`.
  A kártyák (`Card`) narancs→kék átmenetes neon kerettel; `Avatar` kerek profilkép.
* **Logó/ikon:** `assets\rkbully.png` (512×512) és `assets\rkbully.ico` (16…256) – a `tools/make_icons.py` generálja a forrásképből (ehhez Pillow kell; a forráskép az `assets\rkbully_forras.png`); a logó cseréje a README „A logó cseréje” részében.
* **Hangok:** `assets\sounds\*.wav` (`sounds.FILES`, `CUES`); a `tools/make_sounds.py` szintetizálja őket (külső csomag nélkül). Új hang: tedd be a `.wav`-ot, vedd fel a `CUES`/`FILES`/`NAMES` táblába.
* **Felolvasás:** `speech.py`: magyar számnevek (`hu_number`), mondatok (`announcement`), hangmotor: Qt TTS → ennek hiányában a Windows PowerShell System.Speech.

### Gyakori módosítások – hol nyúlj hozzá

| Mit akarsz | Hol |
|---|---|
| Név, verzió, szerző | `appinfo.py` (a README, telepítők és a Névjegy innen veszik; a verziót a `README.md` fejlécében és a `requirements-lock.txt` fejlécében is írd át) |
| Új játékmód / szabályváltoztatás | `games.py` (`MODES`, a megfelelő `Game` osztály) |
| Színek, betűk, méretek | `theme.py` (`build_qss`, konstansok) |
| Új beállítás | `Main.cfg[...]` olvasás/írás (3. fejezet) + kapcsoló az `options.py` megfelelő oldalán |
| Felismerés érzékenysége | `vision.py` `Detector` / `DartTracker` paraméterei (5. fejezet) |
| Kamera-ellenőrzés küszöbei | `camcheck.py` |
| Kiszálló javaslatok | `games.checkout_routes`, `FIN_D`, `FIN_S` |
| Statisztika-oszlopok | `statsview.py` (`HEAD`-ek, `total_rows`), `history.aggregate` |
| Meccs végi képernyő | `finish.py` |
| Telepítő szövegei / lépései | `installer/install.ps1` (**csak ASCII**!) → utána `tools/build_installer.py` |

---

## 9. Fejlesztői környezet és tesztek

### Futtatás a telepített mappából
```bat
cd "%LOCALAPPDATA%\RKBully Darts System"
venv\Scripts\python.exe rkbully.py              rem a program indítása (konzollal, hibák látszanak)
venv\Scripts\python.exe -m unittest discover -s tests          rem az összes teszt
venv\Scripts\python.exe -m unittest tests.test_games           rem egy tesztfájl
venv\Scripts\python.exe check_model.py models\dart.pt kep1.jpg   rem modell ellenőrzése képeken
```
A hibák megjelenítéséhez használd a `venv\Scripts\python.exe`-t (konzolos), ne a `pythonw.exe`-t (az a parancsikon, nem ír ki semmit).

### Teljesen új gépen, forrásból
```bat
git clone https://github.com/rknoise/rkbully-darts-system
cd rkbully-darts-system
py -3.12 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m pip install -r requirements-felismeres.txt   rem opcionális, nagy
venv\Scripts\python.exe rkbully.py
```
Pontosan az 1.0-ban tesztelt verziókhoz: `pip install -r requirements-lock.txt` (a lock fájl a teljes, rögzített listát tartalmazza).

### Tesztek
* Keretrendszer: `unittest`. A UI-tesztek maguk állítják be a `QT_QPA_PLATFORM=offscreen`-t.
* A tesztek száma és fájlonkénti leírása a `KODTERKEP.md` utolsó fejezetében van.
* `tests/synth.py`: szintetikus dartstábla-képeket renderel (`render(..., fill=0.39)`) – a kamera-ellenőrzés és a varázsló tesztjei ezt használják; saját kalibrációs vagy
  felismerési teszthez ez a kiindulópont.
* Ismert jelenség: a PySide6 kilépéskor ritkán összeomolhat, ha a főablak nincs szabályosan lebontva; a tesztek és szkriptek ezért `rkbully.dispose(win)`-t hívnak.
  Ha saját szkriptet írsz, ugyanezt tedd. Modális ablak ne maradjon nyitva egy szkriptben (megakad).
* A telepítő tesztjei: `tests/test_assets.py` (ASCII-ellenőrzés, CRLF, az összeállított telepítő tartalma, az offline mód bekötése).

### Szabályok, amiket a tesztek számon kérnek
* A `.bat`/`.ps1` fájlok **csak ASCII** karaktert tartalmazhatnak és **CRLF** sorvégűek (különben a Windows konzol kódlapja elrontja).
* A kötelező csomagok között nincs `ultralytics` (csak a `requirements-felismeres.txt`-ben); a program nélküle is elindul.
* `requirements-lock.txt`: minden sor `==` rögzített; minden kért csomag benne van; nincs benne a nagy, nem használt `pyside6-webengine`.

---

## 10. Telepítők és kiadás

### Két telepítő
| Fájl | Méret | Mikor |
|---|---|---|
| `RKBully_Darts_System_1.0_Teljes_Telepito\` (`Telepites.bat` + `offline\`) | ~420 MB | internet nélkül is: tartalmazza a Python 3.12.8 telepítőt, az összes csomag wheel-jét (PySide6, OpenCV, NumPy, PyTorch, ultralytics…) és a `yolov8n.pt`-t |
| `RKBully_Darts_System_1.0_Telepito_online.bat` | ~12 MB | egyetlen fájl; a Python-t és a csomagokat az internetről tölti |

A két telepítő **ugyanaz a script** (`installer/install.ps1`): ha a `Telepites.bat` mellett van egy `offline\wheels\` mappa wheel fájlokkal, offline módban fut
(`pip install --no-index --find-links offline\wheels`), különben online. `RK_FORCE_ONLINE=1` kikapcsolja az offline módot.

### A telepítő működése (`installer/install.ps1`)
1. **Kicsomagolás** – a `.bat` végén base64 zip van (`#__ZIP__` jel után): forrás, tesztek, eszközök, dokumentáció, `Inditas.bat`, `Eltavolitas.bat`.
2. **Python keresése** – 64 bites Python 3.10–3.13 (offline módban csak 3.12); ha nincs, offline a csomagbeli telepítő, online winget, majd python.org.
3. **venv + csomagok** – `venv` létrehozása, `requirements.txt` telepítése.
4. **Dobásfelismerés** – `requirements-felismeres.txt` (ultralytics + PyTorch); ha ez nem sikerül, a program akkor is indul. Offline módban a `yolov8n.pt` a `base\`-be kerül.
5. **Jegyzék + parancsikonok** – `TELEPITES_INFO.txt`, Asztal és Start menü parancsikon (`pythonw.exe rkbully.py`), `Eltavolitas.bat`.

Környezeti változók: `RK_DIR` (telepítési mappa), `RK_NOLAUNCH=1` (ne induljon el a végén), `RK_NODETECT=1` (ne telepítse az ultralytics-et),
`RK_EXTRACT_ONLY=1` (csak kicsomagol – tesztelésre), `RK_FORCE_ONLINE=1`.

### Újraépítés
```bat
venv\Scripts\python.exe tools\build_installer.py                      rem csak az online telepítő → dist\
venv\Scripts\python.exe tools\build_offline.py                         rem letölti a wheel-eket + Python telepítőt + yolov8n.pt-t → dist\offline (internet kell)
venv\Scripts\python.exe tools\build_installer.py --offline dist\offline   rem a teljes csomag → dist\RKBully_Darts_System_1.0_Teljes_Telepito\
venv\Scripts\python.exe tools\build_installer.py --offline dist\offline --zip   rem + kiadási zip és SHA256SUMS.txt (a GitHub Releases-hez)
venv\Scripts\python.exe tools\make_codemap.py                          rem docs\KODTERKEP.md frissítése
```
A telepítő szövegének módosítása után mindig építsd újra, és futtasd a `tests\test_assets.py`-t.
A `dist\` mappa a `.gitignore`-ban van: a nagy fájlokat nem a git tárolóba, hanem a GitHub **Releases**-be töltsd fel.

### Új verzió kiadása
1. `appinfo.VERSION` átírása; a `requirements-lock.txt` frissítése (új wheel-ek: `build_offline.py`).
2. `README.md` verzió-hivatkozások, `docs/KIADAS_*.md` jegyzék.
3. Tesztek → telepítők építése → GitHub Release (a fájlok + `SHA256SUMS.txt`).

### Csomagok és verziók
Az 1.0-ban tesztelt pontos verziók a `requirements-lock.txt`-ben vannak (pl. PySide6 6.12.0, OpenCV 5.0.0.93, NumPy 2.5.4, PyTorch 2.15.0, ultralytics 8.4.211).
A PyTorch a PyPI Windows-os, **CPU-s** kiadása. NVIDIA videokártyás (CUDA) betanításhoz telepíts a venv-be CUDA-s PyTorch-ot a pytorch.org utasítása szerint
(`venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu1xx`) – ez internetet kér.
A `PySide6-Addons` kell (QtMultimedia = hangok, QtTextToSpeech = felolvasás); a teljes `PySide6` meta-csomagot nem használjuk (a ~130 MB-os WebEngine-t is behúzná).

---

## 11. Hibaelhárítás fejlesztőknek

| Tünet | Ok / teendő |
|---|---|
| Parancsikon nem indít semmit | futtasd `venv\Scripts\python.exe rkbully.py`-t konzolból, a hiba kiíródik |
| `ModuleNotFoundError: PySide6` | a venv sérült: futtasd újra a telepítőt (megőrzi a beállításokat) |
| „A dobásfelismerő csomag hiányzik” | `Felismeres_telepitese.bat`, vagy `pip install -r requirements-felismeres.txt` a venv-ben |
| Offline telepítés: „csomagok telepítése nem sikerült” | hiányos az `offline\wheels` mappa; nézd a `telepites.log`-ot, hogy melyik wheel hiányzik; építsd újra: `build_offline.py` |
| Offline telepítés: Python 3.12 nincs | az `offline\` mappában kell lennie a `python-3.12*-amd64.exe`-nek, a `Telepites.bat` mellett |
| Betanítás „yolov8n.pt” letöltési hiba | internet nélkül csak az offline csomaggal megy (`base\yolov8n.pt`), vagy másold a fájlt a `base\` mappába |
| A modell nem találja a 4 pontot | kalibrációs varázsló: zöld állapotig állítsd a fényt/helyet; a modellt a saját képeiden kell betanítani |
| Újratelepítés után elveszett beállítás | nem veszhet el: a `%USERPROFILE%\.rkbully\` érintetlen; ha mégis, az adatok ott vannak |
| Teszt akad / ablak marad nyitva | UI-tesztben/szkriptben ne hagyj modális ablakot; `rkbully.dispose(win)` |

---

## 12. Amit nem teszteltünk valós eszközön (őszintén)

* A telepítő Windows-os lépései (Python-telepítés, venv, pip, parancsikonok) – a kicsomagolás és a script szintaxisa PowerShellben ellenőrzött, de a teljes futás valódi Windows 10/11-en még nem.
* A kalibrációs varázsló küszöbei szintetikus képeken hangoltak; valós kamerán a felhasználó zöldre állította és mentette, de más kamerán finomítás kellhet.
* Hangeffektek és magyar felolvasás valós hangeszközön; a modell-betanító valós kamerával; iPhone-os kamera; a három kamerás összevetés éles használatban.
* A csomaglista rendszerkövetelményei becsült értékek.
