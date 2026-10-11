# Mindustry — provenance and research notes

Status: **research notes only. Nothing from Mindustry is implemented, imported, or pinned yet.** Written 11 October 2026, documentation-only; no upstream clone was made in this session.

## What is recorded

| Item | Value |
| --- | --- |
| Official source repository | `https://github.com/Anuken/Mindustry` |
| Language / build | Java; Gradle |
| Licence | GPL-3.0 (stated in the upstream repository; verify the `LICENSE` file and per-directory notices at the pinned revision) |
| Pinned revision | **NONE YET.** The implementation agent chooses a release tag or commit at least two weeks old, records the full SHA in `sources/manifest.json` (`id: mindustry`) and in `docs/SOURCE_REUSE.md`, and clones into `external/mindustry` via `scripts/setup_external.*`. |
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
