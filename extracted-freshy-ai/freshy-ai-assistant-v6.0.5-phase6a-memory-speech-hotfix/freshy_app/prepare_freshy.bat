@echo off
title Preparing Freshy App Windows Scaffold...
color 0B

cd /d "%~dp0"

echo Generating Flutter Windows scaffold for Freshy App...
where flutter >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Flutter is not found in PATH!
    pause
    exit /b 1
)

flutter create --platforms=windows .
if errorlevel 1 (
    echo [ERROR] Failed to generate Windows scaffold.
    pause
    exit /b 1
)

call flutter pub get
if errorlevel 1 (
    echo [ERROR] flutter pub get failed.
    pause
    exit /b 1
)

echo [OK] Scaffold generated and dependencies installed!
pause
