# JOE DESIGN DECISIONS

**Status:** All items `[UNDECIDED]` until Joe explicitly answers.  
**Do not implement** until approval.  
Review entry: [README.md](README.md).

---

## Recommendation status (Joe 2026-09-21)

The following decisions are **ACCEPTED for implementation** on `refactor/canonical-ontology-g05`. See [`docs/CANONICAL_GAME_ONTOLOGY.md`](../CANONICAL_GAME_ONTOLOGY.md).

| ID | Accepted direction |
|---|---|
| D01 | Soldiers are Persons |
| D02 | Model B — UnitState + `person_id` |
| D03 | Unit death ⇒ Person death |
| D04 | NPC = shorthand only |
| D05 | All living Persons Observe + Talk |
| D06–D07 | Composition; occupation ≠ activity |
| D09–D10 | Fixtures = setup; one actor per Person |
| D11 | Building names; industry processes hidden |
| D14 | Quests bind real causes |
| D15 | G05 coherent slice before T097 |
| D16 | No presentation-created People |
| D17 | Leaders = Person role |
| D19 | Carts = `cart:*` only |
| D20 | Defer Champion; Vehicle=Cart |
| D21 | No inventory encumbrance cap |

Individual sections below retain Option text for history; **Joe decision** lines are updated where accepted.

---

## D01 — Are military units Persons?

**Current documentation:** C01 separates `people/jobs` and `units/formations`. C07 defines UnitState. GDD says every visible soldier is a persistent unit; living NPCs (including workers) survive eras; collapse keeps civilian NPCs and disbands military.

**Current implementation:** Separate `state.units` with no `person_id`; Observe assigns `unit.person_name` (`sim/dmb/core/world.py:_ensure_unit_person_name`).

**Option A — Retain separation:** Person ≠ Unit; soldiers get display names only; no dialogue/relationships on Units.

**Option B — Unit references Person:** Keep Unit combat record; require `person_id` for social identity (recommended).

**Option C — Combatant on Person only:** Merge humanoid Unit into Person; Formation references person IDs.

**Recommendation:** **B** — clarity for players without ECS merge; preserves G03/G04 combat codepaths.

**What changes depending on the answer:** Save schema; spawn; dialogue/quests about soldiers; era/collapse tables; semantic Talk; tests.

**Joe decision:** **B ACCEPTED** (2026-09-21) — every soldier is a Person; UnitState requires `person_id`.

---

## D02 — What does “NPC” mean?

**Current documentation:** GDD uses NPC for living identities and sometimes contrasts NPCs with units.

**Current implementation:** No Python NPC type; Godot entity kind `"npc"` remains in older paths.

**Option A:** NPC = Person only (civilians/workers/leaders).

**Option B:** NPC = any non-wizard human the player can recognise (Person, and Units if separate).

**Option C:** Retire “NPC” from design language; say Person / Soldier.

**Recommendation:** **C** in design docs; **B** acceptable in casual player speech if D01=B.

**What changes:** Doc banners, agent vocabulary, UX copy guidelines.

**Joe decision:** [UNDECIDED]

---

## D03 — Can every visible human be talked to?

**Current documentation:** Talk is a people/NPC verb; G04 shared session includes Observe/Talk for NPCs and combat verbs for soldiers.

**Current implementation:** Dialogue/QuestBinder target Persons; Units lack Talk.

**Option A:** Talk only Persons (workers, leaders, quest stakeholders).

**Option B:** All humans Talk (requires D01 B or C).

**Option C:** Soldiers get short banter only; deep dialogue remains Persons.

**Recommendation:** **A** for G05 MVP cost; revisit **C** after G06 if soldiers need colour.

**What changes:** SemanticResolver actions; dialogue content volume; G05 expectations.

**Joe decision:** [UNDECIDED]

---

## D04 — What does worker walking represent?

**Current documentation:** GDD/C09 — illustrative motion; carts are real cargo.

**Current implementation:** WorkerController presentation-only; IndustryService owns rates.

**Option A:** Keep illustrative; teach via UI that blocking workers does not stop the factory.

**Option B:** Make carrier pathing authoritative (rejects GDD).

**Recommendation:** **A** (already LOCKED intent). Confirm UX teaching strength only.

**What changes:** Tutorials/labels; not sim ownership if A.

**Joe decision:** [UNDECIDED]

---

## D05 — What should building Inspect show?

**Current documentation:** Knowledge-filtered observations; no raw IDs.

**Current implementation:** IndustryProjection gaining `player_building_observation`; risk of process jargon.

**Option A:** Plain language only (“Ore works stopped — slope unsafe”).

**Option B:** Plain + optional skilled detail (Aspect/knowledge gated rates).

**Option C:** Debug-ish throughput always visible.

**Recommendation:** **B**.

**What changes:** Inspect strings; G03/G05 teachability; spoiler risk.

