# G07 Morning Review — AUTO_READY_FOR_OWNER_REVIEW

**Gate:** G07 — All eras and repeated historical cycles  
**Status:** `AUTO_READY_FOR_OWNER_REVIEW`  
**Human acceptance:** PENDING — do **not** invent `PASS` or `accepted_by`  
**Overnight policy:** continuation to T133+ permitted without equating automation to PASS

## Candidate

- Branch: `phase/g06-g12-autoqa`
- Fixture: `FX-CYCLE` (seed 1212) — Godot storyboard boots **FX-ERA** parent at seed 1212 (legitimate cycle parent; `play_fx_cycle.sh` reseeds in Python)
- Launch smoke: `bash tools/play_fx_cycle.sh`
- Headed storyboard: `python3 tools/run_headed_storyboard.py --gate G07`
- Auto report: `tracking/gates/G07/auto/result.json`
- Visual report: `tracking/gates/G07/auto/visual_report.json`
- Montage: `tracking/gates/G07/auto/montages/g07_storyboard.png`

## Screenshot storyboard

| Checkpoint | Screenshot | What it proves | Automated result |
|---|---|---|---|
| Cycle prehistoric core | `auto/screenshots/01_cycle_prehistoric_core_450x800.png` | FX-ERA@1212 settlement (FX-CYCLE parent) | PASS |
| Cycle world map 450×800 | `auto/screenshots/02_cycle_world_map_450x800.png` | Board / map overlay | PASS |
| Chronicle pins 450×800 | `auto/screenshots/03_cycle_chronicle_pins_450x800.png` | Chronicle overlay | PASS |
| Cycle world map 1280×720 | `auto/screenshots/04_cycle_world_map_1280x720.png` | Landscape map | PASS |
| Chronicle pins 1280×720 | `auto/screenshots/05_cycle_chronicle_pins_1280x720.png` | Landscape chronicle | PASS |
| Historic core after Wait | `auto/screenshots/06_historic_core_450x800.png` | Prehistoric→Historic via Wait | PASS (`era=historic`) |

Each PNG has a sibling `.json` with era, modal, viewport controls, and semantic IDs.

## Automated evidence

| Suite | Result |
|---|---|
| Full catalogue + Modern/Future tech | PASS |
| Later eras Hist→Mod→Fut + cycles + dystopia path | PASS |
| Pollution/alien/nuclear/machine + mixed hazards | PASS |
| `tools/evaluate_full_world.py` | PASS |
| `tools/profile_world.py` (honest limits) | PASS_WITH_HONEST_LIMITS |
| Headed storyboard + visual validator | PASS (`visual_status`) |

## Owner playtest focus

1. Walk Historic → Modern → dystopian Future at a known place.
2. Pollution cleanup (no duel), alien response, Future nuclear/machine.
3. Future→Prehistoric reseed: living person/quest continuity; no Future army domination.
4. Chronicle pins remain intelligible; six-faction / solo recovery still playable.

## Known limits

- Semantic placeholders only (no art polish).
- Headed storyboard covers FX-ERA@1212 shell + Historic Wait; full Modern/Future/hazard frames remain state-oracle backed (`evaluate_full_world` / scenario tests).
- Profile probe uses 200-unit sample; 10k-unit headless stress not run overnight.
- Utopia pack absent; `next_future_path` defaults/rejects to dystopia.
