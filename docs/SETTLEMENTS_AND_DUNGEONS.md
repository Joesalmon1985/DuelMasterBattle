# Settlements & Dungeons Pass — What Was Built

Branch: `settlements-and-dungeons` (cut from `main` @ `3c679f2`).

Design inputs: `Duel_Master_Battle_Puzzle_Catalogue`, `_Puzzle_Mechanics`,
`_Node_Map_Mechanics`, `_Node_Map_Visual_Catalogue` (all in `docs/`). The brief
overrode those where they disagreed (notably: no edge/road areas; two-colour start).

## 1. Early combat progression

| Beat | Before | Now |
|---|---|---|
| Halvard's staff | Water, weave 1 | **Water + Vine, weave 2** — the real slot game from the first duel |
| Ashby lesson 1 | 1v1 fixed Water | 2v2, Ashby's Ward is *told* to you (Water, Vine): guaranteed win, teaches slots |
| Ashby lesson 2 | 2-slot, unwinnable with 1 knot | **3-slot** of Water/Vine, unwinnable with 2 knots → grants **weave 3** on the loss |
| Ashby lesson 3 | 2v2 | 3v3 fair fight, Water/Vine both sides |
| Burnt Wood tier 1 | 2-slot imps | 2-slot imps, `candidate_filter` — reinforces the two colours |
| Fire pendant | Fire | Fire (third colour). **All tier-2+ creatures are now 3-slot** (`steam_sprite`, `steam_brute`, `cinder_golem`, `moss_shade`) |
| Story defeats | 1st left-for-dead, 2nd → Jane | Same rule but **only counts once John has 3 colours**; two-colour losses return `"wait"` (knocked down, no penalty) |
| Phases | `pre_trial → trial → post_trial_recovery` | `ashby_training` and `pre_trial` may also jump straight to `post_trial_recovery` (two defeats in the wood, Trial never reached) |

Stone (golem shard) and the Trial's fourth/fifth colour stay optional; `trial_ready()` still demands 4 spells / 3 knots for the Trial door only.

Files: `sim/bestiary.gd`, `client/world/world_data.gd`, `client/world/story_events.gd` (`ashby_training`, `_story_defeat`, `jane_wake`), `client/scripts/adventure.gd` (`record_story_defeat`, `PHASE_NEXT`).

## 2. Inventory ("Pockets")

`DmbItems` (sim/world/items.gd): catalogue of quest/puzzle objects, 8-slot cap, generated ids for `sigil_*`, `token_*`, `cure_fragment_*`. `Adventure.items()/add_item()/remove_item()/inventory_full()` persist in the save. HUD **Pockets** button (shown once in the world or when non-empty) opens a tap-to-inspect list. Jane's letter is the first item, handed over in `jane_wake`.

## 3. Direct node-to-node travel

Unchanged in spirit (already node→node) but roads are now *drawn into* the node map: owned faction roads run paved from the exit to the centre, unowned tracks fade after two tiles. The signpost lists every way out with its owner. Board edges remain sim-only.

## 4. Settlements emerge from the sim

`DmbSettlementProfile.describe(sim, nid)` → `{kind, family, production[], processing[], development, housing, civic[], roads[], infection, mood, dungeon, products[]}` derived from surrounding hexes, tokens, roads, demons, city flag and quest moods.

`DmbNodeProjection` lays it out: production huts per resource hex (idle when infected), works (sawmill/kiln/weaver/mill/smithy/…) when the inputs exist, houses (roof+door tiles) scaling with development and doubled for towns, civic set (well/shrine → +hall/market for towns), a **town wall** on the city upgrade, workers with lines that shift with the settlement's mood, floor tiles by terrain family. Test asserts the settlement→city upgrade changes tiles and adds buildings.

Workers walk between post and workplace (`_tick_workers` in overworld.gd) — design doc §14 ambient loops.

## 5. Local quests

`DmbQuests`: three templates (`missing_flock`, `tainted_well`, `road_toll`) chosen from settlement state (infection → well; pasture → flock; otherwise toll). Each is a binary tree of 2–3 decisions over 3 inhabitants, 4 leaves. Leaves apply effects to the sim: faction AI weights, resources, treating hexes, a persistent **mood** (stored in `DmbWorldSim.settlement_moods`, saved), items, or a fight (resolved on return from battle). Every leaf grants the faction **token** (the first dungeon's dependency) so no choice can lock progression. Outcomes persist in `adv.state.quests[node]`; NPCs switch to aftermath lines.

Client: `WorldPlay.run_quest / finish_outcome / after_battle`.

## 6–7. Dungeons and the network

`DmbDungeons` (sim): at world setup one **tower** per settlement on the nearest free non-adjacent node (BFS ≤3, deterministic tie-break); later settlements (faction AI `settlement` event) spawn a **cave**. Dungeon nodes are **reserved** — `DmbCatanState.reserved_nodes` blocks them from settlement/city placement.

Each dungeon: seed, 4 puzzles (`DmbPuzzleGen`), `provides: sigil_<word>`, `needs: {item, from}`. Dependencies only ever point *backwards* in creation order (dungeon 0 needs the founding settlement's token; later ones need an earlier sigil) → provably acyclic; `validate()` checks it, tests walk the whole network with only what earlier stops gave. The imported item is **shown, not consumed**, so shared sources never run dry.

Reward on completing all four rooms: the next colour John lacks (Stone → Vine → Storm → Light → Shadow, skipping known), else a `cure_fragment_N` for the Pandemic arc. The dungeon's sigil is also collected there.

`DmbDungeonMap` renders a dungeon as a 4-room area (`dg_<id>`); doors open as rooms are solved; `WorldPlay.interact_puzzle` drives every interaction through choice dialogs (mobile-friendly, no new controls).

## 8. Puzzle mechanics implemented

`DmbPuzzleLogic.act(puzzle, state, action, ctx)` — pure, save-friendly:

| Template | Catalogue | Mechanic |
|---|---|---|
| `offerings` | 01/20/27 | item receptacles, one local + one imported |
| `exchange` | 17/23 | occupied slot / swap under weight |
| `switch_chain` | 08/41 | ordered triggers with reset |
| `plate_hold` | 21 | pressure plate held by an object |
| `timed_gate` | 06 | timed state, decremented per step |
| `mosaic` | 12/03 | ordered floor sequence |
| `magic_target` | 36/37/38 | environmental magic (Water/Vine/Fire) |
| `two_levers` | 14/16 | lying guide; wrong pull summons a fight |

## Tests

- `sim/tools/run_tests.gd` — 23 suites (new: `test_dungeons`, `test_quests`; extended `test_projection`, `test_story_phase`). Runner now fails a suite whose script does not compile.
- `client/tests/run_world_loop.gd` (`tools/run_world_loop.sh`, in `run_all_checks.sh`) — Jane's house → world → quest via UI → walk to the tower → solve all four rooms via UI → reward colour + sigil → save/load round-trip.
- Existing flows updated: `run_adventure_flow` (new weave numbers), `test_asymmetric_battle`, `test_early_solver`.

## Known gaps / next

- Buildings use existing props as markers (logs/rock/box/idol/ring/door_stone); the visual catalogue's dedicated sprites are not drawn yet.
- Caves are spawned by the AI settlement event; there is no in-fiction announcement beyond the world-event log line and the new node name.
- Quest templates: 3. Adding one = one `match` arm in `DmbQuests.build_template` + a `pick_template` rule.
- Dungeon rewards after the colours run out are cure fragments; nothing consumes them yet.
