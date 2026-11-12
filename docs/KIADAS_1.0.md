# RKBully Darts System 1.0 – kiadási jegyzék

**Verzió:** 1.0 · **Szerző:** RKNOISE · **Licenc:** AGPL-3.0 (lásd `LICENCEK.md`)

## Letölthető csomagok (GitHub Releases)

| Fájl | Méret | Mire jó |
|---|---|---|
| `RKBully_Darts_System_1.0_Teljes_Telepito.zip` | ~410 MB | **Internet nélkül** telepíthető: Python 3.12.8 + minden csomag (PySide6, OpenCV, NumPy, PyTorch, ultralytics) + a betanítás alap-súlyfájlja. Kicsomagolás után: `Telepites.bat` |
| `RKBully_Darts_System_1.0_Telepito_online.bat` | ~12 MB | egyetlen fájl, az internetről tölti a Python-t és a csomagokat |
| `SHA256SUMS.txt` | | ellenőrző összegek |

Telepítés után a program az Asztalon és a Start menüben jelenik meg; a telepítési mappa: `%LOCALAPPDATA%\RKBully Darts System`.

## Mit tud az 1.0

* 20 játékmód (Klasszikus, Party, Gyakorló), 1–8 játékos profilokkal (név, kép, szín), statisztikák és tartós előzmény.
* Neon-HUD felület, hangeffektek, magyar pontszám-felolvasás, meccs végi képernyő, szünet, „utolsó meccs” gomb.
* Kamerák: USB webkamera és telefon IP-kamera (legfeljebb 3), kamerás dobásfelismerés (YOLO + homográfia), több kamera összevetése, kör-jóváhagyás.
* Kalibrációs varázsló (élő kép, zöld/sárga/piros ellenőrzés, húzható pontok, automatikus tábla-keresés).
* Modell-betanító a saját kamerádból (mintagyűjtés, betanítás, kiértékelés, használatba vétel).
* Egy kattintásos telepítő (online és teljes offline), eltávolító, parancsikonok.
* Fejlesztői dokumentáció és kódtérkép a telepített mappában (`docs\FEJLESZTOI_ADATLAP.md`, `docs\KODTERKEP.md`).

## Tesztelés – őszintén

* Automatikus tesztek (`tests/`): mind sikeres a kiadás előtt; képernyő nélkül (offscreen) futnak.
* Valós Windows-os géppel igazolt: a program indul, a kalibrációs varázsló működik valós kamerával (a felhasználó zöld állapotig kalibrált és mentett).
* **Még nem igazolt valós eszközön:** a telepítő teljes Windows-os lefutása (Python-telepítés, venv, pip, parancsikonok), hangeffektek és felolvasás, a modell-betanító
  valós kamerával, iPhone-os kamera, a kamerás felismerés pontossága éles dobásoknál. A csomagok kicsomagolása és a telepítő script szintaxisa ellenőrzött.
* A rendszerkövetelmények becsült értékek.
