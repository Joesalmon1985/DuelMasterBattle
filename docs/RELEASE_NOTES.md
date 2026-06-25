# Release Notes — Wizard Duel Update

## Branch `feature/encounter-progression-rulesets`

### Encounter progression (latest)
- **DuelRuleset** model: variable slots (1–4), secret vs attack magic pools, configurable max attacks
- Four built-in encounters: Blue Apprentice, Thorn Adept, Mirror Mage, **Archmage Duel** (classic regression)
- Main menu encounter select + detail panel; `EncounterSession` autoload
- Dynamic board slots, filtered magic picker, enemy tell label
- Modifiers (first pass): `extra_attacks`, `bot_attack_delay_multiplier` (Counterspell Time field stored but inactive)
- Python + Godot tests; dual UI smoke (Blue Apprentice + Archmage)

## Branch `feature/alternating-duel-flow`

### Alternating duel (latest)
- Human and bot each set hidden patterns at **Cast pattern**; human attacks first.
- One attack per turn; turns alternate until solve or 12 attacks each (draw).
- Dual visible histories: your attacks vs enemy / enemy attacks vs you.
- Human feedback rows appear immediately after **Attack**.

## Branch `feature/wizard-duel-polish-web-demo`

## Summary
Wizard-duel reskin, click-slot magic picker, candidate-elimination solver with difficulty levels, draft sprite placeholders, and Python-only NN experiment scaffold — while preserving playable Human vs Bot flow.

## Track A — Wizard UI
- 10 magic types with labels, symbols, and colours
- Four points: Shield, Body, Staff, Mind
- Click-slot → overlay magic picker (no separate colour row)
- Feedback: Hit / Weakness / Unaffected
- Lock → **Cast pattern**, Submit → **Attack**

## Track B — Bot intelligence
- `SolverBot` / `DmbSolverBot`: 10,000 candidates, opener `[0,0,1,1]`, feedback filtering, minimax (pool capped for Godot responsiveness)
- Difficulty: Easy · Normal · Hard · Expert (UI selector, default Expert)
- Python NN experiment scaffold (`docs/NN_BOT_EXPERIMENT.md`) — not a game dependency

## Track C — Draft art
- `tools/generate_draft_sprites.py` → 17 PNG placeholders
- Magic icons integrated in picker; feedback uses text labels; wizard portraits created but not yet on board

## Tests
| Suite | Result |
|-------|--------|
| Python pytest | 37 passed, 1 skipped |
| Godot rules (6 modules) | pass |
| Godot UI smoke | pass |

## Manual playtest
Not performed in CI (no visible Godot window). UI smoke test passed. See `docs/MANUAL_PLAYTEST.md`.

## Launch locally
```bash
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
"$GODOT" --path godot_project
```

## Deferred
- Full NN training run and weight export
- Wizard portrait sprites on game board
- Point icons in slot headers (labels used instead)
