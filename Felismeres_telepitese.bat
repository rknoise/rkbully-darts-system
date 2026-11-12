@echo off
cd /d "%~dp0"
echo ============================================================
echo  RKBully Darts System - kameras dobasfelismeres csomagjanak telepitese
echo ============================================================
echo.
echo Az indito (RKBully_indit.bat) es a parancsikon-keszito ezt magatol is elvegzi,
echo ezt a fajlt csak akkor kell futtatni, ha a telepites ott nem sikerult.
echo.
echo Az ultralytics csomag nagy (a PyTorch-ot is hozza), a letoltes par percig tarthat.
echo.
python -m pip install -r requirements-felismeres.txt
if errorlevel 1 (
  echo.
  echo Nem sikerult telepiteni. Van Python 3.10-3.13, es be van allitva a PATH-ba?
  pause
  exit /b 1
)
echo.
echo Kesz. Inditsd ujra az RKBully Darts System programot: a modell-betanito megnyilik, ha meg nincs betanitott modell.
pause
