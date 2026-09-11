@echo off
REM ========================================================================
REM Duel Master Battle — Village Dialogue Generation Factory
REM ========================================================================
REM Windows launcher for the offline dialogue generation factory.
REM Uses the local .venv Python and the installed dialogue-generation-factory package.
REM ========================================================================

setlocal

REM Get the directory this batch file lives in
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%"
set "VENV_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"

REM Check if virtual environment exists
if not exist "%VENV_PYTHON%" (
    echo ERROR: Virtual environment not found at %VENV_PYTHON%
    echo Run the setup steps first:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -e tools\dialogue_generation
    pause
    exit /b 1
)

REM Run the dialogue factory CLI
"%VENV_PYTHON%" -m dialogue_generation %*

endlocal