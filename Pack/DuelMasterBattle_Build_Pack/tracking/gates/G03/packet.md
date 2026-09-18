# G03 playtest handoff — FX-INDUSTRY (visual readability repair)

**Status:** AWAITING_HUMAN  
**Scenario:** FX-INDUSTRY · **Seed:** 303  
**Candidate implementation:** (set at commit time — see launch.txt)  
**Platform tested:** Linux 6.8, Godot 4.4.1  
**Save slot:** `g03_playtest` (isolated from G01/G02)

## Why this resubmission

Joe returned `G03 FIX_REQUIRED — industry is not visually understandable`
(one L↔R sweep worker, no workplaces/outputs, path block not visible).
This candidate projects the real FX-INDUSTRY entities as labelled coloured
rectangles, route-based worker activity, factory progress bars, and unit
placeholders. Path obstruction is presentation-only.

## Launch

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g03.sh
```

Default viewport is portrait 450×800. Linux menu: `bash tools/playtest.sh`.
Windows: `Playtest.bat` → option **1**.

## Joe's visual checklist

1. See labelled coloured sites: Woodland source, Ore/Flint source, Cooking Hearth processor, three factories, Assembly yard.
2. Watch the orange worker move between those sites (collecting / carrying / working labels; small carry marker when carrying).
3. Stand in their path (or **Block worker path**) → worker stops or detours with **blocked**; production rates continue.
4. Leave unpaused ≥100 Game Time seconds → one Skirmisher, one Line, one Heavy appear at Assembly with progress bars driven by Python meters.
5. **Set health to 25%** → processor goes red / 25%; rates drop. **Strike** → worker shows on strike; rates 0. **Paid repair** → health 100% and brick+ore cost shown.
6. **Hide Industry inspector** so the village is visible; Pause → worker freezes.

## Automated evidence

- `fx_industry_record.json` — PASS at 100,000 ms; three unit types; finite 590.
- Captures: `before_production.png`, `after_unit_production.png`,
  `worker_path_blocked.png`, `damaged_bottleneck.png`, `strike_stopped.png`,
  plus `screenshot_450x800.png` / `screenshot_wizard.png`.
- `python3 tools/check.py --gate G01|G02|G03` — automated PASS (G03 still human-pending).

## Human acceptance

Reply `G03 PASS — <build/commit>` or `G03 FIX_REQUIRED — <symptom>`.
Only Joe's explicit PASS clears this gate. T059 remains blocked.
