# Phase 2 recovery tasks

Recovery pass after Phase 1 acceptance. Each task is one focused change. Do not widen a task into the next one. Game code changes start at P2R-01. P2R-00 is documentation only.

The live record of progress is [PHASE_2_FIX_LEDGER.md](PHASE_2_FIX_LEDGER.md).

## P2R-00 — Recovery ledger

Create this file and `docs/PHASE_2_FIX_LEDGER.md`. The ledger records current task, status, last good commit, files changed, tests run, known blocker and next task. No game code changes.

## P2R-01 — E17A always uses John

Fix only the test-session player identity. A headless E17A boot must confirm the normal player/John setup is used. Do not touch dialogue, NPCs or layouts.

## P2R-02 — Missing NPC graphics get geometric fallbacks

One generic fallback: if an NPC sprite/resource is unavailable, render a rectangle/circle/label rather than nothing. No asset creation. A deliberately missing sprite must take a visible placeholder path without a resource failure.

## P2R-03 — Fix E17A visible NPC names

Keep internal IDs `a`, `b`, `c` and so on. Story binding depends on them. Display meaningful roles (Miner, Distiller, Reeve, Storekeeper, …). The fixture currently stores visible names `"A"`, `"B"`, and so on.

## P2R-04 — Fix E17A dialogue silence

Do nothing else. Dialogue exists in `dialogue.json`. Add one focused test that interacting with the correct opening NPC/node returns non-empty turns, diagnose why it currently does not, and make that test pass. Do not improve the writing.

## P2R-05 — Increase settlement canvas size only

Do not change placement algorithms yet. Existing limits are 25×19–31×23 for steadings and 33×25–45×33 for towns. Increase them substantially and update structural tests. Success: the larger map generates deterministically and existing reachability tests still pass.

## P2R-06 — Built-up core and outer landscape

Civic buildings, most housing and processing stay inside a central settlement area. A substantial outer band is reserved for work landscape. A generated layout must be able to identify built-core versus outer-work area, and most houses must no longer sit on the map boundary.

## P2R-07 — Open navigation

Main exits connect clearly to the centre. Production zones get simple branches off those routes. Avoid maze generation. Keep or strengthen the flood-fill test so every important interaction point remains reachable. Prefer broad, simple roads over clever procedural streets.

## P2R-08 — Wood production dressing only

Wood production controls deterministic tree/copse density in its outer work sector. Higher wood production must produce more tree placeholder features than lower production. No other resource type.

## P2R-09 — Grain/field production dressing only

Grain production creates correspondingly larger or more numerous field strips/crop placeholders. Simple monotonic test: more grain production means more field representation.

## P2R-10 — Pasture production dressing only

Pasture/sheep working landscape using placeholder fencing and open pasture markers. Density derives from production strength.

## P2R-11 — Ore/mining dressing only

Mining strength controls rock/mining representation and mine entrances. A weak mining settlement gets a modest mine area; a strong one gets a visibly larger, more intensive zone. Keep it geometric.

## P2R-12 — Clay/hill production dressing only

The equivalent for clay pits and brick production. Nothing else.

## P2R-13 — Worker housing and camps

Spread the canonical housing sensibly around the built area. Add deterministic worker-cottage/camp placeholders near major production zones where useful. Do not modify canonical population or economy state just to create scenery.

## P2R-14 — Flavour Crossing spaces

Do not resize or redesign Crossings. Add only terrain/resource-specific placeholder dressing so a forest crossing, mining crossing, field crossing and so on are visibly distinct. Preserve navigation as far as practical.

## P2R-15 — Final structural regression

Run the three canonical cases first, then the broader deterministic sweep. Check determinism, reachability, profile correspondence, E17A basic usability and test-session state restoration. Do not launch the game. Return the manual cases and stop.
