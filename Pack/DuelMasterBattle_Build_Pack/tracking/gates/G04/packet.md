# G04 — Battles, wizard power and catastrophe (Reuse Repair + UI/lifecycle repair)

**Status:** AWAITING_HUMAN (FIX_REQUIRED cleared in code; manual retest required)  
**Repair:** U01–U08 + 2026-09-19 spellbook/lease-return defects  
**Branch:** `fix/g04-retained-ui`  
**Base tip before this repair:** `5257b01`  
**Candidate:** working tree on `fix/g04-retained-ui` (spellbook panel + lease Continue; commit when accepted)  
**Platform (automated):** Linux, Godot 4.4.1 pin, Python 3.12  

## What changed (this repair)

- Open spellbook is a **bounded centred panel** (artwork fits inside max width/height); world remains visible around it
- Spellbook sits above D-pad / action / choice chrome; touch HUD hides while open and restores on close
- Persistent Close control; Escape/ui_cancel and outside-blocker click close the book
- G04 Spells page is lean (Destroy / Shield / Attack Speed / Range) without status dump clutter
- Real pointer regression: `run_g04_spellbook_pointer.gd` at 450×800, 720×1280, 1280×720
- Leased hazard result → **Continue** → `_return_to_world`; menu → **Abandon challenge** (not Play again / Restart)
- Lease-return regression: `run_g04_lease_return.gd`
- Prior fixes retained: battle travel cleanup, Ward SpellSlot presses, Mira semantic labels

## Ensemble follow-up (not in this PR)

Commits `58ea2d2` and `6f7be0f` on `BuildPackV03-ensemble-depth-pass` remain separate.

## Reset (required before judging)

See [reset.md](reset.md). Delete isolated slots `g04_battle`, `g04_hazard`, `g04_hazard_terminal`.

## Launch

```bash
bash tools/play_g04_battle.sh
bash tools/play_g04_hazard.sh
```

## Joe checklist (decisive)

1. Open spellbook in G04 battle — bounded panel, D-pad hidden, spells clickable, Close works, Escape closes.
2. Shield → targeting card → world visible → cancel → reopen → Close.
3. Hazard Challenge → finish duel → **Continue** returns to world (no Play again loop); victory removes that cube only.
4. Mid-duel menu offers **Abandon challenge**, not Restart/Quit-to-menu as the lease escape.

**Do not accept G04 merely because automated checks pass.**

## Automated evidence

```bash
python3 tools/check.py --gate G04
```

Includes `G04_SPELLBOOK_POINTER_OK` and `G04_LEASE_RETURN_OK` in addition to prior playable/smokes.

## Known limits

See [known_defects.md](known_defects.md).

## Stop

`current_task = STOP_FOR_G04`. **T077 remains NOT_STARTED.** Do not mark G04 PASS before Joe's retest.
