@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not exist ".venv\Scripts\python.exe" if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"

set "PYTHONPATH=%CD%\tools"

echo ============================================================
echo DuelMasterBattle - Ensemble Relationship/Scene Builder
echo ============================================================
echo Python: %PYTHON_EXE%
echo Profiles: docs\characters\DMB_Character_Profiles_88_Disco_Elysium_Depth.csv
echo Output: generated\dialogue\ensemble
echo.

"%PYTHON_EXE%" -m dialogue_generation.ensemble_cli build-all --profiles "docs\characters\DMB_Character_Profiles_88_Disco_Elysium_Depth.csv" --output-dir "generated\dialogue\ensemble" --target-scenes 300 --seed 1337
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo SUCCESS: relationship graph and scene manifests generated and validated.
  echo Open: generated\dialogue\ensemble
) else (
  echo FAILED with exit code %RC%.
)
echo.
pause
exit /b %RC%
