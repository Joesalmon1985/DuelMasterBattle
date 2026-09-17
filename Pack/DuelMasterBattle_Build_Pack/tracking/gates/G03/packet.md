# G03 playtest handoff — FX-INDUSTRY

**Status:** AWAITING_HUMAN  
**Scenario:** FX-INDUSTRY · **Seed:** 303  
**Candidate implementation:** `5b6ac03ae477bca40c8dc944d9a54c2d3391682a`  
**Platform tested:** Linux 6.8, Godot 4.4.1  
**Save slot:** `g03_playtest` (isolated from G01/G02)

## Launch

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g03.sh
```

Default viewport is portrait 450×800. `bash tools/playtest.sh` provides the
Linux menu. Windows uses `Playtest.bat`, option 1.

## Joe's ordered check

1. Leave the game unpaused for at least 100 Game Time seconds. Expect one
   skirmisher, one line unit and one heavy unit; each carry returns to zero.
2. Walk onto the worker's horizontal route near the upper trees, or press
   **Block worker path**. Expect the worker to idle/adapt while rates and
   production continue.
3. Press **Damage 25%**. Expect processor health 25/100 and lower rates.
4. Press **Paid repair**. Expect health 100/100 and one brick plus one ore
   consumed. Alternatively use **Strike** then **Clear strike** and observe
   zero then resumed output.
5. Save with a partial carry, walk away, return, and load. Expect the same
   worker person ID/job and the exact saved carry.
6. Keep the window focused and walk with the Industry panel visible, then
   repeat after covering it with **Dev panel**/normal play. Report any
   recurring freeze separately from intentional focus-loss pause.

## Automated evidence

- Production scenario: `fx_industry_record.json` — PASS at exactly 100,000 ms;
  three unit types, finite balance 590, carries zero.
- Rendered captures: `screenshot_450x800.png`, `screenshot_wizard.png`,
  `screenshots/worker_path_blocked.png`,
  `screenshots/damaged_bottleneck.png`.
- G03 sidecar smoke runs the real scene, Python sidecar, 100-second clock,
  damage/paid repair and save/load.
- G01/G02 remain human PASS and their automated regression checks are included
  in the G03 gate wrapper.

## Human acceptance

No human observations are recorded yet. Joe should reply:

`G03 PASS — <build/commit>`

or

`G03 FIX_REQUIRED — <observed behavior and expected behavior>`

Known limitations are in `known_defects.md`; reset instructions are in
`reset.md`.
