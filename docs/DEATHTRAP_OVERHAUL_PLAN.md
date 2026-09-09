# Deathtrap Overhaul Plan — from "burning clearing" to the Trial of Champions

Branch: `game-story-overhaul`. Sources: `DD/` (canonical adaptation report, verified
backbone JSON, encounter CSV, replacement plot). This **supersedes
`docs/SECOND_ADVENTURE_PLAN.md`** (the invented "Trial Pit"); that doc is kept only
for the wound/ledger ideas, which are folded in below where they fit the book.

Plan only — nothing here is implemented yet.

---

## 0. What changes, in one paragraph

Level 1 stops being "forest burns → walk to village → beat the Red Wizard". It becomes
**Ashwell on Trial day**: John watches Halvard and the Red Wizard duel in his own
village, inherits the staff, learns the duel from Ashby, walks the carnival road to the
Trial gate, meets the other contestants, and chooses to enter. Level 1 ends at the
threshold. Everything after is **Deathtrap Dungeon** adapted zone by zone: the 1→2→3→4
weave progression moves inside the dungeon, rival contestants become moving story
state, most book dangers stay traps/choices/traversal, and only the right ones become
Ward duels. The dungeon is a **run** (dies → restart at the gate, keep knowledge);
John's magic is permanent.

---

## 1. Design rules (from the DD report — binding)

1. **Book is canon; the old `deathtrap_ff` pack is scaffolding only.** Every set-piece
   carries `source_passages` + `book_verified` metadata. Nothing marked inferred goes
   in as canon. The five known pack corruptions (22, 60, 281, 302, 399) get regression
   tests before maps are built.
2. **One physical room = many passages.** Do not build 400 rooms. Keep passage IDs as
   provenance.
3. **Not every danger is a duel.** Use the encounter CSV mapping. Mirror Demon, Medusa,
   Troglodytes, Poison Ivy, Dwarf, Igbut are *not* Ward battles by default.
4. **Exploration knowledge changes duel information** (Bloodbeast principle).
5. **Companions are characters** — Throm has a state machine and authored in-world
   behaviour, not a follower AI.
6. **No second stat game.** Run conditions (WOUNDED, POISONED, …) map to a handful of
   duel modifiers, used sparingly.
7. **Permanent vs run state** split (§13 of the report).
8. Mobile rules from PRD still hold: portrait, tappable, aggregate feedback only.

---

## 2. Level 1 overhaul — "Trial Day in Ashwell"

### 2.1 Beats (replaces `forest_home` → `forest_deep` → `village` chain)

| # | Beat | Where | Mechanics | State |
|---|------|-------|-----------|-------|
| 1 | Ordinary morning; village busy with Trial-day travellers | `village` (reworked) | free roam, talk to Mara / neighbour / Pip / stallholders | `opening_done` after N steps or talks |
| 2 | Shouting at the road; Halvard vs Red Wizard four-slot duel cutscene | `village` road | existing `story_events` cutscene helpers (`spawn_actor`, `bolt`, `shake`) — no fires spread | `duel_seen` |
| 3 | Halvard dying, gives staff: learn **WATER**, weave 1; "Enter if you want. Don't enter because a dying fool told you to." | `village` | pickup grant | `has_staff` |
| 4 | Village reacts (dialogue flips on `has_staff`); Ashby recognises the magic → **one-slot tutorial duel** (fixed Water Ward, guaranteed win) | `village` / Ashby's workshop | existing `flame_wisp`-style rules re-skinned as "Ashby's practice Ward" | `ashby_lesson` |
| 5 | Optional: Ashby second lesson — 1-slot deduction (Ward could be Water or Fire) using *his* Fire; John still weave 1 | workshop | `flame_imp` rules re-skinned | optional flag |
| 6 | The road to the Trial: spectators, bookmakers, charm-sellers, failed contestants, healers | **new area `trial_road`** | NPC density; one optional creature duel (Giant Fly, 1-slot, escape allowed) | — |
| 7 | The gate: six contestants visible as sprites — Knight, Elf, two Barbarians (one is Throm), black-clad assassin, **the Red Wizard**; official inspects Halvard's seal; Red Wizard notices the staff | **new area `trial_gate`** | contestant roster as npcs; official as npc with `choose_async` | `contestants_seen` |
| 8 | **ENTER THE TRIAL / NOT YET** | `trial_gate` | `dialogue_box.choose_async` (already exists) | `entered_trial` |
| 9 | Contestants enter one by one (Knight first, Elf, Barbarian, assassin, …, John last); doors close; scream ahead; "THE TRIAL BEGINS." | `trial_gate` → `dd_entrance` | cutscene → travel | chapter end |

