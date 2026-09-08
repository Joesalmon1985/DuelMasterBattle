@echo off
setlocal
set "GODOT=%USERPROFILE%\Downloads\Godot_v4.5.1-stable_win64.exe\Godot_v4.5.1-stable_win64.exe"
if not exist "%GODOT%" set "GODOT=%USERPROFILE%\Downloads\Godot_v4.5.1-stable_win64.exe"
if not exist "%GODOT%" (
  echo Godot 4 not found. Edit this file and set GODOT to your Godot executable.
  pause
  exit /b 1
)
"%GODOT%" --path "%~dp0godot_project"
