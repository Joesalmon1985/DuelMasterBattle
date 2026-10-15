# Android export

**Start at [`../README_ANDROID_TWO_PHONES.md`](../README_ANDROID_TWO_PHONES.md)**: the owner-facing instructions for building the
app on Windows, installing it on two phones and playing a LAN game. The architecture and the known limits are in
[`MOBILE_LAN_MULTIPLAYER.md`](MOBILE_LAN_MULTIPLAYER.md). This file is the engineering summary of the export itself.

## Presets (`godot_project/export_presets.cfg`)

| Preset | Gradle | Output | Use |
| --- | --- | --- | --- |
| `Android` | yes (Chaquopy CPython + the `DmbPySim` plugin) | `build/android/DuelMasterBattle-debug.apk` | the game: a phone can host the world and join |
| `Android Client` | no (plain Godot export) | `build/android/DuelMasterBattle-client.apk` | joins only (a PC or another phone hosts); the fallback while the gradle build is unproven |

Both: `arm64-v8a` only (Chaquopy's CPython is 64-bit), min SDK 24, target SDK 35, package `com.duelmasterbattle.game`,
version `0.1.0` (must equal `wizard_rts/net/protocol.py` `GAME_VERSION`: the phones compare it in `hello`), **signed with the
debug keystore** (an unsigned APK does not install), permissions internet, network state, Wi-Fi state, vibrate. Project settings
already set for the export: `gl_compatibility` renderer, ETC2/ASTC import, portrait 720x1280 stretch, touch from mouse.

## Toolchain (Godot 4.5)

JDK 17, Android SDK command-line tools, platform-tools, build-tools 35.0.0, platform 35, NDK 28.1.13356709 (any installed NDK
is accepted by `setup_gradle_build.py`), the Godot 4.5.1 export templates (`android_source.zip` for the gradle build,
`android_debug.apk` for the plain export), a debug keystore, and the editor settings `export/android/java_sdk_path`,
`android_sdk_path`, `debug_keystore*` (the headless export reads them from `editor_settings-4.5.tres`, not from the environment).

Windows: `WizardRTSHybrid/scripts/android/setup_android_toolchain.ps1` installs all of it into the user profile
(`%LOCALAPPDATA%\DuelMasterBattle\android-tools`, `%LOCALAPPDATA%\Android\Sdk`, `%APPDATA%\Godot\...`); the SDK licence prompt is
left to the user. Linux: `scripts/android/build_apk.sh` expects them at the paths in its header.

## Build steps

1. `scripts/android/setup_gradle_build.py` (cross-platform): unpack the gradle template into `godot_project/android/build`
   (version in `android/.build_version`), apply the Chaquopy overlay to `settings.gradle` / `build.gradle`, swap the NDK pin
   for an installed one, drop in `PySimPlugin.kt` and register it in `GodotApp.java`, then stage the Python sources
   (`stage_python.py`: `wizard_rts`, `sim`, `godot_project/content/source`, isolated self-test). Chaquopy packages the same
   Python major.minor as the build Python, so the script defaults both to the interpreter running it (3.11 to 3.15).
   Idempotent; `tests/test_android_packaging.py` checks it on a synthetic template.
2. `godot --headless --path godot_project --export-debug "Android" build/android/DuelMasterBattle-debug.apk`
   (`scripts/android/build_apk.ps1` on Windows, `build_apk.sh` on Linux; both verify the APK's contents afterwards).
3. `scripts/android/install_apk.ps1`: `adb install -r` on every attached device.

Root launchers: `Setup Android Build Tools.bat`, `Build Android APK.bat [client|noinstall]`, `Install APK On Phones.bat`,
`Host LAN Game.bat` (the PC-hosted fallback; `--first-joiner-hosts` gives the first phone the START button).

## Status

**The pipeline produced the APK on the owner's PC on 15 October 2026** (`build/android/DuelMasterBattle-debug.apk`, 152 MB,
arm64-v8a, `apksigner verify` passes with the debug certificate, scheme v2; `inspect_apk.py`: 13,699 entries, CPython 3.14
runtime, `assets/chaquopy/app.imy` with the staged sources; Chaquopy 17.1.0 and the Kotlin plugin compiled first time). Two
pitfalls were found and are handled by `setup_gradle_build.py`: Godot's export runs gradle twice and its second call (copy
and rename) passes no `export_enabled_abis`, so the template defaulted to all four ABIs and Chaquopy refused `armeabi-v7a`;
the overlay now defaults the list to `arm64-v8a|x86_64`. And the gradle daemon Godot leaves behind (a 1 GB JVM) inherits the
export's output pipe, so a script waiting for Godot's output never sees EOF; the overlay sets `org.gradle.daemon=false`.
Godot's headless log holds only its own progress; gradle's output is in `%USERPROFILE%\.gradle\daemon\<version>\daemon-*.out.log`
when a daemon ran. **No phone has run the game yet.** Failures on a device go to `WizardRTSHybrid/docs/BLOCKERS.md`.
