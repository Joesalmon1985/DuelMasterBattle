# G08 dialogue preview sample

## Branch coverage

### `dead_target` — `dialogue.g08.prehistoric.diplomacy.worker.earth.dead_target.0003`

> [prehistoric/diplomacy/worker/earth] They are gone. Talking about border truces will not bring them back. (3)

Fallback: They have nothing more to add.

### `displaced_target` — `dialogue.g08.prehistoric.military.worker.earth.displaced_target.0004`

> [prehistoric/military/worker/earth] They were displaced. deserters must be handled without their old workplace. (4)

Fallback: They have nothing more to add.

### `full_cycle` — `dialogue.g08.prehistoric.personal.worker.earth.full_cycle.0005`

> [prehistoric/personal/worker/earth] After the cycle, quiet grief remains in living memory, not as a new face. (5)

Fallback: They have nothing more to add.

### `already_world_resolved` — `dialogue.g08.prehistoric.discovery.worker.earth.already_world_resolved.0006`

> [prehistoric/discovery/worker/earth] You arrived late; ruin maps resolved without you. (6)

Fallback: They have nothing more to add.

## Rival samples

- **dialogue.rival.ashen_tactician.sample**: I measure pressure before I strike.
- **dialogue.rival.iron_broker.sample**: Every road has a price; pay it or go around.
- **dialogue.rival.veil_scout.sample**: You will not learn what I choose to hide.
- **dialogue.rival.ember_duelist.sample**: If you want an answer, challenge me cleanly.

## Changed-line preview workflow

1. Open village/debug panel with FX-CONTENT-SAMPLE (seed 808).
2. Select knowledge observer → preview dead/displaced/world-resolved branch.
3. Edit a baseline line in authoring workspace → validate → compile → preview.
4. Export failure bundle from scenario panel into `tracking/village_runs/failure_bundles/`.