**Joe decision:** [UNDECIDED]

---

## D06 — How does free exploration between nodes work?

**Current documentation:** C04/C09 — Travel across real exits; wizard needs no road.

**Current implementation:** Overworld projects one node; Travel command; village travel still hardening.

**Option A:** Discrete places (node rooms) with clear exits — strategic graph honest.

**Option B:** Soft contiguous presentation (visual wilderness) still backed by nodes.

**Option C:** True continuous multi-node loaded map.

**Recommendation:** **A** now; **B** later polish. Avoid **C** until performance/design clear.

**What changes:** Art direction; Travel UX; player fantasy of countryside.

**Joe decision:** [UNDECIDED]

---

## D07 — Does every node get a local projection?

**Current documentation:** C09 LocalProjectionService per area/node as visited; durable anchors.

**Current implementation:** Projections created/stored under `board.local_projections`; not all 54 nodes prebuilt.

**Option A:** Generate on first visit; persist thereafter.

**Option B:** Precompute all settlement nodes at setup.

**Option C:** Only cores / contentful nodes; empty nodes stay abstract Travel.

**Recommendation:** **A** (matches C09 spirit).

**What changes:** Save size; first-visit hitch; wilderness flavour.

**Joe decision:** [UNDECIDED]

---

## D08 — Settlement vs LocalArea naming for players

**Current documentation:** Settlement is strategic ownership; LocalArea is play layout.

**Current implementation:** Same distinction in code; player often hears “village”.

**Option A:** Player says “village/town”; docs keep Settlement/LocalArea.

**Option B:** Expose “settlement” in UI.

**Recommendation:** **A**.

**What changes:** Copy only.

**Joe decision:** [UNDECIDED]

---

## D09 — Role of fixtures (FX-*)

**Current documentation:** Integrated runtime — fixtures = deterministic initial state only.

**Current implementation:** Multiple specialised loaders; FX-VILLAGE converging on BoardBuilder.

**Option A:** Every FX is a seed/profile of one WorldSetup pipeline (hard rule).

**Option B:** Allow miniature boards for early gates forever.

**Recommendation:** **A**; keep old FX as temporary but mark debt.

**What changes:** Fixture maintenance; gate shells; agent discipline.

**Joe decision:** [UNDECIDED]

---

## D10 — One actor per person_id (enforce how hard?)

**Current documentation:** INTEGRATED_RUNTIME_ARCHITECTURE invariant.

**Current implementation:** Export skips industry people; WorkerController `register_dynamic_person`; still a recurring bug class.

**Option A:** Soft guideline.

**Option B:** Hard assert in cumulative checks / load validation (recommended).

**Recommendation:** **B**.

**What changes:** Tests; spawn paths; G05 regressions.

**Joe decision:** [UNDECIDED]

---

## D11 — Factory / processor player vocabulary

**Current documentation:** Buildings + industry process layer.

**Current implementation:** Both exist; inspect can leak process IDs.

**Option A:** Player always hears Structure names; process layer invisible.

**Option B:** Player may hear “processor/factory line” as plain terms without IDs.

**Recommendation:** **A** with light **B** metaphors when teaching shortages.

**What changes:** Observation strings; content authoring.

**Joe decision:** [UNDECIDED]

---

## D12 — What persists across eras / cycles for soldiers vs civilians?

**Current documentation:** C11/GDD — nuanced: ordinary era keeps units/workers; collapse disbands military, displaces civilians; full-cycle reseeds politics.

**Current implementation:** Era services largely pre-T097.

**Option A:** Affirm written C11 tables as-is; fix vocabulary only.

**Option B:** Soldiers who are Persons (D01 B) keep Person across collapse even if Combatant disbanded.

**Option C:** Stronger soldier continuity (military lineages) — design extension.

**Recommendation:** **A** + **B** if D01=B.

**What changes:** T097+; chronicle; player expectations.

**Joe decision:** [UNDECIDED]

---

## D13 — When do local battles appear in the living world?

**Current documentation:** C07 — local tactics when player present; off-screen otherwise; industry produces units.

**Current implementation:** FX-BATTLE / G04 paths; village G05 not centred on army presence.

**Option A:** Battles only when formations engage at player node (baseline).

**Option B:** Scripted G05 army cameo required before G06.

**Recommendation:** **A**; do not block G05 on army spectacle.

**What changes:** G05/G06 content scope.

**Joe decision:** [UNDECIDED]

---

## D14 — Relationship between quests and ordinary simulation

**Current documentation:** Causes in world; solutions restore real output (G05/C10).

**Current implementation:** CauseTracker + QuestBinder + service-owned solutions; old Godot quest runners exist.

**Option A:** Quests are always views/bindings over sim causes (hard rule).

**Option B:** Allow authored story graphs that only set flags.

**Recommendation:** **A**.

**What changes:** Content pipeline; ban parallel quest engines.

