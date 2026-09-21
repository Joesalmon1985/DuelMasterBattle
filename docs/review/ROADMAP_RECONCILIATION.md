# ROADMAP RECONCILIATION

**Baseline:** G01–G04 PASS; G05 `AWAITING_HUMAN` on `feature/g05-village-quest`; T097+ `NOT_STARTED`.  
**This document does not renumber tasks or clear gates.**

---

## 1. Existing sequence (build pack)

| Phase | Tasks | Gate | Intended player experience |
|---|---|---|---|
| P08 Persistent village narrative | T077–T096 | **G05** | Generated village, talk, two real solutions, dungeon/duel, persistence |
| P10 Immediate era transformation | T097–T106 | — | Capacity ranking, collapse/split, Historic conversion |
| P11 Integrated MVP | T107–T114 | **G06** | Two-era sandbox as one game |
| P12 Full catalogue / later eras | T115–T132 | **G07** | All eras + cycles |
| P13 Narrative breadth / tools | T133–T142 | **G08** | Content + authoring |
| P14 Trained leadership | T143–T150 | **G09** | Policies |
| P15 Release | T151–T160 | **G10** | Packaged baseline |

Sources: `BUILD_SEQUENCE.md`, `gates/G05.md`–`G10.md`.

Later gates **constrain** earlier architecture: G06 expects people/quests surviving Historic transition; G07 expects living people across full cycles; G10 forbids duplicate people/units from saves/transitions. That only works if G05’s identity model is honest.

---

## 2. G05 honesty check

### What G05 was supposed to prove (`gates/G05.md`)

- Talk to factory worker; explain why work stopped in your own words.  
- Demon-duel solution restores **actual** work; return visit truthful.  
- Sluice dungeon alternate route; dialogue does not falsely claim demon removed.  
- World-resolved / destroyed-target / item drop-recover; save during talk/puzzle/duel.  
- Same worker, buildings, items, quest persist after travel/save.  
- Experience: want to meet these people again.

### What G05 currently proves (automated + packet claims)

- FX-VILLAGE loads; cumulative G01–G04 regressions asserted in tools.  
- Recent commits bind village to BoardBuilder settlement slice; restore clock/industry; host Overworld from Python.  
- Dirty tree: WorkerController semantic labels, player-safe building observations, topology Travel proofs, `test_village_travel.py`.  
- Gate status returned to `AWAITING_HUMAN` after UX interaction repair notes.

### What is not yet design-closed

| Gap | Kind |
|---|---|
| Person vs Unit ontology for “people you meet” | **Missing design decision** (D01) |
| Whether G05 village includes military humans / talk parity | **Design** (D03) |
| Continuous exploration fantasy vs node Travel | **Design** (D06) |
| Fixture-only semantics residue across FX-* | **Architecture** (D09) |
| Duplicate actor / label bugs | Mix of **presentation** + **implementation** (partially under repair) |
| Dynamic worker semantic range (`pos`=[0,0]); `bridge_talk`/`bridge_challenge` routing; WorkerController freed on rebuild | **Presentation / implementation** (see ENTITY_PRESENTATION_CONTRACT §observed wiring) |
| `person:cart` vs `cart:*` dual identity in older shells | **Ontology smell** (D19) |
| Progress.json `READY_FOR_EXECUTION` / `current_task: T096` while G05 awaits | **Tracking smell** (not gameplay) |

### Verdict on G05 scope

G05 is **not inherently trying to test too many systems** — village narrative *should* compose clock, industry, hazard, duel, puzzle, people. The problem is that **composition landed before a single human ontology and presentation contract were locked**, so failures look like “UI bugs” when some are ontology gaps.

**Do not silently PASS G05 from automation.** Joe’s playtest remains authoritative.

---

## 3. Does the sequence produce one game or isolated demos?

Risk pattern observed G01→G05:

```text
FX-CLOCK → FX-CARGO → FX-INDUSTRY → FX-BATTLE → FX-HAZARD → FX-VILLAGE
```

Each fixture advanced a subsystem. Integrated runtime docs correctly demand one pipeline; practice still tends toward **demo shells**. G06 then adds era conversion — a transformative process that will multiply any identity/presentation cracks.

