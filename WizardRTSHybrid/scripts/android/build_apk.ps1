# Build the Android APK on Windows with a headless Godot export, then optionally install it on every phone plugged in.
#   scripts\android\build_apk.ps1 [-Kind debug|release] [-ClientOnly] [-Install]
# Output: build\android\DuelMasterBattle-<kind>.apk (host-capable: Godot client + the CPython world via Chaquopy) or
#         build\android\DuelMasterBattle-client.apk  (-ClientOnly: plain Godot export, can only join a game hosted elsewhere)
# Needs the toolchain from setup_android_toolchain.ps1 ('Setup Android Build Tools.bat'); the first gradle run downloads
# Gradle, the Android Gradle plugin, Chaquopy and the Android CPython runtime (internet, ~10 minutes, ~1 GB).
param([ValidateSet("debug", "release")][string]$Kind = "debug", [switch]$ClientOnly, [switch]$Install)
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
& $godot --headless --path (Join-Path $repo "godot_project") $exportFlag $preset $out 2>&1 | Tee-Object -FilePath $log | Select-String -Pattern "error|Error|FAIL|BUILD |warning: unused|Chaquopy|chaquopy" | ForEach-Object { $_.Line }

if (-not (Test-Path $out)) {
    Write-Host "ANDROID_APK_FAILED (see $log)" -ForegroundColor Red
    Get-Content $log -Tail 40
    exit 1
}
$size = [math]::Round((Get-Item $out).Length / 1MB, 1)
Write-Host "APK: $out ($size MB)"
& $python - $out @"
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = z.namelist()
py = [n for n in names if n.startswith("assets/chaquopy/")]
libs = [n for n in names if n.startswith("lib/")]
print("APK entries:", len(names), "chaquopy assets:", len(py), "native libs:", len(libs))
print("python runtime:", [n for n in libs if "python" in n][:4])
print("godot:", [n for n in libs if "godot" in n][:2])
print("signed:", any(n.startswith("META-INF/") and n.endswith((".RSA", ".EC", ".SF")) for n in names))
"@
Write-Host "ANDROID_APK_OK $out" -ForegroundColor Green
if ($Install) {
    & "$PSScriptRoot\install_apk.ps1" -Apk $out
}
