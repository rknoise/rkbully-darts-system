# RKBully Darts System – kódtérkép

*Ezt a fájlt a `tools/make_codemap.py` generálja a forráskódból (AST) – ne kézzel szerkeszd; a kód módosítása után futtasd újra.*
A magyarázó szöveg (architektúra, adatformátumok, hogyan módosíts) a `FEJLESZTOI_ADATLAP.md`-ben van.

## Program modulok (gyökérmappa)

### `appinfo.py`  (8 sor)

A program neve, verziója és készítője egy helyen (fejléc, ablakcímek, Névjegy, telepítő).

- konstans `APP_NAME` = `'RKBully Darts System'`
- konstans `SHORT_NAME` = `'RKBully'`
- konstans `SUBTITLE` = `'DARTS SYSTEM'`
- konstans `AUTHOR` = `'RKNOISE'`
- konstans `VERSION` = `'1.0'`
- konstans `GITHUB_URL` = `'https://github.com/rknoise'`
- konstans `TAGLINE` = `'Darts · Fun · Together'`

### `ask.py`  (15 sor)

Igen/Nem megerősítő kérdés magyar gombokkal (a Qt alap „Yes/No” gombjai angolok lennének).

- `confirm(parent, title, text, yes, no)` – True, ha a felhasználó az Igen gombot nyomta. Az alapértelmezett (Enter) és az Esc is a Nem.

### `camcheck.py`  (349 sor)

Kamera- és fényellenőrzés a kalibrációs varázslóhoz (felülettől független, tesztelhető).

Egy négyzetes kameraképre (a Detector is ezt a középső négyzetet látja) és a 4 kalibrációs pontra számolja ki, hogy a tábla
elhelyezése és a megvilágítás megfelel-e a felismerő modellnek: méret, középre állítás, látószög, élesség, fényerő,
tükröződés, egyenletes fény, a kép nyugodtsága, és ha van modell, az is, hogy valóban látja-e a négy pontot.

Saját modulokat használ: `dartboard`, `trainer`

- konstans `ICON` = `{OK: '✔', WARN: '⚠', BAD: '✖', NONE: '·'}`
- konstans `ORDER` = `{BAD: 0, WARN: 1, NONE: 2, OK: 3}`
- **class `Check`**
  - `icon()`
- `overall(checks)` – Az összkép: piros, ha valami hibás; sárga, ha csak figyelmeztetés van; zöld, ha minden rendben.
- `worst_first(checks)`
- `instructions(checks, limit)` – A legfontosabb teendők, szövegesen (a hibásak elöl).
- `outer_ring(cal, n)` – A külső dupla gyűrű pontjai a képen (Nx2), a kalibrációból.
- `geometry(cal)` – {"fill", "inside", "offset", "ratio"}: a tábla átmérője a kép arányában, teljesen a képen belül van-e, a középpont
- `gray_of(img)`
- `analyze(sq, cal)` – A képkocka ellenőrzése. Visszaad: [Check, ...] (a kalibrációnak érvényesnek kell lennie).
- **class `ShakeMeter`** – A képkockák közti változásból ítéli meg, hogy a kamera rögzített-e (kézben tartott telefon remeg).
  - `feed(sq)`
  - `check()`
