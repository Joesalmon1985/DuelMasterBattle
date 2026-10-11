# Mindustry — provenance and research notes

Status: **pinned, cloned, imported and partly implemented (M2 slice).** Original research notes of 11 October 2026 follow; the section "Pin and what is implemented" below records what the implementation run did (12 October 2026). Nothing is claimed beyond what the named tests exercise.

## What is recorded

| Item | Value |
| --- | --- |
| Official source repository | `https://github.com/Anuken/Mindustry` |
| Language / build | Java; Gradle |
| Licence | GPL-3.0 (stated in the upstream repository; verify the `LICENSE` file and per-directory notices at the pinned revision) |
| Pinned revision | **`v146` = `26b66f9bdbd3a77b32f10f3cb350a9a737d5f012`** (commit date 2023-09-03; the long-lived stable release, well over two weeks old; tags up to v160.7 exist upstream and may be adopted later by changing the manifest and re-running the importer). Original wording: the implementation agent chooses a release tag or commit at least two weeks old, records the full SHA in `sources/manifest.json` (`id: mindustry`) and in `docs/SOURCE_REUSE.md`, and clones into `external/mindustry` via `scripts/setup_external.*`. |
| Compatibility | GPL-3.0 content may be combined with this GPL-3.0-or-later project. Art, sound and any non-code assets may carry separate terms: check at the pinned revision before copying any asset. Placeholder art is acceptable until checked. |

A manifest entry is not an implemented mechanic. Do not describe Mindustry as integrated until a test exercises a behaviour taken from it.

## What the implementation agent must inspect before coding (D06, D16)

At the pinned revision read the actual definitions, not summaries:

1. **Items and ores:** `core/src/mindustry/content/Items.java` (copper, lead, sand, coal, titanium, thorium, scrap, metaglass, graphite, silicon, plastanium, etc.): `cost`, `hardness`, flammability.
2. **Floors/ores and generation:** `content/Blocks.java` (ore blocks, floors such as sand/darksand, vents), and the world generation / ore placement rules (`mindustry.maps.generators` and the `Planets`/sector presets) to decide which terrain yields which ore. Do not assume "pasture thorium": check, then record the mapping in `DECISION_REGISTER.md` S10.
3. **Drills:** `mechanical-drill`, `pneumatic-drill`, `laser-drill`...: `tier`, `drillTime`, size, `hardnessOffset`, formula in `world/blocks/production/Drill.java`.
4. **Conveyors and item transport:** `world/blocks/distribution/Conveyor.java`, `Junction`, `Router`, `Sorter`, `Bridge`, `Unloader`: speed, capacity per tile (4 items), update order and backpressure.
5. **Power:** `world/blocks/power/*` (generators, batteries, nodes), `PowerGraph.java`: satisfaction ratio model.
6. **Liquids:** `world/blocks/liquid/*`, `Liquid`: pipes, tanks, flow, capacity.
7. **Crafters:** `world/blocks/production/GenericCrafter.java` and block definitions (graphite press, silicon smelter, kiln, etc.): consume/produce, craft time, power.
8. **Unit factories and units:** `world/blocks/units/UnitFactory.java`, `Reconstructor`; `content/UnitTypes.java` (dagger, mace, fortress, nova, flare, horizon, risso...): health, armor, speed, weapons, build cost and time, plans.
9. **Tech prerequisites:** `content/TechTree.java` and `SectorPresets`/research requirements: use to seed the card prerequisite graph (S06).
10. **Block build requirements:** `requirements(Category, with(Items.copper, N...))` for each block, used to derive Widelands-goods costs (S11) via a written conversion table.

## How to use the source (and how not to)

- Port **data and compact algorithms** (drill rate, conveyor movement, power satisfaction, crafter timing, unit stats) into Python modules driven by generated JSON, with unit tests comparing results against values computed from the pinned source.
- Do not copy large Java engine classes, the rendering, networking, or the campaign/wave logic. Do not run a Java process in play. Do not create an independent army or economy.
- Record in `SOURCE_REUSE.md` per mechanic: file and symbol, status (`source-derived adapted`/`not implemented`), comparison test, remaining differences.
- Every Mindustry item must exist as a ware in the shared economy, every produced unit must appear in `world.units`.

