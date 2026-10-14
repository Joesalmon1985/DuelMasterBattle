@echo off
rem Ask the trainer to stop: it finishes its current games, saves and writes the report. "Stop AI Training.bat now" abandons the games in flight.
setlocal
cd /d "%~dp0"
if "%DMB_RUNS%"=="" set "DMB_RUNS=%USERPROFILE%\dmb_runs"
if /i "%~1"=="now" (py -3 train_ai.py stop --now) else (py -3 train_ai.py stop)
echo The trainer will finish its current games and write the session report (WizardRTSHybrid\neuro\models\LAST_SESSION_REPORT.md).
pause
