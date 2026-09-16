# C04 — Board, ownership and construction

Source: GDD §§24–30, 78–81, 99–107. Files below are logical paths resolved through the repository map.

## Services and records

| Class / file under `sim/dmb/` | Public methods | Owns / reads |
|---|---|---|
| `HexBoard` / `world/board.py` | `adjacent_nodes(node)`, `touching_hexes(node)`, `distance(a,b)`, `edge(a,b)` | Immutable topology; no ownership writes |
| `BoardBuilder` / `world/generation.py` | `generate(seed, faction_count) -> SetupPlan`, `validate_setup(plan)` | Setup topology, seeded terrain/tokens and placements |
| `PlacementRules` / `construction/placement.py` | `can_road`, `can_settle`, `can_city`, `can_upgrade_legacy` | Pure predicates over topology/current owners |
| `BuildingService` / `construction/buildings.py` | `create`, `damage`, `repair`, `upgrade_in_place`, `destroy` | Building identity, health/definition/slots; C07 lease routing |
| `ConstructionService` / `construction/orders.py` | `quote(action)`, `reserve_order`, `commit_delivered`, `cancel` | Order state and settlement records; uses StockLedger |
| `ScoreService` / `construction/scoring.py` | `score(faction_id)`, `scores()`, `check_threshold()` | Derived VP only |

`ConstructionOrder`: id, faction, action enum, target node/edge/building, staging store, required goods, reservation IDs, delivered quantities, planned definition, expected ownership version, status, created turn, completion receipt. Statuses: planned, sourcing, in_transit, ready, committed, cancelled, blocked. A blocked order retains reason and cargo; it cannot debit again on retry.

## Geometry and initial placement

Build a radius-2 axial region (19 hexes). Construct shared integer corner coordinates, then deduplicate nodes and undirected endpoint-sorted edges. A correct complete radius-2 board has 54 nodes and 72 edges. Validate reciprocal adjacency and max three touching hexes per node; never use floating-point approximate equality to merge corners.

Terrain counts: Woodland 4, Clay Mountains 3, Ore Mountains 3, Fields 4, Grazing Land 3, Desert 2. Number multiset: 2,3,3,4,4,5,5,6,6,8,8,9,9,9,10,10,11,11,12. Seeded assignment persists for the world lifetime. Desert has a number and industrial production; it yields no Catan good.

Use deterministic backtracking for two distance-legal core sites per starting faction; two factions in MVP, six in the full baseline. Starting core pairs must include a cross-terrain industrial route and a productive non-blocked site after the three initial hazard placements. Prefer access to diverse Catan goods across each pair without inventing guaranteed free imports. Bound generation to 100 attempts, then use a checked-in validated fixture board for that faction count. Record attempts and fallback in development diagnostics.

Each initial core gets basic centre/warehouse, primary slots and three factories plus one feasible processor route. Assign primaries to distinct adjacent terrains before duplicates. Give the C00 starter goods, two carts and one legal road per core once, with setup receipt IDs. Neutral staging stores are not settlements. No initial army. Do not repeatedly search until a faction gets hidden economic bonuses.

## Catan production and scores

Matching roll grants each touching current or legacy operational settlement 1 good, city 2, at its node warehouse. Map woodland→timber, clay→brick, ore→ore, fields→grain, grazing→wool. Any catastrophe on that hex suppresses its grant; depleted industrial balance does not. Roll 7 grants nothing; no robber/discard. A missing/destroyed warehouse cannot receive spendable stock; record suppressed grant reason rather than creating invisible storage. Rebuilding restores future grants.

Current-era settlement 1 VP, city 2 total. Legacy unupgraded site 0 VP. No piece caps or road/army/technology VP. A city's primary flow doubles; primary slot count does not. Recompute after centre creation/destruction, city/legacy upgrade and transition.

## Placement and delivered costs

New settlement: empty node, no adjacent active settlement regardless of owner/era, own-road endpoint connection. Inert collapse ruins never count. A hostile node prevents extending a road through it. Wizard travel and military movement need no road. Road construction may stage at a connected road endpoint reachable from an owned warehouse; the cost arrives there through real carts.

| Action | Cost paid at |
|---|---|
| Road: 1 timber, 1 brick | Connected staging store |
| New settlement or legacy upgrade: 1 timber, 1 brick, 1 wool, 1 grain | Target node store |
| City: 2 grain, 3 ore | Owned current-era target |
| Extra processor/replacement industrial building: 1 timber, 1 brick, 1 ore | Target warehouse |
| Repair: 1 brick, 1 ore | Target warehouse |
| Replacement cart: 1 timber, 1 brick, 1 ore | Home warehouse (I03) |

Commit only after all required goods are delivered, ownership/legality is revalidated and the costs are reserved to this order. One atomic debit creates/upgrades the complete baseline facility set; no animation timer or second charge. Insufficient or remote unshipped goods return a blocked quote, not a negative balance. Prepaid costs for cancelled orders return to available stock at their actual accessible node; goods still on carts follow C05.

Baseline civic/building max health is a new tunable: centre 500, warehouse 300, other industry 200, multiplied once by building era. Damage scales usable industrial capacity linearly. Repairs restore full health for the one delivered repair cost. Ruins from political collapse have no building health or collision.

## Destruction and continuity

Centre loss removes settlement ownership/score, leaves surviving industrial structures inactive/unowned, and revalidates shipments. It does not capture the node. Those real surviving structures retain health/collision and can be claimed/repaired through a legal rebuild. Existing owned roads remain until explicitly destroyed or their faction collapses. Destroying a road edge breaks transport routes.

Warehouse destruction records loss of its spendable/reserved/escrow goods exactly once; goods already aboard carts are unaffected. Building destruction displaces living workers. Worker deaths require a separate explicit event. A faction losing its last centre dissolves; C11 handles organisations and displaced people. All cross-system consequences carry the original entity/cause IDs.

Tests cover geometry counts, seeded setup/fallback, all token mappings, two touching settlements sharing a roll, desert industrial eligibility, legacy scores, missing warehouses, ordered simultaneous winners, cargo-only build funding, rebuild legality and different treatment of stranded structures versus inert collapse ruins.
