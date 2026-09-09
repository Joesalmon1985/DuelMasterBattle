# Level 2 Plan — "The Trial Pit" (roleplay-first, Deathtrap-style)

> SUPERSEDED by `DEATHTRAP_OVERHAUL_PLAN.md` (P0). Kept for the wound/ledger ideas,
> which were folded into the book-faithful plan where they fit.

Follow-up to the First Adventure (`docs/FIRST_ADVENTURE.md`). John follows the Red
Wizard north to a death-trap labyrinth run as a **trial**: enter willingly, few
return. Duels stay the boss language, but most of the level is **choices, traps,
riddles, NPCs** — magic figures constantly, killing everything does not solve it.

## 1. Design intent

Deathtrap Dungeon elements, adapted to this engine (mobile, portrait, one save slot):

- **Trial framing**: a warden warns John, takes his name, lets him in. Inside, a
  running count of entered vs returned sells the stakes.
- **Non-linear hub**: L1 was a line (clearing → wood → village). L2 is a hub with
  **3 wings in any order** + a locked sanctum. Each wing grants one seal; 3 seals
  open the sanctum.
- **Avoidable fights**: every wing has 1 duel you can talk, bribe, riddle or sneak
  past + 1 forced duel. Pacifist run is possible for 3 of 9 fights, at a cost
  (coin, provisions, a wound, a seal oath).
- **Traps with teeth, not permadeath**: traps inflict **wounds** (flags). Each wound
  −1 max cast in the next duel (floor 6 of 10) until rested at a shrine. Defeat
  still wakes John in the grass — Deathtrap lethality without losing mobile players.
- **Moral ledger**: mercy vs ruthlessness tracked as two counters (`mercy_n`,
  `ruth_n`). Pays off in the sanctum (what the Trial Master offers, what the
  ending says).

## 2. Areas (6 new, ASCII grids like L1)

| # | Area id | Name | Size | Role |
|---|---------|------|------|------|
| 4 | `trial_gate` | The Gate Camp | 20×14 | Surface camp: warden, coward knight, rules, first choice, provisions |
| 5 | `the_pit` | The Pit (hub) | 22×18 | Central shaft, 3 wing doors, shrine, score-board of the dead |
| 6 | `hall_of_knives` | Hall of Knives | 20×20 | Blade/needle traps, brass key, 2 duels |
| 7 | `flooded_crypt` | Flooded Crypt | 20×18 | Water, riddles, spirits, mirror shard, 2 duels |
| 8 | `menagerie` | The Menagerie | 22×18 | Caged monsters, goblin toll, moral choice, 2 duels |
| 9 | `sanctum` | The Sanctum | 14×14 | Trial Master (boss), Red Wizard cameo, L3 hook |

Routing: `village` north exit (hill, currently Red Wizard pos [10,0]) → `trial_gate`
→ `the_pit` → wings (any order) → `sanctum` with `requires_flags: [seal_knife, seal_crypt, seal_beast]`.
Each wing is 1 area to keep `world_data.gd` diffs reviewable (~40 entities each).

## 3. Magic progression (still matters, no bigger numbers)

John ends L1 with 4 spells (Fire 0, Water 1, Stone 3, Vine 6) and weave 4 — already
a full duel. So L2 keeps **weave 4 throughout**; difficulty comes from **wider
enemy pools**, not bigger wards:

- New spells: **Light (4)** in the crypt (mirror shard pickup), **Shadow (5)** in
  the menagerie (mercy-choice reward OR toll-bought — never both, ledger matters).
- Final pools use 6 types; John with 6 known spells vs 6-pool wards is the hardest
  fair deduction the engine supports at weave 4.
- Utility magic in the world (no sim change): Water douses braziers (existing
  `fire` kind), Stone holds down pressure plates (reskinned `logs`), Light reveals
  crypt ink (reskinned `sign` with `requires_spell: 4`), Vine pulls the menagerie
  lever from range (trigger with `requires_spell: 6`).

## 4. Beats per area (forced vs avoidable marked F/A)

