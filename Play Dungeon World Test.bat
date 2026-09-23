@echo off
setlocal
set "GODOT=%USERPROFILE%\Downloads\Godot_v4.4.1-stable_win64.exe\Godot_v4.4.1-stable_win64.exe"
if not exist "%GODOT%" set "GODOT=%USERPROFILE%\Downloads\Godot_v4.4.1-stable_win64.exe"
if not exist "%GODOT%" (
  echo Godot 4 not found. Edit this file and set GODOT to your Godot executable.
  pause
  exit /b 1
)
set "DMB_FIXTURE=FX-DUNGEON-WORLD"
if "%DMB_SEED%"=="" set "DMB_SEED=507"
if "%DMB_RESOLUTION%"=="" set "DMB_RESOLUTION=450x800"
echo Dungeon World Spatial Test seed=%DMB_SEED% resolution=%DMB_RESOLUTION%
"%GODOT%" --path "%~dp0godot_project" --resolution %DMB_RESOLUTION% "res://client/scenes/dungeon_world_test.tscn"
pause
