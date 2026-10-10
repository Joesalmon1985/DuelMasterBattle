# Recreate the pinned full-history clones. Does not add them to DuelMasterBattle git.
$ErrorActionPreference = "Stop"
$Hybrid = Split-Path $PSScriptRoot -Parent
$External = Join-Path $Hybrid "external"
$Manifest = Get-Content (Join-Path $Hybrid "sources\manifest.json") -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $External | Out-Null
foreach ($source in $Manifest.sources) {
    $dest = Join-Path $External $source.id
    if (-not (Test-Path (Join-Path $dest ".git"))) {
        git clone --branch $source.branch $source.url $dest
    }
    git -C $dest fetch origin
    git -C $dest checkout $source.commit
    $head = (git -C $dest rev-parse HEAD).Trim()
    if ($head -ne $source.commit) {
        throw "pin mismatch for $($source.id): $head"
    }
    Write-Output "PIN_OK $($source.id) $head"
}
