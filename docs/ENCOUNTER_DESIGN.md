# Encounter Design

Encounters are config-driven **duel rulesets**: slot count, magic pools, attack limits, enemy presentation, and bot difficulty. The sim and UI read a `DuelRuleset` (Python) / `DmbDuelRuleset` (Godot) instead of hardcoded 4/10/12 constants.

## Ruleset fields

| Field | Purpose |
|-------|---------|
| `slot_count` | 1–4 magical points |
| `point_names` | Labels per slot (e.g. Shield, Body, …) |
| `secret_magic_pool` | Magic ids allowed in player/bot secrets |
| `attack_magic_pool` | Magic ids allowed in attack guesses |
| `max_attacks_per_player` | Base attack cap per side |
| `enemy_*` | Name, archetype, visual hint (tell), difficulty |
| `allow_repeats` | Whether secrets/guesses may repeat types |
| `player_modifiers` / `enemy_modifiers` | First-pass keys below |
| `counterspell_seconds` | **Stored only — not active this branch** |

### Modifiers (first pass)

- `extra_attacks` — added to `effective_max_attacks()` for both sides
- `bot_attack_delay_multiplier` — scales enemy attack pacing in the UI

### Pool fairness

`secret_magic_pool` must be a **subset** of `attack_magic_pool` unless `allow_hidden_secret_types == true` (advanced hidden-type mechanic — **not used this branch**). `validate_pools()` runs at load time.

## Built-in encounters

| id | Slots | Max attacks | Difficulty | Notes |
|----|-------|-------------|------------|-------|
| `blue_apprentice` | 1 | 4 | easy | Secret ⊂ attack pool; 4 attack types |
| `thorn_adept` | 2 | 6 | normal | No repeats; 5 attack types |
| `mirror_mage` | 3 | 8 | hard | 4 types, repeats allowed |
| `archmage_duel` | 4 | 12 | expert | Full classic rules — regression anchor |

Magic ids: Flame=0, Frost=1, Storm=2, Stone=3, Light=4, Shadow=5, Vine=6, Metal=7, Spirit=8, Arcane=9.

## Exhaustion and wins (alternating model)

- Solve (Hits == slot count) → **immediate win**
- One side exhausts attacks without solving → cannot win on attacks alone; tie-break uses best feedback progress
- **Both** reach `effective_max_attacks()` without solving → **draw**

## Deferred

- Counterspell Time (real-time comeback)
- Campaign map / unlock progression
- Hidden secret types beyond attack pool (`allow_hidden_secret_types`)
- Web export as a deliverable for this branch

## Adding encounters

1. Add entry to `python_prototype/duel_mastermind/encounters.py` and `godot_project/sim/encounters.gd`
2. Ensure `validate_pools()` passes
3. Add tests in `test_duel_ruleset.py` / `test_encounters.gd`
4. Add menu label via `all_encounters()` ordering
