@echo off
rem Wizard RTS Hybrid: one world, Wizard Explore Mode (walk the terrain, settlements and battles; Ward Duel). Press G for God Mode.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "WizardRTSHybrid\scripts\launch_hybrid.ps1" -Mode Wizard
pause
