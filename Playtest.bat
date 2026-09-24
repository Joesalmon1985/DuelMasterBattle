@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem Windows double-click playtest menu for G01–G05 / FX-MVP / visual review.
rem Always run from the repository root, even if launched from elsewhere.

cd /d "%~dp0"
if errorlevel 1 (
  echo ERROR: Could not change to repository directory:
  echo   %~dp0
  pause
  exit /b 1
)

set "ROOT=%CD%"
set "HELPER=%ROOT%\tools\windows_playtest.py"
if not exist "%HELPER%" (
  echo ERROR: Missing helper script:
  echo   %HELPER%
  pause
  exit /b 1
)

rem Prefer project virtualenv, then py launcher, then python on PATH.
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
  echo Install Python 3.11+ or create a virtualenv at "%ROOT%\.venv".
  pause
  exit /b 1
)

"%PY%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
  echo ERROR: "%PY%" is too old. Python 3.10+ is required.
  pause
  exit /b 1
)

:menu
cls
echo.
echo DuelMasterBattle — Windows playtest
echo Repo: %ROOT%
echo Python: %PY%
echo.
echo === Latest integrated world ===
echo L. Latest integrated world / FX-MVP (g05_shell) — RECOMMENDED
echo E. Near-era-transition / FX-ERA
echo.
echo === Production / combat / hazards ===
echo 3. Unit production / G03
echo 1. Local combat / G04 battle
echo 2. Hazard/manifestation combat / G04 hazard
echo.
echo === Story / earlier gates ===
echo 6. Main story/menu
echo 5. Play G01 directly
echo 4. Play G02 directly
echo.
echo === Visual review ===
echo V. In-world visual review harness
echo W. Ward Duel presentation review
echo.
echo === Checks ===
echo 7. Run G04 automated checks
echo 8. Run all implemented gates G01-G04
echo 0. Exit
echo.
set "CHOICE="
set /p "CHOICE=Select: "

if /I "%CHOICE%"=="L" goto play_latest
if /I "%CHOICE%"=="E" goto play_era
if "%CHOICE%"=="1" goto play_g04_battle
if "%CHOICE%"=="2" goto play_g04_hazard
if "%CHOICE%"=="3" goto play_g03
if "%CHOICE%"=="4" goto play_g02
if "%CHOICE%"=="5" goto play_g01
if "%CHOICE%"=="6" goto play_menu
if /I "%CHOICE%"=="V" goto play_visual
if /I "%CHOICE%"=="W" goto play_ward
if "%CHOICE%"=="7" goto check_g04
if "%CHOICE%"=="8" goto check_all
if "%CHOICE%"=="0" goto bye
echo Invalid choice.
pause
goto menu

:play_latest
echo.
"%PY%" "%HELPER%" play-latest
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" ( echo. & echo Launch failed with exit code !ERR!. & pause )
goto menu

:play_era
echo.
"%PY%" "%HELPER%" play-fx-era
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" ( echo. & echo Launch failed with exit code !ERR!. & pause )
goto menu

:play_g04_battle
echo.
"%PY%" "%HELPER%" play-g04-battle
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" ( echo. & echo Launch failed with exit code !ERR!. & pause )
goto menu

:play_g04_hazard
echo.
"%PY%" "%HELPER%" play-g04-hazard
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" ( echo. & echo Launch failed with exit code !ERR!. & pause )
goto menu

:play_g03
echo.
"%PY%" "%HELPER%" play-g03
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" ( echo. & echo Launch failed with exit code !ERR!. & pause )
goto menu

:play_g02
echo.
"%PY%" "%HELPER%" play-g02
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" ( echo. & echo Launch failed with exit code !ERR!. & pause )
goto menu

:play_g01
echo.
"%PY%" "%HELPER%" play-g01
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" ( echo. & echo Launch failed with exit code !ERR!. & pause )
goto menu

:play_menu
echo.
"%PY%" "%HELPER%" play-menu
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" ( echo. & echo Launch failed with exit code !ERR!. & pause )
goto menu

:play_visual
echo.
"%PY%" "%HELPER%" play-visual-review
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" ( echo. & echo Launch failed with exit code !ERR!. & pause )
goto menu

:play_ward
echo.
"%PY%" "%HELPER%" play-ward-duel-review
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" ( echo. & echo Launch failed with exit code !ERR!. & pause )
goto menu

:check_g04
echo.
"%PY%" "%HELPER%" check-g04
set "ERR=!ERRORLEVEL!"
echo.
echo Check finished with exit code !ERR!.
pause
goto menu

:check_all
echo.
"%PY%" "%HELPER%" check-all
set "ERR=!ERRORLEVEL!"
echo.
echo Checks finished with exit code !ERR!.
pause
goto menu

:bye
exit /b 0
