@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo A programkornyezet hianyzik. Futtasd ujra a telepitot.
  pause
  exit /b 1
)
"venv\Scripts\python.exe" rkbully.py
if errorlevel 1 pause
