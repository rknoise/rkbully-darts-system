# Játékmódok: szabályok, játékosszám, források

A programban minden játékmódnál van **ℹ gomb** (a választóban a kártyán, játék közben az alsó sávban: *Szabályok*),
ami megmutatja, hányan játszhatják, és hogyan kell játszani. Ez a fájl azt rögzíti, **melyik szabályt honnan vettem**,
és hol kellett választanom több elterjedt változat közül. Ha a ti házi szabályotok más, a `games.py` és a leírás
(`MODES` lista) egy helyen módosítható.

## Áttekintés

| Játék | Csoport | Játékosok | Egy kör | Vége |
|---|---|---|---|---|
| 301 / 501 / 701 | Klasszikus | 1–8 (egyedül gyakorlásra is) | 3 nyíl | nullára kiszállás (Double Out vagy Straight Out) |
| Cricket | Klasszikus | 2–8 | 3 nyíl | minden szám lezárva, legalább annyi ponttal, mint másoknak |
| High Score | Klasszikus | 1–8 | 3 nyíl | 10 kör után a legtöbb pont |
| Around the Clock | Party | 1–8 | 3 nyíl | az első, aki a Bullt is eltalálja |
| Shanghai | Party | 1–8 | 3 nyíl | 7 kör, vagy azonnal Shanghai |
| Killer | Party | 2–8 | 1 nyíl számválasztáskor, utána 3 | az utolsó életben maradt |
| Baseball | Party | 1–8 | 3 nyíl | 9 inning, holtversenynél hosszabbítás |
| Golf | Party | 1–8 | 3 nyíl | 18 lyuk, a legkevesebb ütés; holtversenynél hosszabbítás |
| Bermuda Triangle | Party | 1–8 | 3 nyíl | 13 kör, a legtöbb pont |
| Bob's 27 | Gyakorló | 1–8 | 3 nyíl | 21 kör, vagy 0 alá esés után kiesés |
| 121–170 Checkout | Gyakorló | 1–8 | 3 nyíl (feladatonként 3 kör) | 10 kísérlet, a legmagasabb kiszálló nyer |
| Catch 40 | Gyakorló | 1–8 | 3 nyíl (feladatonként 2 kör) | 40 kiszálló (61–100), a legtöbb pont |
| Duplák | Gyakorló | 1–8 | 3 nyíl | D1–D20 és Bull, találatonként 1 pont |
| Bull | Gyakorló | 1–8 | 3 nyíl | 10 kör, külső Bull 1, belső 2 pont |
| A1 gyakorló | Gyakorló | 1–8 | 3 nyíl | az nyer, aki kevesebb kör alatt zár le minden számot |
| 100 nyíl | Gyakorló | 1–8 | 3 nyíl (az utolsó kör 1 nyíl) | pontosan 100 nyíl után a legtöbb pont |
| Scoring 99 / Scoring 121 | Gyakorló | 1–8 | 3 nyíl | 10 kör, a legtöbb sikeres kör |

Azonos eredménynél (ahol a játék nem hosszabbít) **döntetlen** a vége, nem nyer csendben az első játékos.

## Mi honnan van, és mit választottam

**Forrásból átvett szabály** (az oldalakat ellenőriztem, de a szabályok forrásonként kisebb részletekben eltérnek):

