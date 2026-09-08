@echo off
setlocal
set "GODOT=%USERPROFILE%\Downloads\Godot_v4.5.1-stable_win64.exe\Godot_v4.5.1-stable_win64_console.exe"
if not exist "%GODOT%" (
  echo Godot 4 console binary not found. Edit this file and set GODOT.
  pause
  exit /b 1
)
cd /d "%~dp0"
"%GODOT%" --headless --path godot_project --script res://sim/tools/check_scripts.gd
"%GODOT%" --headless --path godot_project --script res://sim/tools/run_tests.gd
"%GODOT%" --headless --path godot_project --script res://client/tests/run_ui_smoke.gd
"%GODOT%" --path godot_project --resolution 720x1280 --script res://client/tools/realtime_playtest.gd
pause