Without an explicit consolidation stop, the roadmap **encourages isolated system demos** more than one increasingly complete game.

---

## 4. Options (for Joe)

### Option 1 — Minimum disturbance (favoured)

Keep T097–T160 numbering and gate IDs.

**Insert** an explicit **architecture / consolidation repair window** before any T097 implementation:

1. Joe decides D01–D15 (or a declared subset).  
2. Agents implement only approved ontology/presentation invariants + G05 FIX_REQUIRED items.  
3. Re-submit G05 if playtest fails.  
4. Only then start T097.

| Pros | Cons |
|---|---|
| No renumbering; pack tools stay valid | Consolidation is “invisible” in BUILD_SEQUENCE unless amended |
| Fastest path if G05 playtest is mostly fine | Risk of under-scoping consolidation |
| Matches AGENT_START_HERE gate discipline | Era tasks still loom psychologically |

### Option 2 — Re-scope G05 / G06

- **G05** must prove one coherent **Prehistoric living-world vertical slice** (people, buildings, travel, carts, industry, one quest family, hazard/duel) on the production runtime with locked ontology.  
- **G06** adds Historic transition to **that same game** (merge P10+P11 emphasis).  

May keep task numbers but change acceptance text; or split “G05b consolidation” in amendments.

| Pros | Cons |
|---|---|
| Gate language matches player truth | More doc churn; may reopen G05 criteria |
| Stronger barrier before era chaos | Longer calendar before T097 |
| Cleaner story for Joe playtests | Need careful amendment drafting |

### Option 3 — Deep resequence (only if strongly justified)

Move era tasks after broader content (toward G08) so “history” lands on a richer peopled world.

| Pros | Cons |
|---|---|
| Maximum content before transformation | Large pack rewrite; invalidates dependency graph; high cost |
| — | **Not recommended** unless Joe rejects Options 1–2 |

---

## 5. Recommendation

**Favour Option 1**, with teeth:

1. **Do not start T097** until Joe PASSes G05 *and* records decisions on **D01, D02, D03, D06, D09, D10, D15** (minimum set).  
2. Treat consolidation repairs as G05 follow-on / amendments work, not as quiet T097 prep.  
3. If Joe’s G05 playtest finds the village still feels like stitched demos, **upgrade to Option 2** (re-scope acceptance) without waiting for era code.

**Why not Option 2 as default?** Task/gate numbering and existing packet cost are high; Option 1 preserves them while still blocking era work on design grounds.  
**Why not Option 3?** Era transition is core to the GDD fantasy of history; delaying it past full content overfits polish before the central loop.

---

## 6. Per-phase checklist (remaining)

### Before / with G05 close

| Item | Need |
|---|---|
| Player experience | Meet people; solve a real shortage; travel; save |
| Ontology | Locked Person/Unit/NPC; actor invariants |
| Extends | G01 clock, G02 cargo, G03 industry, G04 hazard/duel |
| Human criterion | G05 PASS |
| Parallel-impl risk | Village Test Mode / Godot DmbWorldSim revival |

### G06 (T097–T114)

| Item | Need |
|---|---|
| Player experience | Same world through Historic transition |
| New ontology | Era plan, collapse ruins, legacy sites, successor factions |
| Must already be unified | Person IDs, building IDs, quest causes, local projection anchors |
| Human criterion | Integrated game, not demo reel |
| Risk | Reimplementing industry/people “for Historic” |

### G07 (T115–T132)

| Item | Need |
|---|---|
| Player experience | Full cycle identity continuity |
| New ontology | Later-era catalogue, cycle reseeding |
| Prerequisites | G06 continuity table (D12) |
| Risk | Chronicle vs live referent deletion bugs |

### G08–G10

Breadth, policies, packaging — each assumes one runtime and stable IDs (G10 explicitly forbids duplicate people/units).

---

## 7. Tracking note (non-blocking)

`progress.json` shows `status: READY_FOR_EXECUTION`, `current_task: T096` while `tasks.T096: DONE` and `gates.G05: AWAITING_HUMAN`. Agents must still **stop for G05** per AGENT_START_HERE / amendments — do not “resume T097” from status alone.
