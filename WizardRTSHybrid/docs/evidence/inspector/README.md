# God Mode technology inspector: proof (13 Oct 2026)

Headed run through real GUI clicks (`godot_project/client/tests/run_hybrid_god_inspector.gd`; `WizardRTSHybrid/scripts/run_headed_suite.sh inspector`, sim started with `HYBRID_PROFILE=developer HYBRID_CARDSET=v2`):

| file | shows |
| --- | --- |
| `01_inspector_open.png` | the overlay opened by the "Tech inspector (I)" button, 137 cards from the simulation |
| `02_unit_facing_east.png`, `03_unit_facing_west.png` | the Tank card with the facing buttons pressed: the real Red Alert sprite turns |
| `04_building_idle.png`, `05_building_working.png` | a Widelands chain card (Deeper Coal Mine + Smelting Works, barbarians): idle sheet and the imported working animation (smoke) |
| `06_missing_art_filter.png` | the "missing/placeholder art" filter (6 cards: hybrid buildings and Prehistoric units that still borrow another picture) |

Server-free proof (every card's preview resolves to a real texture, facing/state/turret change the picture, the filter equals the Python list): `run_hybrid_inspector.gd`, wrapped in `tests/test_mix_crypto.py`.
