# G03 playtest handoff — FX-INDUSTRY (per-connection carriers)

**Status:** AWAITING_HUMAN  
**Scenario:** FX-INDUSTRY · **Seed:** 303  
**Candidate implementation:** `f37ffe1ceee75209015fd1016e78bf9c74935ce4`
**Platform tested:** Linux 6.8, Godot 4.4.1  
**Save slot:** `g03_playtest` (isolated from G01/G02)

## Why this resubmission

Joe returned `G03 FIX_REQUIRED — replace the single touring worker with
understandable carriers for individual production connections.`

This candidate:

- Derives **five real directed connections** from installed routes/recipes only
  (2 raw inputs + 3 processed outbound). No invented factory tours.
- Assigns **per-connection carriers** that carry one resource, deliver, then
  return empty on that same leg.
- Scales carrier count from throughput with documented
  `VISUAL_CARRY_CAPACITY_PER_SEC=0.01` and `MAX_CARRIERS_PER_CONNECTION=3`.
- Keeps production accounting in Python; path block / physical obstruction are
  presentation-only and must not change rates.
- Labels sources, processor inputs/outputs, factory unit types, resource
  markers (text/symbol), empty returns, factory progress, and completed units.

## Installed connections (seed 303)

| Kind | From → To | Resource | Throughput | Carriers |
|------|-----------|----------|------------|----------|
| raw_input | woodland → hearth | Foraged berries and nuts | 0.030/s | 3 |
| raw_input | ore → hearth | Flint | 0.030/s | 3 |
| processed_output | hearth → heavy | Stone-ground berry paste | 0.050/s | 3 |
| processed_output | hearth → line | Stone-ground berry paste | 0.030/s | 3 |
| processed_output | hearth → skirmisher | Stone-ground berry paste | 0.020/s | 2 |

Snapshot: `connections_snapshot.json`. Contract: C06 / C09 carrier section.

## Launch

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g03.sh
```

Default viewport is portrait 450×800. Linux menu: `bash tools/playtest.sh`.
Windows: `Playtest.bat` → option **1**.

## Joe's visual checklist

1. **Separate input carriers** — berries and flint each have their own labelled
   carriers on woodland→hearth and ore→hearth (not one shared tour).
2. **Real legs only** — every loaded trip follows a row in the table above;
   no woodland→factory or factory↔factory hops.
3. **Empty returns** — carriers return empty on the same connection (distinct
   from loaded trips); they do not teleport or visit other factories.
4. **Output activity** — paste carriers on hearth→factory legs scale with
   allocated flow and stop when that flow stops (strike / damage / inputs).
5. **Path obstruction** — stand in a path or **Block worker path** → that
   carrier stops/detours; factory rates stay unchanged.
6. **Strike** — affected production → 0; **Clear strike** restores it.
7. **Factory meters** — progress bars and Assembly unit counts match Python
   (leave unpaused ≥100 Game Time seconds → Skirmisher=1, Line=1, Heavy=1).
8. **Save/Load** — carrier identities and factory progress survive via
   `g03_playtest`.
9. **Perf** — added carriers must not reintroduce G02 stutter; G01–G03
   automated checks remain PASS.

Also: tap a building for incoming/outgoing connections + bottleneck in plain
language. **Hide Industry inspector** to see the village; Pause freezes carriers.

## Automated evidence

- `fx_industry_record.json` — PASS at 100,000 ms; three unit types; finite 590.
- `connections_snapshot.json` — five real connections + capacity tunables.
- Captures: `before_production.png`, `after_unit_production.png`,
  `worker_path_blocked.png`, `damaged_bottleneck.png`, `strike_stopped.png`,
  plus `screenshot_450x800.png` / `screenshot_wizard.png`.
- `python3 tools/check.py --gate G01|G02|G03` — automated PASS (G03 still human-pending).

## Human acceptance

Reply `G03 PASS — <build/commit>` or `G03 FIX_REQUIRED — <symptom>`.
Only Joe's explicit PASS clears this gate. T059 remains blocked.
