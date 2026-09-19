# G04 — Battles, wizard power and catastrophe (Reuse Repair U01–U08)

**Status:** AWAITING_HUMAN  
**Repair:** U01–U08 (`docs/DuelMasterBattle_G04_Reuse_Repair_Addendum.md`)  
**Branch:** `fix/g04-retained-ui`  
**Base:** `origin/feature/spellbook-ui` @ `454ccf1` + merge `origin/main` @ `441899b`  
**Candidate:** a40b1cbe0db064c4e4e13c07bf7f44c61094587d
**Platform (automated):** Windows 10, Godot 4.5.1 (local), Python 3.14 / project venv 3.11  

## What changed

- Shared `DmbTargetSession` + approved military `AttachedChoiceCard` for units/hazards
- Observation-led durable names (people + soldiers); movement dismissal via shared intent
- Bridge presenter reuses village `WorldInteractionLabel` presentation
- Hazard Challenge hosts retained `game_board.tscn` + `DmbBattleSim` (configure before startup)
- Guess/Resign Mastermind panel removed from production Challenge; Mastermind kept as reference scoring
- Quick duel and Adventure `pending_battle` paths preserved
- Duplicate `ResolveHazardDuel` submission is idempotent
- R06 Mastermind production choice superseded; T077 remains NOT_STARTED

## Ensemble follow-up (not in this PR)

Commits `58ea2d2` and `6f7be0f` on `BuildPackV03-ensemble-depth-pass` are tracked separately and were not merged into this repair branch.

## Reset (required before judging)

See [reset.md](reset.md). Delete isolated slots `g04_battle`, `g04_hazard`, `g04_hazard_terminal`.

## Launch

Windows (this candidate host):

```bat
Playtest.bat
```

Then Play G04 battle / Play G04 hazard, or:

```bat
set GODOT=C:\Users\joesa\Downloads\Godot_v4.5.1-stable_win64.exe\Godot_v4.5.1-stable_win64_console.exe
%GODOT% --path godot_project res://client/scenes/g04_battle_shell.tscn
```

Linux:

```bash
bash tools/play_g04_battle.sh
bash tools/play_g04_hazard.sh
```

## Joe checklist

Use the table in [gates/G04.md](../../gates/G04.md). Expect the **full Ward duel** on Challenge — not four colour buttons + Guess/Resign. **Do not accept G04 merely because automated checks pass.**

## Automated evidence

```bash
python tools/check.py --gate G04
```

Result on this handoff host: **PASS** (see `check_report.json`). Includes Python cumulative, G04 playable (`G04_PLAYABLE_OK`), G01–G03 smokes.

## Known limits

See [known_defects.md](known_defects.md).

## Stop

`current_task = STOP_FOR_G04`. **T077 remains NOT_STARTED.** Agent must not mark G04 PASS or merge before Joe's playtest.
