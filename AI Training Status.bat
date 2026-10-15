@echo off
rem Show how the current training run is doing.
setlocal
cd /d "%~dp0"
if "%DMB_RUNS%"=="" set "DMB_RUNS=%USERPROFILE%\dmb_runs"
py -3 train_ai.py status
pause
