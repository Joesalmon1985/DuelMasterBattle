# G04 — Battles, wizard power and catastrophe (Reuse Repair + UI/lifecycle repair)

**Status:** PASS  
**Accepted by:** Joe Salmon  
**Accepted at:** 2026-09-19T22:05:00Z  
**Accepted implementation / build:** `75b7f539aa1916fb6c0a5f156be3efa5184dd7eb`  
**Present on main via merge:** `15eadbd7dd82ebb56167c745e4998f2fa06809fb`  
**Repair:** U01–U08 + 2026-09-19 spellbook/lease-return defects  
**Repair branch (historical):** `fix/g04-retained-ui`  

## Human acceptance

Joe manually tested the final G04 implementation and considers **G04 PASS**.
The merged main tree contains the same accepted implementation.

Progression to **T077 / G05** is authorized.

## What landed (accepted)

- Open spellbook is a **bounded centred panel**; world remains visible around it
- Spellbook sits above D-pad / action / choice chrome; touch HUD hides while open and restores on close
- Persistent Close control; Escape/ui_cancel and outside-blocker click close the book
- G04 Spells page is lean (Destroy / Shield / Attack Speed / Range)
- Real pointer regression: `run_g04_spellbook_pointer.gd`
- Leased hazard result → **Continue** → `_return_to_world`; menu → **Abandon challenge**
- Lease-return regression: `run_g04_lease_return.gd`
- Prior fixes retained: battle travel cleanup, Ward SpellSlot presses, Mira semantic labels
- Retained `game_board.tscn` + `DmbBattleSim` duel path (not Python Mastermind as production)

## Ensemble follow-up (not in this acceptance)

Commits `58ea2d2` and `6f7be0f` on `BuildPackV03-ensemble-depth-pass` remain separate.

## Automated evidence (necessary, not decisive)

```bash
python3 tools/check.py --gate G04
```

## Historical repair notes

Prior FIX_REQUIRED / AWAITING_HUMAN wording described the repair-in-progress and
manual-retest hold. That hold is cleared by Joe's explicit PASS. Useful
observations remain in `known_defects.md`, `acceptance.json`, and U01–U08 /
R01–R08 handoffs.

## Next

`current_task = T077`. Do not reopen G04 without a new FIX_REQUIRED from Joe.
