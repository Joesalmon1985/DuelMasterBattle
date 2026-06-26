# Godot Implementation Agent Role

## Responsibility
Port tested game into Godot 4.4.x 2D with sim/client separation.

## For this project
- `sim/`: authoritative `RefCounted` rules, encounters, bots — headless-testable
- `client/`: scenes, encounter menu, dynamic peg slots, filtered picker — no rule re-derivation
- `EncounterSession` autoload stores selected encounter; board reads ruleset at `_ready`
- M4/M11: playable encounter flow + Archmage regression before commit

## Scenes
- Main menu (difficulty + encounter select), game board (portrait duel), locus sockets, essence picker, feedback display, result screen

## References
- **[PRD.md](../PRD.md)** — real-time sim, mobile UI, animation events
