# Mobile LAN multiplayer (branch `feature/mobile-lan-multiplayer`)

Base commit: `143797baf862076399832f8acf758a6ef476e689` (`main`, merge of PR #15), the merge-base of every active unmerged branch
(`feature/wizard-settlement-stories`, `feature/neuroevolution-plan`, `feature/wizard-mode-implementation`), so this work can be
rebased onto or merged with any of them. Nothing on those branches was touched.

Goal (owner brief, 15 October 2026): two people, each holding a phone on the same Wi-Fi, enter the same living DuelMasterBattle
world, walk around together and fight a real human-versus-human Ward duel, with no computer, server, account or internet.

Status in one line: **the Python-authoritative LAN game is implemented and tested end to end on desktop (automated two-client
harness, headed Godot acceptance with screenshots); the host-capable Android APK packaging is implemented (Chaquopy CPython inside
the Godot app) but no APK was produced in this run (the headless export was stopped for memory pressure on the build laptop before
gradle ran); physical two-phone verification is BLOCKED (no device or emulator on this machine).** Section 11 has the details.

## 1. Architecture audit (M1) and risks

Verified against the code on 15 October 2026 (not against the docs):

| Area | What the code does today | Consequence for multiplayer |
| --- | --- | --- |
| `wizard_rts/server.py` | One blocking TCP connection on `127.0.0.1`, newline JSON, `listen(1)`. The **Godot client drives the clock** (`advance` every 200 ms with `sequence`). | A host must own the clock loop and serve several connections; clients must never call `advance`. |
| `HybridWorld.player` | One dict `{tx,ty,facing}`; `set_pose` reassigned it. `magic.fire`, `story.*`, `regions.begin_treatment`, `interact`, `history.cycle_reset`, `server pose` read it implicitly. | Needs a per-player record and an "acting player" binding so the existing code keeps working unchanged. |
| `story.state(world)` | One dict: world-level `npcs/dungeons/quests/known/log` plus player-level `inventory/in_dungeon/duel`. Only `in_dungeon` and `duel` are ever reassigned; the containers are mutated in place. | Per-player story records can share the world-level containers by reference. |
| Hazard Ward duel | `world.interact` leases a `DmbBattleSim` to Godot; Godot plays the duel **locally** and reports `success` to `world.resolve`. | Unusable as-is for PvP (a client would report its own win). PvP needs host-owned rules: `wizard_rts/duel/ward.py` (`score_attack`, `compute_result`, parity-tested against the GDScript) owns the state. |
| Clock pause | `pause_tokens` on `dmb.clock`; a hazard or story duel pauses `game_ms` globally. | A PvP duel pauses globally too (consistent with the existing rule; §6). |
| Snapshot | Delta snapshot (trees as deltas) is ~107 KB on `standard`, 6 ms to build; `entities` is ~90 % of it. Tree deltas track one client (`world._tree_sent`). | Per-client area-of-interest filtering and per-client tree-delta state are required for phones. |
| God Mode / training ops | `GOD_OPS` rejected unless profile is `developer`/`test_*`; `spawn`/`damage` behind `HYBRID_ALLOW_SPAWN`. | The multiplayer host rejects every faction-level op and every clock op from any connection, whatever the profile. |
| Determinism | `tests/test_determinism.py` (two processes, two hash seeds). No wall-clock decisions inside the world. | The host loop converts wall time into `advance(ms)` calls; admission (rate limits, timeouts) is outside the world; the world only sees an ordered command list. |
| Godot client | `hybrid_world.gd` extends `overworld.gd`: local tile movement, `_arrived` sends `pose`; touch D-pad and action button exist (`touch_pad.gd`); `game_board.gd` drives any object with the `DmbBattleSim` surface. | Reuse: a network-backed sim object with the same surface drives the existing board; remote players use `spawn_actor`/`move_actor`. |
| Android | `export_presets.cfg` had a non-gradle Android preset. Godot 4.5.1 at `~/godot451`; 4.5.1 Android templates installed this run; SDK 35, JDK 17, NDK 25.2. No device or emulator (user not in the `kvm` group). | Gradle build with Chaquopy is the hosting path (§2). Device acceptance is BLOCKED until a phone is attached. |
| Unmerged branches | `feature/wizard-mode-implementation` rewrites much of `hybrid_world.gd` (+445 lines) and `server.py` (`new_game`, save/load, `_swap`); the story and neuroevolution branches touch `world.py` (+48/-14) and `history.py`. | Multiplayer lives in new modules (`wizard_rts/net/`, `client/net/`); `world.py`/`server.py`/`hybrid_world.gd` edits are small and additive. See §12. |

Measured on this laptop (pure Python, AI on, `standard` map): world build 4.4 s, 49 ms of CPU per game-second (3.5 ms per 100 ms
quantum, occasional single quanta of 0.7–0.9 s), delta snapshot 107 KB. A phone is roughly 2–3x slower per core, so the host
spends well under one core on the simulation at 1x speed.

## 2. Implemented architecture

```text
   PHONE A (host)                                    PHONE B (client)
   ┌──────────────────────────────────────────┐      ┌──────────────────────────────┐
   │ Godot client (hybrid_world.gd, LAN mode) │      │ Godot client (LAN mode)      │
   │   state polls / move / pvp_* ───┐        │      │   state polls / move / pvp_* │
   │                                 ▼        │      │              │               │
   │ CPython (Chaquopy) in the same app       │◄─────┼──────────────┘ TCP 8765      │
   │   wizard_rts.net.host  HostServer        │  UDP 8767 discovery probes/replies  │
   │     one HybridWorld, one clock loop      │      └──────────────────────────────┘
   │     MultiplayerSession (players, PvP)    │
   └──────────────────────────────────────────┘
```

- **One authoritative simulation.** `HostServer` (`WizardRTSHybrid/wizard_rts/net/host.py`) owns one `HybridWorld` and the only
  clock: every 100 ms of wall time it calls `world.advance(elapsed_ms)` (capped at 500 ms so a stalled host never fast-forwards);
  `ClockService` turns that into 100 ms quanta and honours pause tokens. The AI, economy, logistics, military, eras, quests and
  outbreaks run exactly once per quantum, however many clients are connected (`test_world_advances_once_not_once_per_client`).
- **Players.** `MultiplayerSession` (`net/session.py`) keeps a `Link` per human: a secret reconnect token, the live connection,
  move/cast sequence numbers, per-connection tree-delta bookkeeping, notices and the player's own story record. The world side is
  `world.players[pid] = {id, name, colour, tx, ty, facing}`; the host's own wizard **is** the single-player `world.player` dict, so
  single-player code is unchanged. Every command is bound to the authenticated connection; a client never names the player it acts
  for. `session.acting(link)` points `world.player`/`world.story` at that player's records for the duration of one command, so fire
  magic, story dialogue, dungeons, treatment and the snapshot all see the right wizard without changes to those modules.
- **Godot presents, as before.** `hybrid_world.gd` in LAN mode: hello, asynchronous `state` polls every 200 ms, one validated `move`
  per tile with snap-back on refusal, remote wizards as actors glided between polls, the status line, toasts, the challenge
  button, the invite panel, the network Ward board, reconnect with the token.
- **Single player is untouched.** `LanSession.mode == "single"` keeps the classic `server.py` path (`advance`/`pose`/`snapshot`).
  `test_single_player_world_unchanged_by_the_multiplayer_hooks`, the clean-environment, determinism and retained-duel tests pass.

### Python on the phone: decision

Chosen: **Chaquopy** (Gradle plugin; CPython 3.12 for `arm64-v8a` packaged into the APK; open source, MIT since v15) applied to
Godot's own Android gradle build (Godot 4.5.1 template: AGP 8.6.1, Gradle 8.11.1, minSdk 24, JDK 17; Chaquopy 17.1 supports AGP
7.3–9.4, Python 3.11–3.15, minSdk 24). A small Kotlin Godot plugin (`DmbPySim`, `scripts/android/overlay/PySimPlugin.kt`) is
registered by the host activity (`GodotApp.getHostPlugins`, the Godot 4.2+ GodotHost API, so no manifest editing: Godot regenerates
the manifest on every gradle export) and exposes `start(json)`, `stop()`, `status()`, `logTail(n)`, `selfTest()`,
`pythonVersion()` to GDScript (`Engine.get_singleton("DmbPySim")`). The Python side is `wizard_rts/net/android_entry.py`: it runs
the same `HostServer` in a Python thread inside the app process. `LanSession.start_local_host()` uses the plugin when present and a
`python3` process on desktop.

