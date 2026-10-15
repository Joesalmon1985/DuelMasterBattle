@echo off
rem DuelMasterBattle: install the last built APK (build\android) on every phone plugged in with USB debugging on.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "WizardRTSHybrid\scripts\android\install_apk.ps1"
echo.
pause
