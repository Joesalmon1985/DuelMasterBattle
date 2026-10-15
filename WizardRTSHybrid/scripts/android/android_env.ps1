# Shared by the Android build scripts on Windows: where the tools live, and the Godot editor settings the export needs.
# Dot-source it:  . "$PSScriptRoot\android_env.ps1"
#
# Locations (override with the environment variables named):
#   Godot editor      GODOT         or .dmb_windows_local.json at the repository root ("godot")
#   JDK 17            JAVA_HOME     or %LOCALAPPDATA%\DuelMasterBattle\android-tools\jdk\jdk-17*
#   Android SDK       ANDROID_HOME  or %LOCALAPPDATA%\Android\Sdk
#   Godot templates   GODOT_TEMPLATES or %APPDATA%\Godot\export_templates\<version>
#   Debug keystore    %APPDATA%\Godot\keystores\debug.keystore (password android, alias androiddebugkey)

$script:GodotVersion = "4.5.1.stable"
$script:ToolsRoot = Join-Path $env:LOCALAPPDATA "DuelMasterBattle\android-tools"
$script:SdkRoot = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA "Android\Sdk" }
$script:TemplatesDir = if ($env:GODOT_TEMPLATES) { $env:GODOT_TEMPLATES } else { Join-Path $env:APPDATA "Godot\export_templates\$script:GodotVersion" }
$script:KeystorePath = Join-Path $env:APPDATA "Godot\keystores\debug.keystore"
$script:EditorSettings = Join-Path $env:APPDATA "Godot\editor_settings-4.5.tres"

function Get-RepoRoot {
    # scripts/android -> scripts -> WizardRTSHybrid -> repository
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}

function Get-GodotExe {
    $godot = $env:GODOT
    if (-not $godot) {
        $local = Join-Path (Get-RepoRoot) ".dmb_windows_local.json"
        if (Test-Path $local) { $godot = (Get-Content $local -Raw | ConvertFrom-Json).godot }
    }
    if (-not $godot -or -not (Test-Path $godot)) {
        throw "Godot $script:GodotVersion was not found. Set GODOT to the editor executable (Godot_v4.5.1-stable_win64.exe) or run 'Play Hybrid Wizard Mode.bat' once so .dmb_windows_local.json records it."
    }
    $console = $godot -replace "_win64\.exe$", "_win64_console.exe"
    if (Test-Path $console) { return $console }
    return $godot
}

function Get-JdkHome {
    if ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME "bin\java.exe"))) { return $env:JAVA_HOME }
    $jdkDir = Join-Path $script:ToolsRoot "jdk"
    if (Test-Path $jdkDir) {
        $found = Get-ChildItem $jdkDir -Directory | Where-Object { Test-Path (Join-Path $_.FullName "bin\java.exe") } | Sort-Object Name -Descending | Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    return $null
}

function Get-PythonExe {
    # py -3 is what every launcher in this repository uses; Chaquopy packages the same major.minor into the APK.
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $exe = & py -3 -c "import sys; print(sys.executable)" 2>$null
        if ($exe -and (Test-Path $exe)) { return $exe.Trim() }
    }
    $p = Get-Command python -ErrorAction SilentlyContinue
    if ($p) { return $p.Source }
    throw "Python 3 was not found (py -3)."
}

function Set-GodotAndroidEditorSettings([string]$JdkHome, [string]$SdkRoot) {
    # The headless export reads these from the editor settings file, not from the environment. Godot must not be open
    # while this runs (it rewrites the file on exit).
    $jdk = $JdkHome -replace "\\", "/"
    $sdk = $SdkRoot -replace "\\", "/"
    $ks = $script:KeystorePath -replace "\\", "/"
    $wanted = [ordered]@{
        "export/android/java_sdk_path" = "`"$jdk`""
        "export/android/android_sdk_path" = "`"$sdk`""
        "export/android/debug_keystore" = "`"$ks`""
        "export/android/debug_keystore_user" = "`"androiddebugkey`""
        "export/android/debug_keystore_pass" = "`"android`""
    }
    if (-not (Test-Path $script:EditorSettings)) {
        $text = "[gd_resource type=`"EditorSettings`" format=3]`r`n`r`n[resource]`r`n"
    } else {
        $text = Get-Content $script:EditorSettings -Raw
    }
    foreach ($key in $wanted.Keys) {
        $line = "$key = $($wanted[$key])"
        $pattern = "(?m)^" + [regex]::Escape($key) + " = .*$"
        if ($text -match $pattern) {
            $text = [regex]::Replace($text, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $line }, 1)
        } else {
            $text = $text -replace "(?m)^\[resource\]\r?\n", "[resource]`r`n$line`r`n"
        }
    }
    [IO.File]::WriteAllText($script:EditorSettings, $text, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "Godot editor settings: Java SDK $JdkHome, Android SDK $SdkRoot, keystore $script:KeystorePath"
}

function New-DebugKeystore([string]$JdkHome) {
    if (Test-Path $script:KeystorePath) { return }
    New-Item -ItemType Directory -Force (Split-Path $script:KeystorePath) | Out-Null
    $keytool = Join-Path $JdkHome "bin\keytool.exe"
    & $keytool -genkeypair -v -keystore $script:KeystorePath -storepass android -alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US" | Out-Null
    if (-not (Test-Path $script:KeystorePath)) { throw "keytool did not create $script:KeystorePath" }
    Write-Host "Created the debug keystore $script:KeystorePath"
}

function Test-AndroidToolchain {
    # Returns a list of what is missing (empty when everything the APK build needs is present).
    $missing = @()
    if (-not (Get-JdkHome)) { $missing += "JDK 17 (JAVA_HOME or $script:ToolsRoot\jdk)" }
    if (-not (Test-Path (Join-Path $script:SdkRoot "platform-tools\adb.exe"))) { $missing += "Android SDK platform-tools in $script:SdkRoot" }
    if (-not (Test-Path (Join-Path $script:SdkRoot "build-tools\35.0.0\apksigner.bat"))) { $missing += "Android SDK build-tools 35.0.0 in $script:SdkRoot" }
    if (-not (Test-Path (Join-Path $script:SdkRoot "platforms\android-35"))) { $missing += "Android SDK platform 35 in $script:SdkRoot" }
    if (-not (Test-Path (Join-Path $script:SdkRoot "ndk"))) { $missing += "an Android NDK in $script:SdkRoot\ndk" }
    if (-not (Test-Path (Join-Path $script:TemplatesDir "android_source.zip"))) { $missing += "Godot $script:GodotVersion export templates in $script:TemplatesDir" }
    if (-not (Test-Path $script:KeystorePath)) { $missing += "debug keystore $script:KeystorePath" }
    return $missing
}
