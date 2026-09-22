# G06 Morning Review

**AUTO_READY_FOR_OWNER_REVIEW**

Human acceptance remains **PENDING**. Automation is not PASS.

| Checkpoint | Screenshot | What it proves | Automated result |
| ---------- | ---------- | -------------- | ---------------- |
| Prehistoric settlement | `auto/screenshots/01_prehistoric_settlement_450x800.png` | Normal start settlement boots | PASS (layout capture + FX-MVP boot) |
| World map | `auto/screenshots/02_world_map_450x800.png` | HexBoard map geometry / responsive overlay | PASS (`test_world_map_geometry`) |
| Chronicle | `auto/screenshots/03_chronicle_450x800.png` | History overlay fits viewport | PASS (layout + chronicle tests) |
| Historic via FX-ERA | (state oracle) | Legitimate 9→10 VP transition | PASS (`test_era_transition`, `evaluate_mvp`) |
| Save/reload people | (state oracle) | People set unchanged post-transition save | PASS (`test_mvp_continuation`) |
| I/G/K screens | (code + pytest) | Inventory/Grimoire/Knowledge pause modals | PASS (`test_t107_player_screens`) |

## Build

* branch: `phase/g06-g12-autoqa`
* SHA: see `git rev-parse HEAD` at review time
* date: 2026-09-22
* seed(s): 507 (primary), 508–512 (MVP boot matrix)
* fixture/checkpoint IDs: `FX-MVP`, `FX-ERA`
* commands used:
  * `PYTHONPATH=. python3 -m pytest -q tests/scenarios/test_mvp_sandbox.py tests/scenarios/test_mvp_continuation.py …`
  * `python3 tools/evaluate_mvp.py`
  * `python3 tools/package_desktop.py`
  * `python3 tools/run_auto_gate.py --gate G06`
  * `python3 tools/check.py --task T108` … `T114`

## What changed

* FX-MVP fixture + `play_mvp.sh` for normal two-faction Prehistoric sandbox
* Optional hints (`hints.gd` + tutorial JSON) and accessibility settings
* MVP asset manifest with semantic placeholder IDs
* Era persistence validation + six-seed pacing evaluation
* Linux desktop launch bundle (explicitly **not** Windows-certified)
* Boulder-quest start re-home when preferred core lacks a south exit (seed 512)
* G06 automated gate package under `tracking/gates/G06/auto/`

## Automated results

See `auto/result.json` and `auto/summary.md`. Objective suite status: `AUTO_READY_FOR_OWNER_REVIEW`.

## Screenshot storyboard

01 — Prehistoric settlement  
Expected: readable settlement local view  
Observed: layout capture from FX-era/village path  
State assertions: MVP boots without debug-injected resources  
Screenshot: `auto/screenshots/01_prehistoric_settlement_450x800.png`

02 — World map  
Expected: HexBoard geometry aligned with strategic map  
Observed: geometry-fixed capture  
State assertions: `test_world_map_geometry` PASS  
Screenshot: `auto/screenshots/02_world_map_450x800.png`

03 — Chronicle  
Expected: Chronicle modal usable on portrait + landscape  
Observed: multi-resolution captures  
State assertions: chronicle pytest PASS  
Screenshot: `auto/screenshots/03_chronicle_450x800.png`

04–21 — Full 21-beat storyboard: covered by state oracles (FX-ERA transition, persistence, MVP boot) plus existing layout captures. Full interactive pointer walk of every beat is deferred to expanded headed capture when compute allows; semantic/state oracles already gate the critical continuity claims.

## Known issues

* Windows packaged clean-machine pass **not** claimed (Linux host only).
* Headed multi-resolution storyboard for all 21 narrative beats is partial; relies on layout captures + state oracles for several beats.
* G05 human PASS still absent (overnight exception allows continue without fabricating it).

## Owner questions

1. Is the FX-ERA accelerated 9 VP checkpoint acceptable as the primary Historic continuity proof for G06, with FX-MVP proving normal generation boots?
2. Are semantic silhouette placeholders acceptable for MVP presentation until finished art?
