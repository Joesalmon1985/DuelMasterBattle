# Ward Duel presentation leak evidence

Regression: `godot_project/client/tests/run_ward_duel_presentation.gd`

Fixture: FX-MVP seed 507 — travel west/north to `cube:1`, open retained Ward Duel, return.

| Shot | Meaning |
|---|---|
| `01_before_encounter_*` | World presentation visible before challenge |
| `02_clean_ward_duel_*` | Ward Duel only — no rocks/signs/labels/workers |
| `03_returned_world_*` | World restored after Continue |

Resolutions: 450×800 and 1280×720.

Human aesthetic PASS is not claimed; structural assertions + these shots support owner review.
