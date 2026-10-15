# One-time setup of everything the Android APK build needs on this Windows PC. Safe to rerun: each step is skipped when
# its result is already present. Run it from 'Setup Android Build Tools.bat' at the repository root (or directly).
#
# What it installs and where (about 3 GB of downloads, all from the projects' own release servers):
#   JDK 17 (Eclipse Temurin)           %LOCALAPPDATA%\DuelMasterBattle\android-tools\jdk\jdk-17...
#   Android SDK command-line tools      %LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest
#   Android SDK packages                platform-tools, build-tools 35.0.0, platform 35, NDK 28.1.13356709 (Godot 4.5's list)
#   Godot 4.5.1 export templates        %APPDATA%\Godot\export_templates\4.5.1.stable  (android_source.zip, android_debug.apk, ...)
#   Debug keystore                      %APPDATA%\Godot\keystores\debug.keystore
#   Godot editor settings               export/android/java_sdk_path, android_sdk_path, debug_keystore* in editor_settings-4.5.tres
#
# The Android SDK licence must be accepted by you: the script runs "sdkmanager --licenses" and waits for your answers.
# Close the Godot editor before running this (it rewrites the editor settings file when it exits).
param([switch]$SkipTemplates)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\android_env.ps1"

$JdkUrl = "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.20.1%2B1/OpenJDK17U-jdk_x64_windows_hotspot_17.0.20.1_1.zip"
$JdkSha256 = "e53a79c3c3d86865bd7e787903884331068e71321714ffd44f145785affc7cb0"
$CmdlineToolsUrl = "https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip"
$TemplatesUrl = "https://github.com/godotengine/godot/releases/download/4.5.1-stable/Godot_v4.5.1-stable_export_templates.tpz"
$SdkPackages = @("platform-tools", "build-tools;35.0.0", "platforms;android-35", "ndk;28.1.13356709", "cmdline-tools;latest")

$downloads = Join-Path $script:ToolsRoot "downloads"
New-Item -ItemType Directory -Force $downloads | Out-Null

function Get-File([string]$Url, [string]$Dest, [string]$Sha256 = "") {
    if (Test-Path $Dest) {
        Write-Host "already downloaded: $Dest"
    } else {
        Write-Host "downloading $Url"
        & curl.exe -L --fail --retry 3 -C - -o "$Dest.part" $Url
        if ($LASTEXITCODE -ne 0) { throw "download failed: $Url" }
        Move-Item "$Dest.part" $Dest -Force
    }
    if ($Sha256) {
        $actual = (Get-FileHash $Dest -Algorithm SHA256).Hash.ToLower()
        if ($actual -ne $Sha256.ToLower()) { Remove-Item $Dest; throw "checksum mismatch for $Dest ($actual); deleted, run again" }
    }
}

function Expand-Zip([string]$Zip, [string]$Dest) {
    New-Item -ItemType Directory -Force $Dest | Out-Null
    $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($tar) {
        & tar.exe -xf $Zip -C $Dest
        if ($LASTEXITCODE -ne 0) { throw "could not extract $Zip" }
    } else {
        Expand-Archive -Path $Zip -DestinationPath $Dest -Force
    }
}

# ---- 1. JDK 17
$jdk = Get-JdkHome
if (-not $jdk) {
    $zip = Join-Path $downloads (Split-Path $JdkUrl -Leaf)
    Get-File $JdkUrl $zip $JdkSha256
    Expand-Zip $zip (Join-Path $script:ToolsRoot "jdk")
    $jdk = Get-JdkHome
    if (-not $jdk) { throw "the JDK did not unpack into $script:ToolsRoot\jdk" }
}
Write-Host "JDK 17: $jdk"
$env:JAVA_HOME = $jdk
$env:PATH = (Join-Path $jdk "bin") + ";" + $env:PATH

# ---- 2. Android SDK command-line tools
$sdk = $script:SdkRoot
$sdkmanager = Join-Path $sdk "cmdline-tools\latest\bin\sdkmanager.bat"
if (-not (Test-Path $sdkmanager)) {
    $zip = Join-Path $downloads (Split-Path $CmdlineToolsUrl -Leaf)
    Get-File $CmdlineToolsUrl $zip
    $tmp = Join-Path $downloads "cmdline-tools-unpacked"
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Zip $zip $tmp
    New-Item -ItemType Directory -Force (Join-Path $sdk "cmdline-tools") | Out-Null
    Move-Item (Join-Path $tmp "cmdline-tools") (Join-Path $sdk "cmdline-tools\latest")
    Remove-Item $tmp -Recurse -Force
}
Write-Host "Android SDK: $sdk"
$env:ANDROID_HOME = $sdk
$env:ANDROID_SDK_ROOT = $sdk

# ---- 3. SDK licences (yours to accept) and packages
$missingPkgs = @()
if (-not (Test-Path (Join-Path $sdk "platform-tools\adb.exe"))) { $missingPkgs += "platform-tools" }
if (-not (Test-Path (Join-Path $sdk "build-tools\35.0.0"))) { $missingPkgs += "build-tools;35.0.0" }
if (-not (Test-Path (Join-Path $sdk "platforms\android-35"))) { $missingPkgs += "platforms;android-35" }
if (-not (Test-Path (Join-Path $sdk "ndk\28.1.13356709"))) { $missingPkgs += "ndk;28.1.13356709" }
if ($missingPkgs.Count -gt 0) {
    Write-Host ""
    Write-Host "The Android SDK licence has to be accepted by you. Answer the prompts below (y)." -ForegroundColor Yellow
    & $sdkmanager --sdk_root="$sdk" --licenses
    Write-Host "installing: $($SdkPackages -join ', ') (the NDK alone is about 700 MB)"
    & $sdkmanager --sdk_root="$sdk" $SdkPackages
    if ($LASTEXITCODE -ne 0) { throw "sdkmanager failed (licence not accepted, or no internet?)" }
}
Write-Host "SDK packages: present"

# ---- 4. Godot export templates
if (-not $SkipTemplates -and -not (Test-Path (Join-Path $script:TemplatesDir "android_source.zip"))) {
    $tpz = Join-Path $downloads (Split-Path $TemplatesUrl -Leaf)
    Get-File $TemplatesUrl $tpz
    $tmp = Join-Path $downloads "templates-unpacked"
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    $asZip = "$tpz.zip"
    if (-not (Test-Path $asZip)) { Copy-Item $tpz $asZip }
    Write-Host "unpacking the export templates (1.3 GB, a minute or two)"
    Expand-Zip $asZip $tmp
    New-Item -ItemType Directory -Force $script:TemplatesDir | Out-Null
    Get-ChildItem (Join-Path $tmp "templates") | Move-Item -Destination $script:TemplatesDir -Force
    Remove-Item $tmp -Recurse -Force
    Remove-Item $asZip -Force
}
if (Test-Path (Join-Path $script:TemplatesDir "android_source.zip")) { Write-Host "Godot export templates: $script:TemplatesDir" }

# ---- 5. keystore and editor settings
New-DebugKeystore $jdk
Set-GodotAndroidEditorSettings $jdk $sdk

$missing = Test-AndroidToolchain
if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Still missing:" -ForegroundColor Yellow
    $missing | ForEach-Object { Write-Host "  - $_" }
    exit 1
}
Write-Host ""
Write-Host "ANDROID_TOOLCHAIN_OK  (next: 'Build Android APK.bat')" -ForegroundColor Green
