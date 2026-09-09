# The Deathtrap Dungeon — full run (Zones A–K)

Companion to `FIRST_ADVENTURE.md` (Trial Day) and `DD_FIRST_SLICE.md` (Zones A/B/D).
This describes the whole dungeon as built on `game-story-overhaul`, P3–P7.
Every number below is read from `sim/bestiary.gd` / `client/world/world_data.gd`.

## The run

- **ENTER** at the Trial Gate starts a run: `dd_entrance`, run-scoped pickups, fresh fights.
- **Death** (losing a duel in any `dd_*` area, or three wrong gem placements) ends the run:
  back to the gate, conditions cleared, fights reset. **Kept**: every spell, weave size,
  world flags, and dungeon knowledge (journal).
- **Victory**: place the three gems correctly at Igbut's door → `dungeon_complete`,
  Champion of the Trial, back to the gate in daylight.

## Zone map (west = deeper)

| Area | Name | What happens | Magic |
|---|---|---|---|
| `dd_entrance` | Crystal Entrance | Sukumvit's aid box, table of taken boxes | — |
| `dd_fork` | Footprint Fork | arrows, footprints, Giant Fly (1-slot) east | — |
| `dd_galleries` | Footprint Galleries | statue riddle ("150"), **torch** pickup, Guard Dog (1), bell, chest | — |
| `dd_pit` | Throm's Pit | Throm: let him lower you / go alone / leave him | — |
| `dd_lower` | Lower Route | red book, black book, vial, Cave Troll (2), bone ring, dwarf door | **Fire**, weave 2 |
| `dd_trialmaster` | Trialmaster Complex | Dwarf: dice ("More than 8") + cobra ("Hold its gaze"); Throm forced duel (3) if ally; attack variant wounds | **Stone**, weave 3 |
| `dd_idol` | Idol Cavern | two Flying Guardians (2), idol: emerald eye vs false eye | Emerald |
| `dd_grotto` | Drowned Grotto | Boa Constrictor (3) on the elf, bread, charm | **Vine**, weave 4 |
| `dd_vaults` / `dd_vault_inner` | Sapphire Vaults | sapphire + iron key, true diamond (inner) vs false diamond (outer) | Sapphire, Diamond |
| `dd_service` | Service Tunnels | starved prisoner → **Bloodbeast weakness**; Poison Ivy (2) — pay torch / attack / leave | — |
| `dd_mirror` | Mirror Gallery | smash the mirrors or duel the Mirror Demon (3) | **Light** |
| `dd_blood` | Bloodbeast Lair | Bloodbeast (4); with weakness, Vine is banned from its Ward | **Shadow** |
| `dd_grub` | Grub Tunnels | Rock Grub (3), boulder run (Run! / Hold ground), trapped chest | — |
| `dd_troglodytes` | Troglodyte Cavern | ritual / run the arrow / Troglodyte Champion (3); bridge, reed tube | — |
| `dd_manticore` | Manticore Gate | Manticore (4); optional Red Wizard (4) rematch | — |
| `dd_igbut` | Igbut's Door | gem check (needs all three), 3-strike positional lock, final crossbow trap | Champion |

Correct gem order: **Sapphire, Emerald, Diamond**. Each wrong order reports
"N placed true, N displaced" and wounds; the third ends the run.

## Conditions → duel

- `wounded` = −1 cast next duel (boulder held, trapped chest, wrong gem, attacking the Dwarf).
- Bloodbeast weakness = ward ban on Vine (`ward_ban`), earned by freeing the prisoner.
- Conditions clear when a run fails.

## Tests (all in `tools/run_all_checks.sh`)

| Script | Covers |
|---|---|
| `run_godot_tests.sh` | sim 12/12 incl. canon + run state |
| `run_adventure_flow.sh` | Trial Day village → gate |
| `run_dungeon_flow.sh` | A/B/D + die-and-restart |
| `run_dungeon_p3.sh` | Trialmaster ally / betrayed / attack |
| `run_dungeon_p4.sh` | three gems + journal |
| `run_dungeon_p5.sh` | pacifist galleries + attack legs |
| `run_dungeon_p6.sh` | finale, missing gems, lock failure |
| `run_full_run.sh` | **gate → Fang in one run**, all five dungeon spells earned in play |
| `run_realtime_playtest.sh` | wall-clock duel pacing |

## Art (P7 first pass)

`dd_*` areas render cave floor + brick wall tiles (`tiles/cave_floor.png`, `tiles/cave_wall.png`),
`r` = stalagmite, every sign/door/logs interactable has a visible marker, idol and mirror props.
New bestiary art: throm_duel, flying_guardian, boa_constrictor, mirror_demon, bloodbeast,
rock_grub, trog_champion, poison_ivy, manticore; chars: dwarf, ivy, igbut.
QA shots: `qa/screenshots/adventure/11d–11q`.

## Known gaps / next

- p.149 (betrayed Throm's onward route) stays `NEEDS_PAGE_IMAGE_CHECK`; no content shipped on it.
- Igbut's death and "Fang roars" are prose only — no cutscene art for daylight.
- Zone tiles are one theme (cave); the grotto/river could use water-specific dressing.
- Realtime playtest covers the duel screen, not a full-run wall-clock walk.
