# Decisions

> **Direction update 2026-10-11.** The approved game direction is `docs/DuelMasterBattle_Design_v0_5.md` (decisions `docs/DECISION_REGISTER.md`; real status and gaps `docs/CURRENT_STATUS_AND_GAPS.md`). Where this file mentions a 20 by 20 hex world, two factions, or "do not implement Mindustry", it is superseded. Kept unchanged below as evidence.

## D1 — Hex ownership is cube_round, not a 48 by 48 square

Question: how does one tile plane assign every tile to one hex of a 20 by 20 map?

Alternatives: an exclusive axis-aligned 48 by 48 square centred on each hex; a second collision grid; `cube_round` of the tile center with the largest rounding error kept on z.

Evidence: squares centred on hexes overlap and leave gaps, so they cannot be an ownership map. `tests/test_coords.py` checks one owner, full coverage, a walkable step between edge neighbours, and that the boundary function does not consult collision.

Rejected: the 48-square map. Settlement layout may still use a 48-tile local scene inside a hex footprint. That footprint is the owned tile set.

Reopen if a test shows a tile with two owners or a gap.

## D2 — Source-derived ports until an upstream binary is a dependency of play

Question: how should the first economy and military experiments land?

Alternatives: call the Widelands and OpenRA processes during play; paste upstream sources into the hybrid; port the smallest tested functions and label them.

Evidence: Widelands is GPL-2.0-or-later and must not be pasted as GPL-2-only. OpenRA compiled and its engine tests passed, but `PathFinder.FindPathToTargetCell` needs the OpenRA world, locomotor, and actor map. The hybrid snapshot records `source-derived-adapted` for stock and damage, and `provisional-scaffolding` for carrier routes and soldier steps.

Rejected: naming a DuelMasterBattle cart or formation after either engine. Both engines are not one game until an economic behaviour and a military behaviour from those implementations write the same `WorldState`.

Reopen when a packaged upstream library or process performs the warehouse update or the warhead without the hybrid reading `external/` at runtime.

## D3 — Local TCP is process separation, not netplay

Question: how does Godot see the Python world?

The server is newline JSON on `127.0.0.1`. One process owns the world for its lifetime. A dropped client must not kill the process. The clean-environment test rejects any connect that is not loopback and any `open()` under `external/`.

## D4 — One display scale per art family

Question: how should Widelands and OpenRA sprites share the 64px tile plane?

Terrain stays 1:1 with the tile. Widelands buildings and trees use scale 2 with the source hotspot as the ground contact. Workers use scale 4 so a carrier frame is near the wizard's height. OpenRA buildings and units use scale 3 so a barracks and a tank read next to those buildings. This pin has no Barbarian sawmill, so the plank building is the Empire sawmill.

Reopen if a headed shot shows a building floating or a unit larger than the warehouse.

## Hybrid rules (2026-10-10)

- OpenRA refineries, harvesters, credits and power are removed. Barracks, war factory and turret keep their units but cost Widelands wares (hybrid-defined costs in `construction.py`).
- Recruitment: rifleman = 1 ax (Widelands barbarians/barracks consume=ax, 30 s), tank = 2 granite + 1 plank (hybrid). Goods must be delivered by road; a barracks with no goods builds nothing.
- Mines do not consume rations yet (food chain pending). Hidden mine/smelter workers are not modelled as entities.
- Each faction starts with headquarters stock (12 logs, 6 planks), as Widelands start conditions do.
- Construction sites request their build cost over roads and complete after 20 s with no builder worker (scaffold).
- God Mode and AI must use the same world commands (`build`, `road`, `queue`, `move`, `order`, `demolish`). God Mode suppresses the free-unit provisional AI for the controlled faction only.
- Walking speed: one tile per 600 ms for workers; OpenRA unit speeds 760/570 ms per cell.

## D5 — Square-grid terrain on Widelands rules (2026-10-10, approved by Joe)

Question: how does Widelands terrain, resources and construction fit this tile world?

