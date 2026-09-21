# G05 long-run report — FX-LONG-WORLD

- Fixture: `FX-LONG-WORLD` mode=`long_world`
- Seed: `507`
- World turns advanced: **200** (cap 200)
- Game Time: `0` → `200000` ms
- Settlements: 4 → 4
- Cities: 0 → 0
- Roads: 4 → 5
- Units: 0 → 24
- Determinism (two runs, same seed): **PASS**

## Major event counts

- `ROAD_BUILT`: 1
- `SETTLEMENT_FOUNDED`: 0
- `CITY_UPGRADED`: 0
- `UNIT_PRODUCED`: 24
- `BATTLE_STARTED`: 1
- `BATTLE_ENDED`: 1
- `CART_DEPARTED`: 0
- `CART_DELIVERED`: 0
- `FORMATION_MOVED`: 6
- `FORMATION_CREATED`: 8
- `CASUALTY`: 6
- `HAZARD_PLACED`: 0
- `OUTBREAK`: 0

## Units produced by faction

- `faction:1`: 12
- `faction:2`: 12

## First military encounter

- **Turn 93** — `battle:1` at `node:23`
- Participants: `unit:1..3` (faction:1) vs `unit:4..6` (faction:2)
- Formations: `formation:1` and `formation:2` met in the field (not seed-forced)
- **Turn 94** — outcome `wipe`; 6 casualties (all participants)

## Stagnation flags

- `no_cart_activity` — cargo hauls between warehouses still rare; AI often
  `cargo_scheduled` without a remote source that can cover the full missing set
  in one reservation. Not faked.

## Design findings (do not auto-balance)

1. **No new settlements / cities in 200 turns.** Legal settlement candidates are
   frequently blocked by `adjacent_settlement` / goods placement rules. This is a
   design/economy question, not silently patched.
2. **Single-terrain cores** cannot run two-terrain MVP recipes. Implementation
   fallback: local renewable+finite craft (`recipe.local.{terrain}`) so every
   starting settlement can muster units. Confirm whether Joe wants this retained
   or prefers multi-terrain core bias in generation.
3. **Cart logistics** remain a soft spot — construction sometimes stalls on
   `insufficient_local_goods` without a successful inter-warehouse haul.

## Chronology (abridged)

- Turn 3: **ROAD_BUILT** — `command:6`
- Turn 90: **UNIT_PRODUCED** ×12 + **FORMATION_CREATED** ×4
- Turn 91–92: **FORMATION_MOVED**
- Turn 93: **BATTLE_STARTED** — `battle:1` @ `node:23`
- Turn 94: **CASUALTY** ×6 + **BATTLE_ENDED** (wipe)
- Turn 180: second production wave + new formations

## Checkpoints

- `turn_000_start`: turn=0 roads=4 settlements=4 units=0
- `first_road_built`: turn=3 roads=5 settlements=4 units=0
- `first_unit_produced`: turn=90 roads=5 settlements=4 units=12
- `first_formation_move`: turn=91
- `first_battle_start`: turn=93
- `first_battle_end`: turn=94 (wipe)
- `final_state`: turn=200 roads=5 settlements=4 units=24

Schematic previews (not GPU screenshots): `long_run/schematic_turn_000_start.png`,
`long_run/schematic_final_approx.png`, `long_run/first_battle_note.txt`.
