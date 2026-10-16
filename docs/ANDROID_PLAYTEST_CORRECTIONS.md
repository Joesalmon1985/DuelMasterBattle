# Android playtest corrections (0.2.0, 16 October 2026)

The first two-phone playtest of 0.1.0 (15 October) worked as a LAN game: the phones connected, entered one world and played together. It also showed four
faults. This document is what was found, what was changed, how it is tested and what is still unverified. Branch `fix/android-playtest-corrections`.
No unrelated work was started: the content roster is frozen (D33), the neuroevolution programme and its networks were not touched, and the LAN
transport, discovery, reconnection and the host-authoritative design were kept.

## 1. The imported art did not show on the phones

**Root cause.** `hybrid_art.gd` registered every catalogue image with `Image.load("res://client/hybrid/art/...png")`, and `art.gd` (portraits, backdrops, the
duel board's spell icons and wizard layers) used `FileAccess.file_exists` and `Image.load` on `ProjectSettings.globalize_path("res://assets/...")`. A Godot
export does not ship source PNGs: it ships the *imported* textures (`.godot/imported/*.ctex`) and a `<name>.png.import` remap next to each name. The
editor on the PC reads the files from disk, so it worked there; in the APK every one of those calls returned "not found", `missing` filled up and the game
drew nothing, or its placeholder rectangles.

**What was checked and was fine (not the cause).** All 6,313 PNGs are tracked in Git (none excluded by `.gitignore`; `*.import` is ignored because the editor
regenerates it at export). The existing 0.1.0 APK held 6,316 `.ctex` textures, 6,316 `.import` remaps and `client/hybrid/art/catalogue.json`, so every image was
in the package; only one raw PNG was (the launcher icon). The catalogue's 4,976 referenced files all exist in the repository (`missing_required` is empty).
`export_filter="all_resources"` already exports them. So the art was packaged, and the code asked for it the one way that cannot work in an export.

**Fix.**

* `client/scripts/asset_loader.gd`: `exists()` and `load_texture()` try the imported resource first (`ResourceLoader`, the only thing an export has) and fall back
  to the source file only for a development run that has not imported yet. The result is the engine's own `CompressedTexture2D`.
* `hybrid_art.gd` registers the 5,000 catalogue paths with an existence check (so `missing` still reports a genuinely absent image at load time) and decodes
  each texture on first use. Before, it decoded every image at start-up; 7,000 textures at once is a lot to ask of a phone. State frames and layered sprites go
  through the same path.
* `art.gd` (duel art, portraits, the main menu backdrop) uses the same loader and `res://` paths.
* The Wizard World launch no longer lets the old adventure autoload write its save (see 2).

**Asset audit, as a gate.** `WizardRTSHybrid/scripts/android/asset_audit.py` enumerates what the client will ask for (the catalogue exactly as `hybrid_art.gd`
registers it: sheets, 32-facing sequences with their hull and turret layers, state frames, overlay frames; plus every literal `res://` image, data file and
scene in the client scripts) and fails when a file is missing from the repository or, for an APK, is not in the package in a loadable form (a `.png.import` remap
and the texture it names; a data file as a file; a scene as a remap). `inspect_apk.py` now runs it, checks that every file the Python stager listed is in the packed
sources, and checks the manifest version. `tests/test_android_assets.py` covers all of that with synthetic packages (a package with only source PNGs fails), and
guards the code: no client script may call `Image.load_from_file`, `Image.load` or `FileAccess` on a `res://` image path outside `asset_loader.gd`.

**Proof the exported game loads catalogue art.** `scripts/android/verify_art_export.py` exports the project to a `.pck` (the resource packing an Android export
does), then runs `client/tests/run_art_export_probe.gd` from that pack in an empty working directory, where `res://` can only resolve to what the package holds. It
loaded all 2,565 catalogue items (2,512 sheets, 53 sequences), an animated sheet, 61 building state frames and the duel art, and printed
`ART_PROBE_CONTROL source_png_readable=false imported_texture_loads=true` (the control: the old call fails there, the new one works) and `ART_PROBE_OK`.
`build_apk.ps1` runs this after every build. Headed desktop screenshots with the new loader are in `WizardRTSHybrid/docs/evidence/android_fix/`.

**Honest limit.** Whether the art draws correctly on a physical phone's GPU has not been seen: no phone was attached. What is established is that the package
contains every image, that the loading path an export needs is the one the code now uses, and that an exported pack loads the whole catalogue.
Naval ship and naval yard art, the Mindustry blocks and the story people are deliberate labelled placeholders that never had imported art; nothing was
imported or substituted.

## 2. One game: Wizard World

* `client/scripts/main_menu.gd` is now the whole player-facing menu: **Play Single Player**, **Host Multiplayer**, **Join Multiplayer**, **Settings**. No New
  Game, Resume, Quick Duel or G01 entry. It never reads the old adventure's save, so old save data cannot redirect it (`run_menu_routes.gd` writes a stale legacy
  save and checks the menu is unchanged).