Decision: every tile is one terrain node on a square grid with four-direction movement (`wizard_rts/grid.py`). The hex ownership overlay (`coords.py`, D1) is kept only for the legacy flat world and the player's hex label, and is no longer the territory rule when terrain is on. `HybridWorld(terrain=False)` or `HYBRID_TERRAIN=0` keeps the old flat world so the pre-terrain tests still run; terrain is the default.

Source-derived: terrain classes (arable, mineable, walkable, water, unwalkable, unreachable), fertility, humidity, temperature, valid and default resources (`data/world/terrains`, imported by `scripts/import_widelands_terrain.py`); resource types and maxima (`data/world/resources`); tree growth probability (`terrain_affinity.cc`); the shape of the buildcaps rules in `Map::calc_nodecaps_pass1/pass2` and `calc_buildsize` (nothing buildable on water, beach or unwalkable ground; a mine only where the node is entirely mineable; slope 3 limits to small, slope 4 forbids).

Differences from Widelands, not an exact reproduction:
- Adjacency: 4 neighbours (building size also reads the 8 surrounding tiles) instead of 6.
- Distances: Manhattan on paths, Chebyshev for radii; a Widelands radius covers a different set of nodes.
- Triangles: a node holds one terrain; Widelands has a right and a down triangle per node and decides passability from six triangles.
- Elevation: a byte per node; slope is the largest height difference to the 8 neighbours. Height does not change walking speed.
- Building spaces: each building occupies one tile; Widelands big buildings also occupy the nodes to their left and above. Neighbouring buildings do not shrink each other's size.
- Road geometry: roads are tile paths, not flag-to-flag edges; there are no flags as objects.
- Water has no depth in Widelands. Shore distance (`depth`, shallow within 2 tiles) is our engineering addition.
- The generator (`mapgen.py`) is ours: noise, six stamped homelands, a central sea joined to the six lakes by channels.

Reopen if a terrain-mode test needs hex geometry, or if imported Widelands maps (`.wmf`) require the six-neighbour layout to look right.

## D6 — Training interface, civilian-only Widelands economy, construction priority (2026-10-11)

- `sim_api.HybridEnv` is the training seam: factions in `agent_factions` act only through `step(actions)`; the built-in AI (`world.ai_factions`) plays the rest. Actions are the God Mode commands, validated by the simulation (`check_placement` is the dry run behind the masks). Observations are plain dicts; rewards are deltas of wealth, territory, kills and losses (`world.fstats`) with configurable weights. Determinism, pickle save/restore and replay-by-hash are tested. No Gymnasium or PettingZoo dependency; no learner is shipped.
- Widelands military is deprecated, not deleted: the AI no longer builds a tribe barracks (`ai.BUILD_WL_BARRACKS = False`); it plans only the weapon and armour chain, and the OpenRA barracks every faction starts with takes the tribe's soldier wares (`construction.recipe_for`). Existing soldier code and tests stay until the OpenRA path covers the same loops.
- Construction sites are served before production inputs in `logistics.scan_requests_and_outputs`: otherwise the sawmill takes every log and no new building is finished. The AI places a site when the warehouse has the cost or when the shortfall is a base ware (log, plank, granite) its own producers make (Widelands sites request and wait).
- Woodcutters are placed beside trees and foresters beside woodcutters (`ai._place_near` policies). Lumberjacks fell any grown tree (they had only felled beech since species were added: a bug found by the 60-minute peace run).
- The event log is a bounded window (6000 kept 3000) so long headless runs do not grow without limit.
- Tribe soldier wares with an honest fallback (D6b): an OpenRA barracks first asks for its tribe's soldier wares (`recipe_for`). If its queue head waits `TRIBE_PATIENCE_MS` (25 game minutes) the barracks switches to the hybrid ax recipe (`tribe_fallback` flag, event, row field) so every faction can field infantry while the stalled tribe chains (Amazon rare trees, Atlantean spidersilk and iron, Frisian fur) are completed. Still goods-fed: nothing is free. A 60-minute peace run: Barbarians recruit from minute 15, the other four tribes from minute 25-30.