Ends with John: Water only, weave 1. That's the deliberate hook — he's under-armed.

### 2.2 Cuts and reuse

- **Cut** as story: `forest_home` clearing, burnt wood, fires-as-gates, wisps/imps/
  sprites/brutes/golem/moss shade as *mandatory* content, Red Wizard as chapter boss.
- **Keep** the code: `fire` kind (braziers in the dungeon), bestiary entries (re-skinned
  or used as dungeon fauna), the whole cutscene helper set, save system, battle screen.
- **Red Wizard** survives as recurring rival (report §9 of plot): seen at gate, then his
  traces in the dungeon, a mid-dungeon crossing where he's *not* fightable, and the
  existing 4-slot duel much later (Phase D, optional pre-Manticore branch).
- Roster decision: the book's six + Red Wizard + John = 8 entering (Halvard's vacancy
  is John's). Keep the black-clad assassin and the second Barbarian **distinct** from
  the later Ninja / from Throm until verified (report §8).

---

## 3. The dungeon — zones, in build order

Weave progression inside the Trial (plot §7). Spell pickups are placed at book beats
that already involve a found object, so no new lore is invented:

| Spell | Where (book beat) | Weave |
|---|---|---|
| Water | Halvard's staff (Level 1) | 1 |
| **Fire** | the red book in the books alcove (p.194/52) — Throm scoffs at reading | 2 |
| **Stone** | the Dwarf Trialmaster's test (p.365) — passing the dice-probability procedure earns it | 3 |
| **Vine** | the dying Elf's charm (p.281/399), preserved as the canonical item | 4 |

From Vine onward it's the full 4-slot game.

### Zone A — Trial Gate & Crystal Entrance (`dd_entrance`, `dd_fork`)
p.1, 270, 66, 119, 56. Crystal-lit corridor; stone table with six boxes, one named
(John's — via Halvard's seal); open → 2 gold + Sukumvit's warning that items matter.
**First fork**: painted white arrow west, several wet footprints west, one east. The
east loop reconnects (teaches routes reconnect). Duel: none forced. Optional Giant Fly
(1-slot, escape allowed) on the east loop.

### Zone B — Footprint Galleries (`dd_galleries`)
p.293, 382 (+ bell, side rooms). Three footprint sets split: two west, one north.
North: **old man / statue riddle** — the statue is the **petrified Knight** who entered
first (John recognises the armour: contestant sprite reused as statue with his
heraldry). Riddle answer 100/150/200 via `choose_async`; wrong = trap consequence
(run condition, not death). Small duels: guard dogs / goblins (1–2 slot) on the west
tracks.

### Zone D — Throm Lower Route (`dd_pit`, `dd_lower`) — *the social centre*
p.154, 22, 184, 63, 311, 323, 149, 194, 138, 52, 169, 288, 221. John catches Throm;
**uneasy alliance** (both know only one wins). The **pit**: accept being lowered /
offer to lower Throm / jump together → ally vs **betray** (abandon him) branch.
Lower route: **books alcove** (red book → Fire; black book potion → drink / rub on
wounds / leave — conditions), Throm objects to unfamiliar substances and to reading.
**Cave Trolls**: Throm hears them first; two arrive; **John duels one (2-slot,
Fire+Water) while Throm visibly fights the other in-world** (authored outcome: he
wins, wounded). Bone ring pickup: Throm refuses it and warns; player may still wear
it (curse condition).

