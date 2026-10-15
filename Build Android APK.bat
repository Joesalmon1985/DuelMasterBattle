@echo off
rem DuelMasterBattle: build the Android APK (host-capable: the whole world runs on the phone) and install it on every phone
rem plugged in with USB debugging. Output: build\android\DuelMasterBattle-debug.apk. Needs "Setup Android Build Tools.bat" first.
rem   Build Android APK.bat            build and install
rem   Build Android APK.bat client     a plain client-only APK (joins a game hosted on this PC or another phone)
rem   Build Android APK.bat noinstall  build only
cd /d "%~dp0"
set "ARGS=-Install"
if /i "%~1"=="client" set "ARGS=-ClientOnly -Install"
if /i "%~1"=="noinstall" set "ARGS="
powershell -NoProfile -ExecutionPolicy Bypass -File "WizardRTSHybrid\scripts\android\build_apk.ps1" %ARGS%
echo.
pause
