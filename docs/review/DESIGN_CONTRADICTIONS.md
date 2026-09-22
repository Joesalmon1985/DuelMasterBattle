# DESIGN CONTRADICTIONS

Evidence-backed contradictions and ambiguities.  
**Do not treat implementation as automatically winning.**

Classification of sources: `USER_LOCKED` | `USER_RECENT` | `BUILD_PACK_DEFINED_DEFAULT` | `CURRENT_ARCHITECTURE` | `OLD_BUT_USEFUL` | `STALE` | `IMPLEMENTATION_ACCIDENT`

---

## X01 — Person versus Unit identity

| Field | Value |
|---|---|
| **Topic** | Are soldiers Persons? |
| **Source A** | C01 registry table: separate `people/jobs` and `units/formations` (`C01_core_state.md`, WorldState registry contract). `BUILD_PACK_DEFINED_DEFAULT` |
| **Source B** | GDD: living NPCs persist; every visible soldier is a persistent unit; semantic labels select “NPCs/workers, individual units…”; collapse retains “living civilian NPCs” and **disbands military units** (`GDD_v0.3.md` §§persistence / era / collapse). `USER_LOCKED` (mixed language) |
| **Current implementation** | `state.people` vs `state.units`; `MilitaryService.spawn` has no `person_id`; Observe invents `unit.person_name` (`world.py:_ensure_unit_person_name`) |
| **Why they differ** | Contracts model combat as a specialised registry; player/GDD language treats soldiers as named individuals; G04 selection UX treats them like local targets |
| **Genuine contradiction?** | Partially — abstraction layers differ; player-visible identity is underspecified → **yes for design** |
| **Player-visible consequence** | Named soldiers without talk/relationship/quest stakeholder parity |
| **Suggested options** | Model A retain split; Model B Unit→Person link; Model C Combatant on Person — see D01 |
| **JOE_DECISION_REQUIRED** | **yes** (D01) |

---

## X02 — What “NPC” means

| Field | Value |
|---|---|
| **Topic** | Does NPC = Person only, or all living humans? |
| **Source A** | GDD repeatedly says “living NPCs” survive eras and includes “ordinary workers”; also lists NPCs and units separately (`GDD_v0.3.md`). `USER_LOCKED` ambiguous |
| **Source B** | C09 PersonState / PeopleService; no NPC type. Semantic kinds include `person` and `unit` separately (`semantic.py:REQUIRED_KINDS`). `BUILD_PACK_DEFINED_DEFAULT` / `CURRENT_ARCHITECTURE` |
| **Current implementation** | No Python `NPC` class; Godot still uses entity kind `"npc"` in adventure/village-test paths |
| **Why they differ** | Design prose vs typed registries; retained Godot vocabulary |
| **Genuine contradiction?** | Vocabulary ambiguity, not two sims — still blocks clean docs/UX |
| **Player-visible consequence** | Docs and agents talk past each other; soldiers may be excluded from “NPC continuity” accidentally |
| **Suggested options** | Define NPC = player-facing human; map to Person and/or Unit per D01 |
| **JOE_DECISION_REQUIRED** | **yes** (D02) |

---

## X03 — Talkability of all visible humans

| Field | Value |
|---|---|
| **Topic** | Can every visible human be talked to? |
| **Source A** | GDD: wizard talks to persistent people; semantic actions include NPC Observe/Talk (`EXECUTION_AMENDMENTS` G04; C09). `USER_LOCKED` / `BUILD_PACK_DEFINED_DEFAULT` |
| **Source B** | C07 UnitState is combat-focused; Talk not listed as unit verb. `BUILD_PACK_DEFINED_DEFAULT` |
| **Current implementation** | Dialogue/quest binding targets Persons; Units get Observe/Buff/Destroy |
| **Why they differ** | Social systems built on PeopleService; combat on MilitaryService |
| **Genuine contradiction?** | Design preference undecided |
| **Player-visible consequence** | Soldiers feel like pieces; workers feel like characters |
| **Suggested options** | Talk-all-humans vs Talk-persons-only vs limited soldier banter |
| **JOE_DECISION_REQUIRED** | **yes** (D03) |

---

## X04 — Worker motion authority

