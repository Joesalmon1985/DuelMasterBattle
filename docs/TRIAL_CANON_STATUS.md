# The Trial of Champions: canon status

Kept current by the milestones of `docs/PLAN_OPENING_RPG_AND_DEATHTRAP.md` (M0 first version, 16 October 2026). Every zone, encounter and
consequence of the Deathtrap Dungeon adaptation is in exactly one of three columns:

* **Implemented (legacy)**: built as authored content in the old Godot adventure (`godot_project/client/world/world_data.gd`, `godot_project/sim/bestiary.gd`,
  `godot_project/client/world/story_events.gd`), exported for the Python host as `WizardRTSHybrid/wizard_rts/data/trial/legacy_{zones,bestiary}.json`.
  **Ported to Wizard World** is a separate tick (M5, M6) and is recorded in the Wizard World column.
* **Verified, not implemented**: present in the book-verified backbone (`DD/Deathtrap_Dungeon_Verified_Backbone.json`, 28 passages) or the encounter table
  (`DD/Deathtrap_Major_Encounter_Adaptation.csv`), not built anywhere.
* **Unverified**: known to exist in the book but not verified against the page; nothing is built on it, and nothing built is called canon.

Sources: `DD/Deathtrap_Dungeon_Canonical_Adaptation_Report.md`, the backbone JSON, the encounter CSV, `docs/DEATHTRAP_OVERHAUL_PLAN.md`,
`docs/DD_FIRST_SLICE.md`, `docs/DD_FULL_DUNGEON.md`.

## Zones (physical spaces; one zone holds many passages)

| Zone (legacy id) | Source passages | Legacy | Wizard World | Notes |
| --- | --- | --- | --- | --- |
| Trial gate, official, contestants | report section 3 | the old `trial_gate` area (Ashwell adventure, not exported) | M5 | the roll, the six contestants entering in order |
| Crystal Entrance (`dd_entrance`) | 1, 270 | implemented | M5 | aid box, the table of boxes |
| Footprint Fork (`dd_fork`) | 66, 119 | implemented | M5 | arrow, footprints, Giant Fly on the east loop, draught to the service tunnels |
| Footprint Galleries (`dd_galleries`) | 293, 382 | implemented | M5 | the old man's riddle, the petrified Knight, torch, bell, chest, Guard Dog |
| Throm's Pit (`dd_pit`) | 154, 22, 184, 63, 311, 323 | implemented | M5 | lower / be lowered / jump / climb alone; ally or betray |
| Lower Route (`dd_lower`) | 194, 138, 52, 169, 288, 221 | implemented | M5 | red book (weave), black book (potion), Cave Trolls (Throm fights one), bone ring |
| Trialmaster Complex (`dd_trialmaster`) | 60, 365, 290, 191, 84, 302, 379 | implemented | M6 | Dwarf, dice, cobra, Throm's forced duel, the concealed way |
| Idol Cavern (`dd_idol`) | 37, 240, 351, 239, 34, 89 | implemented | M6 | Flying Guardians, emerald eye, the false eye |
| Drowned Grotto (`dd_grotto`) | 281, 399, 192 | implemented | M6 | Boa Constrictor, the dying Elf, bread, charm (diamond clue) |
| Sapphire Vaults (`dd_vaults`, `dd_vault_inner`) | 162, 218, 65, 252, 269 | implemented | M6 | sapphire and iron key, the false diamond, the true diamond |
| Service Tunnels (`dd_service`) | report section 6 (Poison Ivy, the prisoner), CSV | implemented | M6 | prisoner (Bloodbeast weakness), Poison Ivy's toll, the Basket man's lift |
| Mirror Gallery (`dd_mirror`) | CSV (Mirror Demon) | implemented | M6 | smash the mirrors or duel |
| Bloodbeast Lair (`dd_blood`) | CSV (Bloodbeast) | implemented | M6 | weakness bans Vine from its Ward |
| Grub Tunnels (`dd_grub`) | CSV (Rock Grub), boulder, trapped chest | implemented | M6 | run / hold / brace with Stone; the chest's blades |
| Troglodyte Cavern (`dd_troglodytes`) | CSV (Troglodytes) | implemented | M6 | ritual, run the arrow, or the champion |
| Manticore Gate (`dd_manticore`) | CSV (Manticore) | implemented | M6 | plus the optional Red Wizard rematch (legacy rival, see below) |
| Igbut's Door (`dd_igbut`) | 364, 62, 241, 400, 31, 376, 3 | implemented | M6 | gem check, three-position lock with aggregate feedback, the final crossbow |

