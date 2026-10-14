@echo off
rem Independent check of the saved champion: 12 held-out games against the heuristic AI (takes a while at 240 game minutes).
setlocal
cd /d "%~dp0"
if "%DMB_RUNS%"=="" set "DMB_RUNS=%USERPROFILE%\dmb_runs"
py -3 train_ai.py evaluate --model best --games 12
pause