### Zone E — Dwarf Trialmaster Complex (`dd_trialmaster`)
p.60, 179, 365, 290/191/84, 302, 379, 213, 95. Dwarf locks John + Throm in;
"only one continues". Choice: **attack Dwarf with Throm** (p.179 branch — verify
consequence in book) / **persuade Throm to accept the test**. Secret room: **dice
probability test** (same/less/more than 8 — `choose_async`, seeded outcome), **cobra
reaction test** (timed tap — reuse cast-button timer widget). Passing the
procedure earns **STONE → weave 3**. Then the Dwarf sends in
**Throm, cobra-bitten and delirious** — John protests, Dwarf doesn't care →
**full Duel Master battle, 3-slot** (Throm is a Barbarian, not a wizard: his "weave"
is fury — flavour text; pools Fire/Stone/Water). No loot screen after: return to
arena, Throm's body, Dwarf at crossbow point reveals the way on. Option to punch the
Dwarf (p.95 — verify).
*Only if allied/not betrayed* — the betrayed branch reaches the complex alone.
Per the agreed decision, the betrayal *state* is implemented now, p.149 stays
`NEEDS_PAGE_IMAGE_CHECK`, and **no invented replacement arena opponent** is built
until the book route is verified.

### Zone C — Idol Cavern (`dd_idol`) — **Emerald**
p.37, 351, 240, 34, 89, 239. Giant idol, jewelled eyes, two "stuffed" bird guardians.
Climb → **Flying Guardians**: two sequential 2-slot duels (or one asymmetric 2-slot
vs 3-ward). Take the Emerald eye; the *other* eye is a trap (temptation, run
condition or death).

### Zone I — Sapphire & Diamond routes (`dd_sapphire`, `dd_boa`, `dd_diamond`)
- **Sapphire** (p.162): box with iron key + sapphire, reached only via the correct
  route (iron key opens a later door).
- **Elf / Boa** (p.281, 399, 192): find the Elf being crushed by the Boa; rescue is a
  3-slot duel (Vine not yet known — her Ward pool is what she *has*, John can only
  win with 3 slots if he has Stone). She dies anyway; **clue: the final door needs
  gems, one is a diamond**; her bread heals; her charm → **Vine, weave 4**.
- **Diamond** (p.218 false diamond room by a fallen warrior — lethal trap; p.269/330
  real diamond via the later hall). Preserve "risk your life for the wrong jewel".

### Zone G — Trap & Monster Galleries (`dd_mirror`, `dd_bloodbeast`, `dd_boulder`, …)
Selected set-pieces, not all: **Mirror Demon** (smash mirrors / ring solution first;
duel only if the player chooses to fight), **Bloodbeast** (3–4 slot; if the tongue/eye
clue was learned, John enters with one Ward slot revealed or one essence excluded
from candidates — *the* exploration-changes-combat showcase), **boulder run**
(traversal timer), trapped chest, **Imitator door** (acid solves it), Goblins/Orcs
(small duels), Rock Grub (2–3 slot, retreat allowed), Leprechauns, false exit
chamber. Build the Mirror Demon + Bloodbeast first; the rest are optional branches.

### Zone F — Troglodyte River Cavern (`dd_troglodytes`)
Tribe, ritual, chase, bridge, river, hollow tube. **Traversal/ritual/pursuit**, not a
duel; accept ritual OR run the arrow OR dive/tube route. One representative duel only
if John attacks. Spirit girl's water clue lives here.

### Zone H — Upper/Service Layer (`dd_service`)
Trialmaster servants, the mutilated former contestant (free him → gem clue), wicker
basket operator, **Poison Ivy** (pay / talk / escape; duel only on attack).
Communicates the dungeon is an *institution*.

### Zone J/K — Final approach (`dd_manticore`, `dd_igbut`, `dd_exit`)
p.364, 31/3, 376, 62, 241, 400. **Manticore**: 4-slot creature boss. **Igbut** checks
Emerald + Sapphire + Diamond (missing → Trial failure → run ends, knowledge kept).
**Gem lock**: 3 positions × 3 gems, six permutations, aggregate positional feedback,
wrong = energy blast (run condition / limited attempts) — built as a **dedicated mini
screen using the Ward UI grammar** (loci sockets + Fracture/Echo pips), *not* a
spell duel. Then Sukumvit's final crossbow trap kills Igbut; John walks into daylight
at Fang: **Champion**. Return to wider game.

