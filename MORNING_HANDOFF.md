# Overnight progress (partial — update at end)

**Branch:** `overnight/g12-visual-training-finish`  
**Started from:** `1aa2205` on `phase/g06-g12-autoqa`  
**Platform:** Windows · Godot 4.5.1 · `.venv\Scripts\python.exe`

## Play tomorrow

```bat
Play Latest Integrated Game.bat
```

Or `Playtest.bat` → **L** (FX-MVP) / **E** (FX-ERA) / **1–3** combat-production / **V/W** visual review.

## Done so far

| Item | Status |
|---|---|
| Ward Duel presentation leak | Fixed + regression + clean screenshots |
| Windows latest launcher | `Play Latest Integrated Game.bat` |
| Auto-gate `python3` portability | Fixed + unit tested |
| Overnight resume runner | `tools/run_overnight_g06_g12.py --resume` |
| G06 | AUTO_READY_FOR_OWNER_REVIEW (regenerated) |
| G07 | AUTO_READY_FOR_OWNER_REVIEW (regenerated) |
| G08 | AUTO_READY_FOR_OWNER_REVIEW (regenerated) |
| In-world visual review | 18 screenshots under G11/visual_review |
| G09 honesty tests | Catch stale COMPLETE (manifest≠eval, 40 seeds, diversity 0) |
| G09 training | In progress (collect 96 seeds) |

## Screenshot roots

- Ward leak: `Pack/.../gates/G11/ward_duel_leak/`
- Visual review: `Pack/.../gates/G11/visual_review/`

## Do not claim

- Human PASS for any gate
- G09 COMPLETE until regeneration finishes with 200-seed eval + diversity

This file is refreshed when the overnight run completes.
