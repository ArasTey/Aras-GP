@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM -------- Aras-GP one-click launcher (Windows) --------
REM
REM   run.bat              start the relay engine
REM   run.bat panel        start the control panel  (http://127.0.0.1:8600)
REM   run.bat <args...>    any main.py flag, e.g. --install-cert, --scan
REM
REM Creates a local virtualenv, installs every dependency, runs the setup
REM wizard if there is no config yet, then starts what you asked for.

set "VENV_DIR=.venv"
set "PY="

where py >nul 2>&1
if !errorlevel!==0 (
    set "PY=py -3"
) else (
    where python >nul 2>&1
    if !errorlevel!==0 (
        set "PY=python"
    )
)

if "%PY%"=="" (
    echo [X] Python 3.10+ was not found on PATH.
    echo     Install it from https://www.python.org/downloads/ and tick
    echo     "Add python.exe to PATH" in the installer, then re-run this script.
    pause
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [*] Creating virtual environment in %VENV_DIR% ...
    %PY% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [X] Failed to create virtualenv.
        pause
        exit /b 1
    )
)

set "VPY=%VENV_DIR%\Scripts\python.exe"

REM requirements.txt now covers the panel as well as the engine. It did not,
REM and a virtualenv built here came out without Flask in it, so this script
REM reported success and "python -m panel" then failed on an import error.
echo [*] Installing dependencies ...
"%VPY%" -m pip install --disable-pip-version-check -q --upgrade pip >nul
"%VPY%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo [X] Could not install dependencies. Check your network and retry.
    pause
    exit /b 1
)

REM -------- Panel --------
if /i "%~1"=="panel" (
    echo.
    if defined ARAS_PANEL_PORT (
        echo [*] Starting the Aras-GP panel  --^> http://127.0.0.1:!ARAS_PANEL_PORT!
    ) else (
        echo [*] Starting the Aras-GP panel  --^> http://127.0.0.1:8600
    )
    echo.
    "%VPY%" -m panel
    set "RC=!errorlevel!"
    if not "!RC!"=="0" pause
    exit /b !RC!
)

REM Certificate commands run standalone in main.py, so they must not be
REM ambushed by the setup wizard when there is no config yet.
set "CERTONLY="
echo %* | findstr /C:"-cert" >nul
if not errorlevel 1 set "CERTONLY=1"

if not defined CERTONLY (
    if not exist "config.json" (
        echo [*] No config.json found - launching setup wizard ...
        "%VPY%" setup.py
        if errorlevel 1 (
            echo [X] Setup cancelled.
            pause
            exit /b 1
        )
    )
)

echo.
echo [*] Starting Aras-GP ...
echo.
"%VPY%" main.py %*
set "RC=%errorlevel%"
if not "%RC%"=="0" pause
exit /b %RC%
