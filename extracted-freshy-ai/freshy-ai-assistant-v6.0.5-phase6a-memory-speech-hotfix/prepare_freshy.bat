@echo off
title Preparing Freshy AI Workspace...
color 0B

cd /d "%~dp0"

echo ===================================================
echo       ⚡ FRESHY AI WORKSPACE PREPARATION
echo ===================================================

where flutter >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Flutter is not found in PATH! Please install Flutter SDK and add it to PATH.
    pause
    exit /b 1
)

echo Generating Flutter Windows scaffold inside freshy_app...
cd /d "%~dp0freshy_app"
flutter create --platforms=windows .
if errorlevel 1 (
    echo [ERROR] Failed to generate Windows scaffold.
    pause
    exit /b 1
)

echo Fetching Flutter packages...
call flutter pub get
if errorlevel 1 (
    echo [ERROR] flutter pub get failed.
    pause
    exit /b 1
)

echo ===================================================
echo [OK] Freshy Windows scaffold prepared successfully!
echo ===================================================
pause