**trial_gate** — Warden takes John's name (`trial_entered` flag), warns him.
Coward knight Sir Pell begs John to carry his oath-token (choice: carry it
`oath_pell` / refuse `ruth+1`). Provisions pickup (heals 1 wound out of duel).
Exit north gated on `trial_entered`.

**the_pit (hub)** — Score-board sign ("ENTERED 211 · RETURNED 9"). Shrine of the
Quiet (rest: clears wounds, once per wing — `once_flag` per rest). Three wing
doors each need nothing but nerve; sanctum door needs 3 seals. Blind Warden NPC
gives the riddle-rules and tracks `mercy/ruth` totals in dialogue.

**hall_of_knives (F:2 A:1)** — Needle corridor traps (2 wound-traps, visible wire
hints for fairness). Brass key pickup behind pressure-plate puzzle. F: Needle
Saint (2-slot), Blade Choir brute (3-slot). A: Rusted Knight — duel OR answer his
oath-question (needs `oath_pell` → he yields + `mercy+1`, seal still granted).

**flooded_crypt (F:1 A:2)** — Ink-riddles on walls (Light to read). Mirror shard
→ Light spell. F: Drowned Knight (3-slot). A: Crypt Sphinx (riddle OR 3-slot
duel — wrong riddle answer forces the duel with −1 cast penalty); Wailing Choir
(a 2-slot swarm you can sing past with Vine+Water "reed whistle" event, no duel).

**menagerie (F:2 A:1)** — Goblin toll (pay 3 coin OR duel his champion OR sneak
via Vine lever). Caged horror choice: free it (`mercy+1`, it kills the guards but
also eats your provisions) or leave it (`ruth+1`, cleaner path). F: Toll Champion
(3-slot), Caged Horror's Keeper (3-slot). Shadow spell reward routes on the choice.

