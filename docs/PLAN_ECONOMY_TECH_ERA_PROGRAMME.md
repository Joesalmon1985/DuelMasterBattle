# Plan: economy, technology drafting and era progression programme

Status: **PROPOSAL for owner review. Nothing in this plan is implemented. No gameplay code, data or balance value has been changed.** Written 12 October 2026 on branch `feature/hybrid-playtest-fixes-v03` (HEAD `23ffc4f`) from a read-through of `WizardRTSHybrid/wizard_rts/`, the data files, the tournament evidence and the docs. Where this plan overrides an existing decision (D04, S04/S13, S05/S14, S12) it says so in section 10; none of those overrides takes effect until the owner approves.

Evidence is cited by file. The one new measurement (section 1.3) came from a throwaway script in the scratchpad and was not committed.

---

## 0. Summary

1. The hybrid already has the right *skeleton*: one authoritative world, a generic Widelands programme interpreter (153 of 178 production sites run), a conserved-ware ledger, an OpenRA combat core, a Mindustry slice, VP/era/split/collapse modules and a headless tournament harness. What it lacks is **breadth that is wired to the rest of the game** and **a growth loop that works without cards**.
2. With drafting switched off, **no faction ever founds a second settlement** (measured: 1 command centre each at minute 30, building count flat at about 18 per faction from minute 15). Three independent causes: founders are locked behind cards, the "settlers" recipe needs rations but the primitive kit has no food producer, and the AI has a hard cap and fixed per-kind quotas. Requirement 6 therefore needs real work, not a flag.
3. The current card system unlocks by **substring match on Widelands names** (`wl_patterns`) and by a handful of hybrid "kinds". That cannot scale to one card per building and unit, cannot express dependencies, and cannot be proven to leave no dead cards. It must be replaced by a **compiled content graph** (section 2).
4. The recommended draft is a **rolling 7-Wonders ring**: six packs of seven circulate, every faction picks one card every six game minutes and passes the pack on. The paper building adds a second pick from the same pack. Splits and collapses change the ring, which needs explicit rules (section 3).
5. **Paper does not exist** in the imported Widelands or Mindustry data. It must be a labelled hybrid ware with a real chain (section 3.5).
6. Scale: roughly **350-550 cards** depending on one open decision (section 2.3, Q3). Each faction will draft only 30-50 in a long game, so cards are sparse by design. That makes the *foundation set* and the *reachability guarantees* the load-bearing parts.
7. **Performance is the largest technical risk.** The 180-minute all-plus run took 4,308 s wall (about 2.5x real time overall, about 1x real time after minute 120; `docs/evidence/civilisation/long_all_plus_seed507_180min.txt`). More content will make this worse. A performance milestone comes before content waves.
8. Roadmap: 12 milestones, about 30 long autonomous sessions (a rough estimate; M10 runs alongside the content waves). The first three milestones (section 7) change nothing about cards: they make the no-card civilisation work, build the content graph and fix performance.

---

## 1. Current state

### 1.1 What exists and genuinely works

| Area | Evidence | Limit that matters here |
| --- | --- | --- |
| Square-grid terrain, deposits, buildcaps, real WL maps | `terrain.py`, `wl_map.py`, `tests/test_terrain.py` | Deposits are now inexhaustible (D22) |
| Generic Widelands programme interpreter | `wl_defs.py`, `workers.py`; `docs/generic_building_results.json`: 153/153 pass | The bench runs each building **in isolation with supplied inputs**; 0 are headed-verified, 0 AI-usable (`docs/COVERAGE.md`) |
| Carriers, roads, conserved wares | `logistics.py`, `ledger.py` | No flags, donkeys, priorities, rerouting; no inter-settlement transport except caravans (`trade.py`) |
| Forestry, farming, fishing, food, mining, smelting | tests listed in `CURRENT_STATUS_AND_GAPS.md` | Mines and smelters have **no worker entity**; construction is a **20 s timer with no builder** (D08 gaps G9) |
| OpenRA combat core | `military.py`, `rules.py`, `openra_damage.py`, 92 actors, 45 weapons imported | About 20 units and 8 buildings are buildable; no aircraft, transport, capture, repair, veterancy, support powers |
| Naval slice | `tests/test_naval.py` | Placeholder art |
| Mindustry slice | `industry/`, 11 of 214 blocks | No liquids, routers, sorters, bridges, turrets, reconstructors; 1 of 39 units |
| Territory and MCV/settlers founding | `territory.py` | Separation rule is spatial (OUTPOST radius 16 + buffer 4), which is a legitimate natural limit |
| VP ledger, eras, cycle reset | `vp.py`, `history.py`, `test_vp_eras.py` | World-sum threshold (6, 8, 8), not per-faction |
| Unrest, decline, split, collapse | `society.py`, `history.py` | Needs 3+ settlements; the successor copies the parent's cards |
| Draft engine | `tech.py`, `data/tech_cards.json` (33 cards) | Independent per-faction random offers, not a shared draft |
| Two AIs and a tournament harness | `ai.py`, `ai_plus.py`, `scripts/run_civilisation_tournament.py` | Both AIs cap command centres (3 / 3-6 by era) |
| Determinism and performance bench | `test_determinism.py`, `bench_sim.py` | Early game 32x real time; late game much slower |

### 1.2 What is imported but not functional

Numbers from `data/*.json` and `docs/COVERAGE.md`:

