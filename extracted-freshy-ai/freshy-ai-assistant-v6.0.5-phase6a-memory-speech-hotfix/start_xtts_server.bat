@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Freshy XTTS Human Voice Server
if not exist ".venv-xtts\Scripts\python.exe" (
  echo [ERROR] XTTS environment is missing. Run prepare_xtts_voice.bat first.
  pause
  exit /b 1
)
call ".venv-xtts\Scripts\activate.bat"
set "PYTHONPATH=%CD%"
echo Starting the private Freshy XTTS server on http://127.0.0.1:8020 ...
echo Configuration is read from the project-root .env file.
python freshy_core\xtts_server.py
if errorlevel 1 (
  echo.
  echo [ERROR] The XTTS server stopped with an error.
  pause
)
