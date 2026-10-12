@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem Six-faction / one-settlement REVIEW preset — isolated slot, not Joe's normal saves.

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
echo  DuelMasterBattle — Six-by-One Review Preset
echo  factions=6  cores_per_faction=1  seed=507
echo  Save slot: g05_review_six_one  (isolated)
echo  Flag: DMB_PLAYTEST_REVIEW=1
echo ============================================================
echo.

set "DMB_FACTION_COUNT=6"
set "DMB_CORES_PER_FACTION=1"
set "DMB_SAVE_SLOT=g05_review_six_one"
set "DMB_PLAYTEST_REVIEW=1"
set "DMB_FIXTURE=FX-MVP"
set "DMB_SEED=507"

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
  echo ERROR: Python 3 was not found.
  pause
  exit /b 1
)

"%PY%" "%HELPER%" play-visual-playtest
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" (
  echo.
  echo Launch failed with exit code !ERR!.
  pause
)
exit /b !ERR!