| Source | Imported | Simulated | Blocked reasons |
| --- | ---: | ---: | --- |
| Widelands production sites | 178 | 153 runnable | 25 blocked: `scout` (5), `ship: construct` (5), ferry fleet (5), pond/breeding/dike/balsa/fetch_water/dig/release (about 10) |
| Widelands military sites | 31 | 0 | "militarysite not implemented"; deprecated as soldier producers (D05), but towers and fortresses still have a role (section 4.6) |
| Widelands warehouses and ports | 17 | warehouse only | Port, headquarters and expedition logic missing |
| Widelands training sites | 11 | 0 | Superseded by D05; recommend a formal exclusion |
| Widelands workers | 156 | 40 | Builder, geologist, scout, shipwright, breeders |
| Widelands wares | 128 | 86 | |
| OpenRA buildings | 43 | about 8 usable | Production: `barr`, `tent`, `weap`, `afld`, `hpad`, `syrd`, `spen`, `kenn`, `fact`. Tech: `dome`, `atek`, `stek`. Support: `fix`, `gap`, `silo`, `mslo`, `iron`, `pdox`. Defence: `gun`, `pbox`, `hbox`, `ftur`, `tsla`, `agun`, `sam`. Power/economy (`powr`, `apwr`, `proc`, ...) are superseded by D05 and need a replacement rule (section 4.7). |
| OpenRA units | 49 | about 20 usable | Infantry `e4 e6 e7 spy thf medi mech dog`, aircraft (6), transports, ships (4 of 6), `harv`, `truk` and scenario actors (`ant`, `zombie`) |
| Mindustry blocks | 214 in about 90 Java classes | 11 | Largest classes: `ItemTurret` 17, `GenericCrafter` 16, `Wall` 10, `Reconstructor` 8, `UnitFactory` 6, `ConsumeGenerator` 6, `LiquidRouter` 6 |
| Mindustry units / items / liquids | 39 / 22 / 10 | 1 / 7 / 0 | |

Two honesty points for the programme's "no fake implementations" rule:

* "153/153 bench passes" means each building produces something when handed its inputs. It does not mean a faction can build the chain, haul the inputs and use the output. The programme needs a stronger definition of "done" (section 8.2).
* `docs/feature_status.json` tracks only 261 of 903 imported items as tested. Coverage reporting must stay generated from evidence, never hand-edited.

### 1.3 New measurement: no-card civilisation

Throwaway probe (not committed): `HybridWorld(507, profile="campaign")`, AI on (default baseline policy), `tech.tech_quantum` disabled, 30 game minutes, 34 s wall.

```
min  5: 71 buildings, 6 units   command centres: 1 each
min 15: 107 buildings           1 each
min 30: 109 buildings, 6 units  1 each
final kinds: hunter 12, processor 7, producer 27, quarry 12, ranger 27, warehouse 6, well 6, + a few wl:* fishers/gatherers
events: 'carrier_blocked' 591, 'worker_failed' 372, no deploy, no unit queued
```

Root causes, each confirmed in code:

1. `tech.primitive()["units"] == []`, so neither `settlers` nor `mcv` can be queued (`tech.unit_allowed`). The `dmb.card.settlers` card also requires `dmb.card.farming` and a working farm.
2. The `settlers` recipe costs 3 rations (`construction.RECIPES["warehouse"]["settlers"]`), and `tavern`/`bakery` are unlocked only by `dmb.card.cookery`. The primitive kit has no ration source at all.
3. `ai.MAX_CC = 3`, `ai_plus.MAX_CC_BY_ERA = (3, 4, 5, 6)`, and `_settlement_step` builds only up to the fixed quotas in `_plan()`. After the quotas are met nothing grows.
4. `worker_failed` 372 and `carrier_blocked` 591 in 30 minutes show the primitive economy is not clean either; it should be examined before it is declared a baseline.

Conclusion: requirement 6 needs a **foundation set** (section 5.1), an uncapped **demand-driven expansion planner** and a clean-economy pass.

### 1.4 Existing mechanisms that conflict with the new requirements

| Mechanism | Where | Conflict |
| --- | --- | --- |
| Command-centre caps | `ai.py:243`, `ai_plus.py:35` | Requirement 1 |
| Independent random offers, seeded by `(seed, faction, round)` | `tech.tech_quantum` | Requirement 2 (shared draft) |
| Substring unlock `any(p in name for p in pats)`; `farm` matches `farm`, `fishing_farm`, `wl:*_farm...` | `tech.kind_allowed` | Requirement 5; unlock sets are accidents of naming, and one card unlocks many buildings |
| Fixed AI draft priority list | `tech.ai_pick` | Requirement 2 (intelligent drafting) |
| Draft cadence 4 min, offer up to 7 | `tech.DRAFT_INTERVAL_MS` (S14) | Requirement 2 (6 min, pack of 7 passed) |
| Era ends on world-summed VP gain, thresholds (6, 8, 8), 75 min stall guard | `vp.py` (S13) | Requirement 7 |
| Split needs 3+ settlements and unrest for 10 min | `history.py` | Fine in kind, but nothing yet pushes a large faction toward it |
| No builder, mine or smelter workers | `construction.py`, `workers.py` | D08; also needed before "workers" in requirement 4 are meaningful |
| OpenRA sprites need the player's Red Alert content, available only on the Windows machine | `docs/ASSET_INVENTORY.md` | Ubuntu cannot import it (section 9) |

---

## 2. Proposed architecture: a compiled content graph

### 2.1 Principle

Do not write hundreds of implementations. Write **about 40 behaviour classes once** and describe hundreds of entities as data that select a class and supply parameters. The existing Widelands interpreter is already this pattern; the programme generalises it across all three source games.

```
pinned sources ─▶ importers ─▶ generated JSON (never hand-edited)
                              ─▶ override files (hand-written, labelled deviations)
                              ─▶ content compiler (new: wizard_rts/content/)
                              ─▶ ContentGraph  (entities, edges, cards, reachability)  ─▶ simulation
```

### 2.2 Entity model

Every building, unit, ware, worker, resource and card is an entity with a stable id (`widelands.barbarians_smelting_works`, `openra.3tnk`, `mindustry.silicon_smelter`, `dmb.paper`). A building or unit is a list of **components**:

| Component | Meaning | Existing implementation to reuse |
| --- | --- | --- |
| `production` | programme of consume / sleep / animate / produce / callworker | `workers.py` interpreter |
| `extractor` | reads a deposit layer | `resources.py`, `industry/extraction.py` |
| `conveyor`, `router`, `sorter`, `bridge`, `junction`, `overflow` | belt logic with backpressure | `industry/sim.py` (belts only) |
| `pump`, `conduit`, `liquid_router`, `tank` | liquids | new |
| `power_source`, `power_sink`, `battery`, `node` | per-grid balance | `industry/sim.py` |
| `unit_factory`, `reconstructor` | queue paid in delivered wares, spawn a `world.units` row | `construction.RECIPES`, `recruitment_quantum` |
| `weapon_mount` | turret or unit weapon | `military.py` |
| `garrison` | holds infantry, extends vision/territory | new (section 4.6) |
| `storage`, `settlement_centre` | warehouse behaviour | `territory.py` |
| `housing` | worker spawning / capacity | new (worker entities) |
| `research` | drafting modifier (the scriptorium) | new |

