<#
    Aras-GP Panel — background runner for Windows.

        .\scripts\aras-panel.ps1 start     run detached, no console window
        .\scripts\aras-panel.ps1 stop
        .\scripts\aras-panel.ps1 restart
        .\scripts\aras-panel.ps1 status
        .\scripts\aras-panel.ps1 logs

    Running `python -m panel` in a PowerShell window ties the relay to that
    window: close it and the tunnel dies. This starts the same process hidden
    and tracks it with a PID file.

    If PowerShell refuses to run this file:
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#>

param([Parameter(Position = 0)][string]$Command = "")

$ErrorActionPreference = "Stop"

$Root    = Split-Path -Parent $PSScriptRoot
$RunDir  = Join-Path $Root "panel\data"
$PidFile = Join-Path $RunDir "panel.pid"
$LogFile = Join-Path $RunDir "panel.log"

$VenvPy = Join-Path $Root ".venv\Scripts\pythonw.exe"
if (Test-Path $VenvPy) {
    $Py = $VenvPy
} elseif (Get-Command pythonw -ErrorAction SilentlyContinue) {
    $Py = (Get-Command pythonw).Source
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $Py = (Get-Command python).Source
} else {
    Write-Error "پایتون پیدا نشد. اول venv بسازید:  py -m venv .venv"
    exit 1
}

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

function Test-Running {
    if (-not (Test-Path $PidFile)) { return $false }
    $procId = Get-Content $PidFile -ErrorAction SilentlyContinue
    if (-not $procId) { return $false }
    return [bool](Get-Process -Id $procId -ErrorAction SilentlyContinue)
}

function Start-Panel {
    if (Test-Running) {
        Write-Host "پنل از قبل در حال اجراست (PID $(Get-Content $PidFile))."
        return
    }
    Push-Location $Root
    try {
        $proc = Start-Process -FilePath $Py -ArgumentList "-m", "panel" `
            -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err"
        $proc.Id | Set-Content $PidFile
    } finally {
        Pop-Location
    }

    Start-Sleep -Seconds 2
    if (Test-Running) {
        $port = if ($env:ARAS_PANEL_PORT) { $env:ARAS_PANEL_PORT } else { "8600" }
        Write-Host "پنل بالا آمد (PID $(Get-Content $PidFile))  ->  http://127.0.0.1:$port"
        Write-Host "لاگ: $LogFile"
    } else {
        Write-Error "بالا نیامد. لاگ را ببینید: $LogFile"
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        exit 1
    }
}

function Stop-Panel {
    if (-not (Test-Running)) {
        Write-Host "پنل در حال اجرا نیست."
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        return
    }
    $procId = Get-Content $PidFile
    Stop-Process -Id $procId -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    if (Test-Running) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
    Write-Host "پنل متوقف شد."
}

switch ($Command.ToLower()) {
    "start"   { Start-Panel }
    "stop"    { Stop-Panel }
    "restart" { Stop-Panel; Start-Panel }
    "status"  {
        if (Test-Running) { Write-Host "در حال اجرا — PID $(Get-Content $PidFile)" }
        else { Write-Host "متوقف"; exit 1 }
    }
    "logs"    { Get-Content $LogFile -Wait -Tail 40 }
    default   { Write-Host "استفاده: .\scripts\aras-panel.ps1 {start|stop|restart|status|logs}"; exit 1 }
}
