$ErrorActionPreference = "Stop"
$RepoRoot = (Get-Location).Path
Write-Host "Cleaning obsolete dialogue-factory packaging/runtime artifacts..."
Remove-Item "$RepoRoot\tools\dialogue_generation\dialogue_generation_factory.egg-info" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$RepoRoot\tools\dialogue_generation\SOURCES.txt" -Force -ErrorAction SilentlyContinue
Remove-Item "$RepoRoot\tools\dialogue_generation\dialogue_factory.db" -Force -ErrorAction SilentlyContinue
Remove-Item "$RepoRoot\tools\dialogue_generation\dialogue_factory.db-wal" -Force -ErrorAction SilentlyContinue
Remove-Item "$RepoRoot\tools\dialogue_generation\dialogue_factory.db-shm" -Force -ErrorAction SilentlyContinue
$env:PYTHONPATH = "$RepoRoot\tools"
if (-not (Test-Path "$RepoRoot\.venv\Scripts\python.exe")) {
    throw "Missing .venv. Create it first with: python -m venv .venv"
}
Write-Host "Running dialogue-factory tests..."
& "$RepoRoot\.venv\Scripts\python.exe" -m pytest "$RepoRoot\tools\dialogue_generation\tests" -q
if ($LASTEXITCODE -ne 0) { throw "Dialogue-factory tests failed." }
Write-Host "Patch applied and tests passed. Next: & '.\Run Dialogue Factory.bat' doctor"
