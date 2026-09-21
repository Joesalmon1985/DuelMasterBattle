# G05 — Full Prehistoric world + G01–G04 visual layers

**Status:** AWAITING_HUMAN  
**Stop point:** T096 — do **not** start T097 / G06  
**Foundation commit:** `85fca3c` (topology preserved)  
**Play (normal):** `bash tools/play_g05.sh` — seed **507**, FX-VILLAGE  
**Play (layers demo):** `bash tools/play_world_layers.sh` — FX-WORLD-LAYERS  
**Branch:** `refactor/canonical-ontology-g05`

## Human acceptance

> Starting inside a real settlement, I can walk the board **and** see G01–G04
> systems living in that same world: time, carts, industry, soldiers, hazards,
> and a simple world map — without a separate demo scene for each gate.

## What this pass adds (on top of 85fca3c)

| Layer | Visible now |
|-------|-------------|
| G01 | Turn / Game Time HUD; Travel destination toast; M = world map (pauses) |
| G02 | Cart presenter (faction + cargo pips); construction scaffolds; warehouse goods remain distinct from industry |
| G03 | Factory meter bars; worker carry pips; processor recipe in overlay data |
| G04 | Geometric soldiers (△■●); catastrophe diamonds; Challenge → retained duel |

Quest content remains **archived** (`FX-VILLAGE-QUEST`). No active quest.

## Evidence

- Audit: `docs/review/G01_G04_FULL_WORLD_VISUAL_AUDIT.md`
- Visual language: `docs/WORLD_VISUAL_LANGUAGE.md`
- Board map: `board_map.md`
- Layer previews: `layers_start_settlement.png`, `layers_battle_node.png`, `layers_world_map.png`
- Tests: `tests/sim/test_g05_visual_layers.py` + full-world suite

## Known limitations

- Local battle lease host (in-area fighting animation) is still thinner than
  standalone `g04_battle_shell` — soldiers and READY battle state exist; full
  LocalBattle mount on Travel-into-battle is the next polish item.
- World map node positions are schematic (not true axial node placement).
- Headless Godot cannot capture GPU frames; packet uses schematic previews.

Agents cannot self-PASS G05.
