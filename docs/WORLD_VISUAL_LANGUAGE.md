# World visual language (placeholder geometry)

**Status:** Canonical presentation contract for full-world G05.  
Placeholder graphics preferred over inconsistent sprites. Correctness > art.

## Shapes

| Concept | Shape | Notes |
|---|---|---|
| John | Existing wizard visual | Unchanged |
| Person / worker | Humanoid or small upright marker | One Person ID → one actor |
| Cart | Rounded rectangle | Faction accent strip |
| Skirmisher | Triangle △ | Point in facing direction |
| Line soldier | Square ■ | |
| Heavy soldier | Circle / hexagon ● | |
| Hazard cube | Diamond ◆ | One `cube_id` globally |
| Cargo / resource | Small coloured pip | Beside cart or carried by worker |
| Factory progress | Horizontal bar under yard label | Width = Python meter |
| Construction | Outlined / translucent footprint | Real `ConstructionOrder` only |

## Faction colours

One mapping for soldiers, carts, settlement flags, formation markers, and optional road tint:

| Faction seat | Colour | Hex |
|---|---|---|
| faction:1 | Amber | `#D4A017` |
| faction:2 | Steel blue | `#3A6EA5` |
| faction:3 | Leaf | `#3D8B57` |
| faction:4 | Clay | `#B85C38` |
| Neutral / unknown | Grey | `#7A7A7A` |
| Hazard | Magenta | `#B0006E` |

Do not invent alternate faction palettes per subsystem.

## Resource colours (Catan vs industry)

**Catan construction goods** (warehouse / cart cargo):

| Good | Pip |
|---|---|
| Timber | Brown |
| Brick | Terracotta |
| Wool | Cream |
| Grain | Gold |
| Ore | Slate |

# Resource placeholder grammar (industrial carried / ambient)

| Resource cue | Shape | Colour hint |
|---|---|---|
| Berries / nuts | Small circle | Magenta-red |
| Flint / ore | Diamond | Slate |
| Clay | Brown square | Terracotta |
| Water / spring | Blue circle | Blue |
| Grain / food | Yellow marker | Gold |
| Wool / sheep | White marker | Cream |
| Processed good | Outlined hexagon | Muted purple |

Carried markers must derive from the projected `resource_id` / `resource_label`. Never invent a resource for looks.

## Terrain placeholder grammar

| Terrain | Props | Sparse labels |
|---|---|---|
| Woodland | Many ▲ / tree triangles; occasional stump / log stack | One `Woodland`; `… workings` at real primary |
| Clay mountains | Brown irregular patches; pit at real working | `Clay hills` / `Clay workings` |
| Ore mountains | Grey rocks; darker ore shapes; mine at working | `Ore ridge` / `Flint working` |
| Fields | Striped rectangular patches | `Fields` |
| Grazing land | Open green + ambient animal markers | `Grazing land` + collective `Wild sheep` |
| Desert | Bare stones + scrub | `Desert` |

Ambient animals are presentation-only: no durable IDs, quests, or interaction state.

## Labels

- Prefer shapes + short labels when near/focused.
- No permanent “North path” spam.
- No raw `node:29` / `unit:3` in ordinary play (dev layers may show IDs).

## Layers

Normal play: shapes communicate road vs trail, loaded cart, working people, factory progress, soldiers fighting, hazard diamond.

Developer overlay may toggle Topology / Roads / Logistics / Industry / Military / Hazards with IDs and meters.
