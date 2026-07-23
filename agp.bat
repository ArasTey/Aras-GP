@echo off
REM Aras-GP manager launcher (Windows).
REM   Menu:        aras.bat
REM   One-shot:    aras.bat start ^| stop ^| restart ^| status ^| install ^| version
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
    py -3 manage.py %*
    goto :eof
)
where python >nul 2>&1
if %errorlevel%==0 (
    python manage.py %*
    goto :eof
)
echo [X] Python 3.10+ was not found on PATH.
echo     Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH").
pause
