# RKBully Darts System - parancsikon letrehozasa az Asztalon (RKBully ikonnal).
# Csak ASCII karakterek, hogy a Windows kodlapja ne rontsa el. Futtatas: Parancsikon_letrehozasa.bat

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$icon = Join-Path $root 'assets\rkbully.ico'
$app  = Join-Path $root 'rkbully.py'
$req  = Join-Path $root 'requirements.txt'
$reqDet = Join-Path $root 'requirements-felismeres.txt'
$bat  = Join-Path $root 'RKBully_indit.bat'

function Get-PythonPath {
    # A valodi Python elerese (a Microsoft Store "python.exe" csonk nem szamit: az nem ad vissza utat).
    $found = $null
    $py = Get-Command 'py' -ErrorAction SilentlyContinue
    if ($py) {
        try { $found = & $py.Source -3 -c "import sys; print(sys.executable)" 2>$null } catch { $found = $null }
    }
    if (-not $found) {
        $pn = Get-Command 'python' -ErrorAction SilentlyContinue
        if ($pn) {
            try { $found = & $pn.Source -c "import sys; print(sys.executable)" 2>$null } catch { $found = $null }
        }
    }
    if ($found) { $found = ($found | Select-Object -First 1).ToString().Trim() }
    if ($found -and (Test-Path $found)) { return $found }
    return $null
}

try {
    if (-not (Test-Path $app))  { throw "Nem talalom a rkbully.py fajlt: $app" }
    if (-not (Test-Path $icon)) { throw "Nem talalom az ikont: $icon" }

    $python = Get-PythonPath
    if (-not $python) {
        throw "Nem talalom a Pythont. Telepitsd a python.org oldalrol (jelold be: Add python.exe to PATH), majd futtasd ujra."
    }
    Write-Host "Python: $python"

    Write-Host "Csomagok telepitese (elso alkalommal eltarthat egy ideig)..."
    & $python -m pip install -q -r $req
    if ($LASTEXITCODE -ne 0) { throw "A csomagok telepitese nem sikerult (pip hibakod: $LASTEXITCODE)." }

    # A dobasfelismeres csomagja (ultralytics) nagy es nem kotelezo: ha nem sikerul, a program akkor is mukodik.
    & $python -m pip show ultralytics *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "A dobasfelismeres csomagja (ultralytics) telepitese - ez nagy, par percig tarthat..."
        & $python -m pip install -q -r $reqDet
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Figyelem: az ultralytics telepitese nem sikerult. A program igy is elindul, de a dobasfelismeres nem lesz elerheto."
        }
    }

    # pythonw.exe: konzolablak nelkul indul. Ha nincs (vagy Store-os Python), a .bat indito lesz a cel.
    $pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
    $useBat = (-not (Test-Path $pythonw)) -or ($python -like '*\WindowsApps\*')

    $desktop = [Environment]::GetFolderPath('Desktop')
    $lnkPath = Join-Path $desktop 'RKBully Darts System.lnk'

    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($lnkPath)
    if ($useBat) {
        $lnk.TargetPath = $bat
        $lnk.Arguments = ''
        $lnk.WindowStyle = 7
    } else {
        $lnk.TargetPath = $pythonw
        $lnk.Arguments = '"' + $app + '"'
        $lnk.WindowStyle = 1
    }
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation = $icon + ',0'
    $lnk.Description = 'RKBully Darts System'
    $lnk.Save()

    Write-Host ""
    Write-Host "Kesz: $lnkPath"
    if ($useBat) { Write-Host "(Az indito a RKBully_indit.bat lesz, mert nincs konzol nelkuli pythonw.exe.)" }
}
catch {
    Write-Host ""
    Write-Host "Hiba: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
