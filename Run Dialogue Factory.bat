@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"
set "VENV_PYTHON=%PROJECT_ROOT%.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" (
  echo ERROR: Virtual environment not found at %VENV_PYTHON%
  echo Create it with: python -m venv .venv
  echo Then install the one runtime dependency with: .venv\Scripts\pip install openpyxl
  pause
  exit /b 1
)
set "PYTHONPATH=%PROJECT_ROOT%tools;%PYTHONPATH%"
"%VENV_PYTHON%" -m dialogue_generation %*
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
