@echo off
setlocal
REM ======================================================================
REM  Auto Workshop Management POS — Version 1.2.2
REM  One-Click Windows Environment Installer (Supports `py -3` & `python`)
REM ======================================================================
cd /d "%~dp0"

echo.
echo ======================================================================
echo   Auto Workshop Management POS v1.2.2 — Windows Environment Setup
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
goto :found_py

:try_python
where python >nul 2>&1
if errorlevel 1 goto :no_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 goto :old_python
set "SYS_PY=python"
set "SYS_ARGS="

:found_py
echo [1/3] Detected Python:
"%SYS_PY%" %SYS_ARGS% --version

if exist "%~dp0.venv\Scripts\python.exe" goto :venv_ok
echo [1/3] Creating virtual environment in .venv ...
"%SYS_PY%" %SYS_ARGS% -m venv "%~dp0.venv"
if errorlevel 1 goto :venv_fail

:venv_ok
echo [2/3] Verifying pip and installing dependencies from requirements.txt ...
"%~dp0.venv\Scripts\python.exe" -m pip --version >nul 2>&1
if errorlevel 1 (
    "%~dp0.venv\Scripts\python.exe" -m ensurepip --upgrade
)
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip
"%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto :pip_fail

echo [3/3] Ensuring data directories exist (existing database is preserved) ...
if not exist "%~dp0data" mkdir "%~dp0data"
if not exist "%~dp0data\backups" mkdir "%~dp0data\backups"
if not exist "%~dp0data\logs" mkdir "%~dp0data\logs"
if not exist "%~dp0data\uploads" mkdir "%~dp0data\uploads"

echo.
echo ======================================================================
echo   Installation complete! (Version 1.2.2)
echo   Double-click `run_windows.bat` or run in PowerShell:
echo     .\run_windows.bat          (default http://127.0.0.1:8000)
echo     .\run_windows.bat 7290     (custom port http://127.0.0.1:7290)
echo ======================================================================
echo.
if "%AWP_NO_PAUSE%"=="" pause
exit /b 0

:no_python
echo [ERROR] Python 3.11+ was not found (`py -3` or `python`).
echo Install Python 3.11 or newer from https://www.python.org/downloads/
if "%AWP_NO_PAUSE%"=="" pause
exit /b 1

:old_python
echo [ERROR] Python 3.11 or newer is required.
if "%AWP_NO_PAUSE%"=="" pause
exit /b 1

:venv_fail
echo [ERROR] Failed to create virtual environment (.venv).
if "%AWP_NO_PAUSE%"=="" pause
exit /b 1

:pip_fail
echo [ERROR] Failed to install Python dependencies from requirements.txt.
echo Run repair_windows.bat to rebuild .venv and repair pip automatically.
if "%AWP_NO_PAUSE%"=="" pause
exit /b 1
