# Plan: God World on natural terrain, with living village networks

**Owner brief:** "God World: natural terrain and living village networks" (24 Oct 2026), pasted into the session; it supersedes the earlier PRD
(`docs/GOD_WORLD_PRD.md`) where they conflict (section 1 of the brief). **Base:** `feature/god-world` at `45ff228f`. **Ledger:** `docs/ledger/GOD_WORLD_PROGRESS.md`
(section "Living world"). **Decisions:** D42 to D47 in `docs/DECISION_REGISTER.md` section 8. The brief's screenshot was not attached to the session; the
headed captures of `45ff228f` (`docs/evidence/god_world/headed/`) are the regression reference instead.

## 1. What the brief asks, in one paragraph

Keep the working Catan layer (roles, odds, costs, legality, AI, 10-VP ages, carry-over) and give it a real landscape: the logical 30/80/109 graph laid onto
an adapted Widelands map with winding roads, villages that grow as balanced mixed networks (capacity, not `pips x level` copies), workers and carriers with
real tasks and routes, age-appropriate hubs, modern cargo vehicles and conveyors, causal future processing/water/unit-production chains, correct
scale/facing/depth, upstream planning and logistics reused through constrained adapters, and all of it built autonomously in normal play.

## 2. Improvements to the brief (what this plan does differently, and why)

1. **One validated automatic embedding with an override file, not a hand-authored one.** The brief prefers an authored first embedding; authoring 80 plots
   and 109 corridors by hand is the slowest and least reproducible path. `god_world/embedding.py` relaxes the regular layout onto buildable plots
   (searching the board's scale and offset for the least displacement and the fewest chords over water), routes every corridor by A* over passable
   tiles clear of other plots, repairs crossings, and validates the lot. The result is deterministic, checked in (`data/god_world/embedding_<map>.json`)
   and testable; terrain edits and overrides are recorded fields on the same file if a map ever needs them.
2. **Geometry per map, dressing per world.** Node plots, corridors, catchments and the coast depend only on the map and the board shape. Work sites and
   woodland depend on the seed's resource roles, so they are computed when a world attaches its map (`embedding.dress`), never saved as geometry.
3. **One local-operations engine for all four ages, data-driven.** Instead of four separate systems (Widelands programs, OpenRA trucks, Mindustry belts,
   Mindustry fluids) the village runs one engine of sites, typed buffers, agents with routed tasks, directional segments (roads for carriers and trucks,
   belts and pipes for packets) and processors with recipes. The age's data decides which art, which recipes, which transport. Reuse is at the level of
   behaviour and data (Widelands worker programs and tree lifecycle in `programs_data.py`, Mindustry recipes from the pinned `Blocks.java`, the Widelands
   AI's proximity scoring, OpenRA's facing conventions), with provenance recorded per symbol, not by booting the old `HybridWorld`, the Mindustry engine
   or a native server.
4. **Capacity is a budget, and the budget is explicit.** `capacity = pips x level` per district becomes a planner budget in "station-equivalents"; the
   planner spends it on producers, support, processing and transport by a recorded cost table. Nothing in it writes back to the strategic ledger.
5. **The hub by age is data.** `god_catan_v1.json` names the hub art per age and per level; the primitive hub is composed from existing imported pieces
   (a barbarian timber hut with drawn stockpiles and baskets) rather than a new bitmap, which keeps the content freeze intact and the perspective
   consistent. If the owner wants an authored primitive sprite later, the data slot is there.
6. **Sequencing by what the player sees first.** Terrain and roads first (every view changes at once), then one complete early village with real
   workers and facing fixed, then the age chains, then the planner's generalisation and save/load. Each stage ships through the ordinary Watch the
   World route, verified headed, with the strategic corpus rerun to prove the rules did not move.

## 3. Stages

| Stage | Deliverable | Evidence |
| --- | --- | --- |
| A Terrain | Map choice (Egyptian Mandala v1.2: 60 % contiguous land, mountains and lakes; The Big Lake is half water and fragmented), `embedding.py`, the checked-in embedding, board positions in tiles, journeys along corridors, bank caravans to the coast, natural terrain rendering with the logical overlay optional, picking by catchment. | `test_god_world_embedding.py`; the corpus unchanged; headed whole-map and close views with and without the overlay. |
| B Villages | `local_ops.py` (sites, buffers, agents, tasks, routes), `planner.py` (capacity budget, dependency order, scored placement, bottleneck relief), age-1 and age-2 chains (woodcutter, forester, sawmill; quarry, mason; hunter; reed farm; mines, smelting), the hub by age, carriers to the hub, facing from motion, render profiles. | tests of capacity, tasks and conservation; headed village at ages 1 and 2; a tracked log. |
| C Industry | Age-3 trucks between yards and the command centre; belts with spacing and backpressure; silicon smelter and ground factory fed by belts and a lead delivery; pump, conduit, tank and cultivator; the future hub (core); unit factory recruitment within the garrison quota. | tests of belts, recipes, shortage and recovery; headed modern and future villages. |
| D Generalisation | Every village built by the same planner in normal play; age renovation at carried sites; save/load of jobs, cargo, buffers, segments; strategic invariance test (local detail on or off: same dice, balances, VP). | corpus; `test_ac` invariance; headed age boundary before/after. |
| E Polish | Calibration fixture, depth sorting with footprints, effects by state, performance on a populated map, phone checks when a device is available. | measurements in the ledger. |

## 4. Invariants (never broken by any stage)

- The strategic ledger is the only spendable economy. Local goods are operating units in their own buffers; no API converts them to a hand.
- Rolls credit one token per settlement and two per city per matching region, whatever the village looks like.
- The local layer reads strategic state (roles, level, age, events) and never writes it. Local blocking cannot change receipts or VP.
- Local randomness is its own seeded stream; the dice and the faction AI are untouched by rendering, zoom, culling or local congestion.
- Save/load preserves every local job, cargo, buffer and segment with stable ids; arrivals and completions are idempotent.
- The graph is the rule: a corridor's shape never adds or removes an adjacency; a crossing never makes a node.
