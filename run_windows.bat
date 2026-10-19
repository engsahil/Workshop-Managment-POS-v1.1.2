@echo off
setlocal
REM ======================================================================
REM  Auto Workshop Management POS — Version 1.2.2
REM  Ready-to-Run Windows Launcher (Double-click, PowerShell, or CMD)
REM
REM  Features:
REM    - Detects .venv\Scripts\python.exe, `py -3` (Python Launcher), or `python`
REM    - Creates .venv and installs requirements.txt automatically on first run
REM    - Starts on http://127.0.0.1:8000 (or automatically selects the next
REM      available port if 8000 is occupied)
REM    - Opens the browser ONLY after /api/health confirms the server is live
REM ======================================================================
cd /d "%~dp0"

if not "%~1"=="" set "AWP_PORT=%~1"
if "%AWP_PORT%"=="" if not "%PORT%"=="" set "AWP_PORT=%PORT%"
if "%AWP_PORT%"=="" set "AWP_PORT=8000"

if "%AWP_HOST%"=="" if not "%HOST%"=="" set "AWP_HOST=%HOST%"
if "%AWP_HOST%"=="" set "AWP_HOST=127.0.0.1"

set "PORT=%AWP_PORT%"
set "HOST=%AWP_HOST%"

set "PY_EXE="
set "PY_ARGS="

REM 1. Check existing virtual environment first
if not exist "%~dp0.venv\Scripts\python.exe" goto :detect_sys_py
"%~dp0.venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 goto :detect_sys_py
set "PY_EXE=%~dp0.venv\Scripts\python.exe"
set "PY_ARGS="
goto :check_deps

:detect_sys_py
REM 2. Prefer Windows Python Launcher `py -3` (standard on Windows Python 3.11-3.14+)
where py >nul 2>&1
if errorlevel 1 goto :try_python_cmd
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 goto :try_python_cmd
set "PY_EXE=py"
set "PY_ARGS=-3"
goto :ensure_venv

:try_python_cmd
REM 3. Fallback to `python` on PATH
where python >nul 2>&1
if errorlevel 1 goto :no_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 goto :no_python
set "PY_EXE=python"
set "PY_ARGS="

:ensure_venv
if exist "%~dp0.venv\Scripts\python.exe" goto :use_venv
echo [SETUP] Creating local Python virtual environment in .venv ...
"%PY_EXE%" %PY_ARGS% -m venv "%~dp0.venv" >nul 2>&1
if not exist "%~dp0.venv\Scripts\python.exe" goto :check_deps

:use_venv
set "PY_EXE=%~dp0.venv\Scripts\python.exe"
set "PY_ARGS="

:check_deps
"%PY_EXE%" %PY_ARGS% -c "import fastapi, sqlalchemy, pydantic, argon2, jwt, uvicorn, multipart, tzdata" >nul 2>&1
if not errorlevel 1 goto :start_app

echo [SETUP] Checking pip and installing required packages from requirements.txt ...
"%PY_EXE%" %PY_ARGS% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Repairing pip via ensurepip ...
    "%PY_EXE%" %PY_ARGS% -m ensurepip --upgrade
)

"%PY_EXE%" %PY_ARGS% -m pip install --disable-pip-version-check -r "%~dp0requirements.txt"
if errorlevel 1 goto :pip_fail

:start_app
if not exist "%~dp0data" mkdir "%~dp0data"
if not exist "%~dp0data\backups" mkdir "%~dp0data\backups"
if not exist "%~dp0data\logs" mkdir "%~dp0data\logs"
if not exist "%~dp0data\uploads" mkdir "%~dp0data\uploads"

echo.
echo ======================================================================
echo   Auto Workshop Management POS — Version 1.2.2
echo   Preferred URL: http://%AWP_HOST%:%AWP_PORT%
echo   (If port %AWP_PORT% is busy, the next free port is chosen automatically)
echo ======================================================================
echo.

if "%AWP_NO_BROWSER%"=="" set "AWP_OPEN_BROWSER=1"
cd /d "%~dp0backend"
"%PY_EXE%" %PY_ARGS% run.py %AWP_PORT%
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto :run_failed
exit /b 0

:no_python
echo.
echo [ERROR] Python 3.11+ was not found (checked `.venv`, `py -3`, and `python`).
echo Please install Python 3.11 - 3.14+ from https://www.python.org/downloads/
echo (keep "Use admin privileges / Add py launcher" enabled), then run this file again.
if "%AWP_NO_PAUSE%"=="" pause
exit /b 1

:pip_fail
echo.
echo [ERROR] Could not install Python packages from requirements.txt.
echo Run repair_windows.bat (or see TROUBLESHOOTING.md) to repair pip and retry.
if "%AWP_NO_PAUSE%"=="" pause
exit /b 1

:run_failed
echo.
echo [ERROR] Server exited with code %EXIT_CODE%. Check data\logs\app.log or TROUBLESHOOTING.md.
if "%AWP_NO_PAUSE%"=="" pause
exit /b %EXIT_CODE%
