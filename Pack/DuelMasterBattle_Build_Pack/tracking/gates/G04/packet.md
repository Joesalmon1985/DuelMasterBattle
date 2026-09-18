# G04 — Battles, wizard power and catastrophe (Interaction Repair)

**Status:** AWAITING_HUMAN  
**Repair:** R01–R08 (G04 Interaction Repair Brief)  
**Started from:** `d265f6005c621dcd9b0d60348590e07083d9e312`  
**Candidate:** `d30df58e565c9dbc3a78c7f20c18f96ab50b4869`  
**Platform:** Linux 6.8, Godot 4.4.1 (Windows **not** run on this host)

## What changed

- One-owner FX-BATTLE (Red settlement + Blue invaders); safe spawn; paced armies
- Target-first Observe / Buff… / Destroy choice cards — **no permanent spell toolbar**
- Two-tile range validated against synchronised local/moving poses
- Field-aware view merge (omit ≠ empty); external actors not freed by people rebuild
- Three boundary hazard manifestations; Challenge opens C10 Mastermind (4/6/10)
- Channel×3 shortcut **rejected**; treatment ledger persists across Wait/save/load
- Automated playable path no longer forces `queue_destruction` or Channel wins

## Reset (required before judging)

See [reset.md](reset.md). Delete isolated slots `g04_battle`, `g04_hazard`, `g04_hazard_terminal` so an old fixture save does not obscure the repair.

## Launch

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g04_battle.sh
bash tools/play_g04_hazard.sh
```

Portrait default 450×800. Landscape: `bash tools/play_g04_battle.sh --resolution 1280x720`

## Joe checklist

Use the table in [gates/G04.md](../../gates/G04.md). Decisive proof is walking up to a moving soldier, clicking, choosing a spell, seeing a persistent result — then the equivalent observe/Challenge flow on a visible hazard. **Do not accept G04 merely because automated checks pass.**

## Automated evidence

```bash
python3 tools/check.py --gate G04
```

Result on this handoff host: PASS (Python cumulative + G04 playable + G01–G03 smokes). Captures refreshed under this folder (450×800 and 1280×720).

## Known limits

- Windows playtest not executed on Linux
- Dense melee labels may overlap cosmetically
- Spellbook overlay can intercept chrome Wait clicks; smoke prefers HUD Wait / signal path

## Stop

`current_task = STOP_FOR_G04`. **T077 remains NOT_STARTED.** Agent must not mark G04 PASS.
