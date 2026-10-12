# Copy the hybrid runtime into a fresh directory. external/ is not included.
$ErrorActionPreference = "Stop"
$Hybrid = Split-Path $PSScriptRoot -Parent
$Dest = Join-Path $Hybrid "dist\package"
if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item -Recurse (Join-Path $Hybrid "wizard_rts") (Join-Path $Dest "wizard_rts")
Copy-Item -Recurse (Join-Path $Hybrid "tests") (Join-Path $Dest "tests")
Copy-Item (Join-Path $Hybrid "docs\LICENSES.md") (Join-Path $Dest "LICENSES.md")
@'
# Run from this directory after the DuelMasterBattle repo root is on PYTHONPATH.
# Example: $env:PYTHONPATH = "<repo>;<this package>"; py -3 -m wizard_rts.server
'@ | Set-Content (Join-Path $Dest "README.txt")
Write-Output "PACKAGED $Dest"
