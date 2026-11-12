@echo off
setlocal
title RKBully Darts System - telepito
set "RK_SELF=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$t=[IO.File]::ReadAllText($env:RK_SELF); $m=[regex]::Match($t,'(?ms)^#__PS__\r?\n(.*?)^#__ZIP__'); if(-not $m.Success){Write-Host 'A telepito serult.'; exit 2}; & ([scriptblock]::Create($m.Groups[1].Value))"
set "RK_CODE=%errorlevel%"
if "%RK_CODE%"=="2" pause
exit /b %RK_CODE%