Units are rows in `world.units` for all three games (ARCHITECTURE_CONTRACT section 6). Mindustry drones (`mono`, `poly`, `mega`) can later be real **builders and miners**, closing the D08 gap in Modern.

### 2.3 Card catalogue is generated

A card is **derived** from an entity, not written by hand:

* `card.unlocks = [entity ids]` (exactly one building or unit, per requirement 2),
* `card.era`, `card.rarity` (copies in the deck), `card.requires_working`,
* `card.family` (see below), `card.tags` (economy, military, logistics, power, ...),
* `card.requires_cards` is **computed** from the production graph, then overridden only where a design reason is recorded.

Estimated size (to be confirmed by the compiler, which prints the exact table):

| Group | Entities | Cards | Note |
| --- | ---: | ---: | --- |
| Widelands production sites, merged into functional **families** across the five tribes | 178 sites | about 70 | `smelting_works` / `furnace` / ... form one family; a faction resolves a card to its own tribe's member. Tribe-unique buildings (Amazon, Frisian specials) are single-tribe families |
| Widelands warehouses/ports, military sites (as garrison towers) | 48 | about 15 | After exclusions (section 4.6) |
| OpenRA buildings (production, tech, support, defence) | 43 | about 35 | Minus superseded economy buildings |
| OpenRA units | 49 | about 40 | Minus scenario actors |
| Hybrid Prehistoric units and buildings | about 10 | about 10 | war lodge, clubman, spearman, slinger, scriptorium, paper maker |
| Mindustry blocks (class-level implementation, one card per block) | 214 | about 150 | Excluding logic, payload and core blocks (section 4.5) |
| Mindustry units | 39 | about 30 | |
| **Total** | | **about 350-400 cards**, about **500-550** if Widelands tribe members stay separate | The tribe decision is open (section 10, Q3) |

A faction drafts about 7 cards per 42 game minutes, so about 40-45 in a four-hour game plus bonus picks. That is roughly 10-12% of the catalogue, so each civilisation ends up very different. It also means a card is a real investment, which is why section 5.1 makes the foundation generous.

### 2.4 Static analysis that runs at build time (and in CI)

The compiler builds an AND-OR graph (ware <- recipe <- building <- card <- prerequisite cards/wares) and **fails the build** unless:

1. **Reachability.** Every card is obtainable from the foundation set by some finite sequence of cards of era <= its own, so a card is never permanently useless.
2. **Producer closure.** Every unit card has at least one producer-building card in the same or an earlier era, and every building card's recipe inputs are producible from the foundation plus earlier cards.
3. **No dependency cycles** across cards.
4. **Terrain/geography flags.** Mine, port, shipyard, pump and similar cards are tagged with the geography they need. The dealer (section 3.3) skips them for factions whose reachable territory cannot support them, and a test proves every flagged card has at least one possible faction on the shipped maps.
5. **Unsupported commands** make an entity `status: unsupported` with a reason, never silently free production (already ARCHITECTURE_CONTRACT section 4).
6. **Evidence.** A card is `draftable` only when its unlocked entity has `status: functional`, defined in section 8.2. The catalogue is therefore the honest measure of coverage: cards appear in packs only as their content really works.

This resolves the conflict between "every building gets a card" and "no fake implementations": **cards for unfinished content simply are not in the deck.**

### 2.5 Replace the substring unlocks

`tech.kind_allowed` becomes a set lookup: `entity_id in faction_unlocked`. The unlocked set is `foundation ∪ unlocks(drafted cards) ∪ granted`. All existing callers (`construction.check_placement`, `queue_unit`, the AIs, God Mode) already go through `kind_allowed`/`unit_allowed`, so the change is localised. The 33 existing cards become the seed of the new data via a migration script, with a test showing each old card's unlock set is preserved or deliberately changed.

---

## 3. Technology drafting: a rolling 7-Wonders ring

### 3.1 The mechanism (recommended)