What was investigated and how it is handled:

| Concern | Finding | Handling |
| --- | --- | --- |
| Third-party Python dependencies | The world imports only the standard library. `numpy` is used only by `wizard_rts/learn` and `wizard_rts/envs` (training) and by `ai_plus` *only* when a neural drafter is attached. | `learn`/`envs` are not staged. `pip` is not used. |
| Native extension | `wizard_rts/native/astar.c` is compiled with the host's C compiler on first use and has a byte-identical pure-Python twin (`tests/test_native_astar.py`). | `android_entry` sets `DMB_NO_NATIVE=1`; the Python kernel runs. |
| Asset paths | `wizard_rts/data/*` is read relative to `__file__`; `sim/dmb` reads authored people, dialogue, buildings, units and technology JSON from `godot_project/content/source` located relative to its own file (`parents[3] / "godot_project"`). | `scripts/android/stage_python.py` stages `wizard_rts`, `sim` and `godot_project/content/source` side by side (340 files, 6.7 MB). Chaquopy extracts data files to the filesystem at runtime, so `__file__`-relative reads work. The staged tree is proven standalone by an isolated self-test (`python3 -I`, no repository on the path, no numpy, no compiler: builds and advances the real world). |
| File writes | The world writes nothing at runtime (`write_baseline_content` and `persistence` are tools; the native cache is disabled). | Nothing to relocate; `HOME` is the app's files dir if anything ever needs it. |
| Threading | The host loop is single-threaded (`selectors`); the Python thread is started from Kotlin; Godot talks to it over loopback TCP like any client. | No shared state between Godot and Python except sockets. |
| Android lifecycle | The Python thread keeps running while the activity is paused; the OS may kill the process in the background. | First version: the host phone should stay in the game. A killed host ends the session for both (documented, §11). |
| Performance | See §1 measurements; the host phone also renders the world (the client's `_draw` over thousands of static rows is the known G11 cost: ~7 fps on this laptop, 1 fps while the headed test samples). | Area-of-interest polls keep the host's work per client at ~5 ms; rendering cost is the pre-existing gap, not a multiplayer one. |
| Licensing | Chaquopy MIT; CPython PSF; Godot MIT. | No new copyleft code in the app. |
| Desktop intermediate | A laptop host with two clients works today (the harness and the headed acceptance run that way). | Kept as the development path; not the objective. |

## 3. Supported platforms and limitations

| Role | Linux/Windows desktop | Android (arm64) | iOS |
| --- | --- | --- | --- |
| Host (runs the world) | yes: `python3` process started by the menu (`LanSession.start_local_host`) or `python3 -m wizard_rts.net.host` | **built, not device-verified**: Chaquopy APK (§5) | not built; the protocol is platform-neutral, a future client needs only the Godot export |
| Client (joins) | yes | yes (same APK) | same |
| Discovery | UDP broadcast probe to the limited and subnet broadcast addresses, unicast reply | same (no multicast lock needed) | same |

Limits: Wi-Fi networks with client isolation (guest networks, some campus networks) block phone-to-phone traffic; use a phone hotspot.
32-bit phones are not supported (Python 3.12 on Chaquopy is 64-bit only). Two players by default (`--max-players`, up to four).

## 4. How hosting and joining work

Main menu (0.2.0): **Play Single Player**, **Host Multiplayer**, **Join Multiplayer**, **Settings** (`client/scripts/main_menu.gd`); the old adventure,
Quick Duel and the G01 testing entry are developer tools in `dev_menu.tscn`. Single player is the same Wizard World in a private session (one human
seat and the AI companion, bound to 127.0.0.1); see `docs/ANDROID_PLAYTEST_CORRECTIONS.md`.

Host: name, game name, a four-digit join code (random, editable), map size → **START HOSTING** builds the world on this device
(a few seconds; the screen says so), connects this device's client to it with the host secret, and shows the **lobby** (players,
the Wi-Fi address and code to tell the friend, **START THE WORLD**). Join: name, code, the list of games found on this Wi-Fi
(refreshed every second), or the host's address and port typed by hand → **JOIN** → lobby, waiting for the host. When the host
starts, both screens enter the world; a later joiner spawns straight in. Errors are explained in plain words
(`LanSession.describe_error`: wrong code, version mismatch, full, no host answering, timeout with the client-isolation hint).

