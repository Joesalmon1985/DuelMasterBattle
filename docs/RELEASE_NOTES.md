# Release Notes — Wizard Duel Update

## Branch `feature/encounter-progression-rulesets`

### Encounter progression (latest)
- **DuelRuleset** model: variable slots (1–4), secret vs attack magic pools, configurable max attacks
- Four built-in encounters: Blue Apprentice, Thorn Adept, Mirror Mage, **Archmage Duel** (classic regression)
- Main menu encounter select + detail panel; `EncounterSession` autoload
- Dynamic board slots, filtered magic picker, enemy tell label, **Back to menu**
- Modifiers (first pass): `extra_attacks`, `bot_attack_delay_multiplier` (Counterspell Time field stored but inactive)
- Difficulty driven by encounter (UI difficulty row removed)

### Tests
| Suite | Result |
|-------|--------|
| Python pytest | 53 passed, 1 skipped |
| Godot rules (7 modules) | pass |
| Godot UI smoke | pass (Blue Apprentice + Archmage) |

### Manual playtest
Not performed in CI (no visible Godot window). UI smoke test passed. See `docs/MANUAL_PLAYTEST.md`.

### Launch locally
```bash
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
"$GODOT" --path godot_project
```

### Deferred
- Counterspell Time, campaign/unlock progression, hidden secret types
- Full NN training run and weight export
- Web export as a branch deliverable (local export still available)

---

## Branch `feature/alternating-duel-flow`

### Alternating duel
- Human and bot each set hidden patterns at **Cast pattern**; human attacks first.
- One attack per turn; turns alternate until solve or max attacks each (draw).
- Dual visible histories: your attacks vs enemy / enemy attacks vs you.
- Human feedback rows appear immediately after **Attack**.

---

## Branch `feature/wizard-duel-polish-web-demo`

### Summary
Wizard-duel reskin, click-slot magic picker, candidate-elimination solver with difficulty levels, draft sprite placeholders, and Python-only NN experiment scaffold.

### Track A — Wizard UI
- 10 magic types with labels, symbols, and colours
- Four points: Shield, Body, Staff, Mind
- Click-slot → overlay magic picker
- Feedback: Hit / Weakness / Unaffected
- Lock → **Cast pattern**, Submit → **Attack**
- Wizard portraits and point header icons on board

### Track B — Bot intelligence
- `SolverBot` / `DmbSolverBot`: ruleset-driven candidates, opener `[0,0,1,1]` on Archmage, feedback filtering, minimax (pool capped for Godot responsiveness)
- Difficulty: Easy · Normal · Hard · Expert (per encounter)

### Track C — Draft art
- `tools/generate_draft_sprites.py` → 17 PNG placeholders
- Magic icons in picker; feedback text labels; wizard portraits on board
