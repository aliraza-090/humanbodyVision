#Requires -Version 5.1
<#
.SYNOPSIS
    Build the portable humanbodyVision folder and (optionally) the Windows installer.

.DESCRIPTION
    Runs the test suite, builds a PyInstaller onedir bundle, then invokes Inno
    Setup when it is installed. All output is written to .\dist.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -SkipTests -SkipInstaller
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $Python) {
    throw "Python was not found. Create .venv and install requirements-dev.txt first."
}

Write-Host "== humanbodyVision build ==" -ForegroundColor Green
Write-Host "Project: $Root"
Write-Host "Python : $Python"

if (-not $SkipTests) {
    Write-Host "`n[1/3] Running automated tests..." -ForegroundColor Cyan
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) {
        throw "Tests failed. Packaging aborted."
    }
}

Write-Host "`n[2/3] Building PyInstaller bundle..." -ForegroundColor Cyan
& $Python -m PyInstaller --noconfirm --clean "packaging\humanbodyVision.spec"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed."
}
$AppExe = Join-Path $Root "dist\humanbodyVision\humanbodyVision.exe"
if (-not (Test-Path $AppExe)) {
    throw "Expected executable was not produced: $AppExe"
}
Write-Host "Built: $AppExe" -ForegroundColor Green

if ($SkipInstaller) {
    Write-Host "`nInstaller step skipped." -ForegroundColor Yellow
    exit 0
}

Write-Host "`n[3/3] Building Inno Setup installer..." -ForegroundColor Cyan
$Iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $Iscc) {
    foreach ($candidate in @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )) {
        if (Test-Path $candidate) {
            $Iscc = $candidate
            break
        }
    }
}
if (-not $Iscc) {
    Write-Warning "Inno Setup 6 (ISCC.exe) was not found. The portable build is ready in dist\humanbodyVision."
    Write-Warning "Install Inno Setup from https://jrsoftware.org/isdl.php and rerun this script to create the installer."
    exit 0
}

& $Iscc "packaging\installer.iss"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed."
}

$Installer = Get-ChildItem "dist\installer\humanbodyVision-*.exe" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if ($Installer) {
    Write-Host "Installer: $($Installer.FullName)" -ForegroundColor Green
} else {
    Write-Host "Installer build completed. Check dist\installer." -ForegroundColor Green
}