Spawning: the host's wizard is where the single-player wizard starts (beside the Red settlement). Every other wizard spawns on the
nearest free land tile at least two steps away (breadth-first over the host's walkability rules: in map, not blocked, no standing
tree or rock, no other wizard). Avatars: the host is John; others are the red mage, hedge mage, blue mage or assassin sprites with a
coloured name label.

Security: a join needs the code (or a reconnect token); the host's own client authenticates with a secret only that device knows;
every other message before `hello` is refused; no faction, clock, spawn, damage, inspector or fixture op is reachable through the
host for any connection (`protocol.PLAYER_OPS`; `test_server_side_permission_checks`).

## 5. Build and install

Desktop development (Ubuntu, repo layout):

```
python3 -m pytest WizardRTSHybrid/tests/test_lan_multiplayer.py WizardRTSHybrid/tests/test_lan_story_shared.py -q   # harness
WizardRTSHybrid/scripts/run_lan_headed.sh parse        # scripts parse, net sim mirror, menu screenshots
WizardRTSHybrid/scripts/run_lan_headed.sh two_clients  # Python host + scripted second human + real Godot client
python3 -m wizard_rts.net.host --name "Joe's world" --code 1234 --map small      # a host by hand (from WizardRTSHybrid/)
GODOT=~/godot451/Godot_v4.5.1-stable_linux.x86_64; $GODOT --path godot_project   # the client (Host/Join from the menu)
```

