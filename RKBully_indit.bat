@echo off
if /i not "%~1"=="run" (
  rem Sajat, nyitva marad az ablak, hiba eseten is.
  cmd /k ""%~f0" run"
  exit /b
)
setlocal
cd /d "%~dp0"
title RKBully Darts System
echo ============================================================
echo  RKBully Darts System - inditas
echo ============================================================
echo.
set "PY="
for %%V in (3.12 3.11 3.13 3.10) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)" >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo Nem talalom a Python 3.10-3.13 verziot.
  echo Telepitsd a python.org oldalrol ^(jelold be: Add python.exe to PATH^), vagy hasznald az
  echo egy kattintasos telepitot: dist\RKBully_Darts_System_Telepito.bat
  echo.
  pause
  exit /b 1
)
echo Hasznalt Python:
%PY% --version
echo.
echo [1/3] Alapcsomagok ellenorzese ^(PySide6, OpenCV, numpy^)...
%PY% -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 (
  echo.
  echo Nem sikerult telepiteni a csomagokat. Ellenorizd az internetkapcsolatot.
  pause
  exit /b 1
)
echo.
echo [2/3] Dobasfelismeres csomagja ^(ultralytics^)...
%PY% -m pip show ultralytics >nul 2>nul
if errorlevel 1 (
  echo Az elso inditaskor ez nagy letoltes ^(PyTorch^), akar 5-15 percig is eltarthat. Ne zard be az ablakot!
  echo ^(Dobasfelismeres nelkul is hasznalhato a program: ha megszakitod, kezi bevitellel megy tovabb.^)
  %PY% -m pip install -r requirements-felismeres.txt --disable-pip-version-check
  if errorlevel 1 (
    echo.
    echo Figyelem: az ultralytics telepitese nem sikerult. A program igy is elindul, de a dobasfelismeres
    echo es a modell betanitasa nem lesz elerheto.
    echo.
  )
) else (
  echo Mar telepitve.
)
echo.
echo [3/3] A program indul...
%PY% rkbully.py
if errorlevel 1 (
  echo.
  echo A program hibaval leallt. A fenti hibauzenetet kuldd el, ha segitseg kell.
  pause
)
if not errorlevel 1 exit
