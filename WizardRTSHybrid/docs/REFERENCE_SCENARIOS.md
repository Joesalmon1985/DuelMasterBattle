# Reference scenarios

Comparison tests use the invariant, not the upstream tick rate, cell shape, or numeric balance. Original-engine observations are recorded only when that engine was actually run. Widelands has not been launched. OpenRA's engine tests ran; a skirmish was not played. Hybrid results below are from `tests/test_world.py` unless noted.

## Widelands

| # | Scenario | Invariant | Allowed difference | Hybrid evidence |
| --- | --- | --- | --- | --- |
| 1 | Extraction | A source gains one unit of a raw good. | The good name and the program duration may differ. | Producer adds one `log` every 10 economy quanta. `stats.produce` increases. Not a Widelands productionsite. |
| 2 | Production and consumption | An input good is removed and an output good is added. | Recipes and times may differ. | Processor removes one warehouse `log` and adds one `plank` when the log is present. |
| 3 | Warehouse storage | Stored counts change only through the warehouse list, and the economy total moves with them. | The container type may differ. | `tests/test_widelands_stock.py`. Add updates the economy then the list. Remove does the opposite. |
| 4 | Carrier delivery | The source loses one unit and the destination gains that same unit. | Road geometry may be hexagonal. | `move_good` does that transfer. Blue still delivers while the red road is blocked. |
| 5 | Missing input | Production does not invent the missing good. | The stall signal may differ. | Processor emits `shortage` and does not create a plank when the warehouse has no log. |
| 6 | AI economy without the player | Stocks change while the player sends no orders. | The AI module may differ. | `advance()` with no pose change still produces and delivers. The scheduler is provisional, not the tribe AI. |

## OpenRA

| # | Scenario | Invariant | Allowed difference | Hybrid evidence |
| --- | --- | --- | --- | --- |
| 1 | Move order | A unit's cell changes along a path and does not pass through a blocked cell. | OpenRA cells are square; the hybrid plane is tiles owned by hexes. | Soldiers step onto an in-map unblocked tile. This is provisional movement, not `PathFinder`. |
| 2 | Path around an obstacle | The path reaches the goal without entering a blocked cell. | The pathfinder may differ. | A step onto `world.blocked` is refused. There is no A* search. |
| 3 | Target acquired | An attack starts only against a chosen target. | Range and acquisition rules may differ. | The two soldiers attack only when Manhattan distance is 1. |
| 4 | Weapon damage | HP falls by the modified damage and never leaves `0..max`. | The damage number may differ. | `warhead_damage(4, [], 100)` then `inflict_damage`. Versus 100 leaves the raw value. |
| 5 | Unit destroyed | HP at or below zero is no longer a live unit, and further damage does not apply. | Death animation may differ. | `alive` becomes false. A later hit does not change 0 HP. |
| 6 | AI military action | Units act while the player sends no orders. | The bot may differ. | `advance(120_000)` moves and attacks with no pose commands. The decision rule is provisional. |

## Hybrid extras

- Twenty hex crossings keep one `world_id`, the same entity ids, and `game_ms == 0` when no advance is sent. Pose updates alone do not advance time.
- A duel pause yields zero quanta. One resolve clears or keeps the hazard. A second resolve is idempotent and does not change stocks.