- **Killer:** szám választása a gyengébbik kézzel, a saját dupla = Gyilkos, 3 élet, az ellenfél duplája életet vesz el,
  Gyilkosként a saját dupla életbe kerül. [DartHelp](https://darthelp.com/games/how-to-play-killer-darts).
  *Az én egyszerűsítésem:* ha a választott szám foglalt vagy mellé megy, a játékos nem dob újra azonnal, hanem a következő
  körben próbálkozik (így a kamerás jóváhagyás mindig pontosan 1 nyílat vár). Csak a dupla vesz életet, a tripla nem.
- **Bob's 27:** 27 pont, D1–D20 és Bull, találatonként +érték, ha mind a 3 nyíl mellé megy, −érték. A kieséshez a
  [DartCounter](https://dartcounter.net/games/bobs-27) szerinti "0 alá esik" szabályt használom (a pontosan 0 még bent marad).
  A belső Bull 50 pont ebből a forrásból levezetve.
- **Bermuda Triangle:** a 13 körös változat (12, 13, 14, dupla, 15, 16, 17, tripla, 18, 19, 20, Bull, belső Bull), mind a
  3 nyíl mellé = a pontszám felére esik, lefelé kerekítve. [DartHelp](https://darthelp.com/games/how-to-play-bermuda-triangle-darts),
  [IngaHub](https://ingahub.com/how-to-play-bermuda-triangle-darts) (utóbbi 13 kört ír, de a célok sorrendjét csak képen
  közli, azt a DartHelp alapján vettem át; az IngaHub szerint a célokban megegyezhet a társaság).
- **121 Checkout:** 121-ről indul, 9 nyíl (3 kör) feladatonként, Double Out, siker: +1, kudarc: vissza a kezdőszámra
  vagy az utolsó "bankerre" (3 nyílból sikerült kiszálló). A DartCounter alapértelmezése 10 "kör"; ezt én 10 kísérletnek
  vettem.
  [DartCounter](https://dartcounter.net/games/121-checkout), [Paul Nicholson gyakorlójátékai](https://www.sportinglife.com/darts/news/practice-games-in-darts/179678).
  *A "121–170" elnevezés az enyém:* a feladatok 170-ig mennek, mert az a legnagyobb lehetséges kiszálló.
- **Catch 40:** 40 kiszálló (61–100), egyenként legfeljebb 6 nyíl; 2 nyílból 3 pont, 3 nyílból 2 pont, 4–6 nyílból 1 pont,
  a 99-et 3 nyílból 3 pont éri; legfeljebb 120 pont. [GoDartsPro](https://www.godartspro.com/?p=835). Ezt az egy forrást
  követtem; más oldalakon a feladatok köre eltérhet.
- **A1 gyakorló:** 20–13 és Bull, legalább 2 nyíl a 3-ból a számra = 1 jelzés, 5 jelzés után a szám lezárul, a cél minél
  kevesebb kör alatt mindent lezárni. [GoDartsPro](https://www.godartspro.com/?p=785).
- **Golf:** 18 lyuk, a lyuk száma a cél; döntetlen esetén a 19., 20. lyuk, majd a Bull-lyuk jön.
  [Paul Nicholson gyakorlójátékai](https://www.sportinglife.com/darts/news/practice-games-in-darts/179678),
  [DartHelp](https://darthelp.com/games/how-to-play-golf-darts/). *Az én választásom:* mind a 3 nyíl el van dobva, a
  **legjobb nyíl** számít; tripla 2, dupla 3, szimpla 4, mellé 5 ütés (a két forrás eltérő ütésszámokat ad; ez Nicholson
  "birdie/par/bogey" sorrendjét követi egyenlő lépésközzel). A hosszabbítás nálam **lyukanként** dönt, amíg el nem dől;
  Nicholson a három lyuk összegét veti össze. A "legutolsó nyíl számít, bármikor megállhatsz" változat nincs benne.
- **Baseball:** 9 inning, az inning száma a cél, szimpla 1, dupla 2, tripla 3 futás, holtversenynél a 10., 11. … inning
  (a 10-es, 11-es … számmal). [CyberDarts](https://cyberdarts.com/basics/dartsgames_baseball.html).
  *A bonyolultabb "bázisos" baseball (futók, kiesések, home run) nincs benne*, az elterjedt egyszerű változatot választottam.
- **Duplák:** a [DartCounter Doubles Training](https://dartcounter.net/games/doubles-training) alapján, *de módosítva*: az
  eredeti addig dob, amíg el nem találja, és a minél kevesebb nyíl a cél. Nálam minden dupla 3 nyíl, találatonként 1 pont, hogy a
  körök fix 3 nyilasak maradjanak (ez kell a kamerás jóváhagyáshoz is).

**Az én értelmezésem** (a nevek a kérésedből voltak, a pontos szabályt nem találtam egyetlen szabványos forrásban sem):

- **100 nyíl:** pontosan 100 nyíl (33 kör × 3 + 1 záró nyíl), bárhová dobhatsz, az összpont számít. Kiírja a 3 darts átlagot.
- **Scoring 99 / Scoring 121:** 10 kör; egy kör akkor sikeres, ha a 3 nyíl összege eléri a 99-et (121-et). Azonos sikeres
  körszámnál az összpont dönt.
- **Bull:** 10 kör a Bullra, külső Bull 1 pont, belső Bull 2 pont.

Ha ezekre más szabály él nálatok, szólj, és átírom.

## Ahol a motor eltér a "papír" szabálytól a kamerás jóváhagyás miatt

- A kör mindig a program által meghatározott számú nyíl (a legtöbb játékban 3). A nyílszámot a játék közli a jóváhagyó
  panellel, így pl. a Killer számválasztásakor 1 nyíl után már indul a 60 másodperces visszaszámlálás.
- Ha egy kör idő előtt véget ér (bust, kiszállás, a Gyilkos kiejti magát), a megmaradt nyilak nem kerülnek a következő
  játékoshoz.
