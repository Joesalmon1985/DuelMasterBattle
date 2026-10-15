# Install the APK on every Android phone attached over USB (USB debugging on, "allow this computer" accepted on the phone).
#   scripts\android\install_apk.ps1 [-Apk build\android\DuelMasterBattle-debug.apk]
param([string]$Apk = "")
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\android_env.ps1"

$repo = Get-RepoRoot
if (-not $Apk) {
    $candidates = @("build\android\DuelMasterBattle-debug.apk", "build\android\DuelMasterBattle-release.apk", "build\android\DuelMasterBattle-client.apk") | ForEach-Object { Join-Path $repo $_ } | Where-Object { Test-Path $_ }
    if ($candidates.Count -eq 0) { throw "no APK in $repo\build\android; run 'Build Android APK.bat' first" }
    $Apk = $candidates[0]
}
$adb = Join-Path $script:SdkRoot "platform-tools\adb.exe"
if (-not (Test-Path $adb)) { throw "adb not found at $adb (run 'Setup Android Build Tools.bat')" }
Write-Host "installing $Apk"
& $adb start-server | Out-Null
$devices = (& $adb devices -l) | Select-Object -Skip 1 | Where-Object { $_ -match "^\S+\s+device\b" } | ForEach-Object { ($_ -split "\s+")[0] }
if (-not $devices -or $devices.Count -eq 0) {
    Write-Host "No phone is attached in debugging mode." -ForegroundColor Yellow
    Write-Host "On the phone: Settings > About phone > tap 'Build number' 7 times; then Settings > System > Developer options > USB debugging ON;"
    Write-Host "plug the USB cable in, choose 'File transfer' if asked, and accept 'Allow USB debugging' from this computer. Then run this again."
    Write-Host "Alternatively copy the APK to the phone (USB, Nearby Share, email, cloud drive) and open it there."
    & $adb devices
    exit 1
}
$failed = 0
foreach ($serial in $devices) {
    $model = (& $adb -s $serial shell getprop ro.product.model).Trim()
    $abi = (& $adb -s $serial shell getprop ro.product.cpu.abi).Trim()
    Write-Host "-> $serial ($model, $abi)"
    if ($abi -ne "arm64-v8a") { Write-Host "   this phone is not arm64 ($abi); the APK will not install" -ForegroundColor Yellow }
    & $adb -s $serial install -r $Apk
    if ($LASTEXITCODE -ne 0) { $failed += 1 } else { Write-Host "   installed" -ForegroundColor Green }
}
if ($failed -gt 0) { exit 1 }
Write-Host "ANDROID_INSTALL_OK ($($devices.Count) phone(s))" -ForegroundColor Green
