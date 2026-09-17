@echo off
setlocal EnableExtensions EnableDelayedExpansion
rem Windows double-click playtest menu for G01/G02 (BuildPackV03).
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
  echo Install Python 3.11+ from https://www.python.org/downloads/
  echo or create a virtualenv at "%ROOT%\.venv".
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
echo 1. Play G02 directly — default portrait 450x800
echo 2. Play G01 directly
echo 3. Open the main menu
echo 4. Run automated G01 checks
echo 5. Run automated G02 checks
echo 6. Run both gates
echo 0. Exit
echo.
set "CHOICE="
set /p "CHOICE=Select: "

if "%CHOICE%"=="1" goto play_g02
if "%CHOICE%"=="2" goto play_g01
if "%CHOICE%"=="3" goto play_menu
if "%CHOICE%"=="4" goto check_g01
if "%CHOICE%"=="5" goto check_g02
if "%CHOICE%"=="6" goto check_both
if "%CHOICE%"=="0" goto bye
echo Invalid choice.
pause
goto menu

:play_g02
echo.
"%PY%" "%HELPER%" play-g02
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" (
  echo.
  echo Launch failed with exit code !ERR!.
  pause
)
goto menu

:play_g01
echo.
"%PY%" "%HELPER%" play-g01
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" (
  echo.
  echo Launch failed with exit code !ERR!.
  pause
)
goto menu

:play_menu
echo.
"%PY%" "%HELPER%" play-menu
set "ERR=!ERRORLEVEL!"
if not "!ERR!"=="0" (
  echo.
  echo Launch failed with exit code !ERR!.
  pause
)
goto menu

:check_g01
echo.
"%PY%" "%HELPER%" check-g01
set "ERR=!ERRORLEVEL!"
echo.
echo Check finished with exit code !ERR!.
pause
goto menu

:check_g02
echo.
"%PY%" "%HELPER%" check-g02
set "ERR=!ERRORLEVEL!"
echo.
echo Check finished with exit code !ERR!.
pause
goto menu

:check_both
echo.
"%PY%" "%HELPER%" check-both
set "ERR=!ERRORLEVEL!"
echo.
echo Checks finished with exit code !ERR!.
pause
goto menu

:bye
exit /b 0