Android (host-capable debug APK; first run downloads Gradle, AGP, Chaquopy and the Android CPython runtime):

```
WizardRTSHybrid/scripts/android/setup_gradle_build.sh   # installs Godot's gradle template into godot_project/android/build,
                                                        # applies the Chaquopy + DmbPySim overlay, stages the Python sources,
                                                        # runs the isolated self-test of the staged tree
WizardRTSHybrid/scripts/android/build_apk.sh debug      # headless Godot export -> build/android/DuelMasterBattle-debug.apk
adb install -r build/android/DuelMasterBattle-debug.apk
```

Requirements: Godot 4.5.1 editor and its Android export templates (`~/.local/share/godot/export_templates/4.5.1.stable/`), Android
SDK 35 with build-tools 35 and an NDK (the overlay points the template at the installed NDK), JDK 17 (`JAVA_HOME`), `python3.12` on
the build machine (Chaquopy's `buildPython` must match the app's Python minor version), internet for the first gradle run. The
editor settings used are `export/android/*` in `~/.config/godot/editor_settings-4.5.tres` (SDK, JDK, debug keystore).
`godot_project/android/build` is generated and gitignored; the committed parts are the scripts and the overlay. Two project
settings were needed for a headless Android export and are now in `project.godot`: `rendering/textures/vram_compression/import_etc2_astc=true`
(without it Godot 4.5 refuses the preset with an *empty* "configuration errors" message) and `application/config/icon`
(the launcher icon). Godot 4.5 keeps the template's version id in `android/.build_version` (the parent of the build directory),
which the setup script writes.

Windows (15 October 2026, owner's PC): the owner-facing path is `README_ANDROID_TWO_PHONES.md` at the repository root. The
toolchain is installed once by `WizardRTSHybrid/scripts/android/setup_android_toolchain.ps1` (`Setup Android Build Tools.bat`:
JDK 17, SDK command-line tools, platform-tools, build-tools 35, platform 35, NDK 28.1, the 4.5.1 export templates, the debug
keystore and the `export/android/*` editor settings in `%APPDATA%\Godot\editor_settings-4.5.tres`; the SDK licence prompt is left to
the user). `build_apk.ps1` (`Build Android APK.bat`) runs the cross-platform `setup_gradle_build.py` (the former bash overlay
logic, now shared by `setup_gradle_build.sh`) and the headless export, then `install_apk.ps1` installs on every attached phone.
Chaquopy packages the same Python major.minor as the build Python, so the scripts use `py -3` (3.14 here) for both; the
`python3.12` requirement above is Ubuntu's. The `Android` preset is now **signed** (it exported an unsigned, uninstallable APK
before) and a second preset `Android Client` (no gradle, no Python) is the fallback for phones joining a PC host
(`Host LAN Game.bat`, which starts the host with `--first-joiner-hosts` so the first phone gets the START button when the PC
has no wizard of its own). Verified here: the harness (17 + 2 tests), the Godot parse check, the staging self-test and
`tests/test_android_packaging.py`, and then **the APK itself** (`build/android/DuelMasterBattle-debug.apk`, 152 MB, signed, arm64, CPython
3.14 inside; `docs/ANDROID_EXPORT.md` has the numbers and the two gradle pitfalls fixed on the way). **No phone has run it.**

One APK serves both roles: the Python runtime is started only when hosting (or for single player on a phone, as a private session
bound to `127.0.0.1`). The export preset enables the gradle build, `INTERNET`, `ACCESS_WIFI_STATE` and `ACCESS_NETWORK_STATE`,
minSdk 24, targetSdk 35, arm64-v8a, version 0.1.0.

## 6. The protocol

Newline-delimited JSON over TCP, one request → one reply, in order on one stream; UDP for discovery. Platform-neutral (no Godot
types). `PROTOCOL_VERSION = 2`, `GAME_VERSION = "0.2.0"` (0.1.0 and PROTOCOL 1 were the first phone build) (`wizard_rts/net/protocol.py`; the same constants in
`client/net/lan_session.gd`). A client sends both in `hello`; a different protocol is refused outright, a different major.minor
game version is refused (`version_mismatch`).

