@echo off
rem DuelMasterBattle: evolve the faction AIs. Usage: double-click (8 hours), or "Train AI.bat 3" for 3 hours.
rem It resumes the current run when the code is unchanged, otherwise starts a new run from the saved champion.
setlocal
cd /d "%~dp0"
if "%DMB_RUNS%"=="" set "DMB_RUNS=%USERPROFILE%\dmb_runs"
set "HOURS=%~1"
if "%HOURS%"=="" set "HOURS=8"
echo Runs are stored in %DMB_RUNS%\neuro. Training for %HOURS% hours (stop early: run "Stop AI Training.bat").
py -3 train_ai.py train --run auto --hours %HOURS% --config full240 --workers 14 --keep-awake
echo.
if exist "WizardRTSHybrid\neuro\models\LAST_SESSION_REPORT.md" (
  echo ===== Last session report =====
  type "WizardRTSHybrid\neuro\models\LAST_SESSION_REPORT.md"
)
pause
