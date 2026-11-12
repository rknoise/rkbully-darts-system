# Licencek és harmadik felek csomagjai

## Az RKBully Darts System licence

Az RKBully Darts System 1.0 saját kódja (© 2026 RKNOISE) a **GNU Affero General Public License v3.0 (AGPL-3.0)** alatt van (lásd a `LICENSE` fájlt).

**Miért AGPL?** A dobásfelismerés az `ultralytics` csomagra (AGPL-3.0) épül, és a teljes (offline) telepítő ezt a csomagot, valamint az Ultralytics `yolov8n.pt`
súlyfájlját (AGPL-3.0) is tartalmazza. Az AGPL szerint az ilyen módon együtt terjesztett, ezekre épülő programot ugyanazon feltételekkel kell elérhetővé tenni,
a forráskóddal együtt. A teljes forráskód nyilvános (GitHub), ezért ez teljesül. Ha valaki a programot ettől eltérő (pl. zárt) feltételekkel akarná terjeszteni,
az `ultralytics` kereskedelmi licencét kell beszereznie az Ultralytics-től, vagy le kell cserélnie azt egy másik felismerő háttérre (a `vision.py` háttere cserélhető:
`YoloBackend.detect(image)` az egyetlen illesztési pont).

## A teljes (offline) telepítő tartalma – mind szabadon terjeszthető

A csomag változatlan, a hivatalos PyPI / python.org / Ultralytics kiadásokból származó fájlokat tartalmaz. Minden wheel magában hordozza a saját licencfájlját
(`*.dist-info\licenses\`), a telepítés után a venv `Lib\site-packages\*.dist-info\` mappáiban megtalálható.

| Csomag (verzió az 1.0-ban) | Licenc | Megjegyzés |
|---|---|---|
| Python 3.12.8 (telepítő) | PSF License 2.0 | python.org |
| PySide6-Essentials / -Addons / shiboken6 6.12.0 | LGPL-3.0 (vagy GPL) | Qt for Python. Változatlan, dinamikusan használt; a venv-ben cserélhető (`pip install PySide6-Essentials==…`), így az LGPL feltételei teljesülnek |
| opencv-python 5.0.0.93 | Apache-2.0 | |
| numpy 2.5.4 | BSD-3-Clause (és kapcsolódó engedékeny licencek) | |
| torch 2.15.0, torchvision 0.29.2 | BSD-3-Clause / Apache-2.0 | PyTorch |
| ultralytics 8.4.211, ultralytics-thop, ultralytics-platform | **AGPL-3.0** | lásd fent |
| yolov8n.pt (alap-súlyfájl a betanításhoz) | **AGPL-3.0** | Ultralytics; nem darts-modell, csak a tanítás kiindulópontja |
| matplotlib, contourpy, cycler, kiwisolver, fonttools, pyparsing, python-dateutil | matplotlib (PSF-alapú) / BSD / MIT | az ultralytics függőségei |
| pillow 13.0.0 | MIT-CMU | |
| polars, polars-runtime-32 | MIT | |
| sympy, mpmath, networkx, filelock, fsspec, Jinja2, MarkupSafe, typing_extensions | BSD / MIT / PSF | PyTorch függőségei |
| requests, urllib3, certifi, idna, charset-normalizer, httpx, httpcore, h11, anyio | Apache-2.0 / MIT / BSD / MPL-2.0 (certifi) | |
| psutil, nvidia-ml-py, tzdata, packaging, setuptools, pip, wheel | BSD / Apache-2.0 / MIT | |

A pontos, csomagonkénti lista a `requirements-lock.txt`-ben (verziók) és a telepített `TELEPITES_INFO.txt`-ben van.

## Dobásfelismerő (darts) modell

A programhoz **nem tartozik kész darts-felismerő modell** (a DeepDarts / Dart-Sense modellek külön, saját licenccel és letöltési feltételekkel érhetők el;
lásd a README „Modell és licenc” részét). A modellt a saját kamerádból taníthatod be a programban – az így létrejött modell a tiéd.
