@echo off
rem Wizard RTS Hybrid: one world, God Mode (RTS over six factions). Press G in game to switch to the wizard.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "WizardRTSHybrid\scripts\launch_hybrid.ps1" -Mode God
pause
