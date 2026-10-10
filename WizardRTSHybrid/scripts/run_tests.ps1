# Python hybrid tests plus the Godot coordinate check.
$ErrorActionPreference = "Stop"
$Hybrid = Split-Path $PSScriptRoot -Parent
$Repo = Split-Path $Hybrid -Parent
py -3 -m pytest (Join-Path $Hybrid "tests") -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$godot = $env:GODOT
if (-not $godot) {
    $local = Join-Path $Repo ".dmb_windows_local.json"
    if (Test-Path $local) { $godot = (Get-Content $local -Raw | ConvertFrom-Json).godot }
}
if ($godot -and (Test-Path $godot)) {
    $console = $godot -replace "Godot_v4.5.1-stable_win64.exe$", "Godot_v4.5.1-stable_win64_console.exe"
    if (Test-Path $console) { $godot = $console }
    & $godot --headless --path (Join-Path $Repo "godot_project") --script res://client/tests/run_hybrid_coords.gd
    exit $LASTEXITCODE
}
Write-Output "GODOT not set; Python tests finished and the Godot coordinate check was skipped."
