# Handoff

## Works

The wizard walks one continuous map. Hex crossings do not advance `game_ms`. Idle time produces logs and delivers them with the Widelands-derived warehouse list. Soldiers take OpenRA-derived damage. The retained ward board opens on the route hazard, pauses `game_ms`, clears the hazard on a win, and leaves the pose and entity ids unchanged.

## Does not

Widelands does not compile here (`docs/BLOCKERS.md` B1). OpenRA's pathfinder, orders, and bot are not executing. The carrier and the soldier step are provisional. The hybrid does not read `external/` during play. Do not describe the provisional pieces as Widelands or OpenRA.

## Architecture

`AGENTS.md` and `docs/DECISIONS.md`. Python `wizard_rts/world.py` owns the world. Godot `godot_project/client/scenes/hybrid_world.gd` extends Overworld.

## Rebuild

- Labs: `WizardRTSHybrid/scripts/setup_external.ps1`
- OpenRA: `dotnet build OpenRA.slnx -c Debug` in `external/openra` with .NET 10.
- Mod SDK: `make.cmd all` with `dotnet` on `PATH`.
- Widelands: blocked until a C++ compiler exists. Command in `docs/original_runs/WIDELANDS.md`.
- Hybrid: `scripts/launch_hybrid.ps1`

## Test

Commands are in `docs/PROJECT_STATUS.md`. One sim process on port 8765. Headed shots need `--rendering-method forward_plus`.

## Evidence

- `docs/evidence/walk/walk_start.png`, `walk_middle.png`, `walk_end.png`
- `docs/evidence/duel/duel_open.png`
- `docs/original_runs/`

## Next task

Install a C++ compiler, then rerun the Widelands cmake command. Do not rerun it unchanged.

## First files

1. `docs/PROJECT_STATUS.md`
2. `docs/BLOCKERS.md`
3. `wizard_rts/world.py`
4. `godot_project/client/scenes/hybrid_world.gd`
5. `docs/SOURCE_REUSE.md`
