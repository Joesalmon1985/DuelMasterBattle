# G04 fixture reset (labelled)

Reset **only** the isolated G04 slots. Do not wipe G01/G02/G03 or personal saves.

## Battle fixture (`g04_battle`)

1. Quit the game if it is running.
2. Delete the user save slot named `g04_battle` (Godot user data / DMB saves directory).
3. Relaunch:

```bash
bash tools/play_g04_battle.sh
```

A fresh FX-BATTLE seed (404) loads: Red owns the settlement; Blue invades; wizard spawns at a clear tile with free N/S/E/W movement.

## Hazard fixture (`g04_hazard`)

1. Quit the game if it is running.
2. Delete slots `g04_hazard` and `g04_hazard_terminal` if present.
3. Relaunch:

```bash
bash tools/play_g04_hazard.sh
```

Three labelled manifestations appear at west / north / east boundary approaches.

## Why reset

An old fixture save can preserve mixed-owner buildings, trapped spawn poses, or Channel×3 duel state and obscure the interaction repair. Always reset before judging G04.