* The old menu moved, intact, to `dev_menu.tscn` / `dev_menu.gd` for developer launchers and the existing tests (`DMB_DEV_MENU=1` or `-- --dmb-dev`;
  `dev_mode.gd` can never enable it on a phone). The old adventure, Quick Duel, G01 and test scenes were kept, not deleted.
* **Single player is the same implementation as multiplayer**: a *private* session of the one hosted Wizard World (the host on this device, bound to 127.0.0.1, one
  human seat), on a phone through the packed Python and on a PC through a local Python process. `Play Single Player` offers **Continue campaign** when a
  Wizard World save exists on the device.
* **The hosted world is now the real Wizard World.** The 0.1.0 host (`net/host.py:new_world`) built a bare simulation: no narrative layer, no mentor, no apprenticeship,
  and the narrative ops were not forwardable. So the phones had the civilisation but not the story. `new_world` now enables the narrative layer and casts the mentor, as
  `server.new_world` does for the classic server, and the session forwards the narrative ops (`scene_next`, `duel_resolve`, `journal`, ...). A cycle reset carries the
  wizard over, as the classic server does.
* Save, continue and New game for a private session: `save` and `new_game` ops (host only, one-human sessions only), `--continue` / `continue` start options,
  autosave every five minutes, a save when the app is paused, "Save and leave" in the pause menu. Saves live in `user://dmb_runs` (the menu looks in the same
  folder); a damaged save falls back to its `.prev` twin.
* Launching Wizard World no longer lets the old `Adventure` autoload write its save (`test_mode`), and `hybrid_world` uses `refresh_snapshot()` instead of the
  classic-only `snapshot` op where a scene or a duel ended.

## 3. The campaign for one human, two humans, and the AI wizard

**Principle.** One world and one story. Anything a person has to do to progress is something any one present person can do; a person who is away, slow or
dead never holds the others back; where a second wizard is wanted (a Ward duel partner) an AI wizard can be one.

**The party** (`narrative/party.py`). Every wizard has a *seat*: the host's private story state stays where it always lived (`world.narrative["wizard"]`,
`["conversations"]`, `["checks"]`, `["graph"]`, Aspect actor `player`), every other wizard has its own copy, and `as_player` points those containers at whoever is
acting, the way the session already pointed `world.player` and `world.story` at them. No narrative module had to learn about seats; with one seat nothing is
different (202 narrative, wizard, campaign, story and quest tests pass unchanged). Private to a seat: spells and weave, lessons, duels, worldview, journal, facts,
conversations in progress, dialogue flags, Aspect scores and relationships, the scene being read, fate. Shared: the settlement, its people, the mentor's body and
the stranger, the quest cast, the campaign stage, the clock.

**Rules** (`narrative/campaign.py`; each is a test in `tests/test_wizard_party.py`, driven through the real session):

