@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not exist ".venv\Scripts\python.exe" if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"
set "PYTHONPATH=%CD%\tools"

set /p SEED=Enter deterministic seed [1337]: 
if "%SEED%"=="" set "SEED=1337"
set /p COUNT=Enter target scene count [300]: 
if "%COUNT%"=="" set "COUNT=300"

"%PYTHON_EXE%" -m dialogue_generation.ensemble_cli build-all --profiles "docs\characters\DMB_Character_Profiles_88_Disco_Elysium_Depth.csv" --output-dir "generated\dialogue\ensemble" --target-scenes %COUNT% --seed %SEED%
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
