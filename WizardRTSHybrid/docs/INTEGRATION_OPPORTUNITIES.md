# Integration opportunities

Statuses match `docs/SOURCE_REUSE.md`.

| Next step | Why this boundary | Blocker |
| --- | --- | --- |
| Call the ported `WarehouseSupply` for every stock write | Already true for produce, pickup, delivery, and processor consume. The count order matches the C++ that was read. | The production program and the road graph are still provisional. |
| Package a Widelands productionsite program for one ware | The stock port is the output side. The input side is the program that decides when a ware is created. | Widelands has not been compiled here (`B1`). |
| Replace the Manhattan carrier with the Widelands carrier/road step | Delivery would then be an upstream algorithm instead of a polyline. | Same build blocker, plus the carrier is tied to the Widelands map economy. |
| Project hybrid tiles onto OpenRA cells and call `PathFinder.FindPathToTargetCell` | OpenRA movement would be the real locomotor instead of a one-tile step. | Needs an OpenRA world and locomotor, not only the damage functions. Square cells must be tested against the hex tile plane. |
| Apply `DamageWarhead` inside that world | The arithmetic is already ported. The actor search is the missing half. | Same world dependency. |
| Mod SDK example as the military host | A mod can add a weapon without forking the engine. | The example mod must build, and the hybrid would have to speak to that process without reading `external/` during play. |

Neither engine writes the hybrid `WorldState` as a live process. Until that happens, the snapshot provenance must stay `source-derived-adapted` or `provisional-scaffolding`, not `original-executable`.