## Encounters and consequences

| Item | Passages | Status | Notes |
| --- | --- | --- | --- |
| Sukumvit's aid box and warning | 1, 270 | implemented (legacy) | |
| The east loop reconnects | 119, 56 | implemented (legacy) | |
| Old man's riddle: the petrified Knight | 382 | implemented (legacy) | the **correct answer is unverified** (the legacy puzzle is self-contained: 150 by its own inscription; the book's number needs a page check) |
| Throm: catch-up, alliance, the pit | 154, 22, 184, 63, 311, 323 | implemented (legacy) | |
| Betrayed Throm's onward route | 149 | **unverified** | `NEEDS_PAGE_IMAGE_CHECK`; the legacy builds no content on it |
| Books: red (progression), black (potion) | 194, 52, 138, 397, 25, 369 | implemented (legacy) | the potion's two outcomes as conditions |
| Cave Trolls, Throm wounded, bone ring | 169, 288, 64, 221 | implemented (legacy) | the ring's curse branch (64) is a condition, not verified in detail |
| Dwarf Trialmaster: lock-in, attack or test | 60, 179 | implemented (legacy) | the attack branch's consequence (179) is **unverified** in detail (placeholder wound) |
| Dice and cobra tests | 365, 290, 191, 84 | implemented (legacy) | |
| Throm's forced duel and the Dwarf's crossbow | 302, 379, 213, 95 | implemented (legacy) | 449 (Throm state list) **unverified** |
| Elf and Boa, the diamond clue, bread and charm | 281, 399, 192 | implemented (legacy) | |
| Idol, Flying Guardians, emerald, false eye | 37, 240, 351, 239, 34, 89 | implemented (legacy) | |
| Sapphire and iron key | 162, 442 | implemented (legacy) | |
| False diamond beside the fallen warrior | 218, 65, 252 | implemented (legacy) | |
| True diamond: the later hall route | 269, 127, 330 | implemented (legacy) as the inner vault | the book's **Ninja** and the hall route (269/330) are **verified but not implemented**: the legacy puts the true diamond in a vault reached by the Basket man's lift |
| Igbut's gem check and three-position lock | 364, 31, 3, 62, 16, 392, 177, 287, 132, 249 | implemented (legacy) | the correct order (Sapphire, Emerald, Diamond) follows the legacy; the six permutation passages are not individually verified |
| Final crossbow trap, daylight, Champion | 241, 400, 376 | implemented (legacy) | 376 **unverified** |
| Pit Fiend | CSV | **verified, not implemented** | no legacy zone |
| Medusa | CSV | **verified, not implemented** | no legacy zone |
| Giant Fly (escape allowed) | CSV | implemented (legacy) | |
| Mirror Demon (environmental solution first) | CSV | implemented (legacy) | |
| Bloodbeast with the learned weakness | CSV | implemented (legacy) | |
| Troglodytes: ritual, run of the arrow, champion | CSV | implemented (legacy) | |
| Poison Ivy: tribute, thorns, or escape | CSV | implemented (legacy) | |
| Rock Grub | CSV | implemented (legacy) | |
| Manticore | CSV | implemented (legacy) | the old man's clue (it hates light) is a legacy addition, **not canon** |
| The Red Wizard as a contestant and a rematch | plot document (invented for the Ashwell adventure) | implemented (legacy) | **not canon**; Wizard World's equivalent recurring rival is the stranger of the opening (decision D1); the legacy rival encounter is not ported |
| Contestant roster: Knight, Elf, two Barbarians (Throm), assassin | report section 3 | implemented (legacy, as states) | the assassin and the later Ninja are **not proven** to be one person; kept distinct |

## Palette mapping (the legacy's colours in Wizard World)

The legacy adventure used Water (1), Fire (0), Stone (3), Vine (6), Light (4), Shadow (5) with weave growth 1 to 4. Wizard World's apprentices start
with Flame (0), Frost (1), Vine (6) and a weave of three. The Trial's finds therefore grant: the red book a fourth weave slot; the Dwarf's test
Stone (3); the Mirror Demon Light (4); the Bloodbeast Shadow (5). Opponent pools are translated by the same ids. Recorded here so that nothing
in the data is mistaken for the book.