| Op | Who | What |
| --- | --- | --- |
| `info` | anyone | name, state, players, versions (also the UDP reply) |
| `hello {protocol, game, name, code \| token \| secret}` | anyone | → `{player_id, token, host, reconnect, session, pose, duel}`; errors `protocol_mismatch`, `version_mismatch`, `bad_code`, `full`, `no_spawn_tile` |
| `lobby`, `start` (host only), `leave`, `ping` | players | lobby view; start the world; leave; latency |
| `state {seq, full?, radius?}` | players | the per-player view (below) |
| `move {seq, tx, ty, facing}` | players | one tile; → authoritative pose; errors `stale_seq`, `not_adjacent`, `occupied`, `too_fast`, `in_duel`, `blocked`, `obstacle`, `outside_map`, `bad_facing` |
| `pvp_challenge {target, format}`, `pvp_respond {duel_id, accept}`, `pvp_ward {ward}`, `pvp_cast {attack, cast_seq}`, `pvp_forfeit`, `pvp_leave`, `pvp_view` | players | §8 |
| `terrain`, `tile`, `resources`, `profile`, `tech`, `cards`, `menu` | players | read-only world views (the existing server ops) |
| `interact`, `resolve`, `fire`, `treat`, `talk`, `choose`, `enter`, `dungeon_move`, `dungeon_interact`, `duel_begin`, `duel_guess`, `duel_abandon`, `story_view` | players | the wizard's own actions, passed to the existing server op table *as that player* (`session.acting`), refused while in a PvP duel; replies carry no snapshot |
| `duel_resolve`, `duel_checkpoint`, `end_talk`, `opening_done`, `journal`, `call_out`, `inspect_building`, `inspect_person`, `scene_next`, `scene_choose` | players | the narrative ops of Wizard World (the apprenticeship, lessons, the stranger, conversations), acting as that player's seat in the party (`narrative/party.py`) |
| `save`, `new_game` | the host, only in a one-human private session | Wizard World save slots and a fresh campaign (`session._solo_op`); a shared world has neither |
| anything else | – | `not_allowed_in_multiplayer` (faction commands, `advance`, `speed`, `ai`, `spawn`, `damage`, `inspect`, `fixture`, `snapshot`, `pose`, …) |

The `state` reply: `{you, session_state, snapshot, duel, invite, outgoing, players_online, notices, pose, view_radius}`. The
snapshot is the world's own snapshot built *as this player* (`player` is this wizard's pose; `story` is this player's inventory and
dungeon state), with: entities limited to the area of interest (a window of `radius` tiles, default 36, around the wizard;
buildings by their anchor), a per-connection tree/rock delta limited to the same window (`full: true` on the first or a
reconnecting poll sends the forest again), `players` (every wizard: id, name, colour, tx, ty, facing, connected, in_duel, you),
and, unless `full`, without the developer read-outs (`stocks`, `overview`, `feed`, `tech`, `economy_totals`, `provenance`,
`stats`, `ai_notes`, `recent_events`, `entity_ids`) and with `roads`/`blocked` clipped to the window. Measured: a lean poll is
~16 KB on `small` (entities ~13 KB), ~9 KB/s per client at 5 Hz, host-side cost ~5 ms per poll (`HYBRID_HOST_STATS`, printed
by the host every `--stats-every` seconds and at exit: bytes, messages, advances, quanta, tick and per-op timings).

Movement and latency: the client moves at once (prediction) and sends one `move` per tile with a monotonic sequence; the host
validates adjacency, walkability, player collision and a 12 steps/s cap, and answers with the authoritative pose; a refusal snaps
the avatar back (`_on_move_reply`). Remote wizards are glided to their new tile over one poll interval (`move_actor` tween).
Missed updates: every poll is a full view of the area of interest (not an incremental event stream), so a lost poll costs nothing;
trees are the only delta and are re-sent in full on reconnect. Reconnection: the token from `hello`; the client retries every 2 s,
re-authenticates, asks a `full` state and re-places its wizard from the host's pose. Replay protection: a `move` with an old
sequence is `stale_seq`; a `pvp_cast` with the last sequence is answered idempotently with the same feedback and does not cast
again; a duplicate `pvp_ward` is idempotent.

Discovery: a client sends `DMB_DISCOVER?1` to `255.255.255.255:8767`, its subnet broadcast and `127.0.0.1`; a host answers unicast
with its `info` plus `port` and `lan` addresses. Manual address + port entry is always available.

Determinism: nothing in the world reads the wall clock. The host converts wall time into `advance(ms)` and applies commands in
arrival order; `session.command_log` records every accepted world-mutating command with its `game_ms` (replay evidence). The
admission rules that do use wall time (step rate, invite expiry 30 s, cast timeout 60 s, disconnect grace 20 s, ghost removal
600 s) decide only which commands are admitted, never how the world evolves.

