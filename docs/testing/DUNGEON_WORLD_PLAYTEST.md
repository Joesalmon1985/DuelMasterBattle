# Dungeon World Playtest

Manual mini-game on the real production board (19 hexes / 54 nodes / 72 edges).
Disposable test session — does **not** write the campaign adventure save.

## Launch

```bash
cd ~/Projects/DuelMasterBattle
git switch test/full-board-dungeon-spatial
git pull
./tools/play_dungeon_world_test.sh
```

Portrait resolutions:

```bash
DMB_RESOLUTION=450x800 ./tools/play_dungeon_world_test.sh
DMB_RESOLUTION=720x1280 ./tools/play_dungeon_world_test.sh
```

Windows (from a Git Bash or WSL checkout, or after installing Godot on PATH):

```bat
tools\play_dungeon_world_test.bat
```

If the bat is missing, open Godot on `godot_project` and run scene
`res://client/scenes/dungeon_world_test.tscn` with env `DMB_FIXTURE=FX-DUNGEON-WORLD`.

## What you should see

1. Start in the **player’s starting settlement** (normal local area).
2. **No Halvard** prologue.
3. **No Trial Day** sequence.
4. A short test-only intro panel, then `[dismiss]` / continue — then play.
5. Badge: `DUNGEON WORLD PLAYTEST — disposable world`.
6. Walk to a **path exit at the edge** of the settlement.
7. Step on the exit → travel to an **adjoining terrain node** (one world turn).
8. See a **large rootbound ruin** in the landscape (not a tiny door).
9. **Walk into** the dungeon — no loading screen, no `dg_*` map change.
10. **Puzzle 1 — Four Seasons:** pull Spring → Summer → Autumn → Winter (wrong order resets). Root gate opens.
11. **Puzzle 2 — Restore the water:** pick up the **Channel Stone**, carry it, **Drop here** from Pockets (or `G` quick-drop) while standing on the pressure plate. Channel/water feedback; water gate opens.
12. **Puzzle 3 — Grow the living gate:** pick up the **Sun Seed** (earlier room). At the growth point, install it — **refuses if water is not restored**. With water, the living gate opens.
13. Reach the **final chamber** (Treefolk Presence).
14. Walk back outside the same LocalArea.
15. Leave via a normal strategic exit to another neighbour.
16. Press **M** for the full world map (19 hexes); press M / click to return.

## Controls

| Input | Action |
|-------|--------|
| Arrow keys / WASD | Move |
| Space / E | Interact |
| Pockets | Carried items → Look / **Drop here** |
| G | Quick-drop first pocket item (playtest) |
| M | World map / strategic board |
| Esc | Test menu (tools, exit) |

## Default route (seed 507)

- Home: `player_home_node()` (wardens settlement).
- Playtest dungeon: lowest-id non-settlement neighbour with a natural dungeon type; fixture assigns **GW Rootbound Sanctuary** for the three-puzzle chain.
- Node size profile: **73×55** (65×49 and 81×61 via Esc → Dungeon Test Tools).

## Automated checks

```bash
# Sim journey + spatial
./tools/run_sim_tests.sh
# or specifically via Godot:
godot --headless --path godot_project --script res://sim/tools/run_tests.gd

# Client journey (isolation + travel + kit coexistence)
godot --headless --path godot_project --script res://client/tests/run_dungeon_world_journey.gd
```
