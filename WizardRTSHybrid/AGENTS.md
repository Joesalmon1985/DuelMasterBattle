# WizardRTSHybrid agents

This file is the restart contract. Status, tasks and evidence live in the docs it names. Do not treat chat history as project memory. The previous version is archived at `docs/archive/AGENTS_session3_pre_ratification.md`.

## Objective (ratified 11 October 2026)

DuelMasterBattle is a **wizard-led adventure inside an autonomous civilisation simulation**, not a player-controlled RTS. The wizard walks real settlements, talks to residents, explores dungeons, solves puzzles, intervenes in crises, and fights Mastermind-style duels. The world is a real Widelands-style economy and OpenRA-style military across four eras (Prehistoric, Historic, Modern, Dystopian Future), with Mindustry-style industry arriving in Modern. God Mode and the training API exist for development, tests and AI research only.

Read in this order:

1. `../docs/DuelMasterBattle_Design_v0_5.md` — what the game is.
2. `../docs/DECISION_REGISTER.md` — D01–D20 are closed (APPROVED). Only the S-items are open, with defaults. Do not re-ask them.
3. `../docs/ARCHITECTURE_CONTRACT.md` — authority, registries, conservation, commands.
4. `../docs/CURRENT_STATUS_AND_GAPS.md` — what works, what is partial, what is absent.
5. `../docs/ROADMAP_NEXT_RUN.md` — milestones M1–M6 with acceptance tests. **A milestone starts only when the owner says so.**
6. `docs/PROJECT_STATUS.md`, `docs/TASK_LEDGER.md`, `docs/BLOCKERS.md`, `docs/CLAUDE_HANDOFF.md`, `docs/PLAYTEST_FIXES.md` — hybrid history and evidence.

## Architecture constraints

- Python `HybridWorld` (`wizard_rts/world.py`) is the only live simulation; it embeds DuelMasterBattle `WorldState` and `ClockService`. Godot presents it (`godot_project/client/scenes/hybrid_world.gd` extends `overworld.gd`, helpers in `client/hybrid/`). No second economy, army or clock.
- The **square grid with four-direction movement is authoritative** (D03, `docs/DECISIONS.md` D5). The hex code in `coords.py` is a legacy label and the future logical catastrophe overlay; never a placement, movement or territory rule. Do not restore Catan topology.
- A settlement is a deployed MCV or a faction's first warehouse plus its territory (`territory.py`). Six factions, five Widelands tribes.
- Mindustry is **in scope** (D06) and **not yet implemented**. Official source `https://github.com/Anuken/Mindustry` (GPL-3.0). Read `docs/MINDUSTRY_PROVENANCE.md` before touching it; pin a revision first; no Java runtime; no second army or economy.
- Wares are conserved (`ARCHITECTURE_CONTRACT.md` section 5). Early output comes from real workers and movement; automation uses real belts, pipes, machines and power (D08).
- God Mode and `HybridEnv` are developer/test only. They currently are not gated (gap G1 in the status doc); fix it when M1 is authorised.
- Do not call a DuelMasterBattle cart or formation Widelands or OpenRA. Provenance strings are on the snapshot. Imported data or art is not a feature until a test shows behaviour.
- Widelands, OpenRA and the OpenRA Mod SDK are source labs under `external/`; normal play does not read them. Code copied into this package is listed in `docs/LICENSES.md` and `docs/SOURCE_REUSE.md`.

## Repo layout

- `wizard_rts/` — authoritative world, data, local JSON server.
- `tests/` — Python checks. `test_five_minutes.py` is a wall-clock script, not part of the quick suite.
- `sources/manifest.json` — pinned upstream URL, branch, SHA, licence, build command (Mindustry is **not** in it yet).
- `scripts/` — importers, launchers, tests, reports. `external/` — gitignored clones.
- `docs/` — living record and engine maps; `docs/archive/` — superseded entry files.
- Legacy game: `../sim/dmb`, `../godot_project`, `../tests`, `../DD`, `../python_prototype` (see the inventory in the status doc).

## Build and test

From the repo root (`py -3` on Windows, `python3` on Ubuntu):

```
python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py
python3 -m pytest tests/sim/test_u05_retained_ward_duel.py -q
python3 WizardRTSHybrid/scripts/ai_report.py --minutes 40 --seeds 507 11 23
WizardRTSHybrid/scripts/run_headed_suite.sh [walk visual duel forestry food god war terrain naval playtest wizard mcv]
godot --headless --path godot_project --script res://client/tests/run_hybrid_coords.gd
```

The full Python suite takes several minutes. Headed scripts need the sim on `HYBRID_SIM_PORT` (default 8765), a fresh sim per script, and `--rendering-method forward_plus`. `docs/STATE_OF_PLAY.md` and `docs/PROJECT_STATUS.md` list commands and expected output tokens.

## Rules that must not be forgotten

- **Playtest rule.** A defect the owner sees is fixed only when a headed Godot test (screenshot or rendered-state assertion) shows it fixed.
- **Determinism.** Never decide anything by iterating a `set` of strings or by wall-clock time. `tests/test_determinism.py` runs two processes under different `PYTHONHASHSEED`s.
- **AI tests.** `tests/conftest.py` switches the faction AIs off; tests of the AI must enable `world.ai_enabled`.
- Route searches are the performance cost; use shared routes and counted budgets.
- The retained Ward Duel pauses `game_ms` (pause token `hazard_duel`). Keep that test green.

## Reuse and licensing

Prefer executing an upstream algorithm, then a separate process, then a source-derived port with a comparison test. Widelands is GPL-2.0-or-later; do not paste GPL-2-only files. OpenRA and Mindustry are GPL-3.0. Do not copy large amounts of upstream code or assets blindly. Record every derivation in `docs/SOURCE_REUSE.md` and `docs/LICENSES.md`.

## Commits and branches

Commit verified milestones on the current feature branch (`feature/hybrid-playtest-fixes-v03`). Do not merge into `main` unless the owner asks. Never commit `external/`, `runtime/`, `dist/`, secrets, or unrelated dirty content. Never delete or overwrite the owner's untracked files. An unfinished experiment stays unverified in the ledger.

## Failed experiments

Add a row to `docs/BLOCKERS.md`: upstream file and symbol, what was tried, the exact error, environment problem or incompatibility, and the next approach. Do not retry a failed fix without new evidence named in that row.

## Restart

1. Read the six items above.
2. `git status`, latest commit; trust the repo and tests where a doc disagrees.
3. Rerun the baseline commands.
4. If a milestone is authorised, follow `ROADMAP_NEXT_RUN.md`. If none is, do documentation, review, or bug fixing only and ask.