| Field | Value |
|---|---|
| **Topic** | Do walking carriers simulate logistics? |
| **Source A** | GDD / C09: ordinary worker motion is illustrative; carts carry real cargo. `USER_LOCKED` |
| **Source B** | Some older Godot village docs imply workers walk between posts as ambient loops tied to settlement mood (`SETTLEMENTS_AND_DUNGEONS.md`, `VILLAGE_SYSTEM_CURRENT_STATE.md`). `STALE` / `OLD_BUT_USEFUL` |
| **Current implementation** | IndustryService owns rates; WorkerController animates waypoints; obstruction is presentation-only (`worker_controller.gd` header) |
| **Why they differ** | Pre-migration Godot world sim vs Python-authoritative industry |
| **Genuine contradiction?** | Docs stale; **implementation matches GDD** |
| **Player-visible consequence** | Blocking a carrier must not change output (correct); players may still *believe* it does |
| **Suggested options** | Keep illustrative motion; teach via UX; or change GDD (not recommended) |
| **JOE_DECISION_REQUIRED** | **no** for ownership; **yes** for how strongly UX teaches it (D04) |

---

## X05 — Building inspect surface

| Field | Value |
|---|---|
| **Topic** | What should Inspect reveal? |
| **Source A** | C09/G04: knowledge-filtered observations; no raw internal IDs. `BUILD_PACK_DEFINED_DEFAULT` |
| **Source B** | Industry needs throughput/bottleneck truth for G03/G05 playability. `CURRENT_ARCHITECTURE` |
| **Current implementation** | Dirty tree adds `IndustryProjection.player_building_observation` / public roles; risk remains if debug fields leak |
| **Why they differ** | Simulation richness vs readable adventure |
| **Genuine contradiction?** | Tension, not hard conflict |
| **Player-visible consequence** | Either unreadable factories or useless “it’s a building” stubs |
| **Suggested options** | Plain-language observation layers (public / skilled / debug) |
| **JOE_DECISION_REQUIRED** | **yes** (D05) |

---

## X06 — Settlement vs local area vs exploration

| Field | Value |
|---|---|
| **Topic** | Free exploration between strategic nodes |
| **Source A** | C04: 19 hex / 54 nodes; wizard travel needs no road. C09: Travel after exit. `BUILD_PACK_DEFINED_DEFAULT` |
| **Source B** | Older Godot continuous multi-biome village maps / Village Test composite areas (`README.md`, village test). `STALE` |
| **Current implementation** | One Overworld projects current node; Travel command changes node; FX-VILLAGE wiring still being hardened (dirty tree + `test_village_travel.py`) |
| **Why they differ** | Adventure feel of continuous map vs strategic graph of rooms |
| **Genuine contradiction?** | Yes for player fantasy of “open countryside” |
| **Player-visible consequence** | Travel may feel like loading rooms vs walking a contiguous wilderness |
| **Suggested options** | Keep node rooms; soft contiguous presentation; or authored continuous overlays |
| **JOE_DECISION_REQUIRED** | **yes** (D06, D07) |

---

## X07 — Godot-owned world sim docs vs Python authority

| Field | Value |
|---|---|
| **Topic** | Who owns durable world truth? |
| **Source A** | `docs/INTEGRATED_RUNTIME_ARCHITECTURE.md`, EXECUTION_AMENDMENTS, C00/C01 — Python owns durable state. `CURRENT_ARCHITECTURE` / `USER_RECENT` |
| **Source B** | `docs/VILLAGE_SYSTEM_CURRENT_STATE.md` (2026-09-12): production path `DmbWorldSim → DmbNodeProjection → Overworld`. `STALE` |
| **Current implementation** | Python WorldState + bridge; retained Godot sim modules still exist for older flows |
| **Why they differ** | Mid-migration documentation lag |
| **Genuine contradiction?** | Yes in docs; runtime target is Python |
| **Player-visible consequence** | Agents may rebuild parallel village engines |
| **Suggested options** | Banner STALE; keep useful layout/quest intent notes |
| **JOE_DECISION_REQUIRED** | **no** (ownership settled); indexing only |

---

## X08 — Product identity: mobile duel vs systemic RPG

| Field | Value |
|---|---|
| **Topic** | What game is this? |
| **Source A** | GDD v0.3 / build pack — offline systemic RPG/adventure. `USER_LOCKED` |
| **Source B** | `docs/PLAN.md` — mobile-first Mastermind duel product; RPG out of scope. `STALE` |
| **Current implementation** | Build pack G01–G05 path |
| **Why they differ** | Historical product pivot |
| **Genuine contradiction?** | Yes for newcomers reading root docs |
| **Player-visible consequence** | Confusion; wrong roadmap instincts |
| **Suggested options** | Mark PLAN.md HISTORICAL; point to GDD/build pack |
| **JOE_DECISION_REQUIRED** | **no** (unless Joe wants duel-only product revived) |

---

## X09 — Fixture demos vs one runtime

