# G04 — Battles, wizard power and catastrophe

**Status:** AWAITING_HUMAN  
**Candidate commit:** (filled on T076 commit)  
**Platform:** Linux (Windows launcher wired but not executed on this host)

## What to play

1. FX-BATTLE — walk as wizard among labelled Red/Blue units; cast destroy/buffs without army orders.
2. FX-HAZARD — three adjacent demon hexes with treatment eligibility cues and outbreak warnings.

## Save isolation

- Battle: `g04_battle`
- Hazard: `g04_hazard`
- Terminal destructive tests: `g04_hazard_terminal` (separate from G01–G03 slots)

## Automated evidence

- `python3 tools/check.py --task T076`
- `python3 tools/check.py --gate G04`
- Scenario records: `fx_battle_record.json`, `fx_hazard_record.json`
- Screenshots under this directory and `screenshots/`

## Experience question

Do intervention and competing threats feel powerful and readable?
