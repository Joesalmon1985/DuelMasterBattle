# DuelMasterBattle — Mechanics Completion Plan v4

**Assessed against:** `main` @ `143797ba` (13 Oct 2026, merge of PR #15 `work/gameplay-assets-v3`). This is the newest commit on any branch; the V3 work is already merged, so the V3 report's "not merged into main" is out of date.
**Replaces:** the attached brief "Complete and Validate All Building, Unit and Gameplay Mechanics" as the working instruction. Its goals stand; its ordering, definitions and several assumptions change.
**Rules kept as they are:** seven-round pack draft per era (packs of 7, 6-minute rounds, ring passing, leftover rule, paper bonus picks), Widelands production in Prehistoric, whole OpenRA roster by Historic, Mindustry industry in Modern, Mindustry units in Dystopian, D01–D25.

---

## 1. What I measured on main

| Check | Result |
| --- | --- |
| Full Python suite (`pytest WizardRTSHybrid/tests -n 2`, minus `test_five_minutes.py`) | **851 passed, 18 skipped, 0 failed** in 15 min (Python 3.13, no Godot installed, so Godot-dependent tests skip). Brief item 17.1 is closed. |
| Hash baselines (`scripts/hash_gate.py check`) | All three seeds diverge at minute 1. Stale, as V3 admitted. They also only cover the ungated `test_showcase` world, not the shipped draft rules. |
| Coverage report | 596 entities "functional", 0 pending. "Functional" means "in the build menu or has a recipe". The `verified` field promised in `coverage.py`'s docstring does not exist in any row. |
| Content graph | 593 entities, 380 generated cards: 116 Prehistoric, 61 Historic, 162 Modern, 41 Dystopian. |
| Draft simulation (real `draft.deal` and `pass_packs`, 40 seeds, 6 factions, a picker that always takes the most useful card) | See section 2. |

Four read-only code audits (Mindustry, OpenRA, Widelands, command surface) produced the defect list in section 6. I confirmed three of those by reading the code myself (assembler intake, unarmed pillboxes, ship cost fallback); the rest come from the audits and each must be reproduced with a failing test before it is fixed.

---

## 2. The central finding: the draft cannot deliver the content

The brief's section 9 asks that every card be usable and that a faction can progress into advanced Mindustry industry without grants. Under the rules as shipped, that is arithmetically impossible, and no amount of per-entity work will change it.

- A phase deals 42 cards. Modern has 162. A faction picks 7 per era, 28 per game. A whole six-faction game drafts at most 168 of 380 cards and unlocks about 236 of 540 gated entities.
- The one industrial line the AI can build needs five specific cards (four Modern, one Dystopian). In 240 simulated faction-games with a picker that prioritised exactly those cards, **no faction ever held the whole line**; the average was 0.3 of 6 machines.
- In Dystopian a faction unlocks about 6 Mindustry units but has the producing building for 1.5 of them, and no drill, belt, power or smelter to feed it.
- Prehistoric: a faction ends with about 6 usable cards out of the 14–29 its tribe has.
- Plan v2 section 5.2 specified two dealer guarantees to make sparsity playable (two immediately useful cards per first pack; a producer card dealt for every unit card). Neither is implemented; `deal` only rotates tribes.
- The baseline AI's `tech.ai_pick` only knows the old hand-written card ids, so with generated cards it takes whatever sorts first. Unpicked rounds also default to `offers[0]`.
- No recorded run has reached Dystopian by play: the 180-minute stability run ended in Modern.

So the Mindustry half of the game is currently reachable only through developer grants. This has to be fixed first, because it decides which entities can ever matter and what "end-to-end" can mean.

---

## 3. Assessment of the attached brief

**Right, and confirmed by the code**
- Coverage overstates integration (17.4). Confirmed in every system.
- Per-entity tests mostly inject inputs and force completion rather than use logistics.
- Sea trade is missing; markets are inert.
- No late-game performance benchmark exists; none contains meaningful Mindustry load.
- Hash baselines need re-recording.

**Wrong, missing or unworkable**
1. **It treats reachability as a test to write, when it is a design gap.** Section 9 cannot pass without a change to how cards are composed or what an era grants for free.
2. **No definition of "done" that a report generator can enforce.** It lists seven statuses but no evidence rule, which is how V3 arrived at 596/596.
3. **Flat priority.** Eighteen sections of equal weight. The work has a strict dependency order (rules → shared components → logistics → entities → end-to-end).
4. **"No grants" end-to-end tests need something to play the game.** The brief forbids AI work, but the heuristic AI builds one fixed dagger line and never uses abilities, ports, belts or `configure`. A scripted test driver is needed; it is test harness, not AI tuning.
5. **The legal command surface does not exist yet.** Every faction command is God/developer-only or training-API-only, and several world-level commands do not check ownership. Section 11 of the brief assumes there is something to extend.
6. **No fog of war.** Observations and targeting are global, so "do not reveal hidden information" has no meaning yet, and five OpenRA entities whose whole purpose is vision (radar dome, gap generator, mobile gap, GPS, spy plane) cannot be functional.
7. **Military recipes use only eight wares** (iron, coal, plank, ration, granite, gold, log, ax). Most of the 157 gated Widelands buildings therefore feed nothing. Tools, pack animals, and every advanced weapon and armour ware have no consumer. Plan v2 section 6.1 (differentiated ware mixes) was approved and not built.
8. **Headed Godot proof cannot be produced by a cloud session.** It needs the owner's machine.
9. **Decision register is behind the code.** The 13 October rules (v2 draft default, era gating by source game) are not recorded; S05, S06, S13 and S14 describe rules the code no longer uses; section 4 says "nothing here is approved".

---

## 4. Decisions needed from the owner

Defaults apply if unanswered. Each is implemented as data or a flag so it can be reversed.

| ID | Question | Recommended default | Why |
| --- | --- | --- | --- |
| **A** | How does a faction get a workable base in each era under a 7-pick draft? | **Per-era foundation kits.** Entering an era unlocks a small fixed kit for every faction, exactly as the Prehistoric foundation already works. Modern kit: mechanical drill, conveyor, junction, router, power node, combustion generator, graphite press, silicon smelter. Dystopian kit: ground factory with dagger. Cards stay at one or two entities and become the upgrades, alternatives and specialisations. | Keeps every draft rule intact; uses a mechanism that already exists (`tech.FOUNDATION_*`). The alternative, bundling 4–8 entities per card, breaks the approved "one or two entities" rule. |
| **B** | Implement the two dealer guarantees from plan v2 5.2, plus "a card for another tribe's building is never the only useful card in a first pack"? | Yes | Already approved, never built. |
| **C** | What should the Widelands dead-end wares do? | Build plan v2 6.1: unit recipes draw on differentiated wares (textiles, tools, tribe weapons and armour, pack animals for transports and cavalry-class units) through a ware-class table, so each tribe's own smithies feed its own army. | Otherwise roughly a third of Widelands sites are functional but pointless, and the AI would learn to ignore them. |
| **D** | Fog of war? | Add a minimal per-faction visibility layer (sight radius per unit and building), used by observations and by vision entities. Targeting keeps current behaviour unless a unit is cloaked or gapped. | Needed for legitimate AI observations; makes five OpenRA entities real. |
| **E** | Worker-less sites (119 of 178 have no worker entity) against D08? | Require a resident worker entity (created at the site, visible, killable, counted in population), without walking programmes for indoor trades. Tools and experience stay out of scope. | Matches Widelands, where indoor workers do not leave the building; restores D08 without a large simulation cost. |
| **F** | Confirm exclusions not covered by D05: OpenRA `fact`, `spef`, `hind`, mission creatures, `powr`/`apwr` (no OpenRA power system), fake buildings; Mindustry illuminator and canvas. | Confirm, and record as a D-row. Remove fake buildings from "functional". | They are currently excluded or inert without a recorded decision. |
| **G** | Era pacing: which bar gets worlds to Dystopian by play? | Decide by the existing study scripts after A and B land; target is a natural (non-stall-guard) transition into every era in at least 8 of 10 seeds within 240 game minutes. | Current bar (8, then leader + 4) has never produced a Dystopian world. |

---

## 5. Definition of done

One generated catalogue (`docs/evidence/coverage/catalogue.json` and `.md`), built by a script from the registries **and from the pytest result file**. Nothing is hand-edited. Each entity gets the highest level for which it has a passing test that names it.

| Level | Meaning | Evidence required |
| --- | --- | --- |
| L0 | Imported definition | Present in data |
| L1 | Placeable or producible | Legal command succeeds; cost paid in delivered wares |
| L2 | Behaves | A test asserts the entity's own behaviour in the authoritative sim, with inputs arriving by logistics (belt, pipe, carrier, power graph), not written into buffers. Sandbox sources are not allowed above L1. |
| L3 | Fails and recovers | Loses input, power or connection and stops; recovers when restored; takes damage and is destroyed with the correct downstream effect |
| L4 | Reachable | Unlockable by foundation or card, and built or produced at least once across the 200-game draft corpus without grants |
| X | Excluded | Names a decision row |

Tests declare what they prove with a marker (`@pytest.mark.entity("mdy:silicon_smelter", level=2)`); a conftest plugin writes the evidence file. A gate test fails if the catalogue claims a level without evidence, if a functional entity has only dead-end outputs, or if a unit has no weapon and no modelled ability. **The programme is complete when every non-excluded entity is at L3 and at L4, and the end-to-end scenarios in section 7.6 pass.**

---

## 6. Confirmed defect backlog

Reproduce each with a failing test, then fix in the shared component.

**Widelands**
- A failed sub-programme resets the site to its main programme, so a multi-product site starves when its first product lacks inputs (smelting works made no gold with gold ore and coal in stock).
- `maritime.ship_cost` falls back to the barbarian cost for every tribe; four of five shipyards can never launch.
- Markets are a caravan endpoint flag only. Scouts write an explored set nothing reads.
- Frisian recycling centre inputs have no producer.
- Transfers are not re-routed when a road is cut; dismantling while a worker carries a ware probably creates stock unbooked.
- Enhancement destroys the site's input stock.
- Three assertions in `test_widelands_completion.py` cannot fail (`>= 0` and two `or` forms).

**OpenRA**
- Pillbox and camo pillbox are unarmed (`HYBRID_ARMAMENTS` is never read).
- Landmines are buildings of kind `mine`, the same kind as the coal mine.
- Mk2 variants lose all abilities and Mk2 aircraft cannot rearm; Mk2 variants exist for excluded actors.
- An aircraft with no pad and no ammunition stays "attacking" forever.
- Spread damage hits the primary target only; crushing data is loaded and unused; minimum range is ignored on explicit orders.
- Not modelled: Tanya C4, chrono tank teleport, engineer and building repair, spy disguise, parabombs, spy plane, GPS, phase transport cargo.
- No attack-unit, guard or stance command.

**Mindustry**
- `payload.accepts_payload` has no assembler branch, so tecta, collaris, quell, disrupt, vanquish and conquer cannot be built outside a test that fakes delivery. The assembler module has no step.
- Seven "functional" units have no weapon and no modelled ability (anthicus, quell, disrupt, collaris, conquer, mono, oct).
- No unit abilities at all: crawler suicide, repair field, force field, shield arc, energy field, unit spawn, heal bullets, mining and building.
- Doors never open; armoured, plastanium and stack conveyors and ducts are plain belts; payload router code is unreachable; liquid junction is an average; heat has no direction.
- Turret bullets have no status, pierce or fragment effects, and only the first ammunition type is tested; tractor beam is a `pass`.
- Logic: `control shoot` sets a flag nothing reads; `control enabled` affects only turrets and incinerators; no unit control.
- `state_hash` omits turret ammunition, memory cells, router holds, pipe contents and shipments, so the determinism test cannot see divergence there.
- Machines are fed only by belts or adjacent dumps; carriers never feed them.

**Cross-cutting**
- `legal_actions` covers 52 hybrid kinds and none of the 193 `wl:` or 236 `mdy:` kinds, nor belts, abilities, dismantle, convert or waterways. `HybridEnv` cannot reach `belt`, `configure`, `upgrade` or `trade`.
- `queue`, `cancel`, `move`, `stop`, `rally`, `demolish`, `deploy` and `order` do not check ownership at world level.
- Save is a whole-object pickle with no version; loading in a fresh process is untested.
- `AGENTS.md`, `CURRENT_STATUS_AND_GAPS.md`, `ROADMAP_NEXT_RUN.md`, `RUNBOOK.md`, `LEDGER.md` and `ledger.json` contradict the code (for example "Mindustry is not yet implemented").

---

## 7. Work programme

Branch `work/mechanics-completion-v4` from `main` @ `143797ba`. Small verified commits. No merge to `main`. No neural-network work. Each phase ends by regenerating the catalogue and updating one continuation file, `docs/ledger/V4_HANDOVER.md` (what works, what remains, the next executable command).

### 7.1 Phase 0 — Truth and baseline
1. Pin the Python version used for baselines (recordings were 3.12; this audit ran 3.13) and record it in the runbook.
2. Widen `state_hash` to the full industry state, then re-record hash baselines for two worlds: `test_showcase` (as now) and **campaign profile with v2 draft and the plus AI**.
3. Build the catalogue generator and evidence plugin of section 5. Retire the functional/pending/excluded table. Expect most entities to land at L1; that is the honest starting point.
4. Record the 13 October rules and the section 4 answers as D26 onward; mark S05, S06, S13, S14 superseded. Correct the stale documents in one commit.
5. Delete or repair the vacuous assertions.

*Exit:* suite green, both baselines recorded, catalogue generated from test evidence.

### 7.2 Phase 1 — Draft and era reachability
1. Add `scripts/draft_reachability.py`: static graph check plus the Monte Carlo of section 2 over the real dealer, as a fast test. Metrics per era and tribe: usable cards seen and picked, share of factions with a complete producer chain for at least one military unit, share of unit cards whose producer and producer inputs are obtainable.
2. Implement decision A (foundation kits as data in `tech_cards.json`) and decision B (dealer guarantees).
3. Add static rules to `graph.check()`: no unit card without an obtainable producer; no entity whose inputs have no producer in or before its era for that tribe; no functional site with only dead-end outputs.
4. Replace `tech.ai_pick` and the default pick with a deterministic usefulness order shared with `ai_plus.score_generated`, so an unattended round is never arbitrary.
5. Run the era-pacing study (decision G) and set the bar.
6. Define the corpus measure: over 200 seeded draft-only games, every card is dealt at least 10 times and every card is usable by its holder at least once.

*Exit:* at least 90% of factions hold a complete, feedable Modern line by the end of the Modern phase and can produce at least one Mindustry unit in Dystopian; corpus measure met; hash baselines re-recorded as a versioned rule change.

### 7.3 Phase 2 — Shared components
Fix section 6 in dependency order, test first, one component per commit.
1. **Production and logistics core:** sub-programme failure handling, transfer re-routing, dismantle and enhancement booking, resident workers (decision E), machine feeding from a warehouse (unloader or carrier dock) so the two economies connect in both directions.
2. **Combat core:** spread damage to neighbours, minimum range on orders, crushing, attack-unit and stance commands, building repair, visibility layer (decision D).
3. **Mindustry transport:** real variants for armoured, plastanium and stack conveyors, ducts, payload router, liquid router and junction, directional heat, doors.
4. **Payload and units:** assembler intake and modules, T4 and T5 chains, a unit-ability component set (suicide, repair field, force field, shield arc, energy field, unit spawn, heal bullet, mine, build, carry) driven by the imported ability data.
5. **Turret effects and logic:** status, pierce and fragment bullets, all ammunition types, tractor beam; logic `control` for every controllable block, plus unit bind and control.
6. **OpenRA abilities:** pillbox garrison weapon, landmine kind, Mk2 inheritance, aircraft return-to-base, C4, chrono teleport, engineer repair, spy disguise, parabombs, spy plane, GPS, phase transport cargo.

*Exit:* every component has L2 and L3 tests using logistics-fed inputs; no `pass` or dead condition remains in a simulated role.

### 7.4 Phase 3 — Economy integration
1. Per-tribe ship costs; shipyards for all five tribes.
2. Markets as real stores with offers; sea trade between factions' ports with an automatic ship-trade mode, reusing the caravan fairness rule and `WARE_VALUE`.
3. Decision C: ware-class table and recalibrated unit recipes; Frisian recycling inputs; a consumer for every ware or a recorded exclusion.
4. Mindustry items into Widelands construction and OpenRA production (Mk2 lines already do this; extend to recipes that plan v2 6.2 calls manufactured components).

*Exit:* for each of the five tribes, a raw-to-army chain test passes using only that tribe's buildings and real logistics; ledger balanced; no dead-end ware outside the exclusion list.

### 7.5 Phase 4 — Command and observation surface
1. Introduce a **faction command tier**: every legal faction action is callable with a faction id, ownership-checked in the world, and separate from God commands.
2. Expose the missing verbs through `HybridEnv`: belt, configure (rotation, sorter item, factory plan, recipe, links, logic code), upgrade, trade, ship routes, abilities and support powers with targets.
3. Make `legal_actions` complete over all placeable kinds and all verbs, generated from the registries.
4. Per-faction observation built on the visibility layer, including era, VP, cards, offers, industry state, and unit and building lists.
5. Versioned save format; test load in a fresh process, mid-combat and late-game.

No policy, reward or network design.

*Exit:* a test enumerates every L1+ entity and proves a legal command path to build, configure and use it; a scripted driver plays through that interface only.

### 7.6 Phase 5 — Entity sweep and end-to-end scenarios
1. Parametrised L2 and L3 tests over the whole catalogue, grouped by component, using one shared harness that builds a minimal real supply (belt, pipe, power, carrier) for the role.
2. A scripted **exerciser** (test harness, legal commands only, deterministic) that builds whatever a faction has unlocked. The shipped heuristic AIs are not tuned; where they cannot use a mechanic, record it as an AI-control limitation.
3. End-to-end scenarios on the campaign profile, no grants:
   - each tribe from bare start to a Prehistoric war band;
   - Historic: metal chain to barracks, vehicle factory, airfield and naval yard, one unit of each class fighting;
   - the interaction matrix (infantry, tank, artillery, aircraft, anti-air, naval, submarine, defences, transport landing, capture, repair);
   - Modern: foundation kit to a powered belt-fed line delivering into a warehouse and an OpenRA Mk2 line;
   - Dystopian: factory to reconstructor to T3, and one Erekir assembler unit;
   - raid: a produced unit destroys an enemy production building and that faction's output falls;
   - sea trade between two factions' ports;
   - **the four-era game by play:** draft only, natural transitions, a Mindustry unit kills an enemy, ledger balanced, same result under two hash seeds and across save and load.
4. L4 corpus: 200 campaign games with the exerciser; report which entities were never built and why.

*Exit:* section 5 completion rule met.

### 7.7 Phase 6 — Performance
1. Benchmarks at early (15 min), middle (60 min), Modern with six industrialised factions, and Dystopian with T3+ armies; record throughput and peak memory.
2. Profile; optimise only with hash-equal results (spatial index for targeting, cached routes, sleeping idle machines and belts, batched power graphs).
3. Targets to confirm after the first measurement: at least 25x real time mid-game and 8x in the late industrial game on the training machine.

### 7.8 Phase 7 — Headed proof and readiness report (owner's machine)
1. Headed Godot: God Mode inspector, a roster sweep that places every L3 entity and asserts it renders, and the industry and combat scripts.
2. Final readiness report from the catalogue: levels by game and class, scenarios, performance, remaining limitations, AI-control limitations, and a plain yes or no on readiness for evolutionary training.

---

## 8. Order and size

Phases 0 and 1 are small and unblock everything; do them first and together. Phase 2 is the bulk of the engineering. Phases 3 and 4 can run in parallel after Phase 2 item 1. Phase 5 depends on all of them. Performance work follows Phase 5 so that it measures the real game. Expect several sessions; V3's 2.3 hours produced breadth at L1, and most of the remaining work is depth.

## 9. Standing rules for every session

- Read `docs/ledger/V4_HANDOVER.md`, then `git status` and the latest commit. Trust code and tests over documents.
- Test first for every defect. Never raise an entity's level by editing the catalogue.
- Any gameplay change re-records hash baselines under a new version label in the same commit.
- Determinism, conservation and the retained Ward Duel test stay green.
- Out of scope: neural networks, training, AI strategy tuning, visual polish, new rules beyond the decisions in section 4, excluded content.