* *Training* ends when every **present** human has finished the lessons or `party.training_grace_ms` (two minutes of game time) after the first did; whoever is
  not done is **caught up** (the colours and the weave are granted, the lessons stay open). An absent human is not waited for at all. A late joiner is caught up and
  their journal says what happened before they came.
* *Scenes* (the stranger's arrival, the confrontation, the victory) are lived by every present wizard, each at their own pace and with their own answers; effects that
  belong to the world (the mentor's death, the stranger's retreat) happen once.
* *The lethal duel.* Each wizard faces the stranger in a duel of their own, verified by Python as before; the world does not freeze for the others (alone, it still
  does). A wizard cannot report, checkpoint or resolve another's duel. **The first verified victory repels him for everybody**; every other open duel against him is
  released without penalty and the others are shown the retreat. **Death is personal**: a wizard who loses is out of the story (their `fate`), the others go on;
  only when no human wizard is left is the campaign over.
* *Aftermath* and the final objective count anyone's conversations and reach every journal.
* A wizard who comes back after being away is told in their journal what they missed, and a stranger still at the settlement is faced in a scene of their own.

**The AI wizard** (`net/ai_wizard.py`, `data/ai_wizards.json`). A single-player session has one: Mira, a fellow apprentice. She is not a script that completes things: she has a
seat, a wizard record, an avatar in `world.players`, and everything she does goes through `MultiplayerSession.dispatch`, the entry point a connection uses. She walks one
validated tile at a time to keep near the player, treats an outbreak she is standing in with the real `treat` action, answers a challenge according to her
relationship with that player (`accept_if_relationship_at_least`; it falls when she is beaten and rises when she wins, and is saved with the world), and in a duel she
locks a hidden Ward and casts one guess at a time in real time with the retained candidate-filter solver (`duel.ward.WeaveBot`, the bot that plays the stranger and the
mentor), thinking 5 to 11 seconds between casts against the same host rules, allowance and ignorance of the rival's Ward as a human. She speaks in her own voice as a
notice the client shows as a message. She never takes a human's seat (the seat count is humans only), exists only in a single-player session, and has no
reach into the narrative: another character is another JSON entry. The existing content has exactly one place that needs a second wizard (a Ward duel
partner), and that is the role she fills; the essential beats of the campaign need only one human (tested with and without her).

Not done, deliberately: AI protagonists in the lethal duel (the story's central duel stays the human's), a journal or spellbook redesign, any new story or content.

## 4. Real-time, independent PvP casting

`net/pvp.py` no longer has rounds (`cast_in_round` and `already_cast_this_round` are gone). Each player has their own history, `cast_seq` and `max_casts`; a legal cast is scored
at once and the caster may cast again immediately. The first legal cast that breaks the rival's Ward ends the duel on the host and its caster wins; later casts are refused
(`finished`). A repeated `cast_seq` returns the original feedback without a new guess, a skipped one is `bad_cast_seq`, a cast past the allowance is `no_casts_left`.
If neither Ward breaks, the duel ends when both allowances are spent and `compute_result` decides, as the board does. The 60-second auto-cast is now per player (from
the start of the duel or their last cast) and uses one of their own casts. Forfeit and the 20-second disconnect grace are unchanged. The host is the only authority; the view
exposes `your_casts`, `rival_casts`, `your_casts_left`, and `your_cast_pending` now simply means "free to cast".
`net_duel_sim.gd` no longer shows "Waiting for the rival's cast" (the only block is "No casts left"), refreshes from the host when a cast is refused as `finished`, and the
rival's progress bar shows how much of its allowance it has used. `tests/test_pvp_realtime.py` (unit) and `test_lan_multiplayer.py` (real sockets, two threads sending winning casts at once) cover:
three casts by A while B makes none with both histories correct, either player winning independently, the first winner ending it, per-player allowances, duplicate and bad
sequence numbers, hidden Wards, per-player timeouts and forfeit.

## 5. Version and compatibility

`GAME_VERSION` 0.2.0, `PROTOCOL_VERSION` 2 (`net/protocol.py` and `client/net/lan_session.gd`); export presets `version/name="0.2.0"`, `version/code=2` for both Android presets.
Package `com.duelmasterbattle.game` and the debug signing key are unchanged, so the new APK updates the 0.1.0 install on both phones (Android needs a higher version code; it has one).
A 0.1.0 phone cannot join a 0.2.0 host (the protocol changed shape: PvP casts, narrative ops); update both.

## 6. Tests

Results of the run that produced the commit (Windows 11, Python 3.14, Godot 4.5.1):

* `python -m pytest WizardRTSHybrid/tests`: 1,395 passed, 20 skipped, 1 failed in 32 minutes; the one failure, `test_neuro_controller` (a mean tick time of 15.06 ms against a 15.0 ms
  budget), was measured while the APK build and Godot tests shared the CPU, and passes alone (3 passed). `test_lan_multiplayer.py` (run separately, with `test_lan_story_shared`,
  `test_pvp_realtime`, `test_wizard_party`, `test_ai_wizard`, `test_android_assets`, `test_android_packaging`): 72 passed. The neuroevolution tests and the hash and determinism gates are untouched and green.
* Repository-root `tests/`: 591 passed, 9 failed; the identical 9 fail on `main` before this branch (legacy `sim/dmb` formation and tracking tests), so they are not caused by it.
* Godot: `sim/tools/run_tests.gd` 32 passed; `run_ui_smoke`, `run_adventure_flow` and `run_village_test_mode` pass against the moved developer menu; `run_menu_routes`, `run_single_player_flow`
  (menu, private session, apprenticeship running, one AI companion, save, Continue), `run_single_player_duel` (a real board duel against Mira: 10 casts to her 3, no "waiting"), `run_lan_parse`,
  headed `run_lan_two_clients` (real client against a Python host and a scripted second human, including a PvP duel on the board) and `run_hybrid_visual` all pass; screenshots were inspected
  (`WizardRTSHybrid/docs/evidence/android_fix/`). Known and pre-existing: `check_scripts.gd` reports five scripts that use autoloads (it fails the same on `main`).
* The APK: `Build Android APK.bat noinstall` ran green: 145 MB, arm64, signed with the same debug certificate as 0.1.0 (SHA-256 6055f324...e168), `aapt`: `com.duelmasterbattle.game`
  versionCode 2, versionName 0.2.0, the asset audit and the packed-Python check pass, and the exported-pack art probe prints `ART_PROBE_OK`.

New: `tests/test_pvp_realtime.py`, `tests/test_wizard_party.py`, `tests/test_ai_wizard.py`, `tests/test_android_assets.py`, `tests/_party.py` (a table of real sessions with
a clock the test advances); Godot: `client/tests/run_menu_routes.gd`, `run_single_player_flow.gd`, `run_single_player_duel.gd`, `run_art_export_probe.gd`; `run_lan_parse.gd` and `run_lan_two_clients.gd` updated.

## 7. What is verified and what is not

Automated and on this PC: everything above. **Not verified: any physical phone.** No device was attached (`adb devices` empty), so nothing about the 0.2.0 APK has run on
Android hardware: neither the art on a phone GPU, nor the packed Python hosting a narrative world with the AI companion at phone speed, nor Wi-Fi play between two phones. The build
checks (package contents, version, signature, exported-pack art probe) are not a substitute; the manual two-phone checklist (`docs/MOBILE_LAN_MULTIPLAYER.md` section 10) still applies, with these additions:
single player starts on the arrival text and Mira is beside you; **Duel Mira** works; two humans can both talk to the mentor; the PvP board never says "waiting".
Known limits: the narrative world is heavier than the 0.1.0 bare simulation on a phone (measure it); a story duel in a two-human game does not pause the world; the AI companion is single-player only.
