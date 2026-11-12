@echo off
cd /d "%~dp0"
echo RKBully Darts System parancsikon letrehozasa az Asztalon...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\make_shortcut.ps1"
if errorlevel 1 (
  echo.
  echo Nem sikerult. Probald az RKBully_indit.bat fajlt, az kiirja a hibat.
  pause
  exit /b 1
)
echo.
echo Mostantol az Asztalon az RKBully Darts System ikonra duplan kattintva indul a program.
pause
