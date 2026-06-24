# Godot Implementation Agent Role

## Responsibility
Port tested game into Godot 4.4.x 2D with sim/client separation.

## For this project
- `sim/`: authoritative `RefCounted` rules, headless-testable
- `client/`: scenes, peg selector, feedback markers, menus — no rule re-derivation
- M4 is the hard checkpoint: playable Human vs Bot flow must work before commit

## Scenes
- Main menu, game board, peg selector component, feedback component, result screen
