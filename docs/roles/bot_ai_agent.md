# Bot / AI Agent Role

## Responsibility
Legal bots per encounter ruleset; solver with candidate elimination.

## For this project
- `RandomBot(ruleset, seed)`: generate secret from `secret_magic_pool`, guess from `attack_magic_pool`
- `SolverBot(ruleset, ...)`: ruleset-driven candidate set, opening guess from pool, `register_feedback`
- `make_bot(ruleset, seed)` — difficulty from `ruleset.enemy_difficulty`
- Tests: legal guesses in pool; candidate counts per encounter; Archmage 10⁴

## Performance
- Minimax pool caps (Hard 100, Expert 500) for Godot responsiveness
- Avoid repeated `make_guess()` without feedback in Godot tests

## Deferred
- NN production bot (Python experiment only)
- Counterspell / real-time comeback modifiers
