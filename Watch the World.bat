@echo off
rem God World (docs/GOD_WORLD_PRD.md): the god's view of the island. Opens the scene directly; it hosts the Python world on this PC itself.
rem The main menu's "Watch the World" does the same thing.
setlocal
cd /d "%~dp0"
set "GODOT=%USERPROFILE%\Downloads\Godot_v4.5.1-stable_win64.exe\Godot_v4.5.1-stable_win64.exe"
if not exist "%GODOT%" set "GODOT=%USERPROFILE%\Downloads\Godot_v4.4.1-stable_win64.exe\Godot_v4.4.1-stable_win64.exe"
if not exist "%GODOT%" (
  echo Godot 4 not found. Edit this file and set GODOT to your Godot executable.
  pause
  exit /b 1
)
"%GODOT%" --path "%~dp0godot_project" --rendering-method forward_plus res://client/scenes/god_world.tscn
