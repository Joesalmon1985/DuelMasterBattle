# G05 known defects

- G05 shell is a Python-backed status/host for FX-VILLAGE; full overworld village presentation still uses the broader village test menu / overworld path. Sidecar ownership is authoritative either way.
- `village_test_menu.tscn` still has a DetailsContent path error for generated profiles; prefer `tools/play_g05.sh` → `g05_shell.tscn` for this gate.
- Presentation polish (local Mara model posing, dungeon art pass) may lag the authoritative quest/puzzle/duel systems — record if it blocks inference.
- Ensemble-only commits noted under G04 remain a separate follow-up and are not part of this gate.