**Joe decision:** [UNDECIDED]

---

## D15 — What must G05 prove before era work begins?

**Current documentation:** `gates/G05.md` playtest steps.

**Current implementation:** Packet AWAITING_HUMAN; ontology gaps open.

**Option A:** Exact G05.md text only.

**Option B:** G05.md **plus** locked D01/D02/D10 actor invariants and Travel identity continuity.

**Option C:** Full Option 2 re-scope (coherent Prehistoric slice checklist in amendments).

**Recommendation:** **B** (matches Roadmap Option 1 with teeth). Escalate to **C** if playtest feels like demos.

**What changes:** Whether T097 may start; amendment text.

**Joe decision:** [UNDECIDED]

---

## D16 — Carrier surplus / presentation-only jobs

**Current documentation:** Illustrative carriers; one carrier per connection intent.

**Current implementation:** IndustryProjection may create `presentation_only` / surplus carrier jobs.

**Option A:** Forbid presentation-only persons; animate fewer sprites.

**Option B:** Allow presentation-only jobs if still real Persons with clear non-authority.

**Recommendation:** **A** if it confuses identity; else **B** with strict labelling.

**What changes:** IndustryProjection; headcount; G03 visuals.

**Joe decision:** [UNDECIDED]

---

## D17 — Should leaders be ordinary Persons with a flag?

**Current documentation:** C09 — anchor/leader is profile on same person.

**Current implementation:** `PROFILE_STATES` includes `leader` / `anchor`.

**Option A:** Affirm status quo (recommended).

**Option B:** Separate Leader entity.

**Recommendation:** **A**.

**What changes:** None if A; large if B.

**Joe decision:** [UNDECIDED]

---

## D18 — Stale document handling

**Current documentation:** PLAN.md and VILLAGE_SYSTEM_CURRENT_STATE.md contradict current architecture.

**Option A:** Banner STALE/HISTORICAL; keep content (recommended).

**Option B:** Move to `docs/historical/`.

**Option C:** Delete (rejected by this review’s preserve rule).

**Recommendation:** **A**.

**What changes:** Banners/index only.

**Joe decision:** [UNDECIDED] — banners applied provisionally as STALE; Joe may reverse.

---

## D19 — Cart journeys: `cart:*` only, or allow `person:cart`?

**Current documentation:** C05 — carts are cargo entities.

**Current implementation:** Production village prefers `cart:*` deco; G01/G02/journeys still use `person:cart` for motion.

**Option A:** Production forbids person-as-cart; journeys bind cart IDs (recommended).

**Option B:** Keep person-as-cart as presentation convenience forever.

**Recommendation:** **A**.

**What changes:** Journey presenter, FX-CARGO shells, Destroy/Talk targeting.

**Joe decision:** [UNDECIDED]

---

## D20 — Map or defer GDD leftover kinds (Champion, Vehicle, Named/Generated NPC)?

**Current documentation:** GDD §41 lists kinds beyond C01 registries.

**Current implementation:** No Champion; Vehicle≈Cart; NPC/Worker are not separate registries.

**Option A:** Explicit deferral table in amendments (Champion deferred; Vehicle=Cart; NPC/Worker→Person roles) — recommended.

**Option B:** Implement missing kinds before G06.

**Recommendation:** **A**.

**What changes:** Doc glossary only if A; large scope if B.

**Joe decision:** [UNDECIDED]

---

## D21 — Confirm no inventory encumbrance cap?

**Current documentation:** GDD/C10 — no encumbrance limit.

**Current implementation:** Pack inventory; stale SETTLEMENTS doc had 8-slot pockets.

**Option A:** Affirm no cap; purge any 8-slot UI (recommended).

**Option B:** Reintroduce a soft pocket limit as new design.

**Recommendation:** **A**.

**What changes:** UI copy / old Godot pockets if any.

**Joe decision:** [UNDECIDED]

---

## Decision index

| ID | Topic | Blocks T097? |
|---|---|---|
| D01 | Person vs Unit | **Yes** |
| D02 | NPC meaning | Strongly preferred |
| D03 | Talkability | Preferred |
| D04 | Worker motion meaning | No (UX) |
| D05 | Building inspect | Preferred |
| D06 | Exploration model | Preferred |
| D07 | Local projection coverage | No |
| D08 | Village naming | No |
| D09 | Fixtures | Preferred |
| D10 | One actor invariant | **Yes** |
| D11 | Factory vocabulary | No |
| D12 | Era persistence table | Before T097 design use |
| D13 | Battle appearance | No |
| D14 | Quests vs sim | Preferred |
| D15 | G05 bar before era | **Yes** |
| D16 | Presentation-only jobs | Preferred |
| D17 | Leaders as flags | No |
| D18 | Stale docs | No |
| D19 | Cart vs person:cart | Preferred |
| D20 | GDD leftover kinds | Preferred |
| D21 | Inventory cap | No |
