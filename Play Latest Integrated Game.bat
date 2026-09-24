@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem Double-click launcher for the latest integrated strategic-world build.
rem FX-MVP seed 507 via g05_shell — NOT the older main-menu story alone.

cd /d "%~dp0"
if errorlevel 1 (
  echo ERROR: Could not change to repository directory:
  echo   %~dp0
  pause
  exit /b 1
)

set "ROOT=%CD%"
set "HELPER=%ROOT%\tools\windows_playtest.py"

echo.
echo ============================================================
echo  DuelMasterBattle — Latest Integrated Strategic-World Build
echo  Scene: g05_shell.tscn
echo  Fixture: FX-MVP  Seed: 507  Resolution: 450x800
echo ============================================================
echo.

set "PY="
if exist "%ROOT%\.venv\Scripts\python.exe" set "PY=%ROOT%\.venv\Scripts\python.exe"
if not defined PY if exist "%ROOT%\venv\Scripts\python.exe" set "PY=%ROOT%\venv\Scripts\python.exe"
if not defined PY (
  where py >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%I"
  )
)
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%I in ('where python') do (
      set "PY=%%I"
      goto :py_found
    )
  )
)
:py_found
if not defined PY (
  echo ERROR: Python 3 was not found. Prefer .venv\Scripts\python.exe
  pause
  exit /b 1
)

if not exist "%HELPER%" (
  echo ERROR: Missing %HELPER%
  pause
  exit /b 1
)

"%PY%" "%HELPER%" play-latest
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" (
  echo.
  echo Launch failed with exit code !ERR!.
  pause
)
exit /b !ERR!
