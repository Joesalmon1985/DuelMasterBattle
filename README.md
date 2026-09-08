# Duel Master Battle

**Real-time wizard ward duel** for phones, built in Godot 4. You and a rival wizard each hide a
**Ward of four spells** (six spell types, repeats allowed) and race to deduce each other's Ward
with Mastermind-style aggregate feedback, under a 5–60 second casting window. Ten casts each.

This branch is the **core MVP**: one complete, tested duel loop. The wider game (encounters,
bosses, Last Stand, larger Wards) is designed for but not enabled — see
[docs/CORE_MVP.md](docs/CORE_MVP.md).

## Play

Windows: double-click **`Play Duel Master Battle.bat`** (edit the Godot path inside if needed).

Anywhere:

```bash
export GODOT=/path/to/godot4        # optional; tools/find_godot.sh searches common places
tools/play.sh
```

Choose a rival (Apprentice / Adept / Archmage) → **Start Duel** → set your Ward → **Lock Ward**
→ build guesses and **CAST** in real time → result → **Play again**.

## Run the checks

```bash
tools/run_all_checks.sh        # script parse check + sim tests + UI smoke + real-time playtest (~45 s)
tools/run_godot_tests.sh       # rules, feedback, AI, cast windows, win/lose/stalemate
tools/run_godot_ui_smoke.sh    # drives the real board through a duel (headless)
tools/run_realtime_playtest.sh # wall-clock pacing with synthesised taps (headed)
tools/run_balance_probe.sh     # AI solve rate / average casts per difficulty
tools/capture_visual_qa.sh     # screenshots of every screen state → qa/screenshots/current
```

Windows: **`Run Tests.bat`**.

Python prototype tests (rules reference implementation): `cd python_prototype && python -m pytest -q`.

## Project structure

```
godot_project/
  sim/                 Authoritative rules: DmbRealtimeDuelSim, DmbSolverBot, encounters, tests
  client/scripts/      game_board.gd (duel screen), main_menu.gd, sfx.gd, theme
  client/components/   spell_slot, feedback_pips, cast_button, composite_wizard, spell_vfx
  client/legacy/       Dormant pre-MVP components kept for the wider game
  assets/              Spell icons (tools/generate_essence_icons.py), wizard art
docs/CORE_MVP.md       What the MVP is, what changed, what remains
python_prototype/      Pure-Python rules + pytest
```

## Docs

- [Core MVP](docs/CORE_MVP.md) — current scope, architecture, testing, future hooks
- [Game rules](docs/RULES.md)
- [Encounter design](docs/ENCOUNTER_DESIGN.md) (future)
- [PRD](docs/PRD.md) (wider game vision)
