# Nyílt forrású darts-felismerő projektek: ellenőrzött összehasonlítás

Készült: 2026. 11. 11. A Gemini-válaszban szereplő projekteket forrásból ellenőriztem (GitHub-metaadat, README, licencfájl,
cikk-összefoglaló). Ahol valamit nem sikerült megnyitni, azt jelzem.

## Összefoglaló

| Projekt | Létezik? | Licenc | Állapot | Használható az RKBully-ban? |
|---|---|---|---|---|
| **Dart-Sense** (bnww) | igen, Python, 75 csillag | CC BY-NC 4.0 (LICENSE.md), a README szerint *non-commercial, non-distributable* | aktív, utolsó commit 2026-06-06 | **Igen, személyes használatra.** Ennek a modelljét futtatja az RKBully. |
| **DeepDarts** (wmcnally) | igen, Python, 173 csillag | a kódhoz nincs licencfájl (alapból minden jog fenntartva) | 2021 óta nem frissül | A módszer és a nyílt adatkészlet igen; a kód nem másolható. |
| **OpenDartboard** | igen, C++, 22 csillag | GPL-3.0 | a README szerint *korai fejlesztés, nem éles használatra*; a pontozó (`geometry_detector`) még WIP | Most nem. Raspberry Pi + 3 kamera kell (arm64); a kliensek, köztük a Windowsos, még "coming soon" állapotúak. |
| **Darts-o-mat** (sj14) | igen, Go, 0 csillag | AGPL-3.0 | friss, de egy ember hobbiprojektje | Nem. |
| **Scored** (Der-Penz) | igen, Python, 3 csillag, "single camera keypoint detection" | nincs licencfájl | nagyon friss (2026-11-02) | Nem másolható licenc híján; érdemes figyelni. |
| **SmartDart** | nincs ilyen egyértelmű projekt | – | több, egymástól független apró tároló (pl. razorblade23/SmartDarts_v2, MIT, 2 csillag, villanytáblákhoz) | Nem. |
| **Autodarts** | igen | **zárt forrású** ("Proprietary and Free", AlternativeTo) | működő, kamerás rendszer, saját hardver-támogatással | Nem beépíthető kódként; harmadik fél eszközei (pl. darts-hub) csak az autodarts.io fiókjával működnek. |

A Gemini-válasz tehát nagyjából jól sorolta fel a neveket, de két dolgot túlzott: az OpenDartboardot "megbízható dart-detektáló motornak"
nevezte (a saját README-je szerint még nem az), és nem szólt a licencekről. A **Dart-Sense** a legközelebbi a céljaidhoz.

## Részletek

### Dart-Sense
- YOLOv8n modell (`weights.pt`, 6 MB) detektálja a nyílhegyeket és 6 kalibrációs pontot (`20`, `3`, `11`, `6`, `9`, `15`
  osztályok); a pontok alapján homográfiával a tábla síkjára vetít, onnan mm-ben számol pontszámot.
- Okostelefon-stream az IP Webcam alkalmazással, Tkinter felület, x01 és Cricket, legfeljebb 6 játékos.
- Saját teszt: képenkénti pontosság (PCS) 0,884, precision 0,977, recall 0,942. A hibák többsége takarásban lévő nyíl.
- Tanítóadat: a DeepDarts nyílt képei (~16 000) + a szerző ~8000 képe.
- Függőségek: Windowsos conda-export, Python 3.8, TensorFlow 2.13, PyTorch 2.3, ultralytics 8.2.5. A README
  `npm install requirements.txt` sora elírás. Az RKBully ezért nem a Dart-Sense kódját használja, hanem csak a modellt.
- **Licenc:** a két forrás nem teljesen egyezik. A LICENSE.md CC BY-NC 4.0 (terjeszthető, átdolgozható, névjelzéssel,
  nem kereskedelmi célra), a README viszont "non-distributable" használatot ír, és engedélyt kér a személyes kísérletezésen túlra.
  A szigorúbbat követtük: személyes használat, a modellt nem csomagoljuk az RKBully mellé.

### DeepDarts
- Cikk: McNally és mások, CVPRW 2021 (arXiv 2105.09880). Összefoglaló: 16 ezer kép két táblabeállításról; a 15 ezer
  képes, frontális elsődleges adatkészleten a teljes pontszámot a képek **94,7%-ában** találta el; a nehezebb, többféle szöget
  tartalmazó másodikon (830 tanítókép) **84,0%** volt.
- A kódhoz nem tartozik licenc. Az adatkészlet és az előtanított modellek az IEEE DataPorton nyílt hozzáféréssel
  érhetők el (az adatkészlet licencét nem ellenőriztem).
- Az RKBully a cikkben leírt **módszert** valósítja meg saját kóddal (nyílhegy + kalibrációs pontok mint objektumok,
  homográfia, mm-alapú pontozás): ez nem másolja a kódot.

### OpenDartboard
- C++ (OpenCV, httplib, json), arm64 `.deb` csomag Raspberry Pi Zero 2 W-re, 3 USB-kamerával.
- WebSocket API: `ws://<ip>:13520/scores`; JSON üzenetek `score` (`S1`...`D20`, `T20`, `BULL`, `OUTER`, `MISS`, `END`),
  `position`, `confidence`, `camera` mezőkkel.
- Ez az architektúra jó példa (felismerő szerver + külön kliens), és az RKBully egy WebSocket-bemenettel később
  kapcsolódhatna hozzá. Most azonban a pontozó rész még fejlesztés alatt van.

### Autodarts
- Az AlternativeTo "Proprietary and Free" besorolású. A kamerás rendszerhez saját mounthoz (Vantage) és PC-hez
  ajánl hardvert. Harmadik fél eszközei (darts-hub, darts-caller) az Autodarts fiókjához kapcsolódnak.
- Korábbi válaszomban (a beszélgetés elején) tévesen "open source"-nak neveztem: ez nem igaz, javítom.
- Nem ellenőriztem: a díjszabást és az API pontos feltételeit (az Autodarts dokumentációs oldala nem volt letölthető).

## Források

- Dart-Sense: https://github.com/bnww/dart-sense (README, LICENSE.md, `get_scores.py`, `video_processing.py` átolvasva)
- DeepDarts: https://github.com/wmcnally/deep-darts · https://arxiv.org/abs/2105.09880 · https://test.ieee-dataport.org/open-access/deepdarts-dataset
- OpenDartboard: https://github.com/OpenDartboard/OpenDartboard (README, `docs/api.md`, LICENSE átolvasva)
- Darts-o-mat: https://github.com/sj14/darts-o-mat · Scored: https://github.com/Der-Penz/Scored
- Dart-O-Mat 3000 (régebbi, Python/Flask pontozótábla REST API-val a felismerő szoftvereknek): https://dart-o-mat-3000.readthedocs.io/ · utódja: https://github.com/dascr/dascr-board (MIT)
- Autodarts: https://alternativeto.net/software/autodarts/about/ · https://github.com/lbormann/darts-hub
