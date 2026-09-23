@echo off
REM Dungeon World Playtest launcher (Windows)
setlocal
cd /d "%~dp0.."
if not defined GODOT (
  if exist "%USERPROFILE%\Downloads\Godot_v4.4.1-stable_win64_console.exe" set "GODOT=%USERPROFILE%\Downloads\Godot_v4.4.1-stable_win64_console.exe"
)
if not defined GODOT (
  echo Set GODOT to your Godot 4 console executable path.
  exit /b 1
)
if not defined DMB_SEED set DMB_SEED=507
if not defined DMB_RESOLUTION set DMB_RESOLUTION=450x800
set DMB_FIXTURE=FX-DUNGEON-WORLD
echo Dungeon World Playtest seed=%DMB_SEED% resolution=%DMB_RESOLUTION%
"%GODOT%" --path "%cd%\godot_project" --resolution %DMB_RESOLUTION% res://client/scenes/dungeon_world_test.tscn %*
endlocal
