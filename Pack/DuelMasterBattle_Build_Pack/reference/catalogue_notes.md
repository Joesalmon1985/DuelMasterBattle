# Catalogue provenance and normalization

The original `source/cross_terrain_resource_recipes.xlsx` is included unchanged. It was retrieved by its exact filename from the earlier catalogue. The 240 recipe rows were extracted from its Recipe Catalogue sheet; 48 raw definitions come from Raw Resources. Building families, unique building names, unique outputs and original recipe IDs are retained.

The controlling v0.3 GDD uses **Foraged berries and nuts** where the workbook says **Berries and nuts**, and **Phosphate fertiliser** where it says **Phosphate**. The normalized JSON uses the GDD names and records the original names. The workbook's Futuristic era maps to the stable internal ID `future`. Repeated display names across eras do not merge IDs.

The workbook's Gameplay role column is preserved only as provenance. It does not add population food, upkeep, construction wares or new mechanics. All processor outputs are eligible for the GDD's baseline military supply. The reference data is input to the future compiler; it is not evidence that runtime import or balance has been implemented.

MVP: 15 renewable/renewable cross-terrain pairs plus Woodland renewable + Ore Mountains finite per implemented era, 16 each in Prehistoric/Historic. Full baseline: every 60-per-era combination, 240 total. Culture access remains complete; the MVP enablement manifest is separate.