* **Ring.** The factions are arranged in a fixed circular order (tribe/start order). Direction of passing alternates each *cycle*, as in 7 Wonders (left, right).
* **Packs.** At the start of a cycle the dealer creates one pack of seven cards per faction in the ring.
* **Round.** Every **six game minutes** each faction holds one pack, picks one card, and passes the remaining cards to its neighbour. A pack has one card fewer each round, so a cycle is seven rounds, **42 game minutes**. Then new packs are dealt.
* **Visible information.** A faction sees the cards that remain in the pack in front of it, and may see (as the AI does) what its neighbour picked last round.
* **Timing.** A pick must be made within the round window. If it lapses, a deterministic fallback pick is made (the AI's rank-1 card) and logged as `draft_lapsed`, so the ring never stalls and the log shows what happened.
* **Era change.** A world entering a new era runs an out-of-cycle **era round**: one pack of seven per faction, at least four cards from the new era, one pick each (two for the leader, section 6.3), without disturbing the cycle clock.

This preserves what the current engine already has (seeded determinism, logged events, window and lapse) and replaces the per-faction random offer with the shared ring.

### 3.2 Why single pick per round rather than a full 7-card age

The request says a round starts every six minutes and the paper building gives "two cards instead of one during a drafting opportunity". If every round were a complete 7-pick age, a faction would pick 70 cards per hour; with 500 cards that is far too fast and the building would be negligible. A single pick per six minutes is consistent with both statements. **This is open decision Q1**; the alternative changes numbers, not structure.

### 3.3 Dealing packs (the part that makes the catalogue playable)

Dealing is deterministic from `(seed, cycle)`. For each pack the dealer:

1. Draws from cards with `era <= current era` that are `draftable` (functional, section 2.4) and not geographically impossible for *any* faction in the ring.
2. Weights by rarity (copies), so cheap, common cards appear often and powerful ones rarely.
3. **Coverage guarantee.** Across the six packs, every faction gets at least two cards that are eligible for it right now (its next-step cards: producer building for a unit it holds, a missing input chain, an unfilled era need). Otherwise a faction's pack could hold seven irrelevant cards.
4. **No dead packs.** At least one card in each pack has no unmet prerequisite for the first holder.
5. Includes at most one copy of a card per pack. Different packs may hold the same card, so there is no global scarcity and nothing can be permanently denied. A faction never takes a card it already holds (such cards are dead weight in a pack and are replaced at deal time or skipped).

Cards in a pack that a faction cannot use (another tribe's family member) are still passed on: they are a denial resource, as in 7 Wonders. Family cards resolve to the recipient's own tribe member.

### 3.4 Ring changes caused by the simulation

The ring is a first-class structure with tests, because splits and collapses are central to the game:

* **Split.** The successor is inserted next to its parent and receives, at the next round, the pack that the parent would have passed to its neighbour (the ring grows by one; that pack loses nothing). It receives the parent's cards as today. Packs dealt for a cycle already in progress are not rebuilt.
* **Collapse.** A collapsed faction's pack is passed through unchanged (skipped) each round, and its seat closes at the next cycle.
* **Wizard events.** The wizard does not alter the ring in this programme.
* **Cycle reset.** Full cycle reset (D11) discards the ring, as it discards cards.

### 3.5 Paper and the scriptorium

**Paper is a new hybrid ware, `dmb.paper`.** I searched the imported data: Widelands has reed, rope, cloth, spidercloth but no paper or parchment ware in this pin, and Mindustry has none. Labelled as hybrid-defined in `SOURCE_REUSE.md`.

| Piece | Era | Definition (proposed, tunable) |
| --- | --- | --- |
| Reed supply | Prehistoric | Already imported: `reed_yard` / `reed_farm` families (card `dmb.card.crafts`) |
| **Paper maker's hut** | Prehistoric/Historic | Worker entity "papermaker"; consumes reed 2 + water 1, produces paper 1 per 90 s. Cost: log 3, plank 2, granite 1 |
| **Paper mill** | Modern | Mindustry-style `GenericCrafter` on belts: logs 2 + water + 0.5 power/s, produces paper 4 per 60 s. Gives scale for a leader that wants an extra pick every round |
| **Scriptorium** | Historic | Real building with a scribe worker entity and a 6-paper store. Cost: plank 6, granite 3, cloth 2 |

Rules:

* The scriptorium grants **one extra pick per round, taken from the same pack immediately after the first pick, if the building is operational and holds 2 paper**. Paper is consumed at the moment of the pick. It is never spent by an idle building, so a faction that cannot pick two (the pack has one card, or nothing the faction wants) pays nothing.
* **At most one extra pick per round**, regardless of how many scriptoria. A second scriptorium adds capacity (paper buffer), not picks.
* **Extra-pick tokens** from other sources (era leader reward, section 6.3) are a separate counter and stack with the scriptorium, up to a total of 2 extra in one round.
* **Interaction with passing.** Taking two cards leaves the neighbour a pack with 5 instead of 6 cards, so the advantage has a cost to the neighbour (the 7-Wonders "hate-draft" pressure) and shortens that pack's life. The pack still circulates until empty; a faction handed an empty pack skips that round and loses nothing else.
* **Why it should not break the system.** The bonus is bounded (one card per six minutes), expensive (a chain of three buildings, two workers, and 2 paper per use), loses value if destroyed (the paper store is physical stock that can be lost), and it is itself a card that must be drafted, so a faction that takes it forgoes another card.
* **Balance lever.** Paper use (2) against production (about 0.67 paper/min for one hut) means one hut sustains about one extra pick per 3 minutes of capacity, so a single hut is enough for every-round use but is a single point of failure; a mill makes the extra pick resilient. The ratios live in data, and the tournament reports "extra picks used / available" per faction.

### 3.6 AI drafting strategy

New `wizard_rts/ai_draft.py`, deterministic, with weights per AI policy. For each card in the faction's current pack it computes a utility:

```
U(card) = value_now(card) + value_chain(card) + value_denial(card) - risk(card)
```

* **value_now.** Does the faction already hold what the card needs? Examples: a unit card whose producer building is unlocked and built scores high; a building card for a ware currently in shortage (from the economy report: unmet demand in `_bottleneck_step`) scores high.
* **value_chain.** Plans toward goals. The AI keeps 1-3 **capability goals** (for example "medium tanks", "silicon", "second food chain", "airfield"). For a goal it computes the cheapest set of missing cards on the AND-OR graph (a hyperpath cost), then values a card by how much it shortens the path, discounted by the probability the remaining cards appear in future packs (estimated from the pack contents it can see and the dealer's rarity). Unit cards without a producer get partial credit only if the producer card is already in hand or visible in the pack to be passed (the owner's "powerful units but still need the factory" tension).
* **value_denial.** If the pack is going to the neighbour who is a military threat (distance, army strength, border contact) and the card is high-utility for them but low for us, add a denial term. Weighted by policy.
* **risk.** Infrastructure the faction cannot build (no mountains for a mine card, power with no fuel, ports with no coast), or workers it cannot house.
* **Doctrines.** A policy sets goal weights and a doctrine vector (expansionist, industrial, militarist, naval, balanced) from tribe, terrain composition around its homeland (reuse `history.fertility`), nearby threats, and whether it leads or trails on VP. The AI re-plans every round.
* **Extra pick.** The second pick is chosen after the first, from the reduced pack, with the same scorer.
* **Self-tuning.** The weights are a small vector (about 12 numbers). Tune them by hill-climbing or CMA-ES against tournament results, not by the existing NN harness, which `TRAINING_PROGRAMME.md` reports as failing on the cross-system domain. Evaluation metrics: pick-to-use latency, share of picks used within 12 minutes, orphan rate, VP and army strength against baselines (random, greedy-by-cost, the fixed list).

AI quality is measured against three baselines, so "intelligent" has a number: random pick, fixed priority list (today's `ai_pick`), and a greedy scorer with no goals.

---

## 4. Economic integration: completing the three economies

### 4.1 Ordering rule

Implement by **behaviour class**, not by building. Each wave delivers a class, a generated test per entity of that class, and card eligibility for the entities that pass. Cards for the rest stay out of the deck (section 2.4).

### 4.2 Foundations before breadth (each is a gap now)

1. **Builder workers.** Replace the 20 s timer with a real builder: a worker entity walks from the nearest warehouse, builds over time, consumes delivered wares per stage (D08). Required before "workers" can claim to be real.
2. **Mine and smelter workers** as entities (the hidden-worker exception).
3. **Worker housing and counts.** Many Widelands sites need two or more workers of specific roles; the interpreter supports roles but spawns them from a pseudo-ware pool (`recruit`/`carrier`). Decide the supply of workers (section 5.1) as a real economic input so that a large dispersed civilisation can actually run out of people, a natural brake on uncapped growth.
4. **Transport that scales.** Flags with queues, second carriers (donkeys, oxen) on busy roads, rerouting around blocked roads. Without this a 15-settlement faction's logistics will jam; with it the "challenges of managing dispersed territory" arise from physics, not rules.
5. **Inter-settlement economy.** Today wares move on a road component or by caravan (`trade.py`). Define: a settlement's stock is local; a road link joins economies; separate settlements trade by caravan or ship and may ask the capital for goods. This is the mechanical source of isolation unrest.

### 4.3 Widelands completion

| Group | Action |
| --- | --- |
| 25 blocked production sites | Implement the missing worker commands as generic interpreter commands: `scout` (reveal radius; fog is not simulated, so scouting also feeds AI target knowledge), `breed`, `release`, `fetch_water`, `dig`, `check_dike`, `plant_balsa`, `find_pond`; ferry and ship construction with a shipwright |
| Warehouses and ports | `settlement_centre` (headquarters and warehouse) already; port adds expedition and ship transport as cargo ferry between settlements |
| Military sites (31) | Recast as **garrison towers** (section 4.6) |
| Training sites (11) | Formal exclusion (D05). Keep definitions, mark `excluded: superseded by OpenRA military` |
| Wares and workers | Counts reported by the compiler; every ware needs at least one producer and one consumer or is flagged |

### 4.4 OpenRA completion

Classify by the mechanic missing, then do whole classes:

* **Tier A, fits today's combat:** remaining infantry (`e4` flamethrower, `e7`, `dog`, `medi`, `mech`), light and heavy vehicles, defences (`pbox`, `hbox`, `agun`, `sam`), walls. Cost: data plus tests.
* **Tier B, needs one new mechanic each:** transports/APC cargo, engineers and capture (`e6`, `thf`, `spy`), repair (`fix`, `mech`), aircraft (airfield `afld`, helipad `hpad`, rearm), radar/tech buildings gating (`dome`, `atek`, `stek`), support powers (`gap`, `iron`, `pdox`, `mslo`). Each mechanic becomes one component with its own tests.
* **Prerequisites.** OpenRA `prerequisites` strings (`~afld, stek, ~techlevel.high`) are already imported; the compiler turns them into `requires_working` and card edges instead of the hand-written `RECIPES` dependencies.

### 4.5 Mindustry completion

By class (214 blocks, about 90 Java classes), in order: `GenericCrafter` and `AttributeCrafter` (16+3) → `Drill` family → `Router/Sorter/Junction/Bridge/OverflowGate` → liquids (`Pump`, `Conduit`, `LiquidRouter`, `LiquidBridge`) → generators (`ConsumeGenerator`, `Solar`, `Thermal`, `Battery`, `PowerNode`, `PowerDiode`) → `UnitFactory` and `Reconstructor` (14) → `ItemTurret`/`PowerTurret`/`LiquidTurret` (about 24) → `Wall`, `MendProjector`, `OverdriveProjector`, `ForceProjector` → `Separator`, `Unloader`, `StorageBlock`.

**Proposed exclusions, with reasons, for owner confirmation:** `LogicBlock`, `LogicDisplay`, `MemoryBlock`, `MessageBlock`, `SwitchBlock` (no gameplay value here); `CoreBlock` (collides with the warehouse/settlement model; a Mindustry core could be an upgrade skin of a settlement centre later); `PayloadConveyor/Router/Loader/Unloader`, `MassDriver`, `PayloadMassDriver` (payload systems are a second logistics layer; revisit after the first release). Each exclusion is recorded in the compiler output, so none is silent.

Mindustry ware namespace and the ware map already live in `mindustry_overrides.json`; extend it rather than invent a second mechanism. Liquids need a conserved quantity (the ledger already handles belt and machine buffers) and a pipe-network step per quantum with the same backpressure contract as belts.

### 4.6 Garrison towers (Widelands military sites)

Widelands soldiers are deprecated, so the 31 military sites would otherwise be dead content. Proposal: they become `garrison` buildings that **hold OpenRA infantry**, extend territory by a small radius and vision (the Widelands conquer radius), and shoot with the garrisoned units' weapons. Capture only by destroying or by an engineer once capture exists. This gives border expansion by force a Widelands feel and removes a free defensive-bonus loophole. Needs owner approval (Q8).

### 4.7 OpenRA power and refineries

D05 supersedes OpenRA refineries, harvesters and credits. For OpenRA buildings whose prerequisite is `~powr`/`~apwr`, define: **power is satisfied by the Mindustry power grid in Modern and later; before Modern those buildings simply have no power requirement.** That keeps OpenRA's high-tech gating honest without a second power system.

### 4.8 Asset plan

* Widelands art is on this machine and imports with `import_generic_art.py`.
* OpenRA unit and building sprites come from the Red Alert content packages and `OpenRA.Utility`, which exist only on the Windows machine (`docs/ASSET_INVENTORY.md`). Until a Windows import run, new OpenRA entities use **labelled placeholder shapes**, already the convention for ships.
* Mindustry art: `import_mindustry_art.py` exists. Confirm the licence of the sprite folders in `MINDUSTRY_PROVENANCE.md` before bulk copying.
* Every added asset gets a row in `ASSET_INVENTORY.md` and `LICENSES.md`, enforced by a test that fails when a shipped art file has no manifest row (new, cheap).

---

## 5. Civilisation development: with and without cards

### 5.1 Foundation set (what "essential starting buildings and units" means)

A foundation is defined by **closure**, not by taste: the smallest set of buildings and units from which the faction can produce every ware its settler recipe needs, and then more settlers. Computed per tribe by the compiler, then reviewed by hand. Expected contents:

* Forestry: woodcutter, forester, sawmill. Stone: quarry. Water: well.
* Food: hunter and fisher where available, **plus one ration source** (a basic tavern or equivalent, no bread chain required). This is the missing piece in the measurement.
* Reed/crafts only if a tribe's settler recipe requires them.
* Units: carrier, builder, **settler** (the Prehistoric founder, `dmb.settlers`).
* The warehouse itself.

Mines, farms, smelting, metals, military and everything else are cards. The `dmb.card.settlers`, `cookery` (ration part) and the primitive ration source move into the foundation.

### 5.2 The no-card civilisation (requirement 6)

Acceptance for the `nocards` mode (drafting disabled in `tech_quantum`; a test-only world flag):

* All six factions, 10 seeds, 120 game minutes: every faction founds at least 3 settlements, at least 70% of them within 90 minutes; zero factions collapse from economic causes; zero permanent stalls reported by `diagnostics.watch_quantum`.
* Settlements 2..N are self-sufficient within 15 game minutes of founding (log, plank, granite, ration).
* Ware ledger balances (the existing `ledger.check`).
* `carrier_blocked` and `worker_failed` rates are reported and bounded (a number to be set from the first clean run).

### 5.3 Expansion without caps

Delete `MAX_CC` and `MAX_CC_BY_ERA`. Growth is limited by **cost, space, people and cohesion**, all emergent:

* **Space.** The separation rule (radius 16 + buffer) already caps how densely settlements fit; on the 544x288 map the geometric ceiling is about 100, far above any plausible demand, so it is not an artificial limit.
* **Cost.** A settler wagon costs real wares and a person (section 4.2 item 3). Add a **founding cost that scales with distance from the capital and with settlements held** (formula in data). This is a tunable pacing lever, not a cap: it asks for more surplus the larger you are.
* **Cohesion** (the unrest model in `society.py`) gains terms for **empire size** (settlements held relative to the faction's administrative capacity, for example scribes/courts if the owner wants such buildings), **logistic distance** (road length or transit time to the capital rather than Chebyshev distance), **shortage of goods** beyond rations (cloth, beer, luxury), and the **hegemon** pressure from section 6. Splits and collapses then arise from named, logged pressures (the pressures dict already goes in the chronicle).
* **AI expansion planner** (replacing the quota logic): value a candidate site by deposits and fertility inside its radius, coast access, distance to rivals, defensibility, road connectability and cost; expand when the home economy has surplus of settler wares above a reserve and the cohesion forecast is acceptable. Both AIs use it; `ai_plus` keeps its extras.
* **Demand-driven build planning.** Replace the fixed quotas in `_plan()` with a demand graph: wares needed by pending recipes, queues and construction sites propagate to producers (the existing `tribe_step` and `_bottleneck_step` already do part of this); build the producer for the bottleneck ware, scale the count by demand. This also lets the AI use whatever cards it holds.

### 5.4 With cards

The same planner reads the unlocked set. Order of operations for a new unlock: (1) place the building where its inputs are within reach, (2) request staffing, (3) wire its inputs by roads or belts, (4) set an output sink (storage, unit queue, construction). Section 8.2 tests each step per entity.

---

## 6. Historical progression

### 6.1 Rule

An era ends when **any single faction** holds `T_e` VP **continuously for a sustain window**, or when the stall guard fires (reported separately). Combined VP no longer counts. Settlements remain the main source; conquest remains.

### 6.2 VP across eras (recommendation and alternatives)

Compared options:

| Option | Behaviour | Problem |
| --- | --- | --- |
| A. Absolute standing VP, fixed 10 | Leader at 10 stays at 10 | Next era ends instantly |
| B. Reset: each era counts only VP earned in that era | Fair restart | Punishes the leader's empire; 10 new settlements per era is unrealistic |
| C. **Rising bar: `T_next = max(base_next, leader_VP + Δ)`** | Leader must grow again; others have time | Needs a tuned Δ |
| D. Cumulative thresholds (10, 20, 30) | Simple | Same as C but the bar ignores losses |

**Recommended: C**, with `base = (10, 14, 18)` and `Δ = 5` to start. After the transition the leader stands at about 10, so the next target is at least 15; the other five need to double their size to threaten. Tuned by simulation toward the owner's goal of "significantly longer" eras (the target ranges are in Q9).

Safeguards against accidental or immediate transitions:

1. **Sustain window.** `T_e` must be held for 5 game minutes (a settlement taken and lost does not trigger).
2. **Minimum era duration.** No transition earlier than a data value (default 45 minutes after the previous one).
3. **No double counting.** The VP ledger remains idempotent per key; conquest keys are per settlement id (already true in `vp.py`).
4. **Stall guard** longer than today (150 minutes) and reported as a *non-natural* transition.
5. **Test.** A property test replays logged VP histories and asserts no transition occurs with a lead below `T_e`, nor twice within the minimum duration.

### 6.3 Leader rewards and the cost of success

On the transition the **era leader** (the faction that crossed the bar first; ties by sustained VP then lowest id) receives:

1. **One extra-pick token** usable in the era round (section 3.1), or banked for the next regular round, expiring after one cycle.
2. **Upgraded settlements.** The capital and the settlement nearest the capital are upgraded to the new era's centre for free (an `S08` upgrade with the cost waived); others upgrade at the S08 cost (difference plus 25%) like everyone else.
3. A **chronicle entry** and a named title, used later by dialogue and quests.

And it pays for success through the **hegemon pressure**: while the leader's VP exceeds the runner-up's by more than `Δ_h`, each of its settlements gains unrest proportional to the lead (`society.pressures` gets a `hegemon` term, logged like the others). The other five receive a small cohesion bonus when they have a military contact with the hegemon. The goal is observable cause: "Red split because it ran at 14 VP against a runner-up at 6, with two outposts 90 road-tiles from the capital and ration shortages."

### 6.4 Era round

When the era changes, a new draft opportunity begins immediately: one pack per faction heavy in new-era cards, one pick each, two for the leader. The regular cycle clock is unaffected, so there is no double bonus from timing coincidence.

---

## 7. Implementation roadmap

Each milestone is independently testable, ends with a committed tournament report, and does not start without owner approval. Sessions are rough units of one long autonomous run.

| # | Milestone | Content | Acceptance | Sessions |
| --- | --- | --- | --- | ---: |
| M0 | **Instrumentation and performance** | Profile the late game (the 180-min run went 1x real time after minute 120), spatial indexing for units/buildings, event-driven economy hot spots; baseline report extended with idle reasons per building; throwaway probes of section 1.3 become permanent scenarios | 180-min six-faction game under 30 min wall on the T460 (target 6x real time); determinism and 338-test suite green | 2 |
| M1 | **No-card civilisation** | Foundation set; ration source; builder and mine workers as entities; remove caps; demand-driven build planner; expansion planner; founding cost; flags/second carriers; unrest terms | Section 5.2 acceptance, 10 seeds, 120 minutes | 3 |
| M2 | **Content graph and card compiler** | `wizard_rts/content/`; unify Widelands/OpenRA/Mindustry into one catalogue; family merge; reachability and producer-closure checks; migration of the 33 cards; replace substring unlocks | Compiler passes on current content; test fails on a deliberately orphaned fixture; old unlock sets reproduced or changes listed | 2 |
| M3 | **Draft ring** | Ring, packs, dealer with coverage guarantee, lapse fallback, split/collapse rules, events and snapshot, God Mode view, deterministic across hash seeds | Ring property tests; 1,000 simulated cycles never produce a dead pack; replay equality | 2 |
| M4 | **Paper and scriptorium** | `dmb.paper`, paper maker, paper mill, scriptorium with worker and store, extra-pick logic, ledger entries | Conservation test; extra pick only consumes paper when used; pack-size effect on the neighbour verified | 1 |
| M5 | **AI drafting** | `ai_draft.py`, goals, hyperpath cost, denial, doctrine; tuning harness | Beats the three baselines on pick-to-use latency and VP across 20 seeds with CI95; orphan rate under a set threshold | 2 |
| M6 | **Eras and VP rework** | Single-faction threshold, rising bar, sustain window, leader rewards, hegemon pressure, era round, longer stall guard | Section 6.2 property tests; 10-seed historical runs with eras in the target ranges; at least one natural transition per era in most games | 2 |
| M7 | **Widelands completion wave** | 25 blocked sites, warehouse/port, garrison towers, recreated Widelands bench as a connected-economy test | All Widelands families `functional` by section 8.2 or listed as excluded | 3 |
| M8 | **OpenRA wave A** (Tier A) and **wave B** (mechanics) | Remaining infantry, vehicles, defences, walls; then transports, capture, repair, aircraft, tech buildings, support powers | Each unit/building `functional`; combat matrix report | 4 |
| M9 | **Mindustry waves** | Crafters, drills, routing, liquids, power, turrets, unit factories, reconstructors, then the rest | Class library tests; each block `functional` or recorded exclusion | 5 |
| M10 | **Balance campaign** | Automated reports drive tuning (section 8.4); card rarity, costs, era numbers | Balance acceptance in section 8.5 | 3 |
| M11 | **Headed verification and polish gate** | Content gallery scenario, draft ring view, 16x autoplay, placeholder register | Headed suite plus screenshots reviewed | 1 |

M7-M9 are the long tail; each is repeated in small increments with a card pool that grows only as content becomes functional, so the game stays playable between waves. Order M0 → M1 → M2 → M3 → M4 → M5 → M6 can finish before any content wave; M7-M9 can then run in any order, and M10 is continuous.

---

## 8. Testing and balancing

### 8.1 Layers

1. **Property tests** (fast, in the normal suite): content-graph reachability and closure, draft ring invariants (each card in exactly one place, ring order stable under splits and collapses, determinism under different `PYTHONHASHSEED`), VP monotonic rules, ledger conservation for every transport mode.
2. **Generated per-entity tests** (parametrised from the catalogue, in a separate marker so the quick suite stays quick): for each entity, a laboratory world builds it from a flagged test grant, supplies inputs by real delivery, and checks the observable outcome (ware produced, unit spawned and move/attack/die, power stabilised, liquid delivered).
3. **Integration scenarios**: connected chains (ore to unit), built by the AI from a bare warehouse, with the card mechanism.
4. **Headless tournaments** (existing `run_civilisation_tournament.py`, extended): modes `nocards`, `cards`, `draft-only` (peace, economy only), `war`, `crisis`, `historical`, `stress`. Parallel seeds with `--jobs`. CI95 reporting already exists.
5. **Headed Godot**: one screenshot test per behaviour class (a content-gallery scenario places one of each), plus the draft ring view and 16x autoplay.

### 8.2 Definition of "functional" (the no-fakes rule)

An entity is `functional` only when all of these hold, each backed by a test id recorded in `feature_status.json`:

1. **Schema.** Compiles; no unsupported command.
2. **Isolated behaviour.** The laboratory test passes.
3. **Connected.** Inputs reach it by the real transport and outputs reach a consumer, in a scenario.
4. **Draftable.** Its card is reachable (section 2.4) and drafting it unlocks exactly that entity.
5. **AI-usable.** In a seeded tournament at least one AI builds or produces it without a grant, or it carries a justified `ai_unused: reason`.

A cosmetic stub cannot pass 2 or 3. `make_coverage.py` generates the table from these ids and the CI job fails if `functional` has no evidence.

### 8.3 What the headless runs must prove (mapped to the owner's list)

| Owner's statement | Test or metric |
| --- | --- |
| Six factions survive and expand with no cards | `nocards` acceptance (5.2) |
| Factions operate all supported economic systems | Per-class connected scenarios; tournament coverage of classes used |
| Every building and unit can be unlocked | Reachability check plus a simulated draft that unlocks each card at least once from the foundation within a time bound |
| AI drafts complementary technologies | Pick-to-use latency, complementary-pair rate (unit card plus producer within N picks) |
| Additional settlements without caps | Max settlements per faction distribution; correlation with surplus and cohesion |
| Military units produced, deployed and used | Unit lifecycle events per type; combat matrix |
| Disruption, catastrophe and war affect development | Counterfactual runs: same seed with and without outbreaks, compared with CI |
| A faction reaches 10 VP and triggers an era | Natural transition fraction per era |
| Large factions split or collapse for reasons | Chronicle pressures present on every split; no split without a logged cause |
| Stability and performance | Step time p95, memory, wall per game hour; crash and invariant counts |

### 8.4 Automated reports (new `scripts/content_report.py`, output next to the tournament report)

* **Unused buildings / units:** built or produced count, uptime, first-use time, `used in combat`, per entity, aggregated across games.
* **Bottlenecks:** idle reasons per building from `worker_failed`, `carrier_blocked`, missing-ware counters, ranked by lost production time.
* **Inaccessible tech:** cards never dealt, never picked, picked but never built, built but never used; geography-excluded cards.
* **Ineffective AI strategies:** policy comparisons with CI95; card regret (utility predicted at pick versus observed use).
* **Balance:** win rate and VP by tribe, start position, doctrine; unit cost-effectiveness from a round-robin headless duel matrix; era durations; settlement growth curves; split and collapse causes.
* **Cards:** pick rates by card, with an alert when a card is picked in more than about 70% of games or less than about 2%.

### 8.5 Balance acceptance (initial, tunable)

No tribe wins more than a stated share beyond chance; each of the four doctrines is viable (not the weakest in all games); at least 80% of catalogue cards appear in at least one game of 20; era durations land in owner-approved bands; no card is both always picked and never used.

### 8.6 Statistical method

Pair seeds so a map is played under each policy (the existing mirror pairing). Report mean and CI95. Use at least 10 seeds for a milestone claim and 30 for balance conclusions. Keep a git-tracked `docs/evidence/` summary per milestone rather than raw logs.

---

## 9. Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| **Performance** at scale (about 1x real time late in 180-minute runs; content will add entities) | High | M0 first; profile with `bench_sim.py --profile`; spatial indexing; LOD only with the equal-outcome test required by ARCHITECTURE_CONTRACT section 8 |
| **Sparse card pool** makes factions incoherent | High | Generous foundation, coverage guarantee in the dealer, family merge across tribes, rarity weights, AI goals |
| **Dead or trap cards** | Medium | Static checks, producer closure, "only functional content is dealt" |
| **Scope creep in Mindustry** (about 90 block classes) | High | Class order, explicit exclusions, waves ship value without waiting for the tail |
| **Uncapped growth** produces instant era transitions or runaway leader | Medium | Founding cost scaling, rising bar, sustain window, hegemon pressure; all tuned by simulation |
| **Draft ring bugs with splits/collapses** | Medium | Ring is a first-class tested structure, 1,000-cycle property test |
| **Art blocker** for OpenRA sprites on Ubuntu | Certain | Labelled placeholders; a Windows import run later |
| **Test time** (current suite 338 tests, about 12-25 minutes) | Medium | Markers; generated entity tests run in a separate job |
| **Licence compliance at breadth** | Medium | Manifest-row test for shipped art; GPL notes per importer |
| **AI tuning overfit to one map** | Medium | Seed splits train/validation/test (the env harness already does this) and two shipped WL maps |

---

## 10. Decisions needed from the owner

Defaults are what I will do if no answer is given; each has a cost if wrong.

| ID | Question | Recommended default |
| --- | --- | --- |
| Q1 | Is a "round" **one pick** (rolling, 6-minute cadence, cycle of 7 rounds = 42 min) or a **full 7-pick age** every six minutes? | One pick per round; the second pick from the paper building is a second card from the same pack |
| Q2 | Pass direction: alternate each cycle (as in 7 Wonders), or fixed? | Alternate |
| Q3 | Are Widelands tribe members **families** (one card, tribe resolves) or **separate cards**? | Families, with tribe-unique buildings as single-tribe cards (about 350-400 cards instead of 500-550) |
| Q4 | Bundle trivial variants (wall tiers, conveyor tiers, fences, sandbags) into their parent card, or one card each as stated? | One card each, but common rarity; reconsider after the first pack statistics |
| Q5 | Paper chain: reed + water → paper in Prehistoric; mill in Modern; scriptorium in Historic. Acceptable? Costs as in 3.5? | Yes |
| Q6 | **Foundation set**: forestry, quarry, sawmill, well, hunter/fisher, one ration source, carrier/builder/settler. Anything else that must be free? | As listed in 5.1 |
| Q7 | Mindustry exclusions in 4.5 (logic, cores, payload, mass drivers)? | Confirm |
| Q8 | Widelands military sites become garrison towers holding OpenRA infantry; training sites excluded? | Yes |
| Q9 | Era length targets. Current measured (all-plus 180-minute run): Prehistoric about 30 minutes, Historic about 37, Modern about 50. | Prehistoric 70-90, Historic 90-120, Modern 90-120 game minutes, tuned by M6 |
| Q10 | VP carry rule: option C (rising bar, Δ = 5) or another? | C |
| Q11 | Leader rewards (extra pick, free capital upgrade) and hegemon unrest as described? | Yes |
| Q12 | Replace existing decisions S13 (world-summed VP), S14 (4 min cadence), S12 (split at 4+, code uses 3) and D04's "provisional 10"? | Yes: record as D22-D26 after approval |
| Q13 | Is dropping the OpenRA power requirement before Modern acceptable (section 4.7)? | Yes |
| Q14 | Are Mindustry drones (`mono`, `poly`, `mega`) allowed to become the Modern builders/miners? | Yes, after M9 crafters and power |
| Q15 | Do you want the wizard to have any hand in drafting (steal, gift, burn a card)? | Out of scope for this programme |

Existing decisions this plan would supersede once approved: **D04** (provisional 10-VP threshold becomes the single-faction rising bar), **S04/S13** (world-sum thresholds), **S05/S14** (cadence and independent offers), **S12** (split threshold wording), and the `MAX_CC` constants (no decision recorded for them).

---

## 11. First actions after approval

1. M0: reproduce the late-game slowdown with `bench_sim.py --profile` at minute 120; commit a baseline report.
2. M1 step 1: write the `nocards` tournament mode and its failing acceptance test before changing the AI.
3. Open `docs/DECISION_REGISTER.md` rows for the answers to Q1-Q15.
4. Update `ROADMAP_NEXT_RUN.md`, `STATE_OF_PLAY.md` and `CURRENT_STATUS_AND_GAPS.md` only as milestones complete (this plan is the only document changed now).
