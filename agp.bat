@echo off
REM Aras-GP manager launcher (Windows).
REM   Menu:        agp.bat
REM   One-shot:    agp.bat start ^| stop ^| restart ^| status ^| install ^| version
cd /d "%~dp0"

set "PY="
where py >nul 2>&1
if %errorlevel%==0 goto havepy
where python >nul 2>&1
if %errorlevel%==0 goto havepython
echo [X] Python 3.10+ was not found on PATH.
echo     Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH").
pause
exit /b 1

:havepy
set "PY=py -3"
goto checkver
:havepython
set "PY=python"

:checkver
REM A 3.9 interpreter passes "python exists" but the panel needs 3.10+.
set "PYMAJ=0"
set "PYMIN=0"
for /f "tokens=1,2" %%a in ('%PY% -c "import sys;print(sys.version_info[0],sys.version_info[1])" 2^>nul') do (
    set "PYMAJ=%%a"
    set "PYMIN=%%b"
)
set /a PYOK=0
if %PYMAJ% GTR 3 set /a PYOK=1
if %PYMAJ% EQU 3 if %PYMIN% GEQ 10 set /a PYOK=1
if %PYOK% EQU 0 (
    echo [X] Python 3.10+ is required; found %PYMAJ%.%PYMIN%.
    pause
    exit /b 1
)

%PY% manage.py %*