## 7. Where player state is stored

| State | Where | Scope |
| --- | --- | --- |
| Wizard pose (tx, ty, facing), name, colour | `world.players[pid]` (host's: the same dict as `world.player`) | shared (in every snapshot's `players`) |
| Identity, token, connection, sequences, notices, tree-delta bookkeeping | `MultiplayerSession.links[pid]` (`Link`) | host only |
| Story: quests, NPCs, dungeons, known facts, log | `world.story` containers, shared by reference by every player's record | shared |
| Story: inventory, in_dungeon, dungeon duel | the player's own story record (`Link.story`; the host's is `world.story` itself) | per player |
| Hazard duel lease, pause tokens | `world.dmb` (as in single player) | shared (global pause) |
| PvP duel | `MultiplayerSession.duels[duel_id]` (`PvpDuel`) | host only; each player sees `duel.view(pid)` |
| Fire-magic cooldown | `world.players[pid]["fire_ready_ms"]` over the LAN (`world._fire_ready_ms` in single player) | per player |
| Cycle reset | `history.cycle_reset` copies `world.players`; `session.rebind` re-aliases the host and re-spawns the others | shared |

## 8. The human-versus-human Ward duel

Rules are the existing ones (`wizard_rts/duel/ward.py`: `score_attack` fracture/echo/fade with wrap-around targets, `compute_result`
from `game_logic.gd`, `random_pattern` for auto-casts; parity-tested against the GDScript in `tests/test_ward_parity.py`). The host
owns everything (`net/pvp.py`):

1. **Challenge** – `pvp_challenge` when the other wizard is within 2 tiles, both free; one open challenge per player; invite expires
   in 30 s. The target sees the invite panel (Accept/Decline, also Y/N on a keyboard); the challenger sees a toast and the
   `declined`/`accepted`/`invite_expired` notices.
2. **Accept** – the host creates the duel, acquires a pause token (`pvp_duel:<id>`): the shared world freezes for everyone, exactly
   as the existing hazard and story duels freeze it (`run_hybrid_duel.gd` rule). Movement and wizard actions are refused for the
   duelists (`in_duel`).
3. **Ward setup** – each player sends `pvp_ward` once (validated: `slots` spells from the `pool`, repeats as the format says). The
   board shows "The rival is weaving a Ward…" until both are in; the rival's slots are `?`.
