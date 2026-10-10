# Start the local sim and the Overworld hybrid scene.
# -Mode Wizard (default) or God. Press G or click the HUD button to switch at any time.
param([ValidateSet("Wizard", "God")][string]$Mode = "Wizard")
$ErrorActionPreference = "Stop"
$Hybrid = Split-Path $PSScriptRoot -Parent
$Repo = Split-Path $Hybrid -Parent
if (-not $env:HYBRID_SIM_PORT) { $env:HYBRID_SIM_PORT = "8765" }
$env:HYBRID_START_MODE = $Mode.ToLower()
$godot = $env:GODOT
if (-not $godot) {
    $local = Join-Path $Repo ".dmb_windows_local.json"
    if (Test-Path $local) {
        $godot = (Get-Content $local -Raw | ConvertFrom-Json).godot
    }
}
if (-not $godot -or -not (Test-Path $godot)) {
    throw "Set GODOT to the Godot executable, or provide .dmb_windows_local.json."
}
$console = $godot -replace "Godot_v4.5.1-stable_win64.exe$", "Godot_v4.5.1-stable_win64_console.exe"
if (Test-Path $console) { $godot = $console }
$python = "py"
Start-Process -FilePath $python -ArgumentList @("-3", "-m", "wizard_rts.server") -WorkingDirectory $Hybrid -WindowStyle Hidden
Start-Sleep -Seconds 1
& $godot --path (Join-Path $Repo "godot_project") --rendering-method forward_plus "res://client/scenes/hybrid_world.tscn"
