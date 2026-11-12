# RKBully Darts System @VERSION@ - egy kattintasos telepito (a Telepites.bat / *_Telepito.bat resze).
# Csak ASCII karakterek, hogy a Windows konzol kodlapja ne rontsa el a szoveget.
# Kornyezeti valtozok (opcionalis): RK_DIR = telepitesi mappa, RK_NOLAUNCH=1 = ne inditsa el a programot a vegen,
# RK_NODETECT=1 = ne telepitse a dobasfelismeres (ultralytics) csomagjat, RK_EXTRACT_ONLY=1 = csak kicsomagol (teszt),
# RK_FORCE_ONLINE=1 = akkor is az internetrol telepitsen, ha a telepito mellett van "offline" mappa.
# OFFLINE MOD: ha a telepito mellett van egy "offline" mappa (offline\wheels\*.whl + offline\python-*.exe), a telepites
# semmit nem tolt le az internetrol: a Python 3.12-t es az osszes csomagot onnan telepiti (pip --no-index --find-links).

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }

$AppName = 'RKBully Darts System'
$AppVersion = '@VERSION@'
$PyDownload = 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe'
$InstallDir = if ($env:RK_DIR) { $env:RK_DIR } else { Join-Path $env:LOCALAPPDATA $AppName }
$Venv = Join-Path $InstallDir 'venv'
$Log = Join-Path $InstallDir 'telepites.log'