4. **Active** – real time, no rounds (0.2.0). Each player has their own history, cast counter (`cast_seq`) and allowance (`max_casts`). `pvp_cast {attack,
   cast_seq}` is scored at once against the rival's hidden ward (the caster learns fracture/echo/fade) and the caster may cast again immediately: a player can make
   three guesses while the rival makes none. A repeated `cast_seq` returns the original feedback (no extra guess); a skipped or old one is `bad_cast_seq`; past the
   allowance it is `no_casts_left`. A player who has not cast for 60 s (from the start of the duel or their last cast) gets a random legal weave cast for them (the
   board's auto-cast rule), which uses up one of their own casts. The board never says "waiting for the rival" (a player is only ever blocked by an empty allowance).
5. **Result** – the first legal cast that breaks the rival's ward ends the duel on the host and wins it for its caster; every later cast is refused (`finished`),
   so simultaneous winning casts have exactly one winner (arrival order at the host). If nobody breaks a ward, the duel ends when both have used their whole
   allowance and `compute_result` decides (a draw when both are exhausted; the board's rule). Forfeit (`pvp_forfeit`, the board's "Give up") and a disconnect beyond the
   20 s grace end it the same way. The pause token is released the moment the duel ends, so the world never stays frozen behind a
   player who does not press Continue. Only then does the view carry `rival_ward`.
6. **Return** – Continue → `pvp_leave` → the board closes, input unlocks, both wizards stand where they were in the same world.

Format: `three` (3 slots, 3 colours: Flame, Frost, Stone; repeats allowed; 10 casts) is the first PvP format; `classic` (4×6) and
any `{slots, colours, max_casts, allow_repeats}` go through the same code (`pvp.make_format`). The Godot side is the retained board
(`game_board.gd` with `configure_from_network`) over `DmbNetDuelSim` (`client/duel/net_duel_sim.gd`), which mirrors the host's view
behind the `DmbBattleSim` surface: no rules, no bot, no checkpoint. Cheating surface: a client can only send a ward and casts; it
cannot see the rival's ward, report feedback or report a result (`test_full_pvp_duel_lifecycle_and_return_to_world`, the headed
run's `revealed_early` check).

## 9. Automated tests

```
python3 -m pytest WizardRTSHybrid/tests/test_lan_multiplayer.py -q      # 16 tests, ~12 s
python3 -m pytest WizardRTSHybrid/tests/test_lan_story_shared.py -q    # 1 test, ~11 s
WizardRTSHybrid/scripts/run_lan_headed.sh parse                          # Godot: scripts, net sim mirror, menu screenshots
WizardRTSHybrid/scripts/run_lan_headed.sh two_clients                    # Godot: the two-client acceptance (~4 min)
python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py   # the whole suite (~45 min)
python3 -m pytest tests/sim/test_u05_retained_ward_duel.py -q
```

`test_lan_multiplayer.py` runs the real `HostServer` in a thread with real sockets and the real `HybridWorld` (AI on), two
`NetClient`s speaking the production protocol, plus one test that starts the host as a separate process bound to the machine's LAN
address (`192.168.0.22` here) and connects over it. It covers the owner's list: (1) one host, (2) two independent clients, (3)
distinct identities and tokens, (4) both spawned into one world on different tiles, (5)(6) movement seen both ways, (7) the world
advances once for two polling clients and no client can touch the clock, (8)–(12) a complete PvP duel with hidden wards,
authoritative feedback, consistent results on both sides and the return to the world, (13)(14) disconnect and reconnect with the
avatar kept, no duplicate player, exactly two links and connections; plus simultaneous commands from two threads, illegal
movement (teleport, bad facing, off-map, onto the other wizard, too fast), replayed and stale sequences, invalid wards and casts,
hidden-ward confidentiality until the end, duplicate submissions, clash/stalemate/forfeit outcomes, auto-cast and invite expiry,
disconnect during a duel, full resynchronisation, area-of-interest and lean polls, discovery, bad JSON and oversize lines,
version and permission checks, and single-player snapshot stability. `test_lan_story_shared.py` covers cooperative exploration
(§7). The headed acceptance (`run_lan_two_clients.gd`) exercises the real Godot client against a Python host and a scripted second
human (`scripts/lan_bot.py`): both wizards on screen, movement accepted by the host, the bot walking up, an invite declined, the
challenge button, ward setup through the board UI, host-scored casts until the result, the rival's ward hidden then disclosed,
Continue, free movement afterwards. Screenshots: `WizardRTSHybrid/docs/evidence/lan/` (`lan_two_wizards`, `lan_invite_panel`,
`lan_adjacent_challenge_button`, `lan_duel_setup`, `lan_duel_feedback`, `lan_duel_result`, `lan_after_duel`, `lan_menu_*`,
`main_menu_lan_buttons`).

## 10. Manual two-phone test

Install `build/android/DuelMasterBattle-debug.apk` on two arm64 Android phones (`adb install -r`, or copy and open the file).

1. Turn mobile data off on both phones (airplane mode, then Wi-Fi back on) to show nothing needs the internet.
2. Connect both to the same Wi-Fi (a phone hotspot is fine and avoids client isolation).
3. Phone A: **Host Multiplayer** → name, game name, note the join code → **START HOSTING**. Wait for the lobby (the world is built on
   the phone; expect roughly 10–20 s on a mid-range phone for `small`).
4. Phone B: **Join Multiplayer** → name, the code → tap the game in "Games on this Wi-Fi" (or type Phone A's address shown in its
   lobby) → the lobby shows both names.
5. Phone A: **START THE WORLD**. Both phones enter the world beside the Red settlement; each sees its own wizard centred and the
   other wizard with a name label. The top-right line reads `LAN host/joined · 2 online · N ms`.
6. Walk towards each other with the D-pad. The other wizard moves on your screen; when you stand within two tiles the **⚔ Duel**
   button appears above the ✦ button.
7. Phone A taps **⚔ Duel**; Phone B sees "A challenges you to a Ward duel" → **Accept**. Both boards open; set three spells and
   **Lock**; cast in turns; the rival's ward shows as `?` until the end; the result screen names the winner and shows both wards;
   **Continue** on both.
8. Both are back in the same world, unfrozen (workers move, the era line ticks). Walk together to another part of the map; both see
   the same buildings, carts and workers.
9. Walk up to a settlement person and tap ✦ to talk; the dialogue appears only on the phone that tapped. Make a choice; the quest
   line on both phones updates.
10. Watch a minute: both phones show the same new buildings/events; the clock advances once (the era progress is identical).
11. Put Phone B in airplane mode for ten seconds and back: it reads "connection lost · reconnecting…" then "Reconnected"; Phone A
    shows B greyed out then back; B's wizard is where it was.

Expected failures to recognise: "No game is answering at that address" (host not on the Host/lobby screen, or Wi-Fi isolation →
use a hotspot); "The host runs a different game version" (install the same APK on both).

**Result: BLOCKED.** No Android device is attached to this machine (`adb devices` empty) and no emulator can run (the user is not in
the `kvm` group), so steps 1–11 have not been executed on phones. See §11 for what was and was not verified.

## 11. Known bugs, limits and remaining work

- **(Resolved 15 Oct 2026 on Windows: the APK builds; see `docs/ANDROID_EXPORT.md`.) No APK was produced in this run.** `scripts/android/build_apk.sh debug` reaches Godot's export (template installed, overlay
  applied, Python staged and self-tested, preset and project settings fixed: ETC2/ASTC import, icon, `android/.build_version`), but
  the two export attempts after those fixes were stopped by the session harness for low system memory (the laptop had ~3 GB free
  beside the owner's desktop applications; the gradle JVM asks for 4.5 GB). Nothing in the pipeline has yet run gradle, so the
  Chaquopy/Kotlin steps are **unverified**. Rerun `WizardRTSHybrid/scripts/android/build_apk.sh debug` on a machine with ~8 GB
  free and internet; the first run downloads Gradle 8.11.1, AGP 8.6.1, Chaquopy 17.1 and the Android CPython 3.12 runtime.
- **Physical devices: not verified.** The APK path (template, overlay, staging, export) was exercised on this machine; the Chaquopy
  runtime was never started on a phone here. The first device run should tap WIZARD WORLD (a private hosted session on the phone) and
  check `LanSession.host_status()` reaches `ready`; `DmbPySim.selfTest()` returns the world's build time and hash as evidence.
- **Hazard duel in multiplayer stays client-resolved.** `interact`/`resolve` are the single-player lease (Godot plays `DmbBattleSim`
  and reports success). It is allowed over the LAN *as that player* and pauses the world for everyone, as in single player. It is not
  the PvP path and a dishonest client could report a hazard win. Either move the hazard duel onto the host rules (the PvP duel shows
  how) or refuse `interact` over the LAN before a release.
- **Story quantum runs as the host's wizard.** `story_quantum` (the per-second story bookkeeping: quest opening, outbreak checks,
  releasing a story duel) runs outside any `acting()` and sees the host's story record; a non-host player's *dungeon duel* is
  therefore not released by the quantum if its quest fails meanwhile (it still ends by `duel_abandon`/`duel_guess`). Per-player
  dungeon runs otherwise work (`test_lan_story_shared.py`).
