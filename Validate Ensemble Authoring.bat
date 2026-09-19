@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not exist ".venv\Scripts\python.exe" if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"

set "PYTHONPATH=%CD%\tools"

echo ============================================================
echo DuelMasterBattle - Validate Existing Ensemble Output
echo ============================================================
"%PYTHON_EXE%" -m dialogue_generation.ensemble_cli validate-output --profiles "docs\characters\DMB_Character_Profiles_88_Disco_Elysium_Depth.csv" --output-dir "generated\dialogue\ensemble"
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo VALIDATION PASS.
) else (
  echo VALIDATION FAILED with exit code %RC%.
)
echo.
pause
exit /b %RC%