**sanctum (F:1 boss)** — Trial Master cutscene reads the ledger. Boss: **The Pale
Warden**, 4-slot / 6-pool, `capped_minimax`, think band 10–18 s (fastest fair).
On win: Red Wizard cameo takes the prize first ("Count yourself lucky I have
somewhere to be" callback → he descends, L3 hook). Ending text varies on
mercy vs ruth majority. `beat_pale_warden` flag; free-roam after.

## 5. Bestiary additions (all weave ≤ 4, pools ≤ 6)

| Enemy | Wv/Wd | Attack pool | Ward pool | Bot | Notes |
|---|---|---|---|---|---|
| needle_swarm | 1/1 | Fire | Water, Fire | random | tutorialises wound-duels |
| rusted_knight | 2/2 | Stone, Fire | Stone, Fire | candidate_filter | avoidable via oath |
| blade_choir | 3/3 | Fire, Stone, Water | Fire, Water, Stone | candidate_filter | hall mini-boss |
| drowned_knight | 3/3 | Water, Stone, Vine | Water, Stone, Light | candidate_filter | crypt forced |
| crypt_sphinx | 3/3 | Light, Shadow, Water | Light, Shadow, Water | candidate_filter | riddle-or-duel |
| toll_champion | 3/3 | Stone, Fire, Shadow | Fire, Stone, Shadow | candidate_filter | menagerie forced |
| menagerie_keeper | 3/3 | Vine, Shadow, Fire | Vine, Water, Stone | candidate_filter | horror choice gates help |
| pale_warden | 4/4 | Fire, Water, Stone, Vine, Light, Shadow | same 6 | capped_minimax cap 40, 10–18 s | sanctum boss |

No `fixed_ward` except needle_swarm (teaches wounds). No weave-5: keeps
`DmbProgression.to_combatant()` and the duel UI untouched.

## 6. Engine work (minimal, no save-schema change)

All state is **flags + defeated/picked/extinguished lists** — `adventure.gd` schema
(`SAVE_VERSION 1`) is untouched. New work, in order:

1. **`world_data.gd`**: 6 builders + exits; reuse kinds (`npc creature wizard pickup
   sign door fire trigger exit corpse burnt`). New kinds (all optional-gated with
   existing `requires_flag`/`requires_spell`/`requires_defeated`/`once_flag`):
   - `trap {id, rect|pos, wounds: 1, hint, disarm_spell?}` — solid? No: walkable,
     fires `story_events.trap_sprung(id)` once per pass.
   - `choice {id, pos, prompt, options: [{label, set_flag, counter}]}` — walks into
     `dialogue_box` branch; implement as `npc` with `lines_choice` if cheaper.
   - `shrine {id, pos}` — npc that clears `wound_*` flags (see below).
2. **`story_events.gd`**: `trap_sprung`, `riddle_asked/answered`, `toll_paid`,
   `oath_kept`, `sanctum_ending` cutscenes; wound application
   (`adv.set_flag("wound_1"..3)`), seal grants, ledger counters
   (`mercy_n`/`ruth_n` as flag ints via `state["flags"]`).
3. **Wound → duel bridge** (smallest viable): `adventure.pending_battle` carries
   `player_max_casts_override = 10 − wounds`; `battle_sim`/`realtime_duel_sim`
   reads it for John's combatant only. One field, no progression change. Shrine
   clears wound flags.
4. **`bestiary.gd`**: 8 entries above; portraits
   `assets/pixel/creatures/<archetype>_portrait_0.png` + world sprite per
   `docs/FIRST_ADVENTURE.md` adding-content rule.
5. **`overworld.gd`**: render `trap` wire hint + `shrine` glow; trap trigger check
   in movement (same path as `trigger` kind).
6. **`run_adventure_flow.gd`**: extend full-path test: gate → pit → knife wing →
   crypt → menagerie → sanctum + save/load round-trip with wound flags set.

Out of scope: coin economy UI (coin is a flag counter, spent in dialogue),
provisions beyond heal-1, weave 5+, Last Stand in adventure duels, multiplayer.

## 7. Content checklist

- 6 maps, ~120 entities, ~25 NPC dialogue sets (warden, Pell, blind warden, sphinx
  riddles ×3 with answers, toll goblin, keeper, pale warden ×2 ledger variants).
- 8 bestiary entries + 8 portraits + 8 world sprites (PIL via
  `tools/build_pixel_assets.py` convention).
- 2 spell pickups (mirror shard → Light, shadow gift/toll → Shadow) with
  `grant: {spell}` text in L1 style.
- 3 seals (`seal_knife/crypt/beast`), oath token, brass key, mirror shard as
  flags/pickups; score-board and 4 riddle-ink signs.
- Ending cards: mercy / ruth / even variants + Red Wizard descend hook.

## 8. Tests & QA (per godot-mobile-game-dev skill)

- Sim tests green baseline first (`tools/run_godot_tests.sh`).
- New `sim/tests/test_pit_bestiary.gd`: every new id loads, pools valid
  (`secret ⊂ attack` rule per ENCOUNTER_DESIGN), weave/ward ≤ 4.
- Adventure flow extension (above) + wound-override unit test (3 wounds → 7 casts,
  floor 6; shrine clears).
- Headed screenshots (`capture_adventure_qa.sh`): gate, hub, one trap corridor,
  one riddle wall, sanctum; 4-up contact sheet reviewed for readability.
- `.bat` entry points unchanged (`Play Puca`-style launcher + `Run Tests.bat`).

## 9. Milestones

| # | Name | Gate |
|---|------|------|
| M20 | Pit data + bestiary | maps load, 8 enemies validate, flow test stubs pass |
| M21 | Traps/wounds/shrines + ledger | wound→casts override tested, shrine clears, ledger counted |
| M22 | Riddles/choices/toll/oath paths | pacifist-per-wing path playable in flow test |
| M23 | Sanctum + endings + art pass | boss beatable, 3 ending cards, screenshots signed off |

## 10. Open decisions for you

1. Antagonist for L3: does the Red Wizard stay ahead of John (kept as chase), or
   should the Trial Master survive to recur?
2. How cruel may traps be: wounds-only (proposed) or one genuine instant-death
   trap with heavy foreshadowing, Deathtrap-pure?
3. New spells Light + Shadow — or would you rather meet Frost/Storm/Metal/Spirit/
   Arcane first for series continuity?
