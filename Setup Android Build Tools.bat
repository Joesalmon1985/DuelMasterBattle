@echo off
rem DuelMasterBattle: one-time install of the Android build tools (JDK 17, Android SDK, Godot 4.5.1 export templates, debug
rem keystore, Godot editor settings). About 3 GB of downloads; you will be asked to accept the Android SDK licence.
rem Close the Godot editor first. Safe to run again; finished steps are skipped. See README_ANDROID_TWO_PHONES.md.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "WizardRTSHybrid\scripts\android\setup_android_toolchain.ps1"
echo.
pause