- **Global pause.** A PvP duel (and a hazard or story duel) freezes the world for everyone; with two players both are in the duel, so
  nothing is lost; with three or four, spectators wait. Decided for consistency with the existing rule; a per-duel local pause would
  need the world to run with two frozen wizards.
- **Rendering cost on phones is the pre-existing G11 gap** (the Godot `_draw` walks every static row each frame; ~7 fps on this
  laptop). Not changed here; the LAN layer adds ~5 ms per poll on the host and ~16 KB per poll on the wire.
- **Host death ends the session.** No host migration; a client that cannot reconnect shows "reconnecting…" forever (a Leave button
  in that state is a small follow-up).
- **Late join after a cycle reset** re-spawns everyone beside the host (documented in `session.rebind`).
- **Discovery on some Android builds** drops limited broadcasts; the subnet broadcast and manual entry cover it. Multicast lock not
  needed (replies are unicast).
- **Player name label** scale is approximate for the placeholder sprites; cosmetic.
- iOS: not built (the protocol has no platform dependency; a client needs only the Godot export; hosting would need a CPython
  embedding such as BeeWare's support package).

## 12. Integration notes for the other branches

- `feature/wizard-mode-implementation` rewrites `server.py` (`new_world`, save/load, `_swap`, `AFTER_DEATH`) and much of
  `hybrid_world.gd`. The LAN host does not use `server.serve`; it calls `server._handle` for the wizard's passthrough ops, so the
  branch's narrative gates (`spell_unknown`, `game_over`) will apply automatically over the LAN once merged. `hybrid_world.gd`'s LAN
  additions are appended functions plus five small insertions (`_ready` connect block, `_process` early branch, `_unhandled_input`
  key hook, `_arrived` move branch, the LAN UI build); expect a manual merge there. `history.cycle_reset` gains two lines.
- `feature/wizard-settlement-stories` / `feature/neuroevolution-plan` change `world.py` (+48/−14) and `history.py`; this branch's
  `world.py` changes are the `players` field, the in-place `set_pose`, and the `sent`/`view` parameters on `tree_delta`/`snapshot`.
  Any new single-wizard field those branches add (like `_fire_ready_ms`) should be read through `world.player` so `acting()` covers it.
- The training environments (`envs/`, `learn/`) are untouched and not shipped in the APK.
