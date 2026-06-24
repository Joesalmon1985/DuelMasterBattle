# Android Export

## Status
**Not built in this run.** Android export templates for Godot 4.4.1 were not installed on the build machine. Web export was built and verified locally.

## Prerequisites (when attempting)
1. Install Godot 4.4.1 Android export templates:
   - Editor → **Editor** → **Manage Export Templates** → Download 4.4.1
   - Or copy to `~/.local/share/godot/export_templates/4.4.1.stable/`
2. Install Android SDK + JDK (Godot docs: [Exporting for Android](https://docs.godotengine.org/en/4.4/tutorials/export/exporting_for_android.html))
3. Configure debug keystore in editor export preset.

## Steps (outline)
1. Open `godot_project` in Godot 4.4.1 editor.
2. **Project → Export** → Add **Android** preset.
3. Set package name, permissions, orientation (portrait + landscape).
4. Export APK or AAB to `build/android/` (gitignored).

## Mobile UI checklist
- [ ] Peg slots large enough to tap (min 48dp).
- [ ] Colour picker scrollable on narrow screens.
- [ ] Status text readable without horizontal scroll.
- [ ] Lock / Submit buttons reachable in portrait.
- [ ] Result panel fits on screen.
- [ ] New game restarts cleanly.

## Current project readiness
- UI uses Control nodes with minimum sizes on pegs (48×48).
- Further responsive layout pass recommended before store release.
