<#
    Aras-GP — install without git.

    Plenty of Windows machines have no git, and cloning is not the point: all
    that is needed is the folder. This downloads the current main branch as a
    zip, unpacks it, and hands over to run.bat, which builds the virtualenv and
    installs the dependencies.

    Run in PowerShell:

        powershell -ExecutionPolicy Bypass -Command "iwr -useb https://raw.githubusercontent.com/ArasTey/Aras-GP/main/scripts/get-aras.ps1 | iex"

    Or, having saved this file:

        powershell -ExecutionPolicy Bypass -File .\get-aras.ps1
#>

param(
    [string]$Destination = "$env:USERPROFILE\Aras-GP",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # a progress bar makes iwr crawl

$zipUrl = "https://github.com/ArasTey/Aras-GP/archive/refs/heads/$Branch.zip"
$tmpZip = Join-Path $env:TEMP "aras-gp-$Branch.zip"
$tmpDir = Join-Path $env:TEMP "aras-gp-extract"

Write-Host "[*] Downloading Aras-GP ($Branch)..."
try {
    # TLS 1.2 is not the default on older PowerShell and GitHub refuses less.
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $zipUrl -OutFile $tmpZip -UseBasicParsing
} catch {
    Write-Host "[X] Download failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "    Check your connection, or download this by hand and unzip it:"
    Write-Host "    $zipUrl"
    exit 1
}

if (Test-Path $tmpDir) { Remove-Item $tmpDir -Recurse -Force }
Write-Host "[*] Unpacking..."
Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force

# The zip contains a single top-level folder named Aras-GP-<branch>.
$inner = Get-ChildItem $tmpDir | Where-Object { $_.PSIsContainer } | Select-Object -First 1
if (-not $inner) {
    Write-Host "[X] The archive looked empty." -ForegroundColor Red
    exit 1
}

if (Test-Path $Destination) {
    # Never clobber a working install: config.json, ca/ and panel/data are all
    # untracked and would be gone for good.
    Write-Host "[!] $Destination already exists." -ForegroundColor Yellow
    Write-Host "    Not overwriting it — your config.json, ca\ and panel\data\ live there."
    Write-Host "    Delete or rename it first, or pass -Destination <other path>."
    exit 1
}

Move-Item $inner.FullName $Destination
Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue
Remove-Item $tmpDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "[OK] Installed to $Destination" -ForegroundColor Green
Write-Host ""

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Host "[!] Python 3.10+ was not found on PATH." -ForegroundColor Yellow
    Write-Host "    Install it from https://www.python.org/downloads/ and tick"
    Write-Host "    'Add python.exe to PATH', then run:"
    Write-Host "      cd $Destination"
    Write-Host "      run.bat panel"
    exit 0
}

Write-Host "[*] Starting the panel (this builds a virtualenv on first run)..."
Set-Location $Destination
& cmd /c "run.bat panel"
