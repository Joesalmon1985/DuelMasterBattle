# P0 defect ledger — current-main polish

**Source HEAD at ledger:** `9c66ce00342698dc2900c9f7b03c18101221f799`  
**Baseline pytest:** 471 passed, **15 failed** (matches audit comparison count at start)  
**Status:** `BASELINE_RECORDED_WITH_DEFECTS`

## Current pytest failures (owning phase)

| Test | Observed | Owner |
| --- | --- | --- |
| test_t027_buildings::test_content_loads_and_catalog_validates | Catalogue size / validation vs stale expectations | P4 |
| test_t027_buildings::test_baseline_facility_set_and_six_units | Expects six total unit defs; catalogue has era archetypes | P4 — fix test to era contract, do not shrink catalogue |
| test_t059_units::test_unit_belongs_to_at_most_one_formation | Setup double-forms already autoformed units | P4 |
| test_t061_movement (5) | ValueError already in formation from manual setup | P4/P6 |
| test_t067_military_ai::test_no_unobserved_enemy_strength_in_features | Setup fails before hidden-info assertion | P5/P6 |
| test_t073_responders (3) | Formation setup / treatment path | P6 |
| test_t078_village_projection::test_required_exits_reachable | Full-world projection exit expectation | P2/P7 |
| test_t090_sluice | Archived FX-VILLAGE sluice missing | P7 — scope archived fixture |
| test_t095_village_panel | Same archived fixture | P7 |

## Integration defects R01–R13

| ID | Evidence | Reproduction | Normal reachable? | Owner |
| --- | --- | --- | --- | --- |
| R01 | EXECUTED | dispatch overwrites state.rng with stale WorldSim.rng after production advances state | Yes (Wait) | P1 |
| R02 | EXECUTED | WorldState.to_dict omits research/tech_draft/diplomacy | Yes (save) | P1 |
| R03 | EXECUTED | FX-MVP tech_draft empty; era hands discarded by interrupt cleanup | No initial draft | P1/P5 |
| R04 | SOURCE | Tech modifiers not consumed by capacity/HP producers | Research only | P5 |
| R05 | SOURCE | TurnRunner lacks resolve_placement call | Initial cubes only | P6 |
| R06 | EXECUTED | hazard_treat falls through to generic proposed | Decision without effect | P6 |
| R07 | SOURCE | LocalBattle RefCounted added as Node in g05 | Battle record yes; host broken | P6 |
| R08 | SOURCE | Hostility ignores diplomacy; obs key mismatch | Contact yes | P5/P6 |
| R09 | SOURCE | Trade proposals without accept/dispatch orchestration | Proposals yes | P3 |
| R10 | SOURCE | Trained policies not selected; observation gaps | Heuristic only | P5 |
| R11 | EXECUTED | 15 pytest failures | — | P0–P7 |
| R12 | IMAGE | Label clutter (historical G11) | Yes | P2 |
| R13 | SOURCE | Capture report is file existence | Harness | P0 |

## Toolchain

- Python 3.12.3 (Linux)
- Godot pin recorded 4.4.1 at `/home/joe/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64`
- Windows handoff reports 4.5.1 — recorded, not silently upgraded this run
