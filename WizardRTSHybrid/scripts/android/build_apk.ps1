# Build the Android APK on Windows with a headless Godot export, then optionally install it on every phone plugged in.
#   scripts\android\build_apk.ps1 [-Kind debug|release] [-ClientOnly] [-Install] [-SkipArtProbe]
# After the export it inspects the package (runtimes, packed Python, every catalogue image and data file the game reads, the version) and then proves, in an
# exported pack, that catalogue art loads at run time (verify_art_export.py, a few minutes; -SkipArtProbe leaves that out).
# Output: build\android\DuelMasterBattle-<kind>.apk (host-capable: Godot client + the CPython world via Chaquopy) or
#         build\android\DuelMasterBattle-client.apk  (-ClientOnly: plain Godot export, can only join a game hosted elsewhere)
# Needs the toolchain from setup_android_toolchain.ps1 ('Setup Android Build Tools.bat'); the first gradle run downloads
# Gradle, the Android Gradle plugin, Chaquopy and the Android CPython runtime (internet, ~10 minutes, ~1 GB).
param([ValidateSet("debug", "release")][string]$Kind = "debug", [switch]$ClientOnly, [switch]$Install, [switch]$SkipArtProbe)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\android_env.ps1"

$repo = Get-RepoRoot
$hyb = Join-Path $repo "WizardRTSHybrid"
$godot = Get-GodotExe
$python = Get-PythonExe
$missing = Test-AndroidToolchain
if ($ClientOnly) { $missing = $missing | Where-Object { $_ -notlike "an Android NDK*" } }
if ($missing.Count -gt 0) {
    Write-Host "The Android toolchain is incomplete. Run 'Setup Android Build Tools.bat' first. Missing:" -ForegroundColor Yellow
    $missing | ForEach-Object { Write-Host "  - $_" }
    exit 1
}
$jdk = Get-JdkHome
$env:JAVA_HOME = $jdk
$env:ANDROID_HOME = $script:SdkRoot
$env:ANDROID_SDK_ROOT = $script:SdkRoot
$env:PATH = (Join-Path $jdk "bin") + ";" + (Join-Path $script:SdkRoot "platform-tools") + ";" + $env:PATH
Set-GodotAndroidEditorSettings $jdk $script:SdkRoot

$outDir = Join-Path $repo "build\android"
New-Item -ItemType Directory -Force $outDir | Out-Null
if ($ClientOnly) {
    $preset = "Android Client"
    $out = Join-Path $outDir "DuelMasterBattle-client.apk"
} else {
    $preset = "Android"
    $out = Join-Path $outDir "DuelMasterBattle-$Kind.apk"
    Write-Host "preparing the gradle project (template, Chaquopy overlay, Python sources)"
    & $python (Join-Path $hyb "scripts\android\setup_gradle_build.py") --templates $script:TemplatesDir --sdk $script:SdkRoot --build-python $python
    if ($LASTEXITCODE -ne 0) { throw "setup_gradle_build.py failed" }
}
if (Test-Path $out) { Remove-Item $out -Force }
$log = Join-Path $outDir "export-$(if ($ClientOnly) { 'client' } else { $Kind }).log"
Write-Host "exporting '$preset' with $godot (log: $log)"
$exportFlag = if ($Kind -eq "release") { "--export-release" } else { "--export-debug" }
$esc = [regex]::Escape([string][char]27) + "\[[0-9;]*m"  # terminal colour codes in Godot's progress lines
$lines = & $godot --headless --path (Join-Path $repo "godot_project") $exportFlag $preset $out 2>&1 | ForEach-Object { ($_ | Out-String).TrimEnd() -replace $esc, "" }
[IO.File]::WriteAllLines($log, [string[]]$lines, (New-Object System.Text.UTF8Encoding $false))
$lines | Select-String -Pattern "error|Error|FAIL|BUILD |What went wrong|Chaquopy|chaquopy" | ForEach-Object { $_.Line }

if (-not (Test-Path $out)) {
    Write-Host "ANDROID_APK_FAILED (see $log)" -ForegroundColor Red
    Get-Content $log -Tail 40
    exit 1
}
$size = [math]::Round((Get-Item $out).Length / 1MB, 1)
Write-Host "APK: $out ($size MB)"
$inspectArgs = @((Join-Path $hyb "scripts/android/inspect_apk.py"), $out)
$gameVersion = ([regex]::Match((Get-Content (Join-Path $hyb "wizard_rts/net/protocol.py") -Raw), 'GAME_VERSION = "([^"]+)"')).Groups[1].Value
if ($gameVersion) { $inspectArgs += @("--expect-version", $gameVersion) }
if ($ClientOnly) { $inspectArgs += "--client-only" }
& $python @inspectArgs
if ($LASTEXITCODE -ne 0) { Write-Host "ANDROID_APK_FAILED: the APK does not contain what a phone needs (see above)" -ForegroundColor Red; exit 1 }
$apksigner = Join-Path $script:SdkRoot "build-tools/35.0.0/apksigner.bat"
& $apksigner verify --print-certs $out 2>&1 | Select-String -Pattern "Verifies|DOES NOT VERIFY|certificate DN|ERROR" | ForEach-Object { "signature: " + $_.Line }
if ($LASTEXITCODE -ne 0) { Write-Host "ANDROID_APK_FAILED: the APK is not signed (check the debug keystore in the editor settings)" -ForegroundColor Red; exit 1 }
if (-not $SkipArtProbe) {
    Write-Host "proving that catalogue art loads from an exported pack (a few minutes)"
    & $python (Join-Path $hyb "scripts/android/verify_art_export.py") --godot $godot
    if ($LASTEXITCODE -ne 0) { Write-Host "ANDROID_APK_FAILED: the exported game could not load the imported art" -ForegroundColor Red; exit 1 }
}
Write-Host "ANDROID_APK_OK $out" -ForegroundColor Green
if ($Install) {
    & "$PSScriptRoot\install_apk.ps1" -Apk $out
}
