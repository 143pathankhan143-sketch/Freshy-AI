@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Freshy Phase 4.3 XTTS Setup

echo ===================================================
echo      FRESHY XTTS HUMAN VOICE - OPTIONAL SETUP
echo ===================================================
echo This setup is separate from the main Freshy environment.
echo Use only your own voice or a voice with clear permission.
echo.

set "PY_LAUNCHER="
py -3.11 --version >nul 2>&1 && set "PY_LAUNCHER=py -3.11"
if not defined PY_LAUNCHER py -3.12 --version >nul 2>&1 && set "PY_LAUNCHER=py -3.12"
if not defined PY_LAUNCHER py -3.10 --version >nul 2>&1 && set "PY_LAUNCHER=py -3.10"
if not defined PY_LAUNCHER (
  python -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] < (3,15) else 1)" >nul 2>&1
  if not errorlevel 1 set "PY_LAUNCHER=python"
)
if not defined PY_LAUNCHER (
  echo [ERROR] A compatible Python installation was not found.
  echo Install Python 3.10, 3.11, or 3.12 and run this file again.
  pause
  exit /b 1
)

echo [1/3] Creating the isolated .venv-xtts environment...
if not exist ".venv-xtts\Scripts\python.exe" %PY_LAUNCHER% -m venv .venv-xtts
if errorlevel 1 (
  echo [ERROR] Could not create the XTTS virtual environment.
  pause
  exit /b 1
)
call ".venv-xtts\Scripts\activate.bat"

echo [2/3] Installing optional XTTS dependencies...
python -m pip install --disable-pip-version-check --upgrade pip
python -m pip install --disable-pip-version-check -r freshy_core\requirements-xtts.txt
if errorlevel 1 (
  echo [ERROR] XTTS dependencies could not be installed.
  echo Check free disk space and internet access, then run this file again.
  pause
  exit /b 1
)

echo [3/3] XTTS environment is ready.
echo.
echo Install one or more clean consented WAV clips with this example:
echo python freshy_core\voice_profile_manager.py install --id my_voice --label "My Voice" --reference "C:\path\clip1.wav" --reference "C:\path\clip2.wav" --language hi
echo.
echo Then set XTTS_MODE=server in the project-root .env file,
echo run start_xtts_server.bat, refresh Voice Studio, and select the profile.
pause
