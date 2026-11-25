<#
    Benefactor launcher for Windows x86_64.

    Asks for the three CLS-cracked ADFs, downloads the port's source, builds it
    with a self-contained toolchain kit (cmake + ninja + zig + python + capstone
    + SDL2 -- nothing is installed system-wide), then starts the game.

    Usage (PowerShell):
      .\benefactor-launch.ps1                 pick the disks with a file dialog
      .\benefactor-launch.ps1 -Disks d1,d2,d3 use these ADFs, no dialog
      .\benefactor-launch.ps1 -Level 12       start directly at a level
      .\benefactor-launch.ps1 -Rebuild        force a fresh build
      .\benefactor-launch.ps1 -AnyDisks       accept non-CLS images (may fail)

    Everything lives under %LOCALAPPDATA%\BenefactorLauncher.
#>
[CmdletBinding()]
param(
    [string[]]$Disks = @(),
    [int]$Level = 0,
    [switch]$Rebuild,
    [switch]$AnyDisks,
    [switch]$KeepWindow
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$ReleaseTag = 'v0.2.0'
$Repo       = 'salmon85/benefactor_recomp'
$SrcUrl     = "https://github.com/$Repo/releases/download/$ReleaseTag/benefactor-re-source.tar.gz"
$KitUrl     = "https://github.com/$Repo/releases/download/$ReleaseTag/benefactor-buildkit-windows-x86_64.zip"

$Data     = Join-Path $env:LOCALAPPDATA 'BenefactorLauncher'
$SrcDir   = Join-Path $Data 'src'
$Kit      = Join-Path $Data 'kit'
$DisksDir = Join-Path $Data 'disks'
$Build    = Join-Path $SrcDir 'port\build'
$Log      = Join-Path $Data 'launcher.log'

$KnownDisks = @(
    '0B7BC60DACC4AB66BB582C51D8FD12181693749F05AC49B7D7ACBC31EEEE9B71',
    '2ACBE50C90AD2302D97EAA0D18FA9EB6F8C15548817142676EB3960CB4ECD2BE',
    'AFA4B06727DBF7C0D75649D4737BC832DBBB4FF95CF8C0BDD20A37260CB25B2A'
)

function Say([string]$msg)  { Write-Host "[benefactor] $msg" -ForegroundColor Cyan }
function Warn([string]$msg) { Write-Host "[benefactor] $msg" -ForegroundColor Yellow }
function Die([string]$msg)  { Write-Host "[benefactor] $msg" -ForegroundColor Red; exit 1 }
function Log([string]$msg)  { Add-Content -Path $Log -Value $msg }

New-Item -ItemType Directory -Force -Path $Data, $DisksDir | Out-Null
Set-Content -Path $Log -Value "=== $(Get-Date -Format o) ==="

function Invoke-Download([string]$Url, [string]$Out) {
    Say "downloading $(Split-Path $Out -Leaf)"
    $part = "$Out.part"
    if (Test-Path $part) { Remove-Item $part -Force }
    try {
        Invoke-WebRequest -Uri $Url -OutFile $part -UseBasicParsing
    } catch {
        Die "download failed: $Url ($($_.Exception.Message))"
    }
    Move-Item -Force $part $Out
}

function Pick-File([string]$Title) {
    Add-Type -AssemblyName System.Windows.Forms | Out-Null
    $dlg = New-Object System.Windows.Forms.OpenFileDialog
    $dlg.Title = $Title
    $dlg.Filter = 'Amiga disk images (*.adf)|*.adf|All files (*.*)|*.*'
    $dlg.CheckFileExists = $true
    if ($dlg.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        Die "$Title was not provided (-Disks d1,d2,d3 avoids the dialog)"
    }
    return $dlg.FileName
}

function Collect-Disks {
    $have = 0
    foreach ($n in 1, 2, 3) { if (Test-Path (Join-Path $DisksDir "Disk.$n")) { $have++ } }
    if (($have -eq 3) -and (-not $Rebuild) -and ($Disks.Count -eq 0)) {
        Say "using the disks already copied into $DisksDir"
        return
    }
    if ($Disks.Count -eq 0) {
        $Disks = @(
            (Pick-File 'Select Benefactor Disk 1 of 3 (.adf)'),
            (Pick-File 'Select Benefactor Disk 2 of 3 (.adf)'),
            (Pick-File 'Select Benefactor Disk 3 of 3 (.adf)')
        )
    }
    if ($Disks.Count -lt 3) { Die 'three .adf paths are required' }

    for ($i = 0; $i -lt 3; $i++) {
        $src = $Disks[$i]
        if (-not (Test-Path $src)) { Die "not a file: $src" }
        $len = (Get-Item $src).Length
        $sum = (Get-FileHash -Algorithm SHA256 -Path $src).Hash
        if ($len -ne 901120) {
            Warn "Disk.$($i+1) is $len bytes, expected 901120"
            if (-not $AnyDisks) { Die 'not a standard Amiga ADF (use -AnyDisks to override)' }
        }
        if ($sum -ne $KnownDisks[$i]) {
            Warn "Disk.$($i+1) is not the TOSEC CLS image (sha256 $sum)"
            if (-not $AnyDisks) {
                Die "this loader only handles 'Benefactor (1994)(Psygnosis)(Disk $($i+1) of 3)[cr CLS].adf' (use -AnyDisks to try anyway)"
            }
        }
        Copy-Item -Force $src (Join-Path $DisksDir "Disk.$($i+1)")
    }
    Say "disks verified and copied to $DisksDir"
}

function Ensure-Source {
    $tar = Join-Path $Data 'source.tar.gz'
    if ((-not (Test-Path $tar)) -or $Rebuild) { Invoke-Download $SrcUrl $tar }
    $marker = Join-Path $SrcDir 'port\CMakeLists.txt'
    if ((-not (Test-Path $marker)) -or $Rebuild) {
        Say 'extracting source'
        if (Test-Path $SrcDir) { Remove-Item -Recurse -Force $SrcDir }
        New-Item -ItemType Directory -Force -Path $SrcDir | Out-Null
        # Windows 10+ ships tar.exe which handles .tar.gz
        & tar.exe -xzf $tar -C $SrcDir
        if ($LASTEXITCODE -ne 0) { Die 'cannot extract source archive (needs tar.exe, Windows 10 1803+)' }
    }
}

function Ensure-Kit {
    $cmake = Join-Path $Kit 'cmake\bin\cmake.exe'
    $zig   = Join-Path $Kit 'zig\zig.exe'
    if ((Test-Path $cmake) -and (Test-Path $zig) -and (-not $Rebuild)) { Say 'build kit already present'; return }
    $zip = Join-Path $Data 'kit.zip'
    if ((-not (Test-Path $zip)) -or $Rebuild) { Invoke-Download $KitUrl $zip }
    Say 'unpacking build kit (cmake, ninja, zig, python, SDL2)'
    if (Test-Path $Kit) { Remove-Item -Recurse -Force $Kit }
    Expand-Archive -Path $zip -DestinationPath $Kit -Force
    Remove-Item -Force $zip
}

function Build-Game {
    $py     = Join-Path $Kit 'python\python.exe'
    $cmake  = Join-Path $Kit 'cmake\bin\cmake.exe'
    $ninja  = Join-Path $Kit 'bin'
    $zig    = Join-Path $Kit 'zig\zig.exe'
    $sdlInc = Join-Path $Kit 'sdl2\x86_64-w64-mingw32\include\SDL2'
    $sdlLib = Join-Path $Kit 'sdl2\x86_64-w64-mingw32\lib\libSDL2.dll.a'
    $sdlCfg = Join-Path $Kit 'sdl2\x86_64-w64-mingw32\lib\cmake\SDL2'
    $sdlDll = Join-Path $Kit 'sdl2\x86_64-w64-mingw32\bin\SDL2.dll'
    foreach ($p in @($py, $cmake, $zig, $sdlLib, $sdlDll)) {
        if (-not (Test-Path $p)) { Die "build kit is incomplete (missing $p); rerun with -Rebuild" }
    }

    $env:PATH = "$ninja;$($Kit)\cmake\bin;$env:PATH"
    Copy-Item -Force (Join-Path $DisksDir 'Disk.*') (Join-Path $SrcDir 'port')

    $port = Join-Path $SrcDir 'port'
    Say "translating the game's 68000 code from your disks (a few minutes)"
    Push-Location $port
    try {
        & $py 'tools\regen.py' --cc "`"$zig`" cc" *>> $Log
        if ($LASTEXITCODE -ne 0) { Die "bank regeneration failed; see $Log" }

        Say 'building benefactor-pc.exe'
        & $cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release `
            "-DCMAKE_C_COMPILER=$zig" -DCMAKE_C_COMPILER_ARG1=cc `
            "-DSDL2_DIR=$sdlCfg" "-DSDL2_INCLUDE_DIR=$sdlInc" "-DSDL2_LIBRARY=$sdlLib" *>> $Log
        if ($LASTEXITCODE -ne 0) { Die "cmake configure failed; see $Log" }
        & $cmake --build build *>> $Log
        if ($LASTEXITCODE -ne 0) { Die "build failed; see $Log" }
    } finally { Pop-Location }

    Copy-Item -Force $sdlDll (Join-Path $Build 'SDL2.dll')
    if (-not (Test-Path (Join-Path $Build 'benefactor-pc.exe'))) { Die "build produced no binary; see $Log" }
}

Say "data directory: $Data"
Collect-Disks
Ensure-Source
Ensure-Kit

$exe = Join-Path $Build 'benefactor-pc.exe'
if ($Rebuild -or (-not (Test-Path $exe))) { Build-Game } else { Say 'binary already built (use -Rebuild to force)' }

Copy-Item -Force (Join-Path $DisksDir 'Disk.*') (Join-Path $SrcDir 'port')

$gameArgs = @('Disk.1', 'Disk.2', 'Disk.3')
if ($Level -gt 0) { $gameArgs += @('--level', "$Level") }

Say 'starting Benefactor'
Push-Location (Join-Path $SrcDir 'port')
try {
    if ($KeepWindow) { & $exe @gameArgs } else { Start-Process -FilePath $exe -ArgumentList $gameArgs -WorkingDirectory (Get-Location) }
} finally { Pop-Location }
