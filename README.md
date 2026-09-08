# Duel Master Battle

**Real-time wizard ward duel** for phones, built in Godot 4. You and a rival wizard each hide a
**Ward of four spells** (six spell types, repeats allowed) and race to deduce each other's Ward
with Mastermind-style aggregate feedback, under a 5–60 second casting window. Ten casts each.

This branch is the **first adventure**: John the woodcutter finds magic, crosses a
small top-down world (the Clearing → the Burnt Wood → Ashwell village), grows
from one spell and one weave slot to four spells and four slots, and faces the
Red Wizard — see [docs/FIRST_ADVENTURE.md](docs/FIRST_ADVENTURE.md). The
standalone duel loop underneath is unchanged. The wider game (bosses, Last
Stand, larger Wards) is designed for but not enabled — see
[docs/CORE_MVP.md](docs/CORE_MVP.md).

## Play

Windows: double-click **`Play Duel Master Battle.bat`** (edit the Godot path inside if needed).

Anywhere:

```bash
export GODOT=/path/to/godot4        # optional; tools/find_godot.sh searches common places
tools/play.sh
```

Choose **New Game** (or Resume) → walk with the pad / arrow keys, ✦ or Space to
interact → opening cutscene → take the staff → douse fires → fight creatures →
reach Ashwell → face the Red Wizard. **Quick Duel** on the menu plays a
standalone 4-slot wizard match.

## Run the checks

```bash
tools/run_all_checks.sh        # parse check + sim tests + UI smoke + adventure flow + real-time playtest
tools/run_godot_tests.sh       # rules, feedback, AI, cast windows, win/lose/stalemate
tools/run_godot_ui_smoke.sh    # drives the real board through a duel (headless)
tools/run_adventure_flow.sh    # drives the whole first chapter + save/load round trip (headless)
tools/run_realtime_playtest.sh # wall-clock pacing with synthesised taps (headed)
tools/run_balance_probe.sh     # AI solve rate / average casts per difficulty
tools/capture_visual_qa.sh     # screenshots of duel screen states → qa/screenshots/current
tools/capture_adventure_qa.sh  # screenshots of the adventure → qa/screenshots/adventure
```

Windows: **`Run Tests.bat`**.

Python prototype tests (rules reference implementation): `cd python_prototype && python -m pytest -q`.

## Project structure

```
godot_project/
  sim/                 Authoritative rules: battle sim, combatants, bestiary, progression, weave bot, tests
  client/scripts/      game_board.gd (duel screen), main_menu.gd, adventure.gd (save), sfx.gd, theme
  client/world/        overworld.gd, world_data.gd (areas), story_events.gd, dialogue_box.gd, touch_pad.gd
  client/components/   spell_slot, feedback_pips, cast_button, pixel_portrait, spell_vfx (+ legacy composite_wizard)
  client/legacy/       Dormant pre-MVP components kept for the wider game
  assets/pixel/        Committed pixel art (built by tools/build_pixel_assets.py from gitignored Spare Sprites/)
docs/FIRST_ADVENTURE.md What the opening chapter is, bestiary, asymmetric rules, saves, adding content
docs/CORE_MVP.md       The duel underneath: scope, architecture, testing, future hooks
python_prototype/      Pure-Python rules + pytest (predates the adventure; duel rules only)
```

## Docs

- [First Adventure](docs/FIRST_ADVENTURE.md) — chapter path, bestiary, asymmetric duels, saves
- [Core MVP](docs/CORE_MVP.md) — the duel underneath, architecture, testing, future hooks
- [Game rules](docs/RULES.md)
- [Encounter design](docs/ENCOUNTER_DESIGN.md) (future)
- [PRD](docs/PRD.md) (wider game vision)
