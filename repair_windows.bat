@echo off
setlocal
REM ======================================================================
REM  Auto Workshop Management POS — Version 1.2.2
REM  Windows Recovery & Repair Utility (Preserves data\auto_workshop.db!)
REM ======================================================================
cd /d "%~dp0"

echo.
echo ======================================================================
echo   Auto Workshop Management POS v1.2.2 — Repair Utility
echo   Note: Your workshop database (data\auto_workshop.db) is NOT touched.
echo ======================================================================
echo.

set "SYS_PY="
set "SYS_ARGS="

where py >nul 2>&1
if errorlevel 1 goto :try_python
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 goto :try_python
set "SYS_PY=py"
set "SYS_ARGS=-3"
goto :repair_start

:try_python
where python >nul 2>&1
if errorlevel 1 goto :no_python
set "SYS_PY=python"
set "SYS_ARGS="

:repair_start
echo [1/4] Repairing system pip via ensurepip ...
"%SYS_PY%" %SYS_ARGS% -m ensurepip --upgrade

if exist "%~dp0.venv" (
    echo [2/4] Removing stale .venv directory ...
    rmdir /s /q "%~dp0.venv"
)

echo [3/4] Creating fresh .venv virtual environment ...
"%SYS_PY%" %SYS_ARGS% -m venv "%~dp0.venv"
if not exist "%~dp0.venv\Scripts\python.exe" goto :fallback_sys

echo [4/4] Installing required packages into .venv ...
"%~dp0.venv\Scripts\python.exe" -m ensurepip --upgrade
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade --force-reinstall pip
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto :fail
goto :done

:fallback_sys
echo [4/4] Installing required packages using system Python ...
"%SYS_PY%" %SYS_ARGS% -m pip install --upgrade --force-reinstall pip
"%SYS_PY%" %SYS_ARGS% -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto :fail

:done
echo.
echo [SUCCESS] Environment repaired! You can now start the app with:
echo   .\run_windows.bat
if "%AWP_NO_PAUSE%"=="" pause
exit /b 0

:no_python
echo [ERROR] Neither `py -3` nor `python` was found. Install Python 3.11+ from python.org.
if "%AWP_NO_PAUSE%"=="" pause
exit /b 1

:fail
echo [ERROR] Package installation failed. Check internet connection and see TROUBLESHOOTING.md.
if "%AWP_NO_PAUSE%"=="" pause
exit /b 1