**Red Wizard** in the dungeon: traces (a scorched guard, a burned door) in Zones B/G;
a non-fightable crossing in Zone F (he's on the far bank); optional 4-slot duel in
Zone J *before* the Manticore if the player seeks him (existing `red_wizard` entry).

---

## 4. Engine work (in dependency order)

All data-driven where possible; keep `world_data.gd` builders + `story_events.gd`
pattern. New pieces:

### 4.1 Run state (`adventure.gd`)
Add `state["run"]`: `{active, area, pos, checkpoint, visited: [], inventory: [],
gems: [], conditions: [], contestants: {knight, elf, throm, assassin, barbarian2,
red_wizard: <state>}, flags: {}}`. `start_run()`, `fail_run(reason)` (reset run,
keep `state["dungeon_knowledge"]`), `resume_run()`. **Bump `SAVE_VERSION` to 2** with
a migration that leaves old saves playable (run = null). Permanent progression stays
in `DmbProgression`.

### 4.2 New entity kinds (`world_data.gd` + `overworld.gd`)
- `choice {pos|rect, prompt, options:[{label, event|set_flag|set_run_flag}]}` — uses
  `dialogue_box.choose_async` (exists).
- `trap {pos|rect, condition, once_run_flag, hint_sprite}` — walkable; applies a run
  condition via `story_events`.
- `evidence {pos, sprite}` — footprints / arrow / scorch marks; purely visual, gated
  on contestant state (footprints only exist for contestants who are ahead).
- `companion` behaviour: `spawn_actor` + an authored `follow_path` per area
  (Throm walks a scripted route, stops at boundaries, faces things). No pathfinding.
- `statue`, `body`, `box`, `book` = re-skinned `corpse`/`pickup` with new sprites.
- Provenance fields on any entity: `"src": [22, 63], "verified": true` (ignored by
  the engine, checked by a test).

### 4.3 Conditions → duel bridge
`pending_battle["player_mods"]` from run conditions, consumed by
`battle_sim`/`realtime_duel_sim` **for John's combatant only**:

| Condition | Duel effect |
|---|---|
| WOUNDED | `max_casts −1` per wound (floor 6) |
| POISONED | `min_cast_seconds +2` |
| SLOWED | `max_cast_seconds −10` |
| CURSED (bone ring) | one essence unavailable for the first cast |
| WEAVE_DISRUPTED | one weave slot locked to a random essence on cast 1 |
| **Knowledge: bloodbeast_weakness** | one enemy Ward slot revealed pre-duel *(positive)* |

Healing: Elf's bread, black-book potion (rub), Halvard's… no — keep healing rare.

### 4.4 Mini-screens
- **Gem lock** (`client/scenes/gem_lock.tscn` + script): 3 sockets, 3 gems, Cast →
  aggregate pips, blast on wrong, `ui_*` API for tests.
- **Dice test / cobra test**: inline in the dialogue layer (choice + timed tap using
  the existing cast-button ring).

### 4.5 Bestiary additions (`bestiary.gd`)
All ≤ 4 weave/ward, pools ≤ 6 essences (John maxes at Fire/Water/Stone/Vine; add
Light/Shadow only if a Zone G branch teaches them — decision):

| id | Wv/Wd | Bot | Zone |
|---|---|---|---|
| giant_fly | 1/1 | random | A |
| guard_dog / goblin | 1–2 | random / candidate_filter | B, G |
| flying_guardian ×2 | 2/2 | candidate_filter | C |
| cave_troll | 2/2 (asym 2/3 later) | candidate_filter | D |
| boa_constrictor | 3/3 | candidate_filter | I |
| rock_grub | 3/3 | candidate_filter | G |
| mirror_demon (optional) | 3/3 | candidate_filter | G |
| bloodbeast | 4/4 (knowledge-modified) | capped_minimax | G |
| throm (delirious) | 3/3 | candidate_filter, fast band | E |
| pit_fiend | 4/4 | capped_minimax | G |
| manticore | 4/4 | capped_minimax | J |
| red_wizard | existing 4/4 | existing | J (optional) |

### 4.6 Map / knowledge
`state["dungeon_knowledge"]`: per-area `UNKNOWN/SEEN/ENTERED/CLEARED/LETHAL/ITEM`
+ notes; a simple "notebook" panel from the pause menu listing known areas and
recorded clues (Elf's diamond clue, spirit girl's water clue, Bloodbeast weakness).
No auto-map first pass — text list is enough and honours "never show what John
hasn't learned".

### 4.7 Tests
- **Canon regression tests** (report §19) as data tests over the content: p.22 is
  Throm not spider; p.60 exposes both branches; p.281 is Elf; p.302 is Throm; p.399
  is not a death; final gems = E/S/D; p.62 exposes six permutations. Implement as
  `sim/tests/test_dd_canon.gd` reading the entity `src` metadata + choice options.
- Run-state tests: fail_run resets gems/conditions/contestants, keeps spells/weave/
  knowledge; save v1 → v2 migration.
- Condition→duel modifier tests per row of §4.3.
- Gem lock: all 6 permutations score correctly; blast count; solve.
- `run_adventure_flow.gd` rewritten for the new L1 path + first dungeon slice; second
  flow for "pacifist" paths (mirror smash, troglodyte ritual, Poison Ivy payment).
- Screenshot QA per zone; contact sheets reviewed.

---

## 5. Phasing (each phase ends green + playable + committed)

| Phase | Scope | Gate |
|---|---|---|
| **P0 Canon & scaffolding** ✅ DONE | `content/dd_canon.json` + `content/dd_passages/` (29 files) + `test_dd_canon.gd`; `SECOND_ADVENTURE_PLAN.md` marked superseded | 11/11 green |
| **P1 Level 1 overhaul** ✅ DONE | Trial-Day Ashwell, duel cutscene, Ashby lessons, `trial_road`, `trial_gate` (7 entrants), ENTER/NOT YET, threshold ending. Burnt Wood = training detour (grants stripped) | flow test ALL PASSED + sim 11/11 + screenshots reviewed |
| **P2 Run state + first slice** ✅ DONE | run state (save v2+migration), Zones A/B/D through Cave Trolls (Fire via red book), Throm pit choice, conditions→duel bridge, fail/restart loop | unit 12/12 + dungeon flow ALL PASSED + P1 flow/smoke/playtest green + screenshots |
| **P3 Trialmaster** ✅ DONE | Zone E incl. dice/cobra tests (Stone), forced Throm duel, betrayal variant (no invented opponent), attack variant | `run_dungeon_p3.sh` ALL PASSED |
| **P4 Gems** ✅ DONE | Zones C, I (Elf/boa → Vine), false eye, sapphire + iron key, real/false diamond, journal in pause menu | `run_dungeon_p4.sh` ALL PASSED |
| **P5 Galleries & river** ✅ DONE | Zone H (prisoner → Bloodbeast weakness, Ivy toll), Zone G (Mirror Demon smash-or-duel → Light, Bloodbeast → Shadow, Rock Grub, boulder, trapped chest), Zone F (ritual / run / champion) | `run_dungeon_p5.sh` ALL PASSED (pacifist + attack legs) |
| **P6 Finale** ✅ DONE | Manticore, optional Red duel, Igbut gem check, 3-strike gem lock, final trap, Champion → `dungeon_complete` | `run_dungeon_p6.sh` + `run_full_run.sh` (gate → Fang, one run, all spells earned in play) ALL PASSED |
| **P7 Art & polish** ✅ DONE (first pass) | cave floor/wall tiles for `dd_*`, stalagmites, markers on every interactable, idol + mirror props, 11 new bestiary sprites, 11 zone QA shots vision-reviewed | screenshots in `qa/screenshots/adventure/11g–11q` |

P0–P2 is the "first playable Deathtrap slice" the report recommends (§20) and proves
every hard thing once.

---

## 6. Decisions for you before P0

1. **Roster**: book six + Red Wizard + John (8), or fold the Red Wizard into the
   black-clad assassin's slot (6 total, more faithful headcount, less faithful cast)?
2. **Spell placements** (§3 table): Fire=red book, Stone=troll heart-stone, Vine=Elf's
   charm — OK, or do you want Stone from the Dwarf's test as a reward?
3. **Death model**: run reset with kept knowledge (proposed) vs checkpoint-per-zone
   (softer; less Deathtrap)?
4. **Betrayed-Throm branch**: build it in P3 or defer (flag it "coming back later" in
   the fiction) to keep P3 small?
5. **Light/Shadow**: add via a Zone G branch (Mirror Demon = Light, Bloodbeast lair =
   Shadow), or keep John at four essences for the whole book?
6. **Old forest content**: ~~park unreachable (proposed) or~~ repurpose the Burnt
   Wood as an optional practice area off `trial_road` (AGREED).
7. **Book verification workflow**: do you want a `content/dd_passages/` folder where
   each used passage gets a `status` (BOOK_VERIFIED / NEEDS_PAGE_IMAGE_CHECK) that the
   canon test enforces, so unverified passages can't ship as canon?
