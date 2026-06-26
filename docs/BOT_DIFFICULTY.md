# Bot difficulty tuning

Evaluation script: `cd python_prototype && python3 scripts/evaluate_bots.py`

Difficulty is **per encounter** (`enemy_difficulty` on `DuelRuleset`). The evaluator uses **Archmage Duel** rules (4 slots, 10 types, 12 attacks) with `enemy_difficulty` overridden per level so metrics stay comparable to the full game.

## Difficulty levels

| Level | Behaviour | Minimax guess pool cap |
|-------|-----------|------------------------|
| Easy | Random guesses from attack pool (ignores feedback) | — |
| Normal | Candidate elimination + deterministic random pick | — |
| Hard | Minimax over capped candidate pool | 100 |
| Expert | Minimax over larger candidate pool (strongest responsive bot) | 500 |

Expert is **not** claimed to be mathematically optimal. Pool caps keep Godot responsive during enemy attack phase.

Per-encounter bots are created via `make_bot(ruleset, seed)` — e.g. Blue Apprentice uses Easy + 1-slot / 4-candidate space; Archmage uses Expert + 10⁴ candidates.

## Opening guess

Pattern: first attack-pool id twice, second id twice, truncated to `slot_count`. Archmage attack pool `[0..9]` → `[0,0,1,1]`.

## Validation set

- Default: **100** deterministic secrets (`master_seed=42`, 4-peg Archmage-style codes)
- Quick smoke: `python3 scripts/evaluate_bots.py --quick` (8 fixed secrets)

## Sample results (100-secret run, seed 42, Archmage ruleset)

```
easy:   avg=11.34  median=12.0  solved_within_12=12%  failures=88
normal: avg=6.25   median=6.0   solved_within_12=100% failures=0
hard:   avg=6.07   median=6.0   solved_within_12=100% failures=0
expert: avg=6.06   median=6.0   solved_within_12=100% failures=0
```

Expert slightly edges Hard on this set via the larger minimax pool (500 vs 100). Easy remains clearly weakest.

## Godot note

Avoid calling `make_guess()` many times in a row on Expert Archmage in tests without `register_feedback` between calls — minimax is expensive. UI smoke uses zero bot delay and short paths.
