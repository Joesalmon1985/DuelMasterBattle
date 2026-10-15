@echo off
rem Milestone M6: the 60-minute proving run (population 16, 2 seeds per generation, 14 workers, 8 hours). Writes nothing to neuro\models.
rem Afterwards judge it with: py -3 WizardRTSHybrid\scripts\judge_proof.py
setlocal
cd /d "%~dp0"
if "%DMB_RUNS%"=="" set "DMB_RUNS=%USERPROFILE%\dmb_runs"
echo Proving run: 60-minute games at catastrophe level C0. Runs are stored in %DMB_RUNS%\neuro\proving.
py -3 train_ai.py train --run proving --config proving60 --hours 8 --workers 14 --keep-awake --no-models
pause