# Offline csomag keresese a telepito fajl mellett.
$OfflineDir = ''
$Wheels = ''
$OfflinePython = $null
if ($env:RK_SELF -and -not $env:RK_FORCE_ONLINE) {
    $cand = Join-Path (Split-Path -Parent $env:RK_SELF) 'offline'
    $w = Join-Path $cand 'wheels'
    if ((Test-Path -LiteralPath $w) -and (Get-ChildItem -LiteralPath $w -Filter '*.whl' -ErrorAction SilentlyContinue)) {
        $OfflineDir = $cand
        $Wheels = $w
        $OfflinePython = Get-ChildItem -LiteralPath $cand -Filter 'python-3.12*-amd64.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    }
}
$IsOffline = [bool]$Wheels
# Offline modban a csomagok cp312 (Python 3.12, 64 bites) wheel-ek, ezert csak 3.12 jo; online barmelyik 3.10-3.13.
$PyRegex = if ($IsOffline) { '^3\.12$' } else { '^3\.(10|11|12|13)$' }
$PyVersions = if ($IsOffline) { @('3.12') } else { @('3.12', '3.11', '3.13', '3.10') }
$PyDirs = if ($IsOffline) { @('312') } else { @('312', '311', '313', '310') }

function Say([string]$text, [string]$color = 'Gray') {
    Write-Host $text -ForegroundColor $color
    try { Add-Content -LiteralPath $Log -Value ((Get-Date -Format 's') + '  ' + $text) -ErrorAction SilentlyContinue } catch { }
}

function Step([string]$text) { Say ''; Say ('>> ' + $text) 'Cyan' }

function Quote([string]$s) { if ($s -match '[\s"]') { return '"' + ($s -replace '"', '\"') + '"' } return $s }

function Run([string]$exe, [string[]]$arguments) {
    # Nativ program futtatasa; a kimenet a konzolon latszik, visszaadja a kilepesi kodot (a stderr nem dob kivetelt).
    $line = ($arguments | ForEach-Object { Quote $_ }) -join ' '
    $p = Start-Process -FilePath $exe -ArgumentList $line -NoNewWindow -Wait -PassThru
    return $p.ExitCode
}

function Banner {
    Write-Host ''
    Write-Host '  ====================================================================' -ForegroundColor DarkYellow
    Write-Host ('     R K B U L L Y   D A R T S   S Y S T E M   ' + $AppVersion + '   -   telepito') -ForegroundColor Yellow
    Write-Host '     A programot RKNOISE keszitette' -ForegroundColor DarkYellow
    if ($IsOffline) { Write-Host '     OFFLINE telepites: nem kell internet, minden fuggoseg a csomagban van.' -ForegroundColor DarkYellow }
    Write-Host '  ====================================================================' -ForegroundColor DarkYellow
    Write-Host ''
    Write-Host '  FONTOS - amig a telepites fut (nehany perc), mar kesziteld elo a kamerakat:' -ForegroundColor Green
    Write-Host '    * Rogzitsd a telefonokat / webkameraakat allvanyra a darts tabla elott.' -ForegroundColor Green
    Write-Host '    * A tabla kozepe a kep kozepen legyen, a 20-as szam felul.' -ForegroundColor Green
    Write-Host '    * Telefon: inditsd el az IP Webcam (Android) alkalmazast, nyomd meg a Start server' -ForegroundColor Green
    Write-Host '      gombot, es jegyezd fel a kijelzon latszo cimet (pl. 192.168.0.56:8080).' -ForegroundColor Green
    Write-Host '    * Kapcsold fel a tablat vilagito lampakat.' -ForegroundColor Green
    Write-Host '  A telepites utan a program azonnal elindul, es a kalibracios varazslo' -ForegroundColor Green
    Write-Host '  elso inditaskor magatol megnyilik: ott mar elo kepen allitjatok be a tablat.' -ForegroundColor Green
    Write-Host ''
}

function Get-Payload {
    $self = $env:RK_SELF
    if (-not $self -or -not (Test-Path -LiteralPath $self)) { throw 'A telepito fajl nem talalhato.' }
    $text = [IO.File]::ReadAllText($self)
    $mark = $text.LastIndexOf("`n#__ZIP__")
    if ($mark -lt 0) { throw 'A telepito serult: hianyzik a csomag.' }
    $b64 = $text.Substring($mark + 9) -replace '\s', ''
    return [Convert]::FromBase64String($b64)
}

function Expand-App([byte[]]$zip) {
    Add-Type -AssemblyName System.IO.Compression
    $ms = New-Object IO.MemoryStream(, $zip)
    $archive = New-Object IO.Compression.ZipArchive($ms, [IO.Compression.ZipArchiveMode]::Read)
    $root = [IO.Path]::GetFullPath($InstallDir)
    $count = 0
    foreach ($entry in $archive.Entries) {
        if (-not $entry.Name) { continue }
        $rel = $entry.FullName -replace '/', '\'
        $target = [IO.Path]::GetFullPath((Join-Path $InstallDir $rel))
        if (-not $target.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { throw "Ervenytelen fajl a csomagban: $rel" }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        $in = $entry.Open()
        $out = [IO.File]::Create($target)
        try { $in.CopyTo($out) } finally { $out.Dispose(); $in.Dispose() }
        $count++
    }
    $archive.Dispose()
    return $count
}

function Test-Python([string]$exe) {
    # Visszaadja az "x.y" verziot, ha a Python 3.10-3.13 es van venv modulja; kulonben $null.
    if (-not $exe -or -not (Test-Path -LiteralPath $exe)) { return $null }
    if ($exe -like '*\WindowsApps\*') { return $null }             # a Microsoft Store csonk nem valodi Python
    try {
        $v = & $exe -c "import sys, venv, struct; print('%d.%d' % sys.version_info[:2] if struct.calcsize('P') == 8 else '0.0')" 2>$null
    } catch { return $null }
    if ($LASTEXITCODE -ne 0 -or -not $v) { return $null }
    $v = ($v | Select-Object -First 1).ToString().Trim()
    if ($v -match $PyRegex) { return $v }
    return $null
}

function Find-Python {
    $cands = New-Object System.Collections.Generic.List[string]
    $py = Get-Command 'py' -ErrorAction SilentlyContinue
    if ($py) {
        foreach ($ver in $PyVersions) {
            try {
                $p = & $py.Source "-$ver" -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $p) { $cands.Add(($p | Select-Object -First 1).ToString().Trim()) }
            } catch { }
        }
    }
    $pn = Get-Command 'python' -ErrorAction SilentlyContinue
    if ($pn) { $cands.Add($pn.Source) }
    foreach ($ver in $PyDirs) {
        $cands.Add((Join-Path $env:LOCALAPPDATA "Programs\Python\Python$ver\python.exe"))
        $cands.Add("C:\Program Files\Python$ver\python.exe")
    }
    foreach ($c in $cands) {
        $v = Test-Python $c
        if ($v) { return @{ Exe = $c; Version = $v } }
    }
    return $null
}

function Install-Python {
    if ($OfflinePython) {
        Say ('Python telepitese a csomagbol (' + $OfflinePython.Name + ') - csak ennek a felhasznalonak, nem kell rendszergazda...')
        $code = Run $OfflinePython.FullName @('/quiet', 'InstallAllUsers=0', 'PrependPath=0', 'Include_launcher=0', 'Include_test=0', 'Include_doc=0')
        $found = Find-Python
        if ($found) { return $found }
        throw "A csomagban levo Python telepitese nem sikerult (kod: $code)."
    }
    if ($IsOffline) { throw 'Offline modban a Python 3.12 nincs telepitve, es a csomagban sincs python-3.12*-amd64.exe. Masold az offline mappat teljes egeszeben a telepito melle.' }
    $winget = Get-Command 'winget' -ErrorAction SilentlyContinue
    if ($winget) {
        Say 'Python telepitese a winget-tel...'
        $code = Run $winget.Source @('install', '-e', '--id', 'Python.Python.3.12', '--scope', 'user', '--silent',
                                     '--accept-package-agreements', '--accept-source-agreements')
        $found = Find-Python
        if ($found) { return $found }
        Say "A winget nem tudta telepiteni (kod: $code), probalom a python.org-rol." 'Yellow'
    }
    Say 'Python 3.12 letoltese a python.org-rol (kb. 25 MB)...'
    $tmp = Join-Path $env:TEMP 'rkbully-python-setup.exe'
    Invoke-WebRequest -Uri $PyDownload -OutFile $tmp -UseBasicParsing
    Say 'Python telepitese (csak ennek a felhasznalonak, nem kell rendszergazda)...'
    $code = Run $tmp @('/quiet', 'InstallAllUsers=0', 'PrependPath=0', 'Include_launcher=0', 'Include_test=0', 'Include_doc=0')
    Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
    $found = Find-Python
    if (-not $found) { throw "A Python telepitese nem sikerult (kod: $code). Telepitsd kezzel a python.org oldalrol, majd futtasd ujra a telepitot." }
    return $found
}

function New-Shortcut([string]$path, [string]$target, [string]$arguments, [string]$workdir, [string]$icon) {
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath = $target
    $lnk.Arguments = $arguments
    $lnk.WorkingDirectory = $workdir
    $lnk.IconLocation = $icon + ',0'
    $lnk.Description = $AppName
    $lnk.Save()
}

try {
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    $Host.UI.RawUI.WindowTitle = "$AppName - telepito"
    Banner
    Say "Telepitesi mappa: $InstallDir"
    Say ("Verzio: $AppVersion   Mod: " + $(if ($IsOffline) { 'OFFLINE (csomagbol)' } else { 'online' })) 'Gray'

    Step '1/5  Fajlok kicsomagolasa'
    $n = Expand-App (Get-Payload)
    Say "$n fajl kicsomagolva." 'Gray'
    if ($env:RK_EXTRACT_ONLY) { Say 'Teszt mod: kesz.'; exit 0 }

    Step ('2/5  Python keresese (' + $(if ($IsOffline) { '3.12, 64 bites' } else { '3.10-3.13' }) + ')')
    $python = Find-Python
    if ($python) { Say ("Megvan: Python " + $python.Version + "  (" + $python.Exe + ")") 'Gray' }
    else { $python = Install-Python; Say ("Telepitve: Python " + $python.Version) 'Gray' }

    Step '3/5  Programkornyezet es csomagok (PySide6, OpenCV, numpy)'
    $vpy = Join-Path $Venv 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $vpy) -or -not (Test-Python $vpy)) {
        if (Test-Path -LiteralPath $Venv) { Remove-Item -LiteralPath $Venv -Recurse -Force -ErrorAction SilentlyContinue }
        if ((Run $python.Exe @('-m', 'venv', $Venv)) -ne 0) { throw 'A virtualis kornyezet letrehozasa nem sikerult.' }
    }
    $pipSrc = @()
    if ($IsOffline) { $pipSrc = @('--no-index', '--find-links', $Wheels) }
    if ($IsOffline) { Say ('Offline csomagforras: ' + $Wheels) 'Gray' }
    Run $vpy (@('-m', 'pip', 'install', '--upgrade', 'pip', '--quiet', '--disable-pip-version-check') + $pipSrc) | Out-Null
    if ((Run $vpy (@('-m', 'pip', 'install', '-r', (Join-Path $InstallDir 'requirements.txt'), '--disable-pip-version-check') + $pipSrc)) -ne 0) {
        if ($IsOffline) { throw 'A csomagok telepitese az offline mappabol nem sikerult. Ellenorizd, hogy az offline\wheels mappa hianytalan-e (lasd a telepites.log-ot).' }
        throw 'A csomagok telepitese nem sikerult. Ellenorizd az internetkapcsolatot, majd futtasd ujra a telepitot.'
    }

    Step '4/5  Dobasfelismeres csomagja (ultralytics + PyTorch - nagy, par percig tarthat)'
    $detect = $true
    if ($env:RK_NODETECT) { $detect = $false; Say 'Kihagyva (RK_NODETECT).' }
    if ($detect) {
        $code = Run $vpy (@('-m', 'pip', 'install', '-r', (Join-Path $InstallDir 'requirements-felismeres.txt'), '--disable-pip-version-check') + $pipSrc)
        if ($code -ne 0) {
            Say 'Figyelem: az ultralytics telepitese nem sikerult. A program igy is elindul, de a dobasfelismeres' 'Yellow'
            Say 'es a modell betanitasa nem lesz elerheto. Futtasd ujra a telepitot jobb halozaton, vagy lasd a README-t.' 'Yellow'
        }
    }

    if ($IsOffline) {
        # A modell betanitasahoz kell kiindulo sulyfajl (yolov8n.pt): offline csomagbol, hogy a tanitashoz se kelljen internet.
        $bw = Join-Path $OfflineDir 'yolov8n.pt'
        if (Test-Path -LiteralPath $bw) {
            New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir 'base') | Out-Null
            Copy-Item -LiteralPath $bw -Destination (Join-Path $InstallDir 'base\yolov8n.pt') -Force
            Say 'A tanitashoz szukseges alap-sulyfajl (yolov8n.pt) a base mappaba masolva.' 'Gray'
        }
    }

    # Telepitesi jegyzek: verzio, mod, Python es a pontos csomagverziok - masik gepen ebbol latszik, mi van telepitve.
    try {
        $freeze = & $vpy -m pip freeze --disable-pip-version-check 2>$null
        $info = @("$AppName $AppVersion", ('Telepitve: ' + (Get-Date -Format 's')),
                  ('Mod: ' + $(if ($IsOffline) { 'offline (csomagbol)' } else { 'online (internetrol)' })),
                  ('Python: ' + $python.Exe + '  (' + $python.Version + ')'), ('Mappa: ' + $InstallDir), '', 'Telepitett csomagok (pip freeze):') + $freeze
        Set-Content -LiteralPath (Join-Path $InstallDir 'TELEPITES_INFO.txt') -Value $info -Encoding UTF8
    } catch { }

    Step '5/5  Parancsikonok'
    $pythonw = Join-Path $Venv 'Scripts\pythonw.exe'
    $app = Join-Path $InstallDir 'rkbully.py'
    $icon = Join-Path $InstallDir 'assets\rkbully.ico'
    $desktop = [Environment]::GetFolderPath('Desktop')
    $start = Join-Path ([Environment]::GetFolderPath('Programs')) $AppName
    New-Item -ItemType Directory -Force -Path $start | Out-Null
    New-Shortcut (Join-Path $desktop "$AppName.lnk") $pythonw ('"' + $app + '"') $InstallDir $icon
    New-Shortcut (Join-Path $start "$AppName.lnk") $pythonw ('"' + $app + '"') $InstallDir $icon
    New-Shortcut (Join-Path $start 'Eltavolitas.lnk') (Join-Path $InstallDir 'Eltavolitas.bat') '' $InstallDir $icon
    Say "Parancsikon az Asztalon es a Start menuben: $AppName" 'Gray'

    Say ''
    Say ('  ================  A TELEPITES KESZ  (' + $AppVersion + ')  ================') 'Green'
    Say "  Inditas: az Asztalon az '$AppName' ikon." 'Green'
    Say '  Elso inditaskor a Kalibracios varazslo magatol megnyilik.' 'Green'
    Say '  Naplo: ' 'Gray'
    Say "         $Log" 'Gray'
    Say ''
    if (-not $env:RK_NOLAUNCH) {
        Say 'A program indul...' 'Cyan'
        Start-Process -FilePath $pythonw -ArgumentList ('"' + $app + '"') -WorkingDirectory $InstallDir
        Start-Sleep -Seconds 4
    }
}
catch {
    Say '' 'Red'
    Say ('HIBA: ' + $_.Exception.Message) 'Red'
    Say "A reszletek a naplofajlban: $Log" 'Yellow'
    Write-Host ''
    Read-Host 'Nyomj Entert a bezarashoz'
    exit 1
}
