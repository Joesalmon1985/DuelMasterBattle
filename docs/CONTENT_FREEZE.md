# Content freeze

Decision D33 (owner, 14 October 2026): the imported content roster is frozen permanently. No new buildings, units, wares, items, liquids or cards from Widelands, OpenRA, Mindustry or any other game. Fixing, completing, rebalancing, re-costing, re-arting and speeding up any entity on the roster continues, and so does adding mechanics (orders, policies, commands) that use existing entities. The development priority is autonomous faction play by hierarchical neuroevolution (`docs/PLAN_HIERARCHICAL_NEUROEVOLUTION.md`, `docs/EXECUTION_PLAN_NEUROEVOLUTION.md`).

## What is frozen

The roster `roster-1.0.0`, recorded in `WizardRTSHybrid/wizard_rts/data/content_freeze.json` (generated, committed):

| List | Count | Source |
| --- | ---: | --- |
| entities | 582 | `content.graph.entities()` |
| of which buildings | 486 | 206 Widelands, 25 OpenRA, 252 Mindustry, 3 hybrid |
| of which units | 96 | 42 OpenRA, 50 Mindustry, 4 hybrid (`unit:*` ids) |
| generated cards | 168 | `content.graph.generated_cards()`; four eras of 42 |
| hand-written cards | 33 | `tech.cards()` (legacy draft) |
| Widelands wares | 128 | `wl_defs.defs()["wares"]` |
| Mindustry items | 22 | `data/mindustry_defs.json` |
| Mindustry liquids | 11 | `data/mindustry_defs.json` |
| excluded entries | 99 | `coverage.build()` rows with status `excluded`, including the 11 OpenRA decoy buildings (D27) |

The manifest also records the sha256 of the seven raw data files (`widelands_defs.json`, `openra_rules.json`, `mindustry_defs.json`, `mindustry_full.json`, `mindustry_overrides.json`, `tech_cards.json`, `terrain_defs.json`; line endings normalised), the three pinned upstream commits from `sources/manifest.json`, and `roster_sha256` over the seven id lists. Every run manifest, model file and checkpoint of the training programme records `roster_version` and `roster_sha256`.

## How it is enforced

* `WizardRTSHybrid/tests/test_content_freeze.py` (fast, no world) fails with the ids named when anything is added or removed, an excluded entity becomes playable, a data file changes, a source pin moves, or an importer runs without the unfreeze switch.
* Every `scripts/import_*.py` exits with code 3 and prints "content is frozen" unless `DMB_UNFREEZE=1` is set and `--reason "<text>"` is given (`wizard_rts/freeze_guard.py`).
* Importers are kept as the provenance record; they are not deleted.

## Checking

```
py -3 WizardRTSHybrid/scripts/freeze_content.py --check
py -3 -m pytest WizardRTSHybrid/tests/test_content_freeze.py -q
```

## Changing the roster (a bump)

A bump is a deliberate act. It needs the owner's approval and a written reason. A bump must never remove or rename an id, because saved games hold definition ids as strings (a removal is allowed only as a recorded compatibility exception with the reason below). Then:

```
py -3 WizardRTSHybrid/scripts/freeze_content.py --bump minor --reason "..."
```

This regenerates the manifest, raises `ROSTER_VERSION` in `wizard_rts/freeze.py` and appends a dated row to the table below. Models and checkpoints record the roster version, so a bump makes old models "incompatible" by rule (plan section 10.4), never silently reused.

## Changelog

| Date | Roster version | Reason | Count changes |
| --- | --- | --- | --- |
| 2026-10-14 | roster-1.0.0 | First freeze (D33), measured on the merged v4 tree | 582 entities, 168 cards |
