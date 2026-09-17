# G02 playtest handoff — FX-CARGO factions, cargo and construction

**Status:** AWAITING_HUMAN (do not start T049)  
**Scenario:** FX-CARGO · **Seed:** 202  
**Tested revision:** `90c0d6511bbff7163a1d88b267cd83a2f2259bba`  
**Save slot:** `g02_playtest` · recovery: `_recovery`

## Launch (verified on this host)

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g02.sh --direct
```

Portrait default **450×800** (native Linux Godot 4.4.1). Economy is a **bounded collapsible** top-right panel (toggle **Economy ▾ / ▸**). Movement pad, Observe/✦, Wait and the bottom action bar stay clickable.

## Playable world (fresh launch)

- Three linked rooms: **Warehouse Yard** (`node:1`) → **Blocked Way** (`node:2`) → **Construction Staging** (`node:3`)
- Visible/inspectable: **Timber Warehouse**, **Hauler Cart**, exit toward the road; staging has **Construction Site**
- G01-style automatic exits and linked arrival poses preserved

## Manual checklist (normal simulation commands — not `run_fx_cargo()`)

| Step | How | Expect |
| --- | --- | --- |
| Inspect | Open Economy panel; approach warehouse/cart | Stocks + cart id/node; labels **Timber Warehouse** / **Hauler Cart** |
| Start delivery | Economy → **Start delivery** | Cart `en_route`, cargo aboard (reserved from warehouse) |
| Block route | Economy → **Block**, then **Wait** | `delivery=blocked_route`; cart `blocked` at `node:1`; goods stay aboard (no teleport) |
| Clear + resume | Economy → **Clear**, then **Wait** twice | Cart resumes `node:2` then `node:3` / `arrived`; staging store gains goods |
| Construction | Keep **Wait**-ing after delivery | Settlement commits at staging once costs are local; Economy shows construction/order fields |
| Faction + tech | Watch Economy after full seat rounds | `turn` / `round` / `seat`; tech draft active + pick results under `last_seat` / tech lines |
| Save/load | **Save** while cargo aboard, **Load** | Same cart node, cargo lots and quantities |

**Experience question:** Can you see why goods and construction are delayed?

Reply `G02 PASS — <build/commit>` or `G02 FIX_REQUIRED — <symptom>`.

## Automated evidence

- `python3 tools/run_scenario.py --fixture FX-CARGO --seed 202 --record Pack/DuelMasterBattle_Build_Pack/tracking/gates/G02/fx_cargo_record.json` — PASS
- `python3 -m pytest tests/integration/test_construction_cargo.py` — includes Interact start/block/clear path
- `python3 tools/check.py --gate G02` — cumulative Python + packet files + G02 pointer smoke + G01 smoke/playable/bridge
- Godot `run_g02_smoke.gd`: real `g02_shell`, pointer pad move, Wait click (+1 turn), block/resume/save

## Screenshots (actual gameplay capture dimensions)

| File | Captured size |
| --- | --- |
| `screenshot_450x800.png` / `screenshot_wizard.png` | **450×800** |
| `screenshot_720x1280.png` (desktop-clamped alias of `screenshot_720x1011.png`) | **720×1011** |
| `screenshot_1280x720.png` | **1280×720** |
| `screenshots/warehouse_cart.png` | **450×800** |
| `screenshots/blocked_route.png` | **450×800** (`delivery=blocked_route`) |

**Not claimed as human gate PASS.**
