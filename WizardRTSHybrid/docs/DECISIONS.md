# Decisions

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
