# Blockers

## B1 — Widelands source build

- Subsystem: Widelands lab.
- Error: `cmake` and `cl` were not on PATH. `vswhere.exe` is not installed. No `gcc` or `clang` command was found.
- Reproduction: from `external/widelands`, the upstream command is `cmake -S . -B build`. Without a compiler, configure cannot generate a build.
- Expected: a compiled `widelands` binary and a production or logistics test.
- Observed: the clone is complete at `47c5cae8c6cb080e4bf86163a3873bd0847bc0e4`. The executable was not produced.
- Environment: Windows 10.0.26200, feature branch, no MSVC installation discovered.
- Cause: environment. This is not an engine incompatibility.
- Attempts: 1) confirmed the three compiler names are absent. 2) `winget install Kitware.CMake` so the configure command exists. A compiler install was not finished in this session. See `docs/original_runs/WIDELANDS.md`.
- Next: install Visual Studio Build Tools or MSYS2, then rerun the cmake command in that note. Do not retry a bare `cmake` until a compiler is on PATH.
- Resolving commit: none.

## B2 — OpenRA skirmish not played

- Subsystem: OpenRA launch.
- Error: none. The process reached `Loading mod: ra` with an OpenGL window and was then stopped.
- Expected: a played skirmish or a saved frame of the menu.
- Observed: source launch log in `docs/original_runs/OPENRA.md`. No screenshot of that window was taken.
- Cause: the process was stopped on purpose so it would not keep the display. This is not a compile failure.
- Next: launch again and save a frame before starting a match. Do not treat the missing screenshot as a failed build.

| 15 Oct 2026 | Android two-phone acceptance (`../docs/MOBILE_LAN_MULTIPLAYER.md` §10) | `adb devices` lists nothing; the Android emulator needs `/dev/kvm` and the user is not in the `kvm` group (`id` shows no kvm) | Not an error: no hardware. The host-capable APK is built by `scripts/android/build_apk.sh`; the staged Python passes an isolated self-test on the build machine | Attach a phone (USB debugging) and run §10; or add the user to `kvm` and install an arm64/x86_64 system image |
| 15 Oct 2026 | Android APK export (`scripts/android/build_apk.sh`) | The headless Godot export (gradle + Chaquopy) was stopped twice by the session harness for low system memory (~3 GB free; gradle JVM wants 4.5 GB) | Pipeline implemented and the staged Python self-tests; gradle never ran, so the Kotlin plugin and Chaquopy packaging are unverified | Rerun on a machine with ~8 GB free; the first run downloads Gradle, AGP, Chaquopy and the Android CPython runtime |
