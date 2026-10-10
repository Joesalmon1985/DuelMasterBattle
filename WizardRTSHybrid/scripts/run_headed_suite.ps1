# Run every headed Godot test of the hybrid, each against a fresh simulator.
# Usage: scripts\run_headed_suite.ps1 [-Only forestry,food]
# Needs GODOT (console exe) or .dmb_windows_local.json; py -3 on PATH.
param([string[]]$Only = @())
$ErrorActionPreference = "Continue"
$Hybrid = Split-Path $PSScriptRoot -Parent
$Repo = Split-Path $Hybrid -Parent
$godot = $env:GODOT
if (-not $godot) {
    $local = Join-Path $Repo ".dmb_windows_local.json"
    if (Test-Path $local) { $godot = (Get-Content $local -Raw | ConvertFrom-Json).godot }
}
$console = $godot -replace "Godot_v4.5.1-stable_win64.exe$", "Godot_v4.5.1-stable_win64_console.exe"
if (Test-Path $console) { $godot = $console }

# name, script, env overrides, expected marker
$tests = @(
    @("walk", "run_hybrid_walk.gd", @{}, "HYBRID_WALK_OK"),
    @("visual", "run_hybrid_visual.gd", @{}, "HYBRID_VISUAL_OK"),
    @("duel", "run_hybrid_duel.gd", @{}, "HYBRID_DUEL_OK"),
    @("forestry", "run_hybrid_forestry.gd", @{ HYBRID_SPEED = "4" }, "HYBRID_FORESTRY_OK"),
    @("food", "run_hybrid_food.gd", @{ HYBRID_SPEED = "10" }, "HYBRID_FOOD_OK"),
    @("god", "run_hybrid_god.gd", @{}, "HYBRID_GOD_OK"),
    @("war", "run_hybrid_war.gd", @{ HYBRID_SPEED = "20"; HYBRID_WAR_SECONDS = "240" }, "HYBRID_WAR_OK")
)
$port = 8900
$failed = @()
foreach ($t in $tests) {
    if ($Only.Count -gt 0 -and $Only -notcontains $t[0]) { continue }
    $port += 1
    $env:HYBRID_SIM_PORT = "$port"
    $sim = Start-Process -FilePath "py" -ArgumentList @("-3", "-m", "wizard_rts.server") -WorkingDirectory $Hybrid -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 2
    foreach ($k in $t[2].Keys) { Set-Item -Path "Env:$k" -Value $t[2][$k] }
    $out = & $godot --path (Join-Path $Repo "godot_project") --rendering-method forward_plus --script "res://client/tests/$($t[1])" 2>&1 | Out-String
    foreach ($k in $t[2].Keys) { Remove-Item -Path "Env:$k" -ErrorAction SilentlyContinue }
    Stop-Process -Id $sim.Id -Force -ErrorAction SilentlyContinue
    if ($out -match $t[3]) { Write-Output "PASS $($t[0])" } else { Write-Output "FAIL $($t[0])"; $failed += $t[0]; ($out -split "`n" | Select-String "FAIL|ERROR|SCRIPT" | Select-Object -First 5) | ForEach-Object { Write-Output "  $_" } }
}
if ($failed.Count -gt 0) { Write-Output "HEADED_SUITE_FAILED $($failed -join ',')"; exit 1 }
Write-Output "HEADED_SUITE_OK"
