# Bot difficulty tuning

Evaluation script: `cd python_prototype && python3 scripts/evaluate_bots.py`

## Difficulty levels

| Level | Behaviour | Minimax guess pool cap |
|-------|-----------|------------------------|
| Easy | Random guesses (ignores feedback) | — |
| Normal | Candidate elimination + deterministic random pick | — |
| Hard | Minimax over capped candidate pool | 100 |
| Expert | Minimax over larger candidate pool (strongest responsive bot) | 500 |

Expert is **not** claimed to be mathematically optimal. Pool caps keep Godot responsive during enemy attack phase.

## Validation set

- Default: **100** deterministic secrets (`master_seed=42`, `generate_validation_secrets`)
- Quick smoke: `python3 scripts/evaluate_bots.py --quick` (8 fixed secrets)

## Sample results (100-secret run, seed 42)

```
easy:   avg=11.34  median=12.0  solved_within_12=12%  failures=88
normal: avg=6.25   median=6.0   solved_within_12=100% failures=0
hard:   avg=6.07   median=6.0   solved_within_12=100% failures=0
expert: avg=6.06   median=6.0   solved_within_12=100% failures=0
```

Expert slightly edges Hard on this set via the larger minimax pool (500 vs 100). Easy remains clearly weakest.