## Open questions for the implementation agent to answer in writing

- Units: are belt speed/drill time in ticks (60/s)? Map to the sim's quantum with an explicit scale factor and document it.
- How do the first Mindustry machines translate to Widelands goods (S11)?
- Which Mindustry units are first (suggest ground: dagger/mace; air: flare)?
- Art: use a clearly labelled placeholder if asset terms are unconfirmed.


## Pin and what is implemented (12 October 2026)

| Item | State |
| --- | --- |
| Pin | `sources/manifest.json` entry `mindustry` (tag `v146`, full SHA above, GPL-3.0). `scripts/setup_external.sh mindustry` makes a sparse checkout (content, type, world/blocks sources, unit sprites, about 10 MB; `MINDUSTRY_FULL=1` gives a full one). `scripts/setup_external.ps1` walks the manifest and makes a full clone. `scripts/verify_pins.py` checks every checkout against the manifest; `tests/test_mindustry_pipeline.py` runs it. |
| Source read directly | `Items.java`, `Liquids.java`, `Blocks.java`, `UnitTypes.java` (all imported), `Drill.java` (`getDrillTime`: `drillTime + 50 * hardness`, divided by the drill multiplier), `Conveyor.java` (`itemSpace 0.4`, `capacity 3`, `speed` tiles per tick), `UnitFactory.UnitPlan`, `PowerNode` fields (`laserRange`, `maxNodes`), `Battery` (`consumePowerBuffered`). Not yet read in depth: `TechTree.java`, junction/router/sorter, pumps and conduits, reconstructors, effects. |
| Importer | `scripts/import_mindustry_defs.py` → `wizard_rts/data/mindustry_defs.json` (22 items, 10 liquids, 214 blocks that have a `requirements` call, 39 unit types). Original numbers only; ticks converted to seconds in derived fields. `--check` fails if the JSON is out of date. Known simplification: the importer takes one weapon per unit and the first bullet's damage; drill `items_per_second` lists only the items in `DRILLABLE`. |
| Adaptation | `wizard_rts/data/mindustry_overrides.json` (labelled as our decisions): ware map, hybrid construction costs in Widelands goods, extraction rules (D21), unit scales (`hp_scale` 50, `damage_scale` 25, speed and range in RTS cells, mirrored weapons). The registry keeps the upstream cost as `source_cost`. |
| Registry | `wizard_rts/industry/registry.py`. Blocks: mechanical and pneumatic drill, conveyor, power node, battery, combustion generator, solar panel (small, large), silicon smelter, graphite press, ground factory. Unit: dagger. |
| Behaviour (tests) | `tests/test_industry_mechanics.py` (18 tests), `tests/test_industry_slice.py` (4), `tests/test_mindustry_pipeline.py` (17). Rates tested: drill formula, belt speed (8 tiles in about 4.4 s), spacing, backpressure, power satisfaction, battery, combustion fuel, factory plan time. |
| Not implemented | Liquids, pumps and conduits; junction, router, sorter, bridge; plastanium and surge items; reconstructors and other factories; air and naval Mindustry units; thorium and scrap extraction beyond the rule table; drill water boost; warmup; Erekir content. |
| Art and sound | **None imported.** `external/mindustry/core/assets*` is checked out (sprites exist) but the asset terms were not verified (the repository `LICENSE` is GPL-3.0 for the whole tree; per-asset notices were not checked), so every machine, belt and unit is a labelled placeholder drawn by `godot_project/client/hybrid/industry_view.gd` (coloured shapes, "placeholder art" text). Never describe them as upstream art. |
| Runtime | No Java, no second economy, battlefield or clock: the layer runs inside `HybridWorld.advance`. |
