# Ledger: polish for watching (0.5.1, branch `feature/polish-watching-feel`)

Design and the per-event checklist: `docs/POLISH_WATCHING_FEEL.md`. Budget: the owner gave three and a half hours (22 Oct 2026, from 19:14).
Base: `feature/village-minigames` at `69165b95` (the 0.5.0 minigames). Merging into `main` is the owner's call.

Note on the working tree: when this branch was cut, the checkout carried uncommitted changes that are not this branch's (the rival's name in the
AI wizard, a name prompt in the main menu, test and data edits, `observations.json`). They were left as they were, uncommitted; this ledger's
commits add only the polish files. The APK built from this tree carries them.

## Milestones

- [x] P0 Branch, orientation (the art layer has no tweens or particles; the table and the cards are static; `Sfx` is procedural).
- [x] P1 The world's watching layer `client/hybrid/ambience.gd`: deliveries (dust, the ware icon, a clack), pickups, chimney smoke for working
  buildings, the construction arc, completions (ring, sparks, chime), felled trees (chips, chop), saplings, new units, the waiting crate; rationed
  sounds; wired into `hybrid_world.gd` (observe on every snapshot, step in `_process`, draw after the entities, view bounds from `_draw`).
- [x] P2 The table: `table_fx.gd` (tap rings, result banner, sparks), the panel's pop-in, the message flash, the staggered deal, tumbling dice,
  the shake and red message on a refused move; widgets pass themselves to `widget_act`.
- [x] P3 Menus and cards: `press_feel` on every themed button, `pop_in` on cards and main-menu overlays, `fade_in` for a card's next page, `swish`.
- [x] P4 Version 0.5.1 (Android code 6; protocol 4 unchanged, the messages did not change shape), docs, the headed test's two new checks.
- [x] P5 Headed evidence and the APK (`build/android/DuelMasterBattle-debug.apk`); the phone install is the owner's step (below).
- [x] P6 Red team / blue team rounds 1 to 4 (`docs/POLISH_RED_BLUE.md`).

## Session log (real clock)

- 22 Oct 2026 19:14 Start. Branch cut from `feature/village-minigames` at `69165b95`. Read `hybrid_world.gd`, `hybrid_art.gd`, `industry_view.gd`, the
  table and widgets, `visual_theme.gd`, `narrative_card.gd`, `sfx.gd`, the snapshot's entity rows (`working`, `constructing`, `cargo`, `carrying`,
  `stage`, `status_text`).
- 19:20 to 19:30 First wave: `ambience.gd`, `table_fx.gd`, the sounds, the theme helpers, the table and widget changes, the card and menu pops.
  Godot `--check-only` on every changed script: clean (the `LanSession` autoload errors are the checker's, as before). Headed
  `run_hybrid_minigames.gd` (rps, yahtzee, slide, whist, guesswho): `HYBRID_MINIGAMES_OK`, `MINIGAMES_AMBIENCE` delivered 2, picked 3, one sound.
  Python `test_minigames_village.py` + `test_lan_multiplayer.py`: 29 pass. Committed `0b141084`.
- 19:31 to 19:45 Second wave: the forest sways, the HUD's gains line, the day's light, the host's figure on the table, the banner on a band placed
  from the screen, material-specific delivery sounds, the HUD names a finished building, the main menu's living backdrop. Checker clean;
  `MENU_ROUTES_OK`.
- 21:22 A rerun of the headed minigames test failed to open the village: two Godot instances and their Python hosts from earlier runs were still
  holding port 8765 (the client reached a stale host). Killed by pid; rerun on a clean port, chained to the APK build.

- 21:25 The chained run passed and the 0.5.1 APK built (`ANDROID_APK_OK`, second wave).
- 21:30 onwards The owner asked for red team / blue team rounds over every screen (`docs/POLISH_RED_BLUE.md`): rounds 1 to 4 fixed the faces,
  grouped actions, scroll cues, key hints, the status block and top strip under modals, the Games page's Back, the host's figure for residents,
  the Settings rows and the LAN launcher's home. Each round verified by a headed run with screenshots. Found on the way: `run_menu_routes.gd`
  left its single-player host on port 8765, which made the next minigames run fail to open the village; the test now stops its host.

- 22:45 to 22:55 Red/blue round 5 verified (`HYBRID_MINIGAMES_OK`, `MENU_ROUTES_OK`), the result's band placed from the settled layout, the
  branch pushed to `origin/feature/polish-watching-feel` (eight commits after `69165b95`), the final APK built from `4ecc3282`.
  Not this branch's and left uncommitted in the checkout: another session's rival-name and name-prompt work (see the note at the top).

## Testing on the phone

1. Build (done by the session when the headed test passed): `Build Android APK.bat` at the repository root, or
   `powershell -NoProfile -ExecutionPolicy Bypass -File WizardRTSHybrid/scripts/android/build_apk.ps1`. The APK lands at
   `build/android/DuelMasterBattle-debug.apk` (0.5.1, Android version code 6).
2. Plug the phone in by USB with USB debugging on; accept the "allow USB debugging" prompt on the phone.
3. Install: `Install APK On Phones.bat` (or `WizardRTSHybrid/scripts/android/install_apk.ps1`). It upgrades the 0.5.0 build in place (same
   package, higher version code); saves are kept.
4. On the phone: Settings > "Developer: the village of games" for the village with every host; or Play Single Player for the real world.
   What to look for: smoke over working buildings, dust and a drifting ware icon when a carrier sets a load down, the quiet "+n log" line under the
   HUD title every few seconds, the gold arc over a site under construction and the ring, sparks and HUD line when it finishes, the forest swaying,
   the light shifting over eight minutes; at a table: the host's figure by their name, rings where you tap, tumbling dice, the banner and sparks at
   the end; every button dips when pressed; the main menu's motes.
