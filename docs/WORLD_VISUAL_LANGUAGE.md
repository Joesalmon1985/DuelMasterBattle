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

**Industrial resources** use catalogue display names and a separate muted-green family so they are never confused with Catan goods.

## Labels

- Prefer shapes + short labels when near/focused.
- No permanent “North path” spam.
- No raw `node:29` / `unit:3` in ordinary play (dev layers may show IDs).

## Layers

Normal play: shapes communicate road vs trail, loaded cart, working people, factory progress, soldiers fighting, hazard diamond.

Developer overlay may toggle Topology / Roads / Logistics / Industry / Military / Hazards with IDs and meters.
