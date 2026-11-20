@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Freshy AI Phase 3 Voice Model Setup
color 0B

cd /d "%~dp0"

echo ===================================================
echo   Freshy AI - Phase 3 Offline Voice Model Setup
echo ===================================================
echo.

set "MODEL_DIR=freshy_core\models\vosk-model-small-en-in-0.4"
set "ZIP_FILE=freshy_core\models\vosk-model-small-en-in-0.4.zip"
set "MODEL_URL=https://alphacephei.com/vosk/models/vosk-model-small-en-in-0.4.zip"

if not exist "freshy_core\models" (
    mkdir "freshy_core\models"
    if errorlevel 1 (
        echo [ERROR] Could not create freshy_core\models.
        exit /b 1
    )
)

if exist "!MODEL_DIR!\am\final.mdl" (
    echo [OK] Vosk model is already installed.
    echo Location: !MODEL_DIR!
    exit /b 0
)

echo [1/3] Downloading the Indian-English Vosk model...
echo URL: !MODEL_URL!
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '!MODEL_URL!' -OutFile '!ZIP_FILE!'"
if errorlevel 1 (
    echo [ERROR] Model download failed.
    echo Check the internet connection, then run this file again.
    exit /b 1
)

if not exist "!ZIP_FILE!" (
    echo [ERROR] The downloaded model archive was not created.
    exit /b 1
)

echo.
echo [2/3] Extracting the model...
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath '!ZIP_FILE!' -DestinationPath 'freshy_core\models' -Force"
if errorlevel 1 (
    echo [ERROR] Model extraction failed.
    exit /b 1
)

echo.
echo [3/3] Removing the temporary archive...
del /f /q "!ZIP_FILE!" >nul 2>&1

if not exist "!MODEL_DIR!\am\final.mdl" (
    echo [ERROR] The extracted model is incomplete.
    exit /b 1
)

echo.
echo ===================================================
echo [SUCCESS] Offline voice model is ready.
echo Location: !MODEL_DIR!
echo ===================================================
exit /b 0