- `model_check(det, cal, conf, max_dev)` – A modell látja-e a 4 kalibrációs pontot, és ott, ahol a felhasználó megjelölte. det: vision.Detections vagy None.
- `estimate_points(sq)` – A tábla megkeresése a piros-zöld dupla gyűrű alapján (a 20-as legyen felül). Visszaad: {pont: (x, y)} vagy None.
- `ring_score(points, colored, size)` – Mennyire fedi a kalibrációból vetített dupla gyűrű a kép piros-zöld sávját: a sáv közepén sok színes pont, a
- `wire_score(points, gray, size)` – A szektorhatár-drótoknál mennyire vált a fényerő (0..1): jó kalibrációnál a drót két oldalán eltérő a szektor színe.
- `_refine(points, colored, gray, size, seed)` – A kezdeti (ellipszis-alapú) becslés finomítása véletlen kereséssel, durvától a finomig: először elmosott képen (nagy
- `refine_points(points, colored, gray, size, seeds)` – Több véletlen indítás közül a legjobb illeszkedésű (éles képen mért) eredményt adja.

### `check_model.py`  (55 sor)

A dobásfelismerő modell és a kamera-beállítás ellenőrzése egy-egy képen.

Használat:   python check_model.py models/dart.pt kep1.jpg [kep2.jpg ...]
Kiírja a felismert kalibrációs pontokat és nyilakat pontszámmal, és az eredményt képként a
check_output mappába menti (zöld kör = kalibrációs pont, piros kör = nyílhegy a pontszámmal).
Ha a 4 zöld pont a tábla dupla gyűrűjének külső szélén, a szektorhatár-drótoknál van, jó a beállítás.

Saját modulokat használ: `dartboard`, `vision`

- `annotate(img, res)`
- `main(argv)`

### `dartboard.py`  (126 sor)

Darts tábla geometriája: pontszámítás, kalibráció (homográfia) és bizonytalanság-mérés.

Koordináta-rendszer a "tábla síkjában": a közép az origó, x jobbra, y lefelé, mm-ben.
A szögeket felülről, óramutató járásával megegyező irányban mérjük (a 20-as szektor közepe 0 fok).

- konstans `R_BULL` = `6.35`
- konstans `R_OUTER_BULL` = `15.9`
- konstans `R_TRIPLE` = `(99.0, 107.0)`
- konstans `R_DOUBLE` = `(162.0, 170.0)`
- konstans `SECTORS` = `(20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5…`
- konstans `CAL_ANGLES` = `{'20': -9.0, '6': 81.0, '3': 171.0, '11': 261.0, '9': 297.0, '15': 117…`
- konstans `_NOTATION` = `{'DB': (2, 25), 'BULL': (2, 25), 'SB': (1, 25), 'OUTER': (1, 25), '25'…`
- `cal_point_mm(name)` – A kalibrációs pont helye a tábla síkjában (mm).
- `score_at(x, y)` – (szorzó, szám) a tábla síkjának (x, y) pontjára. Mellé: (0, 0); Bull: (2, 25); 25-ös: (1, 25).
- `margin_mm(x, y)` – Milyen messze (mm) van a pont a legközelebbi pontszám-határtól (gyűrűtől vagy szektordróttól).
- `notation(mult, num)` – Gépi jelölés: S20, D16, T19, DB (bull), SB (25), MISS.
- `parse_notation(text)` – Visszafejti a jelölést (S20, D16, T19, DB/BULL, SB/25/OUTER, MISS) -> (szorzó, szám), vagy None.
- `_fit(points_px, names)`
- `homography(points_px, max_err_mm)` – Kép (pixel) -> tábla síkja (mm) transzformáció a felismert kalibrációs pontokból.
- `apply_h(H, pts)` – Pontok (N×2) átvetítése a H homográfiával.

### `finish.py`  (214 sor)

Meccs végi képernyő: a győztes kiemelése, konfetti és a játékosok átlagai.

A `standings` a játék állapotából számol (felülettől független, tesztelhető), a `MatchEndDialog` csak megjeleníti.

Saját modulokat használ: `stats`, `statsview`, `theme`

- konstans `HEAD` = `['#', 'Játékos', 'Eredmény', 'Átlag (3 nyíl)', 'Nyilak', 'Legjobb kör'…`
- konstans `CONFETTI` = `['#ff8a1f', '#ffd23f', '#3a9bff', '#38e07b', '#ff4d9d', '#ffffff']`
- `is_x01(game)`
- `standings(game)` – Játékosonként a meccs számai, a helyezés szerint rendezve (a győztes(ek) elöl).
- `highlights(rows)` – A meccs kiemelései: a legjobb átlag és a legjobb kör játékosa (csak ha volt dobás).
- `fmt_avg(v)`
- **class `MatchEndDialog`** (QDialog) – A győztes képernyője. Az eredmény (`choice`): "rematch" (visszavágó), "stats" vagy "close".
  - `tagline(winners)` – Egy mondat a győztesről: átlag és legjobb kör.
  - `finish(choice)`
  - `done(result)`
  - `burst(n)`
  - `step()`
  - `paintEvent(_)`

### `fusion.py`  (243 sor)

Több kamera összevetése.

Miért nem kell valódi háromszögelés: a nyílhegy a tábla síkján van, és minden kamera a *tábla saját jelöléseiből*
(20, 3, 11, 6) számol homográfiát, vagyis mindkét kamera ugyanabba a koordináta-rendszerbe (a tábla síkja, mm) vetíti
a nyílhegyet. A kamerák között ezért nincs külön kalibráció. Az összevetés három dolgot csinál:

  1. ugyanazon nyíl két észlelését egyetlen dobássá egyesíti (nincs dupla számolás),
  2. a két becslést súlyozva átlagolja (a magabiztosabb, jobban kalibrált kamera többet számít),
  3. jelzi, ha a kamerák nem értenek egyet, vagy az egyik nem látta a nyilat, akkor a játékosnak kell jóváhagynia.

A kameránkénti felismerés (vision.Detector) változatlan: minden kamerának saját dobáskövetője van, ez az egység a
már megerősített Throw / Removed eseményeket fogja össze. Egyetlen kamerával pontosan úgy viselkedik, mint korábban.

Saját modulokat használ: `dartboard`, `vision`

- **class `FusionHub`** – Kamerák eseményeinek egyesítése. A felület szálából használható (nincs benne saját szál).
  - `add_camera(name, healthy)`
  - `remove_camera(name)`
  - `set_health(name, ok)`
  - `reset()` – Új kör / új játék: minden függő állapot eldobása.
  - `push(cam, events)` – Egy kamera új eseményei (Throw / Removed). Visszatér az összevetett eseményekkel.
  - `poll(now)` – Időzített teendők: a várakozás lejárta után egy kamera dobása önállóan is kiadódik; a kihúzás időtúllépése.
  - `_weight(th)` – Heurisztikus súly: a magabiztosabb és jobban kalibrált kamera többet számít (nem mért értékekből levezetve).
  - `fuse(a, b)` – Két kamera becslésének egyesítése egy Throw-vá.
- **class `FusionService`** – A felület ezzel beszél: kamerák háttérszálai (vision.DetectionService) + az összevető egység.
  - `add(name, service)`
  - `remove(name)`
  - `stop()`
  - `reset_round()`
  - `error()`
  - `poll()` – A felület időzítőjéből hívva: összegyűjti a kamerák eseményeit, és visszaadja az összevetett eseményeket.

### `games.py`  (680 sor)

RKBully játékmotor: pontszámítás és szabályok (a felülettől és a kameráktól független).

Egy dobás = (szorzó, szám); szorzó 0 = mellé, szám 25 = Bull (2 = belső Bull = 50).
Minden játék körökre épül: egy kör (turn) legfeljebb `turn_darts()` nyíl, a kör idő előtt is véget érhet.

- `label(m, n)`
- konstans `ORDER` = `[(3, n) for n in range(20, 0, -1)] + [(2, 25)] + [(2, n) for n in rang…`
- konstans `FIN_D` = `{m * n: (m, n) for m, n in reversed(ORDER) if m == 2}`
- konstans `FIN_S` = `{m * n: (m, n) for m, n in reversed(ORDER)}`
- `checkout_routes(left, k, dbl, limit)` – Kiszálló útvonalak legfeljebb k nyílból, a legkevesebb nyíllal kezdve: [((szorzó, szám), ...), ...].
- `checkout(left, k, dbl)` – Ugyanez szövegesen: ["T20 → T17 → D18", ...].
- `target_name(n)`
- **class `Game`**
  - `setup()`
  - `apply(p, m, n)` – A p játékos egy dobása. True = a kör idő előtt véget ért.
  - `end_turn(p)`
  - `skip(p)`
  - `turn_darts()`
  - `value(p)`
  - `score(p)`
  - `big(p)`
  - `stats(p)`
  - `hint()`
  - `snap()`
  - `throw(m, n)`
  - `undo()`
  - `next()`
  - `finish()` – A játék vége pontok szerint. Holtversenynél hosszabbít (ha a mód engedi), különben döntetlen.
  - `round_text()`
- **class `X01`** (Game)
  - `setup()`
  - `apply(p, m, n)`
  - `value(p)`
  - `score(p)`
  - `stats(p)`
  - `hint()`
- **class `Cricket`** (Game)
  - `setup()`
  - `apply(p, m, n)`
  - `value(p)`
  - `hint()`
- **class `Clock`** (Game)
  - `setup()`
  - `target(p)`
  - `apply(p, m, n)`
  - `value(p)`
  - `score(p)`
  - `hint()`
- **class `Shanghai`** (Game)
  - `setup()`
  - `apply(p, m, n)`
  - `value(p)`
  - `hint()`
- **class `HighScore`** (Game)
  - `setup()`
  - `apply(p, m, n)`
  - `value(p)`
- **class `Killer`** (Game) – Mindenkinek van egy száma és 3 élete. Aki a saját duplájába dob, Gyilkos lesz, és az ellenfelek duplájával
  - `setup()`
  - `skip(p)`
  - `turn_darts()`
  - `alive()`
  - `hurt(q)`
  - `apply(p, m, n)`
  - `value(p)`
  - `score(p)`
  - `big(p)`
  - `stats(p)`
  - `hint()`
- **class `Baseball`** (Game) – 9 inning: az inning számát kell dobni; szimpla 1, dupla 2, tripla 3 futás.
  - `setup()`
  - `apply(p, m, n)`
  - `value(p)`
  - `hint()`
- **class `Golf`** (Game) – 18 lyuk (1–18), lyukanként 3 nyíl, a legjobb nyíl számít; kevesebb ütés a jobb. Döntetlennél a 19., 20. lyuk, majd a Bull.
  - `setup()`
  - `hole()`
  - `cost(m, n)`
  - `apply(p, m, n)`
  - `end_turn(p)`
  - `value(p)`
  - `score(p)`
  - `hint()`
- **class `Bermuda`** (Game) – 13 kör, körönként más cél; ha mind a 3 nyíl mellé megy, a pontszám felére esik.
  - `setup()`
  - `target()`
  - `points(m, n)`
  - `apply(p, m, n)`
  - `end_turn(p)`
  - `value(p)`
  - `hint()`
- **class `Bobs27`** (Game) – 27 ponttal indulsz, D1–D20, majd Bull. Találatonként +a dupla értéke; ha mind a 3 mellé megy, −a dupla értéke.
  - `setup()`
  - `target()`
  - `skip(p)`
  - `apply(p, m, n)`
  - `end_turn(p)`
  - `value(p)`
  - `stats(p)`
  - `hint()`
- **class `Doubles`** (Game) – D1–D20, majd Bull; mindegyikre 3 nyíl, minden találat 1 pont.
  - `setup()`
  - `target()`
  - `apply(p, m, n)`
  - `value(p)`
  - `hint()`
- **class `BullPractice`** (Game) – 10 kör a Bullra: külső Bull 1 pont, belső Bull 2 pont.
  - `setup()`
  - `apply(p, m, n)`
  - `value(p)`
  - `hint()`
- **class `Hundred`** (Game) – Pontszerző gyakorlat: pontosan 100 nyíl (33 kör × 3 + 1), bárhová dobhatsz, az összpont számít.
  - `setup()`
  - `turn_darts()`
  - `apply(p, m, n)`
  - `value(p)`
  - `stats(p)`
  - `hint()`
- **class `Scoring`** (Game) – 10 kör; egy kör akkor sikeres, ha a 3 nyíl összege eléri a célpontot (99 vagy 121).
  - `setup()`
  - `apply(p, m, n)`
  - `end_turn(p)`
  - `value(p)`
  - `score(p)`
  - `stats(p)`
  - `hint()`
- **class `A1`** (Game) – A1 gyakorlat: 20, 19, …, 13 és Bull. Egy szám akkor kap jelzést, ha a 3 nyílból legalább 2 a számra esik;
  - `setup()`
  - `current(p)`
  - `skip(p)`
  - `apply(p, m, n)`
  - `end_turn(p)`
  - `closed(p)`
  - `value(p)`
  - `score(p)`
  - `big(p)`
  - `stats(p)`
  - `hint()`
- **class `Finisher`** (Game) – Közös alap a kiszállást gyakorló módokhoz: játékosonként külön feladat (Double Out), egy feladatra `visits` kör jut.
  - `setup()`
  - `first()`
  - `extra()`
  - `skip(p)`
  - `set_target(p, t)`
  - `apply(p, m, n)`
  - `end_turn(p)`
  - `big(p)`
  - `hint()`
- **class `Checkout121`** (Finisher) – 121-től indulsz; 9 nyíl (3 kör) alatt kell kiszállni dupla zárással. Siker: a következő szám (egészen 170-ig),
  - `first()`
  - `extra()`
  - `advance(p, t)`
  - `solved(p, used)`
  - `failed(p)`
  - `value(p)`
  - `score(p)`
  - `stats(p)`
- **class `Catch40`** (Finisher) – 40 kiszálló (61–100), egyenként legfeljebb 6 nyíl (2 kör). 2 nyílból 3 pont, 3-ból 2 pont, 4–6-ból 1 pont
  - `first()`
  - `extra()`
  - `advance(p)`
  - `solved(p, used)`
  - `failed(p)`
  - `value(p)`
  - `score(p)`
  - `stats(p)`
- `apply_round(game, darts)` – Egy kör dobásait (szorzó, szám) viszi be a játékba. Megáll, ha a kör idő előtt véget ér
- konstans `GROUPS` = `('Klasszikus', 'Party', 'Gyakorló')`
- konstans `MAX_PLAYERS` = `8`
- **class `Mode`**
  - `players_text()`
- konstans `_X01_RULES` = `(('Cél', 'Elsőként érj pontosan nullára a kezdőpontról.'), ('Menet', '…`
- konstans `MODES` = `[Mode('301', '301', 'Klasszikus', 'Gyors lejátszású, 301-ről nullára',…`
- konstans `MODE_IDS` = `[m.id for m in MODES]`

### `history.py`  (94 sor)

A befejezett játékok tartós előzménye és a profilonkénti összesítés (a felülettől független).

Egy játék a végén egyetlen bejegyzésként mentődik a `history.json` fájlba. A játékosok azonosítója a profil azonosítója,
így az átnevezés az összesítést nem szakítja szét; a bejegyzésben a név is megmarad, hogy törölt profilnál is olvasható legyen.

Saját modulokat használ: `stats`

- konstans `MAX_RECORDS` = `1000`
- `history_path(cfg_file)` – Az előzményfájl a beállításfájl mellett van.
- `load(path)`
- `save(records, path)`
- `make_record(game, pids, mode, now)` – Egy befejezett játék bejegyzése. `pids`: a játékosok profilazonosítói a játék sorrendjében.
- `aggregate(records, mode_id, since)` – Profilonkénti összesítés, a legtöbbet győzőtől a legkevesebbig. `mode_id`: csak az a játékmód (None = mind).
- `modes_in(records)` – A játékmódok azonosítói, amikből van bejegyzés (a szűrőhöz), előfordulás szerint rendezve.

### `options.py`  (546 sor)

Beállítások (fogaskerék menü) és játékos hozzáadása. Minden beállítás egy helyen, a bal oldali menüből választva.

A felület (Main) adja az adatokat és a műveleteket; ez a modul csak a párbeszédablakokat tartalmazza.

Saját modulokat használ: `appinfo`, `ask`, `history`, `profiles`, `sounds`, `theme`

- `avatar_pixmap(profile, size)` – A profil kerek képe (vagy kezdőbetűje) kis ikonként a listákhoz.
- `label(text, name, wrap)`
- **class `ProfilesPage`** (QWidget) – Profilok szerkesztése: név, profilkép feltöltése, szín, új profil, törlés.
  - `reload(select)`
  - `profile()`
  - `stats_row(p)` – A profil összesítése a mentett játékokból (None, ha még nincs egy sem a nullázás óta).
  - `show_stats(p)`
  - `reset_profile_stats()`
  - `add_profile()`
  - `rename()`
  - `set_color(color)`
  - `choose_image()`
  - `clear_image()`
  - `delete_profile()`
- **class `GamePage`** (QWidget)
  - `set_end_screen(on)`
- **class `CameraPage`** (QWidget)
  - `refresh()`
  - `choose()`
- **class `SoundPage`** (QWidget) – Hangeffektek: be/ki, hangerő és próbagombok minden hanghoz.
  - `set_volume(percent)`
- **class `LookPage`** (QWidget)
  - `set_max(on)`
  - `set_welcome(on)`
  - `open_welcome()`
- **class `AboutPage`** (QWidget)
- **class `OptionsDialog`** (QDialog)
- **class `AddPlayerDialog`** (QDialog) – Játékos hozzáadása a játékhoz: egy még nem játszó profil, vagy új profil.
  - `fill()`
  - `accept_pick()`
  - `new_profile()`

### `profiles.py`  (109 sor)

Játékosprofilok: név, profilkép (feltöltött JPG/PNG), szín. A beállításfájlban tárolva, a felülettől független.

A profilképet a program egy kis (256×256, négyzetre vágott) JPG-vé alakítja a `~/.rkbully/avatars` mappában, így a
nagy fényképek sem lassítják a felületet, és az eredeti fájl törlése nem rontja el a profilt.

- konstans `AVATAR_DIR` = `Path.home() / '.rkbully' / 'avatars'`
- konstans `AVATAR_PX` = `256`
- konstans `COLORS` = `['#ff8a1f', '#3a9bff', '#38e07b', '#e05aff', '#ffd23f', '#ff5a7a', '#2…`
- konstans `MAX_PLAYERS` = `8`
- `new_id()`
- `make_profile(name, used_colors)` – Új profil: az első még nem használt színnel.
- `clean(profile)` – Hibás/hiányos bejegyzésből használható profil (a beállításfájl kézzel is szerkeszthető).
- `load(cfg)` – (profilok, játékosok azonosítói) a beállításokból. A régi, csak neveket tároló fájlból profilokat készít.
- `dump(profiles, players)`
- `name_taken(profiles, name, except_id)`
- `unique_name(profiles, base)` – "Játékos 3" típusú, még nem használt név.
- `avatar_path(profile, folder)` – A profilkép fájlja, ha van és létezik.
- `import_avatar(src, pid, folder)` – Egy képfájlból (JPG/PNG/…) kis, négyzetes JPG profilkép. Visszaadja a fájlnevet; ValueError, ha nem kép.
- `delete_avatar(profile, folder)`

### `review.py`  (177 sor)

A kamerával felismert, még el nem fogadott kör: összegyűjtés, javítás, visszaszámlálás, jóváhagyás.

A felismert dobások nem kerülnek azonnal a játékba. Amikor megvan a 3 nyíl, elindul egy visszaszámlálás;
a játékos jóváhagyhatja a kört, vagy kijelölheti és átírhatja bármelyik nyilat. A felülettől független, tesztelhető.

- **class `Item`**
  - `points()`
  - `edited()`
- **class `RoundReview`**
  - `set_size(size)` – A játék közli, hány nyilas a soron következő kör. A felesleges dobások a következő körbe kerülnek.
  - `active()`
  - `full()`
  - `total()`
  - `seconds_left()`
  - `paused()`
  - `pause()`
  - `resume()` – A szünet alatt eltelt idővel kitolja a határidőt: a visszaszámlálás ott folytatódik, ahol megállt.
  - `needs_manual()` – Van olyan dobás, amit a játékosnak kell jóváhagynia.
  - `due()` – Lejárt a visszaszámlálás, és automatikusan elfogadható (nincs bizonytalan dobás).
  - `add_detected(throw)` – Kamera által felismert dobás (vision.Throw). Ha a kör már teljes, a következő körbe várakozik.
  - `add_manual(mult, num)` – Kézzel beütött dobás (pl. a kamera által nem látott "mellé"). Teljes körnél nem fogad el újat.
  - `select(idx)`
  - `edit(idx, mult, num)`
  - `on_removed()` – A nyilakat kihúzták. Ha kevesebb dobást láttunk, mint a kör nyílszáma, a hiányzókat "mellé"-nek vesszük (megerősítést kérve).
  - `accept()` – Elfogadja a kört: visszaadja a dobásokat [(szorzó, szám), ...], és a várakozó dobások lesznek az új kör.
  - `discard()`
  - `_touch()` – Javítás közben ne járjon le az idő: legalább min_after_edit másodperc marad.
  - `undo()` – Az utolsó még el nem fogadott dobás törlése.
  - `text()`
- `show(mult, num)` – Megjelenített név: S5 / D16 / T20 / Bull / 25 / Mellé.

### `rkbully.py`  (1712 sor)

RKBully Darts System – többjátékos darts kezelőfelület (max. 8 játékos)

Telepítés:  pip install -r requirements.txt
Indítás:    python rkbully.py
Kamerás dobásfelismerés (nem kötelező):  pip install ultralytics  +  modellfájl, lásd README.md

Saját modulokat használ: `appinfo`, `ask`, `finish`, `fusion`, `games`, `history`, `options`, `profiles`, `review`, `sounds`, `speech`, `stats`, `statsview`, `theme`, `trainer_ui`, `vision`, `welcome`, `wizard`

- konstans `MODE_BY_ID` = `{m.id: m for m in MODES}`
- konstans `APP_DIR` = `Path(__file__).resolve().parent`
- konstans `CFG_FILE` = `Path.home() / '.rkbully' / 'settings.json'`
- konstans `LOGO_FILE` = `APP_DIR / 'assets' / 'rkbully.png'`
- konstans `APP_ID` = `'RKBully.Darts.App'`
- konstans `MAX_CAMS` = `3`
- `set_app_id()` – Windowson külön alkalmazásazonosító, különben a tálcán a Python ikonja látszik. Máshol nem csinál semmit.
- `logo_pixmap()` – A logó képe (üres, ha a fájl hiányzik: a program ikon nélkül is működik).
- `load_cfg()`
- `save_cfg(cfg)`
- konstans `QSS` = `build_qss(1.0)`
- `dispose(win)` – Az ablak szabályos lebontása. Nélküle a főablak az értelmező leállásakor, véletlen sorrendben semmisül meg, és a
- `clear(lay)` – Egy elrendezés tartalmának törlése. Csak widgetek vannak benne (a sorok és cellák saját widgetbe csomagolva),
- `rules_html(mode, n_players)` – A játék leírása az infóablakhoz: hányan játszhatják, és hogyan kell játszani.
- **class `InfoDialog`** (QDialog) – Egy játékmód leírása: játékosszám és szabályok.
- `show_mode_info(parent, mode, n_players)`
- **class `ModeDialog`** (QDialog) – Játékmód-választó: csoportosított kártyák, mindegyiken ℹ gomb a szabályokkal.
  - `choose(mode_id)`
- `draw_overlay(img, ov)` – Rárajzolja a kalibrációs pontokat és a felismert nyilakat a kamerakép egy másolatára.
- `fmt_time(seconds)`
- `ultralytics_help(python_exe, app_dir)` – A hiányzó dobásfelismerő csomag üzenete: pontos telepítési parancs ugyanahhoz a Pythonhoz, amivel a program fut.
- **class `Cam`** (Card) – Egy kamera élő képe (USB webkamera vagy telefon IP-kamera stream).
  - `grab()`
  - `update_view()`
- **class `Main`** (QWidget)
  - `paintEvent(_)`
  - `set_scale(k)` – Betűk, térközök, méretek a k szorzóval; a tartalom újraépül.
  - `settle()` – Lefuttatja a függő elrendezési eseményeket, hogy a méretek (fits) a valós állapotot mutassák.
  - `fits()`
  - `fit()` – A felület az ablakhoz igazodik. A méretarány az ablak méretéből jön; ha így is kilógna (kis képernyő vagy sok
  - `resizeEvent(e)`
  - `toggle_fullscreen()`
  - `set_pad_visible(on)` – A „Kézi bevitel” gomb. Kis képernyőn (összecsukott állapotban) csak erre a munkamenetre nyit, a mentett
  - `editing()`
  - `update_pad()` – A kézi bevitel kapcsolható; egy nyíl javításakor magától megjelenik. Ha az ablak kicsi, a fit() összecsukja
  - `new_review()`
  - `approval_idx()`
  - `set_approval(idx)`
  - `set_countdown(seconds)`
  - `rv_click(i)`
  - `accept_round()`
  - `discard_round()`
  - `refresh_review(force)`
  - `cur_mode()`
  - `choose_mode()`
  - `set_mode(mode_id)`
  - `new_game()`
  - `remember_match()` – A játék beállításai (játékosok, játékmód, kiszállás) a „legutóbbi meccshez”, ha már dobtak benne.
  - `last_match()` – A mentett legutóbbi meccs, ha még érvényes (van játékosa és ismert játékmódja); különben None.
  - `update_last_button()`
  - `restart_last_match()` – Visszaállítja a legutóbbi meccs játékosait, játékmódját és kiszállását, és újraindítja a játékot.
  - `show_match_end()`
  - `schedule_match_end()` – A győzelem után kis késéssel (a fanfár és a felolvasás kezdete után) megjelenik a meccs végi képernyő.
  - `toggle_pause()`
  - `set_paused(on)`
  - `hit(n)`
  - `undo()`
  - `update_banner()`
  - `sync_history()` – A befejezett játék egyszer mentődik az előzménybe; ha a visszavonás visszaviszi a játékot, a bejegyzés is törlődik.
  - `update_sound_button()`
  - `set_sound(on)` – A hangeffektek be/ki (a fejléc hangszóró gombja és a beállítások is ezt hívja).
  - `set_speech(on)` – A pontszám felolvasása be/ki.
  - `set_volume(percent)`
  - `play_cue()` – Egy új dobás után a megfelelő hang. Új játéknál és visszavonásnál nem szól semmi.
  - `stats_since()` – Profilonként a statisztika nullázásának ideje (csak a nullázott profiloké).
  - `reset_stats(pid)` – Egy profil statisztikájának nullázása: a mostantól befejezett játékok számítanak. A játékok listája megmarad.
  - `clear_history()`
  - `refresh()`
  - `refresh_helper(g, cur, winner)` – Segédlet: 301/501/701-nél kiszálló útvonalak (a legkevesebb nyíllal), más játékoknál a játék tippje.
  - `refresh_strip(g, cur)`
  - `set_avatar(widget, i, size, ring)`
  - `refresh_players(g, cur, winners)`
  - `refresh_recent(g)`
  - `update_timer()`
  - `update_connection()`
  - `profile_by_id(pid)`
  - `profile_at(i)` – A i. játékos profilja (azonosító alapján, ennek hiányában név alapján); None, ha nincs.
  - `fill_players(minimum)` – Legalább `minimum` játékos legyen: a hiányzókat még nem játszó profilokból, vagy újakból pótolja.
  - `add_player()`
  - `del_player()`
  - `rename_profile(pid, new)` – Átnevezés: a most játszó játékos neve, a játék és az előzmények is frissülnek.
  - `profiles_changed()`
  - `open_options(page)`
  - `show_stats()`
  - `add_cam()`
  - `add_cam_source(text)`
  - `rm_cam(cam)`
  - `update_left()` – A kamerák egyenlően osztják el a bal oszlopot; a „Kamera hozzáadása” gomb elrejtődik, ha elértük a maximumot.
  - `get_backend()`
  - `toggle_detect(cam, on)` – Egy kamera dobásfelismerésének be- és kikapcsolása. Több kamera egyszerre is mehet: a dobásaikat a
  - `detect_off(cam)`
  - `stop_detection()`
  - `restart_round()` – A kamerák köre megváltozott: tiszta jóváhagyó panel, a követők és az összevető is újraindul.
  - `poll_detection()` – A háttérszál eseményeinek átvétele (új dobás / nyilak kihúzva).
  - `tick()`
  - `calib_file()`
  - `silent_backend()` – A modell párbeszédablakok nélkül (a varázsló háttérszálából): None, ha nincs modell vagy ultralytics.
  - `open_wizard(startup)` – Kalibrációs varázsló. A kamerák nevei a főképernyőn látható nevek; ha nincs kamera, a varázsló elmagyarázza a
  - `open_trainer()` – Modell-betanító: a saját kamerák képeiből tanít dobásfelismerő modellt.
  - `startup_wizard()` – Az első indításkor (a telepítés után) a kalibrációs varázsló, hacsak nem kapcsolták ki vagy már megvolt.
  - `startup_welcome()` – Induláskor a bemutató kép, hacsak a felhasználó nem pipálta be a „Többé ne jelenjen meg” jelölőt.
  - `show_welcome()`
  - `startup()` – Induláskor: bemutató kép, majd (először) a kalibrációs varázsló.
  - `save_state()`
  - `closeEvent(e)`

### `sounds.py`  (109 sor)

Hangeffektek: melyik esemény melyik hangot játssza (felülettől független), és a lejátszó.

A hang a játék állapotából következik, nem a gombnyomásból, így a kézi bevitel és a kamerás felismerés ugyanúgy szól.
A visszavonás és az új játék néma.

Saját modulokat használ: `stats`

- konstans `HEADLESS` = `('offscreen', 'minimal')`
- konstans `CUES` = `('dart', 'double', 'triple', 'bull', 'next', 'ton', '180', 'bust', 'wi…`
- konstans `FILES` = `{'dart': 'dart.wav', 'double': 'double.wav', 'triple': 'triple.wav', '…`
- konstans `NAMES` = `{'dart': '🎯  Nyíl a táblán', 'double': '✨  Dupla', 'triple': '⚡  Tripl…`
- `dart_cue(mult, num)` – Egy nyíl hangja: a bull, a tripla és a dupla külön effektet kap, minden más a sima puffanást.
- `cue_for(game)` – Az utolsó dobás(ok) után melyik hang szóljon (None = egyik sem). A hívó azt garantálja, hogy a játék előrelépett.
- **class `SoundBoard`** – A hangok betöltése és lejátszása. Hiányzó fájl vagy hanglejátszó nélkül is csendben működik.
  - `preload()` – Az összes hang betöltése induláskor, hogy az első lejátszás se késsen.
  - `set_volume(volume)`
  - `play(cue, force)` – Lejátssza a hangot. `force`: a némítástól függetlenül (a beállítások „Próba” gombjához).

### `speech.py`  (227 sor)

Pontszám-felolvasás: magyar számnevek, a felolvasott mondatok (felülettől független) és a hangmotorok.

A felolvasás a játék állapotából következik, mint a hangeffektek: a kör végén (és a győzelemnél) szól, a kör közbeni
nyilaknál nem. Hangmotor: a Qt beépített TTS-e (Windowson a rendszer hangja), ennek hiányában a Windows PowerShell
System.Speech-je; ha egyik sincs, a program csendben megy tovább.

Saját modulokat használ: `stats`

- konstans `ONES` = `['', 'egy', 'kettő', 'három', 'négy', 'öt', 'hat', 'hét', 'nyolc', 'ki…`
- konstans `TEENS` = `{10: 'tíz', 20: 'húsz'}`
- konstans `TENS_PREFIX` = `{1: 'tizen', 2: 'huszon'}`
- konstans `TENS` = `{3: 'harminc', 4: 'negyven', 5: 'ötven', 6: 'hatvan', 7: 'hetven', 8: …`
- konstans `HEADLESS` = `('offscreen', 'minimal')`
- `hu_number(n)` – Egész szám magyarul kimondva (0–9999; negatívnál „mínusz”). Pl. 180 -> „száznyolcvan”, 22 -> „huszonkettő”.
- `_below_100(n)`
- `_below_1000(n)`
- `_below_10000(n)`
- `digits_or_words(n, hungarian)` – Magyar hang esetén szavakkal, más nyelvű hangnál számjegyekkel (a hang a saját nyelvén olvassa).
- `announcement(game, hungarian)` – Mit olvasson fel a program a legutóbbi dobás után (None = semmit). Csak lezárt körnél vagy győzelemnél szól.
- **class `NullEngine`**
  - `say(text)`
  - `stop()`
- **class `RecordingEngine`** (NullEngine) – Tesztekhez: elteszi, mit kellett volna felolvasnia.
  - `say(text)`
- **class `QtEngine`** (NullEngine)
  - `say(text)`
  - `stop()`
- konstans `PS_SCRIPT` = `"Add-Type -AssemblyName System.Speech;$s = New-Object System.Speech.Sy…`
- **class `PowerShellEngine`** (NullEngine) – Windows: a beépített System.Speech. A magyar hang meglétét induláskor egyszer kérdezi le.
  - `has_hungarian()`
  - `say(text)`
  - `stop()`
- `make_engine()` – A legjobb elérhető hangmotor; képernyő nélküli környezetben (tesztek) és hang nélkül a NullEngine.
- **class `Announcer`** – Felolvasó: be/ki kapcsolható; a hangmotor lustán, az első használatkor jön létre (az indulást nem lassítja).
  - `engine()`
  - `speak_for(game, force)` – A játék állapota alapján felolvas valamit, ha kell. Visszaad: a felolvasott szöveg vagy None.
  - `say(text, force)`
  - `sample()` – A beállítások „Próba” gombja.

### `stats.py`  (91 sor)

Játékstatisztika a játékmotor előzményeiből (a felülettől független).

A `Game.hist` minden dobás előtti állapotot őriz, ebből visszaállítható, ki mit dobott. Így a visszavonás is
automatikusan helyes: a visszavont dobás kikerül az előzményekből, és vele a statisztikából is.

Saját modulokat használ: `games`

- `_closed_rounds(game)` – A befejezett körök időrendben: (játékos_index, [(szorzó, szám), ...], kör eleji állapot, kör utáni állapot).
- `round_log(game)` – A befejezett körök időrendben: [(játékos_index, [(szorzó, szám), ...]), ...].
- `points(darts)`
- `player_stats(game)` – Játékosonként: körök, nyilak, dobott pont, legjobb kör, 3 nyilas átlag (a folyamatban lévő kör nyilaival együtt).
- `recent(game, limit)` – A legutóbbi körök, legfrissebb elöl: [(név, [feliratok], összeg), ...].
- `x01_rounds(game)` – X01 körök a ténylegesen levont pontokkal: bustnál a kör 0-t ér, bár a nyilak értéke nem 0.
- `summary(game)` – A tartós előzményhez: játékosonként körök és nyilak; X01-nél a ténylegesen számított pontok, a legjobb kör,

### `statsview.py`  (213 sor)

Statisztika-ablak: összesítés profilonként, a folyó játék és a befejezett játékok előzménye.

Saját modulokat használ: `ask`, `games`, `history`, `stats`

- konstans `MODE_NAMES` = `{m.id: m.name for m in MODES}`
- konstans `LOG_LIMIT` = `200`
- `dash(value, fmt)` – Üres érték (None, 0) helyett gondolatjel.
- `num(value, fmt)` – Mint a dash, de a 0 valódi érték (0% győzelem, 0.0 átlag), csak a hiányzó (None) lesz gondolatjel.
- `fill_table(table, rows, left_cols)` – A táblázat tartalmának cseréje (a fejléc és a méretezés marad).
- `make_table(head, rows, left_cols, stretch)` – Egyszerű, csak olvasható táblázat a program stílusával. `stretch`: a kitöltő oszlop sorszáma (a többi a tartalomhoz
- `muted(text)`
- **class `StatsDialog`** (QDialog) – Három oldal: Összesítés (profilonként, játékmód szerint szűrhető), Folyó játék, Előzmények.
  - `show_page(i)`
  - `name(pid, fallback)`
  - `build_totals()`
  - `total_rows()`
  - `fill_totals()`
  - `build_current()`
  - `result_text(rec)`
  - `log_rows()`
  - `build_log()`
  - `clear()`

### `theme.py`  (220 sor)

RKBully Darts System neon-HUD megjelenés: színek, stíluslap, neon keretes kártya, kerek profilkép.

Minden méret egy `k` szorzóval skálázódik (az ablak méretéhez igazodik), így a felület kis és nagy képernyőn is
ugyanúgy néz ki.

- `build_qss(k)` – A teljes stíluslap, minden méret a k szorzóval skálázva.
- `glow(widget, color, blur, alpha)` – Neon fény egy elem körül (nagy számoknál, gomboknál).
- **class `Card`** (QFrame) – Sötét panel neon keretttel: narancs -> kék színátmenetes szegély, külső fénnyel.
  - `set_kind(kind)`
  - `paintEvent(_)`
- **class `Avatar`** (QWidget) – Kerek profilkép: feltöltött kép, vagy a név kezdőbetűje színes körben.
  - `set_size(size)`
  - `set_player(name, path, color, ring)`
  - `paintEvent(_)`
- `paint_backdrop(widget, painter)` – A főablak háttere: sötét alap, a sarkokban narancs és kék fénnyel (a koncepciótervhez hasonlóan).

### `trainer.py`  (681 sor)

Modell-betanító logika (a felülettől független): kalibráció kattintásokból, nyílkereső képkülönbséggel,
YOLO-adatkészlet, a tanítás indítása és a kész modell ellenőrzése.

Hogyan tanul a program a saját kamerádból:
  1. Egyszer megjelölöd a tábla négy kalibrációs pontját (20, 3, 11, 6) a kamera képén. Ebből homográfia lesz.
  2. Üres tábláról referenciaképet rögzít, aztán figyeli a kamerát. Amikor a kép megnyugszik, a referenciához képest
     megjelent új foltot nyílnak veszi, és javasolja a nyílhegy helyét. Te jóváhagyod, vagy a képre kattintva javítod.
  3. Minden jóváhagyott nyílból tanítóképet készít: a kép + a nyílhegyek + a 4 kalibrációs pont helye (YOLO formátum,
     pontosan olyan osztályokkal, amiket a vision.py vár: `dart`, `20`, `3`, `11`, `6`).
  4. Az ultralytics-szel betanít egy kis YOLO modellt, és megméri, mennyire találja meg a nyilakat a saját képeiden.

A modell ugyanazt a középső négyzetet látja, mint éles használatban (vision.Detector), ezért a betanítás is azon dolgozik.

Saját modulokat használ: `dartboard`, `vision`

- konstans `CAL_NAMES` = `('20', '3', '11', '6')`
- konstans `CLASS_NAMES` = `('dart',) + CAL_NAMES`
- konstans `CAL_BOX` = `0.045`
- konstans `DART_BOX` = `0.035`
- konstans `MASK_MM` = `260.0`
- konstans `MIN_SAMPLES` = `30`
- konstans `GOOD_DARTS` = `150`
- konstans `PRESETS` = `{'fast': (40, 640, 'Gyors'), 'normal': (80, 640, 'Normál'), 'thorough'…`
- `square_crop(frame)` – A kép közepének négyzete, ahogy a vision.Detector vágja. Visszaad: (kép, x0, y0).
- `initial_points(size, fill)` – Kiinduló becslés a négy kalibrációs pontra: a tábla a négyzet közepén van, szabványos állásban (a 20-as felül).
- **class `Calibration`** – A kamera képe (pixel) és a tábla síkja (mm) közti megfeleltetés a négy megjelölt pontból.
  - `problem()` – Miért nem használható a kalibráció (None = rendben).
  - `to_mm(x, y)`
  - `to_px(mx, my)`
  - `board_mask(margin_mm)` – Fehér folt a képen ott, ahol a tábla (és a nyilak repülési tere) van; máshol fekete.
  - `center_px()`
  - `shapes(n)` – A tábla rajza a képre vetítve (ellenőrzéshez): gyűrűk és szektordrótok, pixelben.
  - `dump()`
  - `load(cls, data)`
- `prep(img)`
- `diff_binary(ref, cur, mask, thr)` – Fehér pontok, ahol a mostani kép érdemben eltér az üres tábla képétől. A fényerő-eltolódást kiegyenlíti.
- `find_blobs(binary, size)` – A zajnál nagyobb foltok: [{"centroid", "area", "pts", "too_big"}].
- `propose_tip(pts, center, mean_dir)` – A nyílfolt két végpontja közül a nyílhegy. Ha már tudjuk, merre áll a hegy a folt közepéhez képest (a korábbi
- **class `Candidate`** – Egy új, még el nem bírált folt: a javasolt nyílhegy helye és a kép, amelyen látszik.
- **class `Sample`** – Egy tanítókép: a kép, a nyílhegyek és a kalibrációs pontok pixelben (a négyzetes képen).
- **class `Collector`** – A kamera figyelése: üres tábla referencia + nyugodt képnél új foltok keresése. Az idő kívülről jön (tesztelhető).
  - `set_empty(img)` – Az üres tábla képe. Új referenciánál a körben lévő nyilak listája kiürül.
  - `mean_dir()` – Merre áll a nyílhegy a folt közepéhez képest (egységvektor), ha a jóváhagyások elég egyirányúak.
  - `feed(img, t)` – Egy új képkocka. Visszaad: események [("candidate", Candidate) | ("removed",) | ("busy", szöveg)].
  - `accept(tip)` – Jóváhagyja a függő jelöltet. A javasolt helyett `tip` (kattintással javított hely) is megadható.
  - `reject()` – „Nem nyíl” (árnyék, kéz, fényvisszaverődés): a folt többé nem jelölt.
  - `undo()` – Az utolsó jóváhagyott nyíl visszavonása: a nyíl újra jelölt lesz.
- `coverage(darts_mm)` – A nyilak eloszlása 12 zónában (4 negyed × 3 sugársáv): {(negyed, sáv): darab}. A gyenge zónák keresésére.
- konstans `ZONE_NAMES` = `{0: 'jobb felső', 1: 'jobb alsó', 2: 'bal alsó', 3: 'bal felső'}`
- konstans `RING_NAMES` = `{0: 'belső', 1: 'középső', 2: 'külső'}`
- `coverage_hint(darts_mm, minimum, start)` – Szöveges tanács: hová dobj még. Az első `start` nyílig nem szól.
- **class `DatasetStore`** – A jóváhagyott tanítóképek mappája. Minden kép azonnal lemezre kerül, így megszakadás után is megvan, és egy
  - `ids()`
  - `label_lines(darts, cal, size)`
  - `add(sample, session)`
  - `remove(sid)`
  - `remove_last()`
  - `meta(sid)`
  - `all_meta()`
  - `count()`
  - `n_darts()` – Hány nyílhegy-címke van összesen. (A körönként növekvő mintákban ugyanaz a nyíl többször szerepel, ezért a
  - `build(out_dir)` – A tanítás bemenete: train.txt / val.txt (képlisták) és data.yaml. A validáció körönként van elkülönítve
- `python_exe(exe)` – A konzolos Python (a parancsikon pythonw.exe-je nem ír ki semmit, így a tanítás üzeneteit nem látnánk).
- `ultralytics_available()`
- konstans `BASE_WEIGHTS` = `'yolov8n.pt'`
- `base_weights(app_dir)` – A kiinduló súlyfájl útvonala: ha az offline telepítő a `base` mappába tette (internet nélküli tanításhoz), azt használja;
- `job_config(data_yaml, preset, project, name, base)`
- `parse_line(line)` – A tanító script üzeneteinek értelmezése: ("epoch", n, összes, mAP) | ("done", útvonal) | ("error", szöveg) | None.
- **class `TrainJob`** – A tanítás külön folyamatban fut (a felület közben él, és megszakítható). A kimenet sorait a `poll` adja vissza.
  - `start()`
  - `poll()`
  - `running()`
  - `finished()` – Lejárt a folyamat, és az utolsó sorokat is elolvastuk.
  - `cancel()`
- `evaluate(backend, items, match_frac)` – A modell megméri magát a címkézett képeken. items: [(kép, [nyílhegyek px], {pont: (x, y)})].
- `verdict(result)` – Rövid, érthető értékelés a mérésből.
- `estimate_remaining(epoch_times, done, total)` – Hátralévő idő másodpercben a már lefutott epochok átlagából (None, ha még nincs adat).
- **class `FrameSource`** – Saját kamera-kapcsolat (ha a főablakban még nincs ilyen kamera): háttérszál olvassa a képet.
  - `stop()`

### `trainer_ui.py`  (659 sor)

Modell-betanító ablak: a saját kamerád képeiből tanít dobásfelismerő modellt.

Négy lépés (fülek): ① előkészítés (kalibráció, csomagok), ② gyűjtés (a program javasolja a nyílhegyeket, te jóváhagyod),
③ betanítás (külön folyamatban, haladásjelzővel), ④ próba (a modell megméri magát a tanításban nem használt képeken,
majd használatba veheted). A logika a trainer.py-ban van; ez csak a felület.

Saját modulokat használ: `ask`, `sounds`, `theme`, `trainer`, `vision`, `wizard`

- konstans `TABS` = `('①  Előkészítés', '②  Gyűjtés', '③  Betanítás', '④  Próba')`
- konstans `HOWTO` = `'Így tanul a program a saját kameráidból:\n\n1.  Kalibrációt mentesz a…`
- `dataset_darts_mm(store)` – A gyűjtött nyilak helye mm-ben (körönként a legtöbb nyilat tartalmazó minta): a lefedettség ellenőrzéséhez.
- `fmt_time(seconds)`
- **class `TrainerDialog`** (QDialog) – sources: [{"label", "text", "get"}] (mint a varázslónál). store_path: a kalibrációs fájl. data_dir: a tanítókészlet és a
  - `build_prepare()`
  - `build_collect()`
  - `build_train()`
  - `build_test()`
  - `fill_sources()`
  - `set_sources(sources)`
  - `on_add()`
  - `pick_camera(i)`
  - `key()`
  - `frame()`
  - `on_tab(_)`
  - `refresh_all()`
  - `update_buttons()`
  - `update_test_texts()`
  - `reset_collection()`
  - `ensure_calibration(size)` – A mentett kalibráció az aktuális képmérethez; változásnál új gyűjtő (az üres tábla képét újra kell rögzíteni).
  - `set_empty()`
  - `on_click(x, y, button)`
  - `accept_candidate()`
  - `reject_candidate()`
  - `undo_last()`
  - `clear_dataset()`
  - `on_wizard()`
  - `tick()`
  - `draw_overlay()`
  - `set_status(text, color)`
  - `start_training()`
  - `cancel_training()`
  - `poll_job()`
  - `pick_model()`
  - `eval_items()` – A kiértékelés képei: a tanításban nem használt (validációs) képek, ha vannak; különben az összes.
  - `evaluate_model()`
  - `poll_eval()`
  - `install_model()`
  - `done(result)`
  - `closeEvent(e)`

### `vision.py`  (377 sor)

Kamerás dobásfelismerés.

Folyamat:  kamerakép -> YOLO-modell (nyílhegyek + kalibrációs pontok) -> homográfia (kép -> tábla síkja, mm)
           -> pontszám -> dobáskövető (új nyíl észlelése, a nyilak kihúzásának észlelése).

A modell: DeepDarts / Dart-Sense típusú YOLO (.pt). Osztályok: 'dart' és kalibrációs pontok ('20', '3', '11', '6', ...).
Az `ultralytics` csomag csak a modell betöltésekor kell (késői import), nélküle is indul az alkalmazás.
A modell-fájlt NEM tartalmazza a program: a letöltés és a használat feltételeit a README írja le.

Saját modulokat használ: `dartboard`

- konstans `BOARD_LIMIT_MM` = `260.0`
- konstans `FAR_MISS_MM` = `240.0`
- **class `Detections`** – Egy képkocka nyers felismerése, a bemeneti kép pixelkoordinátáiban.
- **class `Throw`**
  - `text()`
  - `note()` – Rövid megjegyzés a jóváhagyó panelnek.
- **class `Removed`** – A nyilakat kihúzták a táblából.
- **class `YoloBackend`** – Ultralytics YOLO (.pt) modell DeepDarts / Dart-Sense osztályokkal.
  - `detect(image)`
- `find_model(app_dir, saved)` – Megkeresi a modellfájlt: RKBULLY_MODEL környezeti változó, mentett útvonal, majd a models mappa.
- `normalize_source(text)` – A beírt szövegből kamera-forrás: szám = USB webkamera, cím = telefon IP-kamera.
- **class `CalibrationTracker`** – A kalibrációs pontok helyét több képkockán át mediánnal simítja, és belőle homográfiát számol.
  - `update(cal)`
- **class `DartTracker`** – A tábla síkjában talált nyílhegyekből eseményeket készít: új dobás, nyilak kihúzva.
  - `reset()`
  - `update(dets, cal_err, n_cal)` – dets: [(x_mm, y_mm, biztonság)] ebben a képkockában. Visszatér: események listája.
- **class `Detector`** – Egy kamera teljes feldolgozása: kép -> felismerés -> kalibráció -> dobáskövetés.
  - `reset_round()` – A nyilak kihúzva (kézi jelzés): a következő nyilak új dobásnak számítanak.
  - `healthy()` – Megbízható-e most a kamera: van kalibráció, mind a 4 pont látszik, és a visszavetítési hiba kicsi.
  - `process(frame)` – Feldolgoz egy BGR képkockát; visszatér az új események listájával (Throw / Removed).
  - `step(cal, darts, square)` – A felismert pontokból (kép pixelben) eseményeket és megjelenítési adatot készít.
- `analyze_image(backend, frame, crop_square, cal_conf, dart_conf)` – Egyetlen képet elemez (kalibráció + pontszámok) – a beállítás ellenőrzéséhez és teszteléséhez.
- **class `DetectionService`** – Háttérszál: egy kamera képét dolgozza fel, az eseményeket sorba teszi a felületnek.
  - `overlay()`
  - `healthy(max_age)` – A kamera használható az összevetéshez: képet kapunk, és a kalibráció jó.
  - `poll()` – Kiveszi a sorban várakozó eseményeket (Throw / Removed), a felület szálából hívható.
  - `reset_round()` – Új játék / kézi nullázás: a követő elfelejti a leírt nyilakat, a még le nem kért események eldobódnak.
  - `start()`
  - `stop()`

### `welcome.py`  (63 sor)

Üdvözlő ablak: induláskor a bemutató kép, bezárható, és egy pipával végleg el is rejthető.

Saját modulokat használ: `appinfo`

- konstans `IMAGE_NAME` = `'welcome.jpg'`
- konstans `FOOTER_PX` = `78`
- `image_path(app_dir)`
- `fit_size(src, avail)` – A kép mérete a képernyőn: az arányt megtartva belefér a rendelkezésre álló területre (nagyítani nem kell).
- **class `WelcomeDialog`** (QDialog) – A bemutató kép egy ablakban. A „Többé ne jelenjen meg” pipa állapotát a hívó olvassa ki (`hide_forever`).
  - `hide_forever()`

### `wizard.py`  (505 sor)

Kalibrációs varázsló: élő kameraképpel segít a táblát és a fényeket a felismerő modellnek megfelelően beállítani.

A kép zöld (minden rendben), sárga (figyelmeztetés) vagy piros (javítandó) kerettel jelzi az állapotot, mellette
pipás lista mutatja, mi rendben és mi nem, szöveges teendőkkel. A négy kalibrációs pont húzható (vagy a program
megkeresi a táblát), a tábla rajza élőben követi. A mentett kalibrációt a betanító is használja.

Saját modulokat használ: `camcheck`, `theme`, `trainer`

- konstans `LEVEL_COLOR` = `{cc.OK: GREEN, cc.WARN: YELLOW, cc.BAD: RED, cc.NONE: '#5b6390'}`
- konstans `HANDLE_HELP` = `{'20': '5 | 20 drót (felül)', '6': '13 | 6 drót (jobbra)', '3': '17 | …`
- konstans `PLACEMENT` = `'1.  Rögzítsd a telefont vagy a webkamerát állványra a tábla elé (kézb…`
- `load_store(path)`
- `save_calibration(path, camera, points, size)` – Egy kamera kalibrációja a közös fájlba, a kép méretére normalizálva (így felbontásváltásnál is érvényes).
- `saved_points(path, camera, size)` – A kamera mentett kalibrációja pixelben az adott képmérethez, vagy None.
- **class `FrameView`** (QWidget) – Egy kép (BGR) arányosan kifeszítve, rárajzolt vonalakkal és húzható pontokkal. Koordináták: a kép pixelei.
  - `set_frame(bgr)`
  - `clear_frame()`
  - `to_view(x, y)`
  - `to_img(pos)`
  - `paintEvent(_)`
  - `mousePressEvent(e)`
  - `mouseMoveEvent(e)`
  - `mouseReleaseEvent(_)`
- **class `ModelProbe`** – Háttérszál: a betöltött modellel ~2 képkockát/mp elemez, hogy a varázsló lássa, felismeri-e a kalibrációs pontokat.
  - `stop()`
- **class `CalibrationWizard`** (QDialog) – sources: [{"label", "text", "get"}] – a kamerák (a get a legfrissebb BGR képkockát adja). get_backend: modell
  - `fill_sources()`
  - `set_sources(sources)` – A kamerák listája megváltozott (pl. kamerát adtak hozzá a varázslóból).
  - `on_add()`
  - `pick_camera(i)`
  - `frame()`
  - `start_probe()`
  - `key()`
  - `load_points()` – A kamera mentett kalibrációja, vagy a kiinduló becslés.
  - `init_points(size)`
  - `points(size)`
  - `on_handle(name, x, y)`
  - `reset_points()`
  - `auto_find()`
  - `tick()`
  - `model_check()`
  - `update_texts(problem, level)`
  - `set_banner(text, level)`
  - `render_checks(checks, problem)`
  - `save()`
  - `hide_offer()`
  - `done(result)`

## Eszközök (`tools/`)

### `tools/build_installer.py`  (138 sor)

A telepítők összeállítása (futtatás:  python tools/build_installer.py [--offline <offline_mappa>]).

* dist/RKBully_Darts_System_<verzió>_Telepito_online.bat – kis (néhány MB) egyfájlos telepítő, a csomagokat az internetről tölti.
* --offline megadásakor: dist/RKBully_Darts_System_<verzió>_Teljes_Telepito/ – Telepites.bat + offline\ mappa (Python 3.12.8 telepítő
  és az összes wheel): internet nélkül telepíthető. Az offline mappát a tools/build_offline.py állítja elő.

A telepítő egyetlen .bat fájl: az elején egy kis batch betöltő, utána a PowerShell telepítő (installer/install.ps1), a végén a
program fájljai base64-es zip-ként. A zip tartalmazza a forráskódot, a teszteket, a fejlesztői eszközöket és a dokumentációt is,
így a telepített program mappája egyben fejlesztői környezet (lásd docs/FEJLESZTOI_ADATLAP.md).

Saját modulokat használ: `appinfo`

- konstans `ROOT` = `Path(__file__).resolve().parent.parent`
- konstans `DIST` = `ROOT / 'dist'`
- konstans `OUT` = `DIST / f'RKBully_Darts_System_{VERSION}_Telepito_online.bat'`
- konstans `FULL_DIR` = `DIST / f'RKBully_Darts_System_{VERSION}_Teljes_Telepito'`
- konstans `TOP_FILES` = `['requirements.txt', 'requirements-felismeres.txt', 'requirements-lock…`
- konstans `SKIP_ASSETS` = `set()`
- konstans `EXTRA` = `{'Inditas.bat': ROOT / 'installer' / 'Inditas.bat', 'Eltavolitas.bat':…`
- konstans `LAUNCHERS` = `['RKBully_indit.bat', 'Felismeres_telepitese.bat', 'Parancsikon_letreh…`
- `payload_files()` – [(archívum-útvonal, fájl)] – a program futtatásához ÉS módosításához kellő fájlok (régi verziók, modellek nélkül).
- `build_zip()`
- `crlf(text)`
- `installer_text()`
- `build()` – Az online (kis) telepítő.
- konstans `OLVASSEL` = `'RKBully Darts System {version} - TELJES (OFFLINE) TELEPITO\n=========…`
- `build_full(offline_src)` – Teljes (offline) csomag: dist/..._Teljes_Telepito/Telepites.bat + offline/ (Python + wheel-ek).
- `write_checksums(paths)` – SHA256 ellenőrzőösszegek a kiadás fájljaihoz (dist/SHA256SUMS.txt).
- `make_zip(full)` – A teljes csomag mappájából kiadási zip (a GitHub Releases-hez): dist/<mappa>.zip.

### `tools/build_offline.py`  (74 sor)

Az offline telepítő "offline" mappájának előállítása: a Python 3.12.8 telepítője + az összes csomag wheel-je.

Futtatás (internet kell, Windows/Linux/macOS bármelyiken működik – a wheel-eket Windows-ra tölti le):
    python tools/build_offline.py [kimeneti_mappa]          (alapértelmezés: dist/offline)

A csomagok a requirements-lock.txt rögzített verziói (win_amd64, cp312). Ezután:
    python tools/build_installer.py --offline dist/offline  → dist/RKBully_Darts_System_<verzió>_Teljes_Telepito/

- konstans `ROOT` = `Path(__file__).resolve().parent.parent`
- konstans `PY_VERSION` = `'3.12.8'`
- konstans `PY_FILE` = `f'python-{PY_VERSION}-amd64.exe'`
- konstans `PY_URL` = `f'https://www.python.org/ftp/python/{PY_VERSION}/{PY_FILE}'`
- konstans `PY_MIN_BYTES` = `20000000`
- konstans `BASE_FILE` = `'yolov8n.pt'`
- konstans `BASE_URL` = `'https://github.com/ultralytics/assets/releases/download/v8.3.0/' + BA…`
- konstans `BASE_MIN_BYTES` = `5000000`
- `download_wheels(dest)` – pip download a rögzített listához; --no-deps, mert a lista már a teljes (feloldott) függőségfa.
- `download_python(dest)`
- `download_base(dest)` – Az alap-súlyfájl a betanításhoz. Ha nem sikerül, a csomag akkor is jó: a betanítás az első indításkor maga tölti le.
- `build(out)`

### `tools/make_codemap.py`  (74 sor)

Kódtérkép generátor: docs/KODTERKEP.md – minden modul feladata, osztályai, függvényei az AST-ből (a kóddal mindig egyezik).

Futtatás:  python tools/make_codemap.py        (a kód módosítása után érdemes újragenerálni)

- konstans `ROOT` = `Path(__file__).resolve().parent.parent`
- konstans `OUT` = `ROOT / 'docs' / 'KODTERKEP.md'`
- `first_line(doc)`
- `describe(path)`
- `build()`

### `tools/make_icons.py`  (36 sor)

Az ikonfájlok (assets/rkbully.png és assets/rkbully.ico) újragyártása a forrásképből.

Csak ehhez kell a Pillow (pip install pillow); a programnak és a kész ikonfájloknak nem.
Használat:  python tools/make_icons.py [forraskep.png]
Ha másik logót szeretnél, írd felül az assets/rkbully_forras.png fájlt (négyzet alakú, átlátszó háttérrel a legjobb),
vagy add meg a képet argumentumként, majd futtasd újra.

- konstans `ASSETS` = `Path(__file__).resolve().parent.parent / 'assets'`
- konstans `SIZES` = `(16, 20, 24, 32, 40, 48, 64, 96, 128, 256)`
- `square(im)` – Négyzetre egészíti ki a képet (átlátszó szegéllyel), hogy a torzítás nélkül skálázódjon.
- `main(src)`

### `tools/make_screenshots.py`  (106 sor)

A README képernyőképeinek elkészítése (képernyő nélkül, offscreen). Futtatás:  python tools/make_screenshots.py

A képek a valódi felületet mutatják szintetikus (generált) játékadatokkal és tesztképpel; a program nem igényel kamerát.

Saját modulokat használ: `rkbully`, `sounds`, `speech`, `trainer_ui`, `wizard`

- konstans `ROOT` = `Path(__file__).resolve().parent.parent`
- konstans `OUT` = `ROOT / 'docs' / 'images'`
- `main()`

### `tools/make_sounds.py`  (107 sor)

A hangeffektek (assets/sounds/*.wav) legyártása: kis, szintetizált hangok, külső fájl és csomag nélkül.

Használat:  python tools/make_sounds.py
Ha más hangokat szeretnél, egyszerűen írd felül a WAV fájlokat az assets/sounds mappában (16 bites, mono vagy sztereó).

- konstans `OUT` = `Path(__file__).resolve().parent.parent / 'assets' / 'sounds'`
- konstans `RATE` = `44100`
- konstans `NOTE` = `{'C4': 261.63, 'E4': 329.63, 'G4': 392.0, 'A4': 440.0, 'C5': 523.25, '…`
- `silence(seconds)`
- `tone(freq, seconds, volume, decay, shape, glide, attack)` – Egy hang lecsengő hangerővel; `glide`: a végfrekvencia (hangmagasság-csúszás).
- `noise(seconds, volume, decay, seed)`
- `mix()`
- `delayed(track, seconds)`
- `concat()`
- `write(name, samples, peak)`
- `build()`

### `tools/train_worker.py`  (59 sor)

A modell betanítása külön folyamatban (a betanító ablak indítja: python tools/train_worker.py beallitas.json).

A felület ennek a kimenetét olvassa: RKBULLY_EPOCH|n|összes|mAP, RKBULLY_DONE|útvonal, RKBULLY_ERROR|szöveg.

- `main(cfg_path)`

## Tesztek (`tests/`)

| fájl | sor | teszt | mit ellenőriz |
|---|---|---|---|
| `synth.py` | 88 | 0 | Szintetikus tábla- és nyílképek a betanító teszteléséhez (valódi kamera nélkül). |
| `test_assets.py` | 154 | 13 | Az ikonfájlok és a parancsikon-készítő scriptek ellenőrzése (Pillow és PySide6 nélkül is futnak). |
| `test_dartboard.py` | 111 | 10 |  |
| `test_features.py` | 336 | 25 | Névjegy és név, kör-óra szünet, legutóbbi meccs, meccs végi képernyő (képernyő nélkül). |
| `test_fusion.py` | 340 | 22 | Két kamera összevetése: szimulált kamerákkal (más-más nézőpont = más homográfia), valódi Detectorokkal. |
| `test_games.py` | 174 | 19 |  |
| `test_history.py` | 195 | 20 | A tartós előzmény és az összesítés (Qt nélkül): X01 pontozás bustokkal, bejegyzések, profilonkénti összesítés, fájlkezelés. |
| `test_modes.py` | 613 | 60 | Az új játékmódok szabályai + a minden módon végigfutó véletlen-dobásos próba. |
| `test_profiles.py` | 148 | 18 | Játékosprofilok: betöltés, régi beállításfájl átvétele, névkezelés, profilkép importálása. |
| `test_review.py` | 223 | 20 |  |
| `test_sounds.py` | 215 | 22 | Hangeffektek: melyik esemény melyik hangot szólaltatja meg, a hangfájlok épsége, ki/be kapcsolás, hangerő, felületi bekötés. |
| `test_speech.py` | 104 | 15 | Pontszám-felolvasás: magyar számnevek, a mondatok és a be/ki kapcsolás (hangmotor nélkül, felvevő motorral). |
| `test_stats.py` | 123 | 13 | Statisztika a játékmotor előzményeiből, és a kiszálló útvonalak. |
| `test_trainer.py` | 586 | 66 |  |
| `test_trainer_ui.py` | 474 | 27 | A modell-betanító ablak: gyűjtés szintetikus kamerával, betanítás hamis folyamattal, próba, használatba vétel. |
| `test_ui.py` | 227 | 17 | Felület-tesztek képernyő nélkül (offscreen Qt). PySide6 nélkül a tesztek kihagyják magukat. |
| `test_ui_history.py` | 344 | 19 | Felület-tesztek: a befejezett játékok mentése, a visszavonás hatása, újraindítás, Statisztikák ablak. |
| `test_ui_profiles.py` | 508 | 38 | Felület-tesztek: profilok és profilképek, beállítások (fogaskerék), játékos hozzáadása, szünet, statisztika, ablakillesztés. |
| `test_vision.py` | 170 | 12 |  |
| `test_welcome.py` | 119 | 8 | Az induláskor megjelenő üdvözlő ablak és a „Többé ne jelenjen meg” jelölő (képernyő nélkül). |
| `test_wizard.py` | 503 | 46 | Kalibrációs varázsló: kamera- és fényellenőrzés, a tábla automatikus keresése, mentés, felület (szintetikus képekkel). |
