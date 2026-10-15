# Mobile LAN multiplayer (branch `feature/mobile-lan-multiplayer`)

Base commit: `143797baf862076399832f8acf758a6ef476e689` (`main`, merge of PR #15), the merge-base of every active unmerged branch
(`feature/wizard-settlement-stories`, `feature/neuroevolution-plan`, `feature/wizard-mode-implementation`), so this work can be
rebased onto or merged with any of them.

This file is the record of the multiplayer feature: the audit, the architecture, the protocol, the build, the tests and what is not done.
Sections are filled in as milestones land.

## 1. Architecture audit (M1) and risks

Verified against the code on 15 October 2026 (not against the docs):

| Area | What the code does today | Consequence for multiplayer |
| --- | --- | --- |
| `wizard_rts/server.py` | One blocking TCP connection on `127.0.0.1`, newline JSON, `listen(1)`. The **Godot client drives the clock** (`advance` every 200 ms with `sequence`). | A host must own the clock loop and serve several connections; clients must never call `advance`. |
| `HybridWorld.player` | One dict `{tx,ty,facing}`; `set_pose` reassigns it. `magic.fire`, `story.*`, `regions.begin_treatment`, `interact`, `history.cycle_reset`, `server pose` read it implicitly. | Needs a per-player record and an "acting player" binding so the existing code keeps working unchanged. |
| `story.state(world)` | One dict: world-level `npcs/dungeons/quests/known/log` plus player-level `inventory/in_dungeon/duel`. Only `in_dungeon` and `duel` are ever reassigned; the containers are mutated in place. | Per-player story records can share the world-level containers by reference. |
| Hazard Ward duel | `world.interact` leases a `DmbBattleSim` to Godot; Godot plays the duel **locally** and reports `success` to `world.resolve`. | Unusable as-is for PvP (a client would report its own win). PvP needs host-owned rules: `wizard_rts/duel/ward.py` (`score_attack`, `compute_result`, parity-tested against the GDScript) can own the state. |
| Clock pause | `pause_tokens` on `dmb.clock`; a hazard or story duel pauses `game_ms` globally. | A PvP duel will pause globally too (consistent with the existing rule; see §6). |
| Snapshot | Delta snapshot (trees as deltas) is ~107 KB on `standard`, 6 ms to build; `entities` is ~90 % of it. Tree deltas track one client (`world._tree_sent`). | Per-client area-of-interest filtering and per-client tree-delta state are required for phones. |
| God Mode / training ops | `GOD_OPS` rejected unless profile is `developer`/`test_*`; `spawn`/`damage` behind `HYBRID_ALLOW_SPAWN`. | The multiplayer host must reject every faction-level op and every clock op from any connection, whatever the profile. |
| Determinism | `tests/test_determinism.py` (two processes, two hash seeds). No wall-clock decisions inside the world. | The host loop converts wall time into `advance(ms)` calls; admission (rate limits, timeouts) is outside the world; the world only sees an ordered command list. |
| Godot client | `hybrid_world.gd` extends `overworld.gd`: local tile movement, `_arrived` sends `pose`; touch D-pad and action button exist (`touch_pad.gd`); `game_board.gd` drives any object with the `DmbBattleSim` surface. | Reuse: a network-backed sim object with the same surface drives the existing board; remote players use `spawn_actor`/`move_actor`. |
| Android | `export_presets.cfg` has an Android preset (non-gradle). Godot 4.5.1 at `~/godot451`; 4.5.1 Android templates installed this run; SDK 35, JDK 17, NDK 25.2. No device or emulator (no `kvm` group). | Gradle build with Chaquopy is the hosting path (§2). Device acceptance is BLOCKED until a phone is attached. |
| Unmerged branches | `feature/wizard-mode-implementation` rewrites much of `hybrid_world.gd` (+445 lines) and `server.py` (`new_game`, save/load, `_swap`); the story and neuroevolution branches touch `world.py` (+48/-14) and `history.py`. | Keep multiplayer in new modules (`wizard_rts/net/`, `client/net/`) and keep `world.py`/`server.py`/`hybrid_world.gd` edits small and additive. See §12. |

Main risks, in order: (1) CPython on Android must host the real `HybridWorld` at playable cost (measured on this laptop: world build 4.4 s, 49 ms of CPU per game-second, pure Python, AI on; a phone is roughly 2–3x slower, so the host spends well under a core on the sim); (2) JSON snapshot volume on a phone (area of interest + deltas); (3) the duel UI was written around a local sim; (4) merge friction with the wizard-mode branch.
