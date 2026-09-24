# G06 Morning Review

**AUTO_READY_FOR_OWNER_REVIEW**

Human acceptance remains **PENDING**. Automation is not PASS.

| Checkpoint | Screenshot | What it proves | Automated result |
| ---------- | ---------- | -------------- | ---------------- |
| Prehistoric settlement | `auto/screenshots/01_prehistoric_settlement_450x800.png` | FX-MVP normal start settlement boots | PASS (headed capture + state JSON) |
| Inventory modal | `auto/screenshots/02_inventory_450x800.png` | Inventory overlay opens on MVP shell | PASS (headed + metadata) |
| World map 450×800 | `auto/screenshots/03_world_map_450x800.png` | HexBoard map overlay fits portrait | PASS (`expected_modal=world_map`) |
| Chronicle 450×800 | `auto/screenshots/04_chronicle_450x800.png` | Chronicle modal fits portrait | PASS (`expected_modal=chronicle`) |
| World map 1280×720 | `auto/screenshots/05_world_map_1280x720.png` | Responsive landscape map | PASS |
| Chronicle 1280×720 | `auto/screenshots/06_chronicle_1280x720.png` | Responsive landscape chronicle | PASS |
| World map via button | `auto/screenshots/07_world_map_via_button_450x800.png` | FX-ERA panel button / invoke opens map | PASS |
| Historic after Wait | `auto/screenshots/08_historic_after_wait_450x800.png` | Legitimate 9→10 VP FX-ERA Wait → Historic | PASS (`era=historic`) |
| Post-save | `auto/screenshots/09_post_save_450x800.png` | Save after Historic | PASS |
| Post-reload | `auto/screenshots/10_post_reload_450x800.png` | Reload continuity | PASS |
| State oracles | (pytest / evaluate_mvp) | MVP boot matrix, persistence, geometry | PASS (see `auto/result.json`) |

## Build

* branch: `phase/g06-g12-autoqa`
* SHA: see `git rev-parse HEAD` at review time
* date: 2026-09-23
* seed(s): 507 (primary), 508–512 (MVP boot matrix)
* fixture/checkpoint IDs: `FX-MVP`, `FX-ERA`
* commands used:
  * `python3 tools/run_headed_storyboard.py --gate G06`
  * `python3 tools/auto_visual_gate_report.py --gate G06`
  * `python3 tools/run_auto_gate.py --gate G06`
  * `python3 tools/evaluate_mvp.py`

## What changed

* FX-MVP fixture + `play_mvp.sh` for normal two-faction Prehistoric sandbox
* Optional hints (`hints.gd` + tutorial JSON) and accessibility settings
* MVP asset manifest with semantic placeholder IDs
* Era persistence validation + six-seed pacing evaluation
* Linux desktop launch bundle (explicitly **not** Windows-certified)
* Headed auto-gate storyboard via `auto_gate_driver.gd` + per-shot JSON metadata
* G06 automated gate package under `tracking/gates/G06/auto/`

## Automated results

See `auto/result.json`, `auto/summary.md`, `auto/visual_report.json`. Objective suite status: `AUTO_READY_FOR_OWNER_REVIEW`. Visual evidence status: see `auto/visual_report.md` (montage `auto/montages/g06_storyboard.png`).

## Screenshot storyboard

01 — Prehistoric settlement (FX-MVP)  
Screenshot: `auto/screenshots/01_prehistoric_settlement_450x800.png` · meta: `.json`

02 — Inventory  
Screenshot: `auto/screenshots/02_inventory_450x800.png`

03–06 — World map / Chronicle at 450×800 and 1280×720 (FX-ERA)  
Screenshots: `03`–`06` under `auto/screenshots/`

07 — World map via FX-ERA panel control  
Screenshot: `auto/screenshots/07_world_map_via_button_450x800.png`

08 — Historic after Wait  
Screenshot: `auto/screenshots/08_historic_after_wait_450x800.png`

09–10 — Save / reload continuity  
Screenshots: `09_post_save_450x800.png`, `10_post_reload_450x800.png`

## Known issues

* Windows packaged clean-machine pass **not** claimed (Linux host only).
* Top-bar settlement labels can overlap cosmetically on compact portrait (owner polish).
* G05 human PASS still absent (overnight exception allows continue without fabricating it).

## Owner questions

1. Is the FX-ERA accelerated 9 VP checkpoint acceptable as the primary Historic continuity proof for G06, with FX-MVP proving normal generation boots?
2. Are semantic silhouette placeholders acceptable for MVP presentation until finished art?
