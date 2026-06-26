# Python Prototype

Pure rules, encounter catalog, bots, and a minimal tkinter UI. **Godot is the primary playable client.**

## Run tests
```bash
cd python_prototype
python3 -m pytest -q
```

Key modules:
- `duel_mastermind/duel_ruleset.py` — `DuelRuleset` model
- `duel_mastermind/encounters.py` — Blue Apprentice, Thorn Adept, Mirror Mage, Archmage Duel
- `duel_mastermind/game_state.py` — `SequentialDuelGame(ruleset, bot_seed=42)`
- `duel_mastermind/candidate_gen.py` — ruleset-driven candidate codes + opening guess

## Run prototype (tkinter)
```bash
cd python_prototype
python3 run_prototype.py
```

Note: tkinter app may still reflect older fixed 4/12 API; use Godot for encounter select and full wizard UI.

## Flow (Godot — authoritative UX)
1. Main menu → choose encounter → **Start duel**
2. Set secret from **secret magic pool** → **Cast pattern**
3. Alternate attacks from **attack magic pool** (human first)
4. Result → **New duel** or **Back to menu**

## Evaluate bots
```bash
cd python_prototype
python3 scripts/evaluate_bots.py          # 100 secrets, Archmage ruleset per difficulty
python3 scripts/evaluate_bots.py --quick  # 8 secrets
```

## Regenerate shared fixtures
```bash
cd python_prototype
PYTHONPATH=. python3 tests/generate_fixtures.py
```