| Field | Value |
|---|---|
| **Topic** | Are FX-* real starting states or alternate games? |
| **Source A** | Integrated runtime rule: fixtures arrange initial state only. `CURRENT_ARCHITECTURE` |
| **Source B** | FX-CLOCK/CARGO historically hand-built tiny graphs; Village Test Mode separate quest runner. `IMPLEMENTATION_ACCIDENT` / `STALE` remnants |
| **Current implementation** | `load_fixture` switches loaders; FX-VILLAGE moving onto BoardBuilder settlement slice |
| **Why they differ** | Gate-by-gate demos evolved faster than shared setup |
| **Genuine contradiction?** | Process smell; improving |
| **Player-visible consequence** | Skills learned in G02 may not transfer if village reinvents travel |
| **Suggested options** | Require every FX to be a seed/profile of one WorldSetup |
| **JOE_DECISION_REQUIRED** | **yes** (D09) |

---

## X10 — Projection proliferation

| Field | Value |
|---|---|
| **Topic** | Too many presenters of “people”? |
| **Source A** | C09 LocalProjectionService + SemanticResolver. `BUILD_PACK_DEFINED_DEFAULT` |
| **Source B** | IndustryProjection.workers, overworld_export NPCs, journeys presenter, Godot semantic adapter, WorkerController. `CURRENT_ARCHITECTURE` |
| **Current implementation** | Multiple justified views, but duplicate-actor risk if static + dynamic both spawn |
| **Why they differ** | Layered presentation growth |
| **Genuine contradiction?** | Responsibility overlap, not opposing rules |
| **Player-visible consequence** | Duplicate actors / missing labels (G05 repair theme) |
| **Suggested options** | One actor owner per person_id; others are views only |
| **JOE_DECISION_REQUIRED** | **yes** for hard invariant enforcement (D10) |

---

## X11 — Building / Processor / Factory vocabulary

| Field | Value |
|---|---|
| **Topic** | Is a factory a Building or an industry meter? |
| **Source A** | C04 buildings with slots; C06 industry processors/routes/meters. `BUILD_PACK_DEFINED_DEFAULT` |
| **Source B** | Player/GDD speak of factories as places. `USER_LOCKED` language |
| **Current implementation** | Both: building entity + industry factory process state |
| **Why they differ** | Dual economy needs both structure and throughput |
| **Genuine contradiction?** | Abstraction difference — needs player mapping |
| **Player-visible consequence** | Inspect confusion |
| **Suggested options** | Structure = Building; production behaviour = attached process; one player name |
| **JOE_DECISION_REQUIRED** | **yes** (D11) |

---

## X12 — G05 scope vs integration maturity

| Field | Value |
|---|---|
| **Topic** | Is G05 proving one village game or many stacked demos? |
| **Source A** | `gates/G05.md` — talk, two real solutions, dungeon, duel, save, persistence. `BUILD_PACK_DEFINED_DEFAULT` |
| **Source B** | Working tree still repairing labels/travel/BoardBuilder bind; progress tracking `READY_FOR_EXECUTION` while gate `AWAITING_HUMAN`. `USER_RECENT` / tracking smell |
| **Current implementation** | Cumulative checks claimed; human packet awaiting Joe; ontology gaps remain |
| **Why they differ** | Gate criteria assume unified ontology that D01–D10 still question |
| **Genuine contradiction?** | Scope vs readiness |
| **Player-visible consequence** | Risk of PASS on a slice that era work will fracture |
| **Suggested options** | Roadmap Options 1–2 |
| **JOE_DECISION_REQUIRED** | **yes** (D15, roadmap) |

---

## X13 — Era persistence of soldiers vs civilians

| Field | Value |
|---|---|
| **Topic** | Do units persist like NPCs across eras? |
| **Source A** | GDD: surviving buildings, workers, **units** remain; living NPCs do not age out; collapse **disbands military** but keeps civilian NPCs (`GDD_v0.3.md` / C11). `USER_LOCKED` |
| **Source B** | If soldiers are not Persons, “living NPC” language may exclude them; C11 assigns units via home settlement. `BUILD_PACK_DEFINED_DEFAULT` |
| **Current implementation** | Separate registries; era services incomplete (pre-T097) |
| **Why they differ** | Ordinary era continuity vs collapse / full-cycle reseeding differ |
| **Genuine contradiction?** | Rule set is nuanced; vocabulary hides it |
| **Player-visible consequence** | Wrong expectations about favourite soldiers across transitions |
| **Suggested options** | Spell out civilian vs military continuity tables — D12 |
| **JOE_DECISION_REQUIRED** | **yes** (D12) |

---

## X14 — Quests vs ordinary simulation

