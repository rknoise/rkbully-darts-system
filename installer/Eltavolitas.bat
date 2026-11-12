@echo off
setlocal
set "APPDIR=%~dp0"
echo ============================================================
echo  RKBully Darts System - eltavolitas
echo ============================================================
echo.
echo Torlodik a program mappaja: %APPDIR%
echo  (a venv, a program fajljai es a sajat modellek a models mappabol is!)
echo.
set /p OK=Biztosan eltavolitod? (i/n): 
if /i not "%OK%"=="i" (
  echo Megszakitva.
  pause
  exit /b 0
)
del "%USERPROFILE%\Desktop\RKBully Darts System.lnk" 2>nul
rd /s /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\RKBully Darts System" 2>nul
echo.
set /p DATA=A beallitasok, jatekos profilok es statisztikak torlese is (%USERPROFILE%\.rkbully)? (i/n): 
if /i "%DATA%"=="i" rd /s /q "%USERPROFILE%\.rkbully" 2>nul
echo.
echo Kesz. Viszlat!
(goto) 2>nul & rd /s /q "%APPDIR%"