## D7 — Command centres, MCV expansion, territory (2026-10-11, from Joe's first playtest; branch `feature/hybrid-playtest-fixes-v03`)

- A faction's first **warehouse is its immobile command centre**: a building may only be placed inside the square (Chebyshev) build area of one of the faction's command centres (`territory.py`, `construction.check_placement`). Home radius 34 tiles.
- The OpenRA **war factory builds an MCV**: queue item `mcv` (hybrid-defined recipe, `construction.RECIPES`): `log 3, plank 8, granite 5` in total, delivered over roads like every recipe. `plank 6, granite 4` make the vehicle; `log 3, plank 2, granite 1` are loaded on it as a starter kit. The production start moves the whole recipe out of the factory's stock (the economy totals agree), deployment moves the kit into the new store. Nothing is created on the way.
- **Deploy** consumes the MCV once and creates a command centre (a warehouse in the simulation, Construction Yard art) with a 16-tile build area. Deployment rules (`territory.deploy_check`, reasons reported in this order): the separation rule against EVERY centre (friendly and enemy), `Chebyshev distance > radius_new + radius_other + buffer` with buffer 4 (`HybridWorld.cc_buffer`), then map bounds, ground terrain with build caps for the whole 3x3 footprint, trees, roads, units in the way, a free access tile. 16 and 4 are the largest values that still leave a legal corridor between two homes 125 tiles apart.
- Outposts are logistics islands: roads join a building to its own centre, carriers work there, wares are never moved between islands. The AI gives each centre its own small plan (`ai.OUTPOST_PLAN`) paid from that centre's store.
- Unit orders (queued recruits, the MCV) outrank standing demand in `logistics.scan_requests_and_outputs`, after construction sites: with the sawmill's standing request first, logs never reached the factory (the economy is log-starved: warehouse logs are 0 for the whole game).
- OpenRA land buildings have real **footprints** (`construction.GROUND_FOOTPRINT`: war factory 3x2, barracks 2x2, command centre 3x3 with the door tile at the bottom middle). Roads and carriers use the door tile; units leave through the row in front of it.
- Destruction: `lifecycle.begin_destruction` at 0 HP (production, queue and deliveries stop, `destroyed` flag), 4 s of Widelands fire, then `purge_building`. Wizard fire magic and combat share this path.

## D8 — Interaction labels, fire magic, deterministic AI budgets, AI structure (2026-10-11)

- Wizard Mode labels reuse `WorldInteractionLabel` and `WorldInteractionResolver` unchanged (same semantic contract). A click on any entity opens its label: description at a distance, the choice "Burn it with fire magic" within 3 tiles. Fire is a command by stable id (`magic.fire`), range checked by the simulation from the authoritative player tile, and uses the same lifecycles as combat (D7).
- Presentation never feeds back into the simulation: the motion layer in `hybrid_art.gd` only glides pictures towards authoritative tiles. Snapshots from the server are deltas for static things (trees, rocks), `entity_ids` and the full tree list are sent only on request.
- Determinism rules found the hard way: never iterate a `set` of strings to make a decision (hash salting differs per process: `cc_ids` is an insertion-ordered dict; `tests/test_determinism.py` runs two processes under different `PYTHONHASHSEED`s through an expansion); never use wall-clock budgets in the simulation (route searches are budgeted by count per quantum, `military.PATH_SEARCHES_PER_QUANTUM`, `JOIN_SEARCHES_PER_QUANTUM`, fair rotation of who gets them).
- AI (`ai.py`): per-settlement economies, MCV expansion, supply-bottleneck response (`_bottleneck_step`), navy planned ahead of the one-site gate (it never started behind it), squads with retreat and retargeting, guard posts on the approach to each centre, targets limited to enemy buildings it has seen (home capitals are public; the army sees what it walks past), attack delay 12 minutes (was 20). Decisions are events (`ai_*`) that are also counted per faction in `world.fstats`, which survive the bounded event window.