| Field | Value |
|---|---|
| **Topic** | Are quests overlays or discoveries of sim state? |
| **Source A** | G05 / C10: causes in world; solutions restore real output. `BUILD_PACK_DEFINED_DEFAULT` |
| **Source B** | Older `DmbQuests` / VillageQuestRunner authored trees on Godot sim. `STALE` |
| **Current implementation** | QuestBinder + CauseTracker + FX-VILLAGE solutions via industry/hazard services |
| **Why they differ** | Migration from story graphs to cause-driven quests |
| **Genuine contradiction?** | Mostly historical |
| **Player-visible consequence** | Fake quest text without world change if old path resurfaces |
| **Suggested options** | Forbid parallel quest engines |
| **JOE_DECISION_REQUIRED** | **no** (rule exists); enforce in roadmap |

---

## X15 — Cart identity vs journey “person”

| Field | Value |
|---|---|
| **Topic** | Is a hauling cart also a Person? |
| **Source A** | C05 CartState; carts are persistent cargo entities. `BUILD_PACK_DEFINED_DEFAULT` |
| **Source B** | FX-CARGO / journeys present motion via `person:cart` (`presentation/journeys.py`, G01–G02 shells). `IMPLEMENTATION_ACCIDENT` / fixture habit |
| **Current implementation** | Village export uses `cart:*` deco + semantic; older shells still use person-as-cart |
| **Why they differ** | Early demo reused people sprites for journeys |
| **Genuine contradiction?** | Yes if both IDs mean “the cart” to the player |
| **Player-visible consequence** | Talking to / destroying the wrong ID; double actors |
| **Suggested options** | Cart journeys bind `cart_id` only; retire `person:cart` from production |
| **JOE_DECISION_REQUIRED** | **yes** (D19) |

---

## X16 — GDD leftover kinds (Champion / Vehicle / Named vs Generated NPC)

| Field | Value |
|---|---|
| **Topic** | GDD §41 lists kinds contracts never implemented |
| **Source A** | GDD §41 entity catalogue includes Named NPC, Generated NPC, Worker, Soldier, Champion/hero, Vehicle… `USER_LOCKED` list |
| **Source B** | C01 registries: people, units, carts, buildings — no Champion; Vehicle ≈ Cart. `BUILD_PACK_DEFINED_DEFAULT` |
| **Current implementation** | No Champion registry; Cart covers vehicle; NPC/Worker are roles/prose |
| **Why they differ** | GDD catalogue broader than migrated C01 |
| **Genuine contradiction?** | Underspecification — risk of inventing parallel kinds |
| **Player-visible consequence** | None today; agent risk later |
| **Suggested options** | Explicitly defer/map leftovers (Vehicle=Cart; Champion deferred; NPC/Worker→Person roles) |
| **JOE_DECISION_REQUIRED** | **yes** (D20) |

---

## X17 — Inventory encumbrance

| Field | Value |
|---|---|
| **Topic** | Pocket / inventory limit |
| **Source A** | GDD / C10 — no encumbrance limit. `USER_LOCKED` / `BUILD_PACK_DEFINED_DEFAULT` |
| **Source B** | `docs/SETTLEMENTS_AND_DUNGEONS.md` — 8-slot `DmbItems`. `STALE` |
| **Current implementation** | Migrated `InventoryService` follows pack; Godot pockets UI may still echo old cap in places |
| **Why they differ** | Pre-migration adventure inventory |
| **Genuine contradiction?** | Docs only if old UI retained |
| **Player-visible consequence** | Fake “full pockets” if 8-slot UI survives |
| **Suggested options** | Affirm no cap; purge 8-slot UI copy |
| **JOE_DECISION_REQUIRED** | **no** if Joe affirms GDD (D21 confirmation only) |

---

## Document classification summary

| Document | Class |
|---|---|
| `GDD_v0.3.md` | `USER_LOCKED` (with internal vocabulary ambiguity) |
| Contracts C00–C14 | `BUILD_PACK_DEFINED_DEFAULT` |
| `EXECUTION_AMENDMENTS.md` / `INTEGRATED_RUNTIME_ARCHITECTURE.md` | `CURRENT_ARCHITECTURE` / `USER_RECENT` |
| `BUILD_SEQUENCE.md` / gates | `BUILD_PACK_DEFINED_DEFAULT` |
| `docs/PLAN.md` | `STALE` (historical duel product) |
| `docs/VILLAGE_SYSTEM_CURRENT_STATE.md` | `STALE` ownership; `OLD_BUT_USEFUL` layout intent |
| `docs/SETTLEMENTS_AND_DUNGEONS.md` | `OLD_BUT_USEFUL` / partially `STALE` |
| Root `README.md` Village Test patch framing | `STALE` product framing; launchers still useful |
| `unit.person_name` without Person | `IMPLEMENTATION_ACCIDENT` (or interim) pending D01 |
| `person:cart` journey identity | `IMPLEMENTATION_ACCIDENT` pending D19 |
