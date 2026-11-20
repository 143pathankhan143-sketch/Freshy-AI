@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Freshy AI Assistant Phase 6 Desktop Launcher
color 0B

cd /d "%~dp0"

echo ===================================================
echo        FRESHY AI ASSISTANT - PHASE 6 DESKTOP
echo ===================================================

echo [1/8] Verifying Python and Flutter...
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not available in PATH.
    echo Install Python 3.11 or 3.12 and enable "Add python.exe to PATH".
    pause
    exit /b 1
)
where flutter >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Flutter is not available in PATH.
    pause
    exit /b 1
)

echo [2/8] Preparing the Python virtual environment...
cd /d "%~dp0freshy_core"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create freshy_core\.venv.
        pause
        exit /b 1
    )
)
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Could not activate freshy_core\.venv.
    pause
    exit /b 1
)
set "REQ_HASH="
set "SAVED_REQ_HASH="
set "REQ_HASH_FILE=.venv\.freshy-requirements.sha256"
for /f "usebackq delims=" %%H in (`powershell -NoLogo -NoProfile -Command "(Get-FileHash -Algorithm SHA256 -LiteralPath 'requirements.txt').Hash"`) do set "REQ_HASH=%%H"
if exist "!REQ_HASH_FILE!" set /p SAVED_REQ_HASH=<"!REQ_HASH_FILE!"
set "INSTALL_DEPS=1"
if defined REQ_HASH if /I "!REQ_HASH!"=="!SAVED_REQ_HASH!" set "INSTALL_DEPS=0"
if "!INSTALL_DEPS!"=="1" (
    echo [INFO] Installing or updating Python dependencies. The first Whisper setup can take time...
    python -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Python dependency installation failed.
        pause
        exit /b 1
    )
    if defined REQ_HASH >"!REQ_HASH_FILE!" echo !REQ_HASH!
) else (
    echo [OK] Python dependencies are unchanged; skipping repeat installation.
)

echo [3/8] Reading safe AI and voice configuration status...
python -c "from config import config; items=[('Groq',config.GROQ_API_KEY),('Mistral',config.MISTRAL_API_KEY),('Gemini',config.GEMINI_API_KEY),('SambaNova',config.SAMBANOVA_API_KEY),('Tavily',config.TAVILY_API_KEY)]; [print('  '+name+': '+('configured' if bool(value.strip()) else 'not configured')) for name,value in items]; print('  Standard voice output: '+config.TTS_PROVIDER); print('  Live voice: '+('available' if bool(config.GEMINI_API_KEY.strip()) and config.LIVE_VOICE_ENABLED else 'not available')+' (mode='+config.LIVE_CONVERSATION_MODE+', model='+config.GEMINI_LIVE_MODEL+')'); print('  XTTS mode: '+config.XTTS_MODE)"
if errorlevel 1 (
    echo [WARNING] Provider status could not be read. Freshy will still attempt local startup.
)

echo [4/8] Checking hybrid Whisper / Vosk speech input...
cd /d "%~dp0"
if not exist "freshy_core\models\vosk-model-small-en-in-0.4\am\final.mdl" (
    echo [INFO] Voice model is missing. Starting one-time preparation...
    call "%~dp0prepare_voice_model.bat"
    if errorlevel 1 (
        echo [WARNING] Voice model preparation failed.
        echo Freshy will still start with text chat and offline TTS.
    )
) else (
    echo [OK] Vosk fallback model detected. Whisper is installed from requirements.txt.
)

echo [5/8] Checking the Flutter Windows scaffold...
cd /d "%~dp0freshy_app"
if not exist "windows\runner\main.cpp" (
    flutter create --platforms=windows .
    if errorlevel 1 (
        echo [ERROR] Flutter Windows scaffold generation failed.
        pause
        exit /b 1
    )
)

echo [6/8] Resolving Flutter packages...
call flutter pub get
if errorlevel 1 (
    echo [ERROR] flutter pub get failed.
    pause
    exit /b 1
)

echo [7/8] Starting Freshy Python Core...
cd /d "%~dp0freshy_core"
start "Freshy Core Backend" cmd /k ^
  "call .venv\Scripts\activate.bat && python main.py"

echo Waiting for http://127.0.0.1:8000/health (maximum 60 seconds)...
set /a WAIT_COUNT=0
:HEALTH_CHECK_LOOP
powershell -NoLogo -NoProfile -Command ^
  "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto LAUNCH_FLUTTER
set /a WAIT_COUNT+=1
if !WAIT_COUNT! geq 60 (
    echo [ERROR] Freshy Core did not become healthy within 60 seconds.
    echo Read the "Freshy Core Backend" terminal for the actual error.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto HEALTH_CHECK_LOOP

:LAUNCH_FLUTTER
echo [OK] Freshy Core is online.
echo [8/8] Launching the Flutter Windows app...
cd /d "%~dp0freshy_app"
start "Freshy App UI" cmd /k "flutter run -d windows"

echo ===================================================
echo Freshy Phase 6 Desktop launch commands were started.
echo Local commands work even when no cloud key is set.
echo Keep the Backend and App UI terminals open.
echo ===================================================
pause
exit /b 0
