# DuelMasterBattle — current-main development, integration, polish and testing plan

> **EXECUTION OVERRIDE (2026-09-24):** Staged “paste one phase / STOP / P0-only” scheduling is superseded for the active run. See [`docs/POLISH_AUTONOMOUS_RUN.md`](POLISH_AUTONOMOUS_RUN.md) and `Pack/.../tracking/polish/run_state.json`. Technical Q/screenshot criteria in this document remain binding. Owner approval stays pending until Joe reviews.

Prepared for Joe Salmon · 24 September 2026 · **Planning document; implementation follows POLISH_AUTONOMOUS_RUN.md.**

**Inspected main:** [`9c66ce00342698dc2900c9f7b03c18101221f799`](https://github.com/Joesalmon1985/DuelMasterBattle/commit/9c66ce00342698dc2900c9f7b03c18101221f799), merge of PR #12, committed 24 September 2026 at 15:39:13 UTC. Verified independently with the GitHub branch API and `git ls-remote`, then audited a clean shallow checkout at that SHA. Recheck main before implementation; findings are pinned to this revision.

The deliverable covers A–L from the brief. Section J contains **ten complete phase prompts**, P0–P9. For the authorized continuous run, execute them in order without owner interrupts between phases. Technical acceptance criteria are unchanged.

## Evidence standard and limits

| Evidence label | Meaning in this report |
|---|---|
| EXECUTED | Reproduced against this checkout with production Python commands/services. Each arranged-state experiment is explicitly identified. |
| SOURCE | Traced implementation and its callers. This establishes a wiring fact, not satisfactory live play. |
| IMAGE | Personally inspected a committed Godot screenshot. These are historical captures in current main, not new captures made during this audit. |
| REPORTED | Repository handoff/gate evidence says it happened; this audit has not independently reproduced the claim. |
| REQUIRED | Proposed acceptance evidence for the implementation phases. It does not exist yet. |

I executed the Python simulation suite using Python **3.12.14**, pytest **9.1.1**, and available NumPy. Final result: **471 passed, 15 failed, 486 collected, 17.84 seconds**. An earlier environment attempt lacked NumPy and failed collection; it was corrected before the complete run. These results are Linux Python evidence, not Windows certification. The full log is included. Some compiler tests wrote generated files; those changes were restored, and the audit checkout was left clean.

I inspected seven committed G11 frames: settlement at both required sizes; portrait map, hazard and near-era panels; landscape battle; portrait Ward Duel. All 24 committed G11 PNG dimensions were checked and agree with their 450×800 or 1280×720 filenames. The visual-review report is dated **23 September**, before the current merge. No fresh headed Godot session, pointer playthrough, Windows launcher run, packaged executable test, or subjective owner acceptance was performed here. A compatible current headed Godot environment was not available in this workspace. P0 must produce fresh main-branch frames; no visual success below is claimed solely from a passing Python test.

Sources S01–S24 in the appendix identify pinned files and symbols. Probe scripts are read-only diagnostics outside the checkout. They do not patch game source. The technology, treatment and save experiments arrange state through production services; they are **not** legal-reachability proofs from a new game.

## A. Executive diagnosis

**The game has both presentation defects and broken connections in the production path. A UI-only pass would conceal the most serious problems.**

The substantial reusable foundation is real: generated 19/54/72 topology, durable people, exact industrial accounting, physical stock/cart services, formation identity, the retained Ward Duel, era conversion services, and semantic presentation tools. What is missing is reliable passage through those systems in ordinary play, plus a clear account of their consequences to the travelling wizard.

### Findings that change the roadmap

| ID / priority | Finding and evidence | Practical consequence | Phase |
|---|---|---|---|
| R01 / P0 blocker | **EXECUTED:** 12 ordinary FX-MVP Wait commands all rolled `[1,1]`. The same seed through direct `TurnRunner` calls produced `[1,1], [3,2], [6,2], [1,5], …`. `WorldSim.dispatch` writes its stale `self.rng` back after subsystem RNG updates. S05/S06. | Production command execution does not preserve the dice stream. Tests calling services directly miss it; economy pacing and policy conclusions are unreliable. | P1 |
| R02 / P0 blocker | **EXECUTED:** `SaveCoordinator` save/load loses all three arranged nonempty fields: `research`, `tech_draft`, `diplomacy`. They are dataclass fields omitted by `WorldState.to_dict/from_dict`. Transactions also use that serializer. S05/S16. | Technological and diplomatic continuity is broken; rollback can also lose durable state. | P1 |
| R03 / P0 blocker | **EXECUTED:** FX-MVP starts with an empty draft and still has none after 12 Waits / six rounds. **EXECUTED:** FX-ERA reaches Historic, but its newly dealt hands are then discarded by the runner's interrupt cleanup. S04/S05/S09/S15. | Faction technology is absent in the initial normal game and fails immediately after the tested era transition. | P1/P5 |
| R04 / P1 major | **EXECUTED arranged probe:** all six Prehistoric technology effects activate in research, but existing channel/processor/cart capacities remain unchanged and subsequently manufactured units retain base HP/attack. **SOURCE:** effective modifiers are read by observations, not these production consumers; factory ceiling remains fixed. S09/S07/S06. | A card can exist in state without changing the world. Fix actual effects before announcing research. | P5 |
| R05 / P1 major | **SOURCE + EXECUTED:** due hazard placement is not called by normal `TurnRunner`; placement ordinal remains zero after 24 Waits. Initial setup silently deactivates settlement-touching cubes: seed 507 has two active cubes, not three. S04/S05/S10. | Threat escalation and the economy–hazard–response chain are not operating as specified. | P6 |
| R06 / P1 major | **EXECUTED arranged probe:** policy selects `hazard_treat` for `cube:3`, but `_apply_candidate` returns generic `proposed`. Cube remains active; responder's spent-turn marker remains 6 while current turn is 25. No production caller invokes `HazardResponder.treat`. S08/S10. | Soldiers can decide to treat a hazard without treating it. This is an integration bug, not merely an unnoticed animation. | P6 |
| R07 / P1 major | **SOURCE:** the integrated shell creates `LocalBattle.new()`, assigns `.name`, and passes it to `add_child`; `DmbLocalBattle` extends `RefCounted`, not Node. The method does not bind or tick its lease. **EXECUTED:** ordinary manufactured formations do create a battle record. S11/S12. | The normal local-battle handoff is incomplete and contains an incompatible host operation. Dedicated G04 battle evidence does not validate this path. Live contact reproduction is required. | P6 |
| R08 / P1 major | **SOURCE:** movement/contact treats another faction as hostile without consulting diplomacy; battle hostility is built from different faction IDs. Attack does not visibly call `declare_war` there. Policy attack-candidate code expects `enemy_military_nodes`, while observations export `enemies`. S08/S11. | Movement and conflict can occur without a coherent diplomatic cause; allies and observed-target reasoning require repair. | P5/P6 |
| R09 / P1 major | **EXECUTED:** 120 seconds of Game Time produces 12 soldiers linked to 12 Person IDs and four formations. After 24 subsequent Waits: four roads, four settlements, eight idle carts, 24 proposed trades, one battle, unchanged 2/2 VP. **SOURCE:** normal policy proposes trade but has no accept/dispatch/escrow-completion orchestration. The dormant dispatch helper creates carts without an order and does not assign road routes. S06/S08. | There is real industry/military activity, but the ordinary economy chain stalls. Do not merely wire the unsafe dormant trade helper into production. | P3/P4 |
| R10 / P1 major | **EXECUTED:** normal factions use heuristic policies. No normal initial/era assignment call selects the three trained policies. Own-stock observations are empty despite two faction-owned warehouse stores. **SOURCE:** enemy-unit observation defaults to visible; normal map export ignores discovery for current ownership/hazards; requested player view fields can include privileged data. S08/S13/S14. | Trained-policy qualification is separate from gameplay selection; both AI observations and player information boundaries need meaningful tests. | P2/P5 |
| R11 / P1 major | **EXECUTED:** 15 current Python failures, including stale six-unit catalogue assertions, formation regrouping assumptions, projection exits and sluice mechanism validation. S23 and the included full test log. | Current main is not a clean regression baseline. Distinguish outdated tests from real defects without deleting invariant coverage. | P0/P1/P4/P7 |
| R12 / P2 usability | **IMAGE:** label stacks obscure the village header; labels intersect touch controls; army labels overlap; map legend is tiny; FX-ERA controls overlap world labels. Ward Duel's portrait frame is clean. S18/S19. | Placeholder shapes already exist, but their hierarchy, label selection and layout are inconsistent. Preserve the successful retained duel presentation. | P2/P6/P7 |
| R13 / P2 evidence | **SOURCE:** G11's runner lists PNGs and process exits, not per-image observed conditions. Most world-review frames use FX-WORLD-LAYERS, FX-BATTLE, FX-HAZARD or FX-ERA. `evaluate_mvp.py` checks six boots plus one arranged FX-ERA transition. S18/S20. | Existing evidence does not demonstrate natural connected play or all dynamic before/after consequences. | P0/P9 |

The 24-Wait observation is a bounded run, not a proof that construction can never happen. The source-backed missing calls, repeated RNG and serialization omissions are stronger evidence than that absence count.

### Preserve these strengths

- One production Python world and existing Godot projection; no second simulation, controller UI or replacement engine.
- Real Person ↔ Unit linkage. The 120-second normal-world probe produced persistent soldiers without strategic travel.
- Existing stock ledger, construction validation, exact factory meters, shared capacity allocator and typed resources.
- Full retained `game_board.tscn` / `game_board.gd` / `DmbBattleSim`, shared attached interactions and presentation-mode suppression.
- Semantic registry and current shape vocabulary; no new art workstream.
- Era/history services and existing continuity checks, while closing the missing save fields and normal-play pathways.

## B. Intended game loop

The player is a powerful **travelling wizard inside an autonomous historical simulation**. Decisions are where to go, whom to understand and where to intervene. Factions choose their own construction, trade, diplomacy, technology and military behaviour. Exact internal plans, card hands, scores and hidden resources belong to QA tools.

There are three clocks: unpaused **Game Time** for industry/local mechanisms/buffs; one **World Turn** per accepted adjacent Travel or distinct Wait press; one **World Round** when its captured surviving faction roster completes its seats. Local walking, reading, rejected Travel and a duel do not grant strategic time. Paused world systems do not catch up later.

| Turn stage | Required authoritative result | Minimum player evidence |
|---|---|---|
| Boundary / arrival | Validate action; close outgoing local combat correctly on Travel; commit one turn and arrival/visit. Wait retains local battle and treatment allowance. | Clear destination and a brief turn change. Rejection explains why without moving the wizard. |
| Production | One 2d6 roll; valid Catan grants to actual warehouses; hazards suppress only relevant grants. | Nearby harvest/warehouse activity; Inspect can explain a visible shortage. Exact dice/cargo ledger in QA. |
| Logistics | All eligible carts move at most one legal road edge; one receipt per delivery; retain blocked cargo. | Loaded cart → exit → arrival → actual consequence, with a clear blocked state. |
| Completion | Fully delivered costs complete legal orders in cyclic seat order; check 10 VP after each completion. | Scaffold becomes road/building/city; nearby completion notice. |
| Active decisions | ≤1 construction, ≤1 trade/diplomacy proposal and one objective per disengaged formation. Treatment reserves that formation's activation. | Visible work and army purpose; no player order controls. |
| Forces | Active faction moves ≤2 edges; respect hostility/alliance; local lease when attended, bounded deterministic off-screen resolver otherwise. | Formation departure/contact/battle/aftermath; local casualties and damage remain. |
| Hazards | Execute planned eligible treatment, then due typed placements/cascades; stop immediately at terminal threshold. | Distinct danger/treatment state and resumption of blocked activity. |
| Consequences | Apply causal world changes, commitments/deadlines and immediate outcomes. | Contextual causal explanation, learned history and changed local objects. |
| Seat / round end | Skip dissolved seats; simultaneously choose from one pre-draft snapshot; acquire/activate/pass; redeal after seven picks. No old-era draft after interrupt. | Witnessed technological change, not a player draft screen. |

Industry continuously uses two-resource cross-terrain routes and global capacity; it creates soldiers through `MilitaryService`, then formations use the same identities. Worker motion illustrates activity and never gates output. Only Catan goods require strategic physical cart shipping in the baseline; do not turn illustrative industrial carriers into another cargo economy.

At the first 10-VP event, atomically convert politics and eligible cores, keep legacy sites and living identities/history, then show the transition. Prehistoric → Historic → Modern → Future → a new Prehistoric cycle preserves the world’s history. The final step retires political/industrial competition and reseeds factions; it is not a colour change.

## C. Actual current-main loop

1. `Play Latest Integrated Game.bat` → `tools/windows_playtest.py play-latest` → FX-MVP seed 507 at 450×800 → `g05_shell.tscn` → sidecar `WorldSim`.
2. FX-MVP delegates to the normal Prehistoric loader: a generated two-faction 19/54/72 board, four cores, four initial roads, eight carts and real industry. Seed 507 starts at **node:35**. An existing boulder blocks an exit; this pass preserves that infrastructure and does not expand it.
3. The loader clears cubes touching any operational starting settlement. It neither deals an initial technology draft nor selects trained policies. The first seat lazily assigns heuristic.
4. Godot local movement sends pose updates; its clock pump sends `AdvanceGame`; Python advances industry. The probe's 120 seconds produced 12 soldiers/Person links and four formations, with no World Turn.
5. Travel/Wait goes through `WorldSim.dispatch`. The runner's actual stage labels are `0_boundary`, `1_arrival`, `2_score`, `2_production`, `3_logistics`, `4_completions`, `5_active_decisions`, `3_follow_on`, `9_seat_end`. Several labels are bookkeeping: there are no dedicated executed forces/hazards/consequences stages matching C03. Pending off-screen battle resolution runs at the start of active decisions; military movement happens while applying policy candidates.
6. The production service updates `state.rng`, but dispatch overwrites it from the cached bank. This explains the command-path repeated dice and why direct-service tests can pass.
7. Policy candidates include construction, generic timber/brick trade probes, diplomacy, movement/objectives and hazard treatment. A single primary choice currently shares the construction/military/hazard budget, unlike the contract's independent construction and per-formation allowances. Trade stays at proposal; hazard treatment falls through to a generic intent.
8. Seat completion can resolve a draft **if one is already active**. The normal loader provides none. The separate era service creates new hands, then the runner's interrupted-turn cleanup clears them.
9. Godot projects stock/building/person/unit/hazard state and supports contextual interaction, map, inventory, grimoire and Ward Duel. The integrated local-battle host is incomplete. The rich major-event log belongs to the explicit long-world developer mode; there is no verified normal-player causal-event stream covering all requested events.
10. Save snapshots retain many IDs, clocks and assets, but currently omit research, draft and diplomacy. Existing equal-serialized-dictionary tests cannot catch fields missing from both dictionaries.

### Design/document discrepancies to record, not silently reinterpret

- The accepted ontology supersedes the review document’s older “soldiers lack Persons” diagnosis. Current manufactured units do have Person links. `JOE_DESIGN_DECISIONS.md` also has an outdated all-undecided banner above an accepted-decisions table.
- The architecture document/C10 retain the former shortage/sluice FX-VILLAGE description; the later execution amendment and actual loader make that scenario archived FX-VILLAGE-QUEST and use the full board plus boulder. Do not resurrect shortage quest development.
- The original toolchain pin was Godot 4.4.1/Python 3.12.3; the newest handoff reports Godot 4.5.1 on Windows. P0 must record the actual intended project version and compatible templates, rather than silently upgrading or treating this Python run as engine certification.
- C13's original finished-art expectation is superseded for this pass by the user’s explicit placeholder-only brief and overnight amendment.
- Earlier stop-before-G06 language and later authorized overnight continuation are historical. This new task authorizes planning, not implementation or new gate PASS. Each future Cursor phase stops independently.
- C03 ordering, C12 draft/effects and C08 hazard scheduling disagree with implementation as described above. Their existing contracts remain targets; do not redefine the game to fit current omissions.

## D. Integration-gap matrix

Status codes expand to the requested classifications: **L** = WORKING AND PLAYER-LEGIBLE; **P** = WORKING BUT POORLY COMMUNICATED; **F** = WORKING ONLY IN SPECIAL FIXTURES; **C** = PARTIALLY CONNECTED TO NORMAL GAMEPLAY; **I** = IMPLEMENTED BUT EFFECTIVELY INVISIBLE; **B** = BROKEN/REGRESSED; **D** = DOCUMENTED BUT NOT IMPLEMENTED; **?** = UNCERTAIN. A row can have a primary and secondary status. “Reachable” describes this revision, not a future phase. Coverage names are existing files, not assertions that they all pass or cover the whole chain.

| System | Status | Design expectation | Current implementation | Normal-game reachable? | Player-legible? | Current test coverage | Main gap | Recommended intervention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Exploration / Travel | P | 19/54/72 board; adjacent Travel only; one local projection | Prehistoric loader wires topology; command probe accepts 35→30→36→31→37 | Yes, command verified | Exits/labels need fresh pointer and clutter review | test_g05_full_world.py; test_natural_world.py; test_t020_playable.py | Graph reachability does not prove accessible local exit affordances | P0/P2: exact input route and protected exit labels; S04/S12 |
| Game Time / World Turns | B | Game Time industry; one Travel/Wait turn; C03 ordering | Clock works; dispatch RNG overwrite and missing scheduled stages | Yes; wrong RNG/cadence | Time HUD exists; stage consequences opaque | test_t012_clock.py; test_t013_turns.py; test_t046_seat_round.py | Direct runner tests miss command path; stage labels overstate work | P1/P6: single RNG authority, ordered receipts, real hooks; S05 |
| Catan production | B | One 2d6; five goods; suppression; warehouse-local grants | Grant service present; command dice repeat [1,1] in probe | Yes, faulty | No demonstrated player causal account | test_t029_catan_grants.py | RNG continuity; ledger/grant trace must agree | P1/P3: actual command sequence and stock witnesses; S05/S06 |
| Stock / reservations | C | Conserved available/reserved/cargo/escrow/loss | StockLedger implements classifications and receipts | Yes | Appropriate local explanation incomplete | test_t030_stock.py | End-to-end grants→shipment→consumption need independent totals | P3: conservation after every boundary, contextual goods; S06 |
| Carts / logistics | C | Persistent cart, actual goods, ≤1 road edge, blocked cargo retained | Cart/route/director and journey ACKs exist; normal probe eight idle | Entities yes; sustained autonomous haul not demonstrated | Fixture cart visible; journey proof incomplete | test_t033_carts.py; test_t034_routes.py; test_t035_director.py; test_presentation_journeys.py | General haul orchestration and cart/source co-location; fixture-specific journey hook | P3: reuse services, route existing carts, delivery sequence; S06 |
| Bilateral trade | C/B | Mutual shortages; reserve both; physical legs; escrow settlement | Policy only proposes; dormant dispatch spawns carts and omits routes | Proposals yes; completed normal trade no wired path found | Effectively invisible | test_t045_trade.py | Accept/dispatch/delivery/deadline orchestration; no free carts | P3: legal executable contracts and existing-cart supply; S06/S08 |
| Roads / construction | C | Delivered cost, legal path, no phantom goods | Orders/completions present; 24-Wait probe had no new road | Possible code path; not demonstrated in normal probe | Staged scaffold frame only | test_t031_placement_score.py; test_t032_orders.py; test_g05_visual_layers.py | Economy/decision stalls, cyclic completion ordering, route supply | P3: replay-reached road and settlement sequence; S05/S06 |
| Settlements / cities / VP | C | 1/2 VP; legacy zero; first 10 interrupts | Scoring and upgrade services; FX-ERA 9→10→Historic verified | Initial sites yes; organic 10 VP unproven | Player-visible growth/history needs sequence | test_t031_placement_score.py; test_t104_era_service.py | Natural expansion route and first-winner transaction | P3/P8: funded growth, immediate stop, era checkpoint; S06/S15 |
| Industry | P/C | Finite/renewable cross-terrain inputs; global shared capacity | Real bootstrap/routes/allocator; produces units through AdvanceGame | Yes, 120-second probe | Workers/buildings visible; cause and bottleneck weak | test_t049_catalogues.py; test_t050_layers_primary.py; test_t051_routes_constraints.py; test_t052_allocation.py; test_t054_industry_service.py | Technology effects not consumed; plain-language flow evidence | P4/P5: existing connections and bottleneck explanations; S07 |
| Workers | P | Persistent Person; animation illustrative | Jobs/worker projection/one-actor infrastructure exists | Yes | Labels and role/activity overlap in images | test_t055_workers_projection.py; test_canonical_ontology.py | Actor lifecycle and selected-label hierarchy | P2/P4: reuse Person actor, no accounting by sprite; S07/S12 |
| Military manufacture | P | Three archetypes; unique Person+Unit; same formation identity | 12 units, linked people, four formations after 120 seconds | Yes, measured | Soldier appearance not enough to explain factory origin | test_t053_factories.py; test_t059_units.py; test_canonical_ontology.py | Birth→yard→Person→formation visual proof; stale regroup tests | P4: before/after factory and same-ID social interaction; S07/S11 |
| Autonomous faction decisions | C | Independent build/proposal/per-formation budgets | Policy activates each seat; one primary slot competes across kinds | Yes | Intent is not reliably expressed as completed activity | test_t043_heuristic.py; test_t046_seat_round.py | Allowances differ from contract; commitments can be inert | P3/P5: legal typed execution and meaningful action budgets; S08 |
| Diplomacy | C/B | Neutral/allied/hostile relations govern decisions and transit | Services/proposals present; military treats foreign as hostile; save loses store | Service yes; coherent natural loop incomplete | War cause/transition not reliably shown | test_t044_diplomacy.py; test_t067_military_ai.py | Alliance safety, acceptance, war establishment and persistence | P1/P5/P6: one relation owner and causal notices; S08/S11 |
| Technology draft | B | Seven hands; one simultaneous pick per full round; pass/redeal | Draft service tested; normal initial deal absent; era cleanup removes fresh hands | No initial normal draft | No normal technological development to communicate yet | test_t041_draft.py | Initialization and interrupted-era lifecycle | P1/P5: initialize once and preserve new hands; S05/S09/S15 |
| Technology effects | B/I | Six scoped modifiers alter production/cart/unit consumers | Research modifiers compute; arranged probe shows unchanged assets/base new units | Research service only until repaired | No meaningful demonstrated consequence | test_t039_tech_defs.py; test_t040_research.py | Consumers, asset-era scope and health proportion | P5: actual capacity/HP/damage/cargo oracle per effect; S07/S09 |
| Military movement | C | Active faction ≤2 edges; new units wait for activation | Movement and autoformations present; command probe forms contact | Yes | Departures/ownership/archetypes need clarity | test_t061_movement.py; test_g05_visual_layers.py | One-primary policy limit; hostility semantics; regression failures | P5/P6: per-formation objectives and physical exit cues; S08/S11 |
| Faction conflict | C/B | Observed hostile objectives, no allied attack, consequences | Contact creates battle, but different owner implies hostility | Contact yes; correct political cause incomplete | Unclear war cause and outcome | test_t067_military_ai.py; test_t044_diplomacy.py | Observed enemy schema mismatch, alliances and war record | P5/P6: diplomacy-aware objectives and aftermath; S08/S11 |
| Local battle | B/F | Exclusive lease; 50ms tactics; wizard immune | Dedicated G04 implementation exists; g05 host misuses RefCounted as Node | Battle record reachable; integrated host source-defective | G04 screenshot exists; not normal-shell acceptance | test_t063_local_battle.py; run_g04_playable.gd | Actual lease binding/ticking/presentation/handoff | P6: reuse G04 controller under proper Node host; S11/S12 |
| Off-screen battle | C | Checkpoint-based deterministic bounded combat; no extra clock | Resolver runs pending battles at active-decision start | Yes in code; full normal handoff unverified | Only later visible consequences should be shown | test_t062_offscreen.py; test_t064_handoffs.py | Stage ordering, complete hostility/checkpoint fields, local release | P6: attended-departure test and persistent aftermath; S05/S11 |
| Hazard spawning / spread | B | Cadence by era-relative turns; typed overflow; terminal 8 | Services exist, normal runner has no resolve_placement caller | Initial cubes yes; scheduled escalation not connected | Fixture dangers visible | test_t069_hazards.py; test_t070_propagation.py | Dead scheduling path and reduced initial cube count | P6: production cadence, stable cascades and terminal barrier; S04/S10 |
| Hazard economic effects | C | Block Catan, both industrial inputs, civilians/carts; retain deposits | Suppression queries are used by production/industry/routes | Yes when a cube is present; starts deliberately cleared at cores | Cause→recovery not demonstrated | test_t071_disruption.py | Normal affected source/route and recovered work evidence | P6: whole chain with controlled matching-roll witness; S06/S07/S10 |
| Faction hazard response | B | One eligible formation removes exact cube instead of movement/attack | Candidate selected; generic proposal fallthrough leaves cube/activation unchanged | Decision yes; treatment effect no | Invisible because effect is missing | test_t073_responders.py (three current failures) | Missing service execution; adjacency/exclusivity need integrated tests | P6: reserve activation, execute and show recovery; S08/S10 |
| Wizard local magic | C | Observe-local validated Destroy/Buff; no combat HP | MagicService and shared bridge controls present | Yes in source; current live input unverified | Attached action design exists; fresh pointer proof needed | test_t065_magic.py; test_t066_buffs.py; test_r04_semantic_magic.py | Moving target range/stale input and cross-system consequences | P7: truthful input/receipt/visible effect checks; S12 |
| Ward Duel | L (historical image), C (current input) | Retained game_board/DmbBattleSim; frozen world; exact selected cube | Production lease adapter and presentation-mode owner retained | Yes in existing FX-MVP harness; strategic route reproduced | Clean portrait frame inspected; live play not rechecked | test_u05_retained_ward_duel.py; run_ward_duel_presentation.gd | True pointer ward entry, resolution/return and allowance proof | P7: retained UI sequence and no ghost actors; S12/S19 |
| People / knowledge | P/C | Same people across employment/army/era; learned facts only | Persistent People/Unit links and semantic services | Yes | Known/name layers exist; technical/hidden leaks remain | test_canonical_ontology.py; test_t077_people_profiles.py; test_t079_semantic_coverage.py | Privacy filter and continuity through all returns | P2/P4/P8: identity and knowledge from allowed evidence; S13/S16 |
| Inventory / grimoire | C | Personal items/progression; paused; no construction funding | Existing player projections/panels and typed inventory operations | Yes in source; no fresh UI walkthrough | Not fully visually reviewed here | test_t087_inventory.py; test_t088_inventory_use.py; test_t107_player_screens.py | Single-pointer access and modal clock regression | P7: retain screens; item/slot and pause checks; S12/S13 |
| Save / load | B | Every durable field and receipt survives; no duplicate effects | Snapshot repository/coordinator work, three domains omitted | Yes, but loses technology/diplomacy | Continuity cannot be certified from matching pixels | test_t014_persistence.py; test_t019_recovery.py; audit persistence probe | Serializer incompleteness and missing field oracle | P1/P8: schema migration, rollback and fresh-process reload; S16 |
| Era transition | C/B | First 10 VP → atomic next era; one presentation | FX-ERA reaches Historic; runner then clears new draft | Arranged FX-ERA yes; natural threshold not proven | Near-era frame only inspected; full sequence needed | test_t097_era_planner.py; test_t104_era_service.py; run_fx_era_ui.gd | First-win scheduling and organic checkpoints | P1/P8: preserve new-era state and complete sequence; S15 |
| Collapse / fission | F/C | Below-five/lowest rules; survivor protection; lawful core pairs | Dedicated planner/collapse/fission/safeguard services | Services/era fixture; normal full history not proven | Needs clear displaced-person/lineage evidence | test_t098_collapse.py; test_t099_fission.py; test_t102_safeguards.py | Integrated asset/research/cargo/Person disposition | P8: fixture oracles plus replay-reached history; S15 |
| Legacy sites | F/C | Old non-core industry persists; zero current VP; upgrade in place | Legacy/upgrades services and presentation markers | Era fixtures; natural return not proven | Semantic marker needs readable contextual history | test_t100_core_upgrade.py; test_t101_legacy.py; test_t126_legacy.py | Actual old/new factory/layer continuation and stable footprints | P8: core/legacy side-by-side return; S15 |
| History / full cycles | F/C | Same people/world; political reseed; scars and known history | Chronicle/cycle services with tests; normal event coverage limited | Arranged/multi-cycle tests; organic cycles unproven | Historical UI exists, raw IDs occur in summaries | test_t105_chronicle.py; test_t125_cycles.py; test_t127_full_cycle_continuity.py | Source-to-event coverage, player filtering and replay lineage | P2/P8/P9: causal history and genuine reseed evidence; S13/S15 |
| Trained faction policies | C/I | Saved seeded assignment; legal distinct executed behaviour | Three artifacts; normal loader uses heuristic; own stocks omitted in observation | Explicit assignment/evaluation yes; normal assignment absent | Consequences, not model internals, should be visible | test_t143_t150_leadership.py; test_neural_family_primary.py | Runtime assignment, observation correctness, full-world validation | P5/P9: fixed models, paired outcome metrics, no retraining; S08/S14 |
| UI / visual feedback | P/C | Semantic placeholders, contextual evidence, responsive single-pointer play | Registry, visual language, attached cards, map and mode suppression | Yes; much capture evidence uses staged fixtures | Current label/control collisions are visible | test_semantic_visuals.py; test_t110_mvp_a11y.py; G11 frames | Geometry assertions/image existence do not prove comprehension | P0/P2/P9: inspect every real frame, owner judges subjective clarity; S17/S18 |

### Player versus QA evidence for every system

| System | Ordinary player evidence | Privileged QA/debug evidence |
| --- | --- | --- |
| Exploration / Travel | Place, adjacent exits, observed terrain, destination | Topology, travel validation, command/visit receipts |
| Game Time / World Turns | Local activity, turn cue and paused screen | Game ms/quanta, turn/round/seat roster, pause tokens |
| Catan production | Nearby harvest/warehouse consequence and local explanation | Dice stream, matching hexes, suppression and grant ledger |
| Stock / reservations | Inspectable known warehouse goods/purpose | Every stock container, reservation and conservation ledger |
| Carts / logistics | Loaded cart, route exit/arrival and visible obstruction | Route IDs, cargo lots, journey ACKs and edge costs |
| Bilateral trade | Observed exchange/delivery; attributed learned account | Both offers, acceptance, escrow, deadlines/default and settlement receipt |
| Roads / construction | Scaffolding, road line, deliveries and completion | Order IDs/costs/legal placement, consumed deliveries |
| Settlements / cities / VP | Known civic status, faction pattern, growth/era consequence | Derived all-faction VP and exact winner/completion order |
| Industry | Facility role/activity and verified local bottleneck | All rates, routes, finite deposits and shared capacity allocation |
| Workers | Recognisable worker/activity and learned name | Person/workplace/assignment IDs; illustrative journey registry |
| Military manufacture | Soldier emerges from yard and can be identified | Factory meter/receipt, Unit.person_id, formation membership |
| Autonomous faction decisions | Completed faction actions and locally justified reasons | Candidate list/scores/policy/model state and budget validation |
| Diplomacy | Witnessed/learned hostility/alliance and causal account | Complete relations/proposals, war graph and decision trace |
| Technology draft | Locally learned development; never choose faction cards | All hands, common snapshot, picks/pass/card instance IDs |
| Technology effects | Observed useful capability/rate change and explanation | All six actual consumer values and controlled counterfactual |
| Military movement | Formation departure/arrival and visible direction | Paths/objectives/activation budgets and military node state |
| Faction conflict | Known opposing forces, battle cause and consequences | Hostility graph, policy threshold, unseen strengths only in QA |
| Local battle | Visible combat, casualties, damage; wizard remains independent | Lease owner/checkpoint/tick order and detailed combat math |
| Off-screen battle | Returned aftermath or legitimately learned history | Deterministic resolver inputs, hostility, rounds and result receipt |
| Hazard spawning / spread | Nearby typed danger/spread with observable effects | Deck/ordinal/counters/visited cascade state across whole world |
| Hazard economic effects | Stopped source/cart and contextual cause; later recovery | Exact suppressed sources/transit predicates and matched-roll oracle |
| Faction hazard response | Formation treatment state, changed hazard, resumed work | Selected cube/capability/adjacency and spent activation |
| Wizard local magic | Local permitted actions and their real consequences | Range/knowledge/cap/caller validation and modifier receipts |
| Ward Duel | Full retained duel, selected encounter and return outcome | Secret/AI/RNG/lease/visit state only in explicit test context |
| People / knowledge | Known name/role/relationships; facts learned legitimately | Complete Person registry, knowledge provenance and private facts |
| Inventory / grimoire | Personal item/grimoire inventory and usable actions | Container ownership, slot/cooldown/lease/puzzle state |
| Save / load | Same recognisable world and appropriate save/load feedback | Full durable snapshot, schema/migration, checksums and next-command equality |
| Era transition | One readable era change and changed familiar place | First threshold, plan/receipt/all asset disposition and new roster |
| Collapse / fission | Known affiliation changes, survivors/successors and displacement | Collapse thresholds/tiebreaks/fission pairs and safeguard proof |
| Legacy sites | Old footprint, legacy marker and learned historical context | Legacy flags, zeroVP, recipes/layers/meters and upgrades |
| History / full cycles | Learned history, same world/people and changed political era | Complete chronicle/reseed/retirement/compaction/pinned references |
| Trained faction policies | Behavioural differences in building, exchange, armies and response | Artifact hashes, assignment, inference/fallback, legal opportunities and distributions |
| UI / visual feedback | Clear controls, semantic shapes, bounded labels and contextual events | Layout/hitbox geometry, actor IDs, scene mode and capture metadata |


No row's unit-test coverage constitutes player-legibility acceptance. The last column points to phases that require both authoritative state and real presentation evidence.

## E. Prioritised visual/UX defect register

| ID / priority | Evidence / defect type | Current problem | Acceptance target / phase |
|---|---|---|---|
| V01 / P1 | IMAGE, both settlement sizes; visual clutter | Many attached labels appear simultaneously, including behind the top bar; role/name text collides. | One selected full card plus bounded nearby labels; no text intersects protected controls; P2. |
| V02 / P1 | IMAGE, portrait settlement and landscape settlement; input obstruction | Rockfall/terrain/worker labels overlap the movement pad. | Reserve pad/header/menu safe regions; placement avoids them at 450×800, 1280×720 and 960×540; P2. |
| V03 / P1 | IMAGE, landscape G04 battle; poor feedback | Multiple labels/HP readouts overlap tightly; building text is tiny; bottom-right controls compete. | Archetype silhouettes and faction pattern remain distinct; selected unit gets readable detail; combat feedback is brief and aggregated; P6. |
| V04 / P1 | IMAGE, portrait map; poor feedback | The small legend is barely usable at native scale. Current geometry/numbers are improved but do not establish discovery correctness. | Readable legend and selection detail; keep token centre free; show discovered/remembered state with age; P2. |
| V05 / P1 | SOURCE + IMAGE; integration gap | War, draft, treatment and production have no dependable unified causal presentation; some causes never execute. | Emit notices only from committed domain outcomes and allowed knowledge; verify each chain before wording it; P2–P6. |
| V06 / P1 | SOURCE; knowledge leak | `reveal_all=False` still exports current settlements/roads/hazards across the board. Player-field requests can return privileged extras. | Known-map cache/filtered projection; explicit debug scope required for hands/plans/raw knowledge; P2/P5. |
| V07 / P2 | IMAGE, FX-ERA portrait; visual clutter | Test panel collides with large world labels; it only shows near-transition, not the full conversion sequence. | Debug panel visibly separated in QA; normal transition uses short history/changed-world cues; P8. |
| V08 / P2 | IMAGE, hazards fixture; poor feedback | Typed danger is a diamond but its cause, treatment and recovery are not explained by this frame; tiny text. | Distinct typed state; nearby source/route visibly interrupted; Inspect explains verified blockage and recovery; P6/P7. |
| V09 / P2 | SOURCE; test gap | File existence and runner exit are the current capture report's principal proof. Fixed time waits can capture the wrong state. | State predicate + matched version/receipt + actual image inspection; missing required frame fails; P0. |
| V10 / P2 | SOURCE; test gap | Fixture screenshots stand in for natural carts, autonomous building and conflict. | Same production shell loads replay-verified normal checkpoints; setup label never hidden in QA metadata; P0/P9. |
| V11 / P1 risk | SOURCE; integration gap | Normal local-battle controller is hosted as a Node despite being RefCounted; rebind/teardown is incomplete. | Reuse G04 lease/controller/presenter responsibilities with one owner and one actor per ID; P6. |
| V12 / regression risk | IMAGE portrait Ward Duel positive baseline | Retained duel appears clean and readable in the inspected frame. That does not prove pointer ward entry or every return path. | Preserve clean mode; capture actual ward entry, resolution, return and actor count; P7. |
| V13 / unverified risk | Not freshly observed; test gap | Ghost people, repeated cart entrances, stale selection, hidden hitboxes after Travel/load/duel/era remain continuity risks. | ID-set and hit-test assertions plus paired captures; P4/P6/P7/P8. |

### Minimal event-salience and information policy

Use the existing semantic system, attached cards, map/knowledge/Chronicle and presentation-mode owner. Add a small event presenter only if there is no suitable existing receiver; it reads committed facts and never mutates gameplay. Local activity is primary; text explains the cause when necessary.

| Event | Level | Ordinary player evidence | QA/debug evidence |
|---|---|---|---|
| Road built | NOTICEABLE locally | Short “A road has opened” plus changed exit/road line if witnessed/learned. | Order, delivered lots, edge and receipt IDs. |
| Settlement created | IMPORTANT locally/when learned | Scaffolding becomes centre/buildings; named-place notice. | Placement validity, delivered cost, owner, derived VP. |
| City upgraded | IMPORTANT | Double-border semantic civic marker and brief “The settlement has grown”. | Same building identity, upgrade receipt, 1→2 VP and channel flow. |
| Cart dispatched | AMBIENT | Cart with visible cargo category moves towards exit. | Physical container, route and assigned turn. |
| Cart blocked | NOTICEABLE | Stopped cart and hazard/road obstruction; contextual reason. | Invalid edge, cargo conserved, no delivery. |
| Trade completed | NOTICEABLE if locally known | Receiving activity; appropriate worker/Inspect explanation. | Two escrow legs and one settlement receipt. |
| Soldier manufactured | NOTICEABLE first locally, then AMBIENT | A distinct soldier leaves the relevant yard. | Factory crossing, unique Unit/Person/formation link. |
| Army moved | AMBIENT; NOTICEABLE if locally threatening | Formation heads to exit and disappears once. | Active seat, path ≤2, movement receipt. |
| War began | IMPORTANT when witnessed/learned | Visible hostility plus concise attributed account. | Diplomatic transition and causal attack event. |
| Battle started | IMPORTANT locally | Readable opposing forces, contact cue; no wizard combat HP. | Hostility graph, participants, exclusive lease. |
| Battle ended | IMPORTANT locally | Retreat/deaths/damage remain; concise outcome. | Casualties, structure changes, resolver receipt. |
| Centre destroyed | IMPORTANT | Centre becomes destroyed state; surviving assets remain unclaimed. | Ownership removed, VP recomputed, no capture. |
| Faction dissolved | IMPORTANT when known | Vacated affiliations and learned-history entry. | Last-centre rule, disbanding/displacement/cargo disposition. |
| Hazard appeared | NOTICEABLE nearby | Typed hazard and suppressed source/transit cue. | Cube/cause identity, source hex and placement receipt. |
| Hazard spread | IMPORTANT nearby; CRITICAL only at terminal | Local new dangers; escalation warning only with justified knowledge. | Propagation visited set, era/lifetime counts. |
| Soldiers treated hazard | NOTICEABLE | Formation treatment state, then one cube disappears. | Reserved/spent activation, exact cube, zero move/attack. |
| Wizard removed hazard | IMPORTANT local | Duel outcome, return, hazard gone and work resumes. | Lease result, selected cube, visit allowance, exactly once. |
| Technology selected | AMBIENT unless learned | No global hidden-hand announcement; contextual “new methods” after a visible change/testimony. | Pre-draft snapshot, selected instances and pass map. |
| Technology activated / effect | NOTICEABLE first local example | Larger observed cart load, stronger unit silhouette detail or increased activity explained in Inspect. Never promise throughput when another bottleneck still binds. | Scoped modifier, actual consumer value and controlled counterfactual. |
| Faction reached 10 VP | CRITICAL transition boundary | Brief era trigger identified through permitted public history. | First triggering event/order; no later old-era stage. |
| Era transition began | CRITICAL | Existing paused transformation, readable skip/reduced-motion. | Atomic receipt and pre/post world hashes. |
| Faction collapsed | IMPORTANT within transition summary | Ruins/displaced people/known affiliation changes. | Rule/tiebreak, losses and identity continuity. |
| Faction survived or split | IMPORTANT within transition summary | Recognisable successors and banners/patterns. | Lineage, core pairing, research/asset assignments. |
| Legacy site remains | AMBIENT; NOTICEABLE on first return | Retained footprint with old-era border/label on inspection. | Legacy status, zero current VP, compatible old industry. |
| New era/cycle began | CRITICAL once | Same world with changed political signs and history. | Era/cycle IDs, roster, hazards, layers, retirements. |

Proposed tunables for P2: one important banner at a time; at most two queued short notices visible; coalesce repeated same-kind/cause events within a turn; retain inspectable known history. Do not replay notices on refresh/reload. Ambient cues remain available without reading text. Critical transitions must not be overwritten by ambient messages. No universal live enemy alerts, numerical hidden strengths or automatic knowledge grants simply because the player opened a panel.

## F. Development roadmap and dependency order

| Phase | Outcome | Depends on | Main evidence gate |
|---|---|---|---|
| P0 — Establish current truth and evidence harness | Fresh, reproducible normal-play baseline and honest defect ledger. | Audited SHA or explicitly re-audited replacement. | Every required capture reviewed; 15 failures classified; no fabricated reachability. |
| P1 — Repair command/state continuity | Correct RNG, complete saves/rollback, correct draft lifecycle and turn bookkeeping. | P0 | Command-path and real save/load oracles pass; no lost new-era hands. |
| P2 — Readable wizard view | Coherent placeholder hierarchy, safe controls, filtered evidence and concise events. | P1 | Both required resolutions plus 960×540; no privileged ordinary view. |
| P3 — Economy, trade and delivery | Autonomous decisions become physically supplied construction and bilateral exchange. | P1/P2 | Conserved before/after cart/trade/construction sequences. |
| P4 — Industry, people and manufacture | Factory work visibly produces the same persistent soldiers the player can meet. | P3 | Real-time accounting, Person identity and local actor continuity. |
| P5 — Faction behaviour and technology | Legal saved policies, diplomacy and draft effects influence observable outcomes. | P3/P4 | All six effect consumers; full draft invariants; measured policy behaviour. |
| P6 — Conflict and hazard response | Battles and hazard treatment complete the economic/military causal chains. | P5 | Production-shell battle and treatment → recovery; exclusivity and alliances. |
| P7 — Wizard intervention and retained encounters | Observe/Talk/magic/Ward Duel fit the same world and return cleanly. | P6 | Actual pointer duel sequence, selected-cube result and no ghosts; puzzle regressions. |
| P8 — Era, history and full-cycle continuity | Historical change preserves identities and correctly transforms politics. | P7 | 10-VP/legacy/fission/reseed and complete persistence sequences. |
| P9 — Integrated journey and final robustness | One coherent playable build, with repeatable evidence and owner review packet. | P0–P8 | Replay-verified journey, final multi-seed report, final Windows Godot run. |

These are phase gates, not time estimates. P0 measures runtime and capture costs before any promise about unattended duration. Each phase may contain several small commits but **stops at its gate**. Keep the existing G01–G12 ledger and append a distinct polish ledger; do not renumber historical tasks or turn AUTO_READY into owner PASS. Final art, model retraining, quest development and shipping-package certification are not new workstreams.

## G. Screenshot acceptance system

### Capture contract for every manifest row

1. Record exact source SHA, tree hash, OS, Python/Godot versions, fixture/seed, policy/content digests and isolated save slot. Refuse a stale/wrong checkout. Preserve user saves.
2. Execute relevant tests, launch the actual production shell or named retained fixture, and reach the stated state. Await authoritative command/lease receipts and a matching world version; do not use a sleep as proof of readiness.
3. For checkpoints, save the full production snapshot **and** initial seed/config plus replayed commands/clock advances. Validate replay hash before capture. `run_long_world` currently writes summaries; a summary is not a reloadable or legally reached checkpoint.
4. Use real pointer/keyboard/touch input for player affordance acceptance. A direct domain call can arrange a fixture or assert logic, but cannot count as successful player clicking, ward selection or battle interaction.
5. Freeze at an existing deterministic capture barrier where needed; account for its pause token. Record simulation version/hash with the screenshot and avoid advancing unseen time between paired state and image capture.
6. Decode image bytes and record actual dimensions. Inspect the full frame at native size, then selected text/control regions. A nonempty PNG, successful process exit or catalogue badge is not visual PASS.
7. For each image report: ID, filename, actual dimensions, source SHA, fixture/checkpoint, state hash/version, expected condition, **observed condition**, PASS/FAIL/MANUAL REVIEW REQUIRED, visible defects, iteration number and fix/retest references. Any unrendered or uninspected image remains unaccepted.
8. Fail on missing frames, wrong dimensions, timeout, blank image, incorrect scenario, stale state or errors. Keep failed originals under `iterations/`; put only reviewed final candidates under `final/`. Preserve metadata, command logs, assertions and failure saves. Do not label an entire phase PASS while required images need manual review.

Reuse `tools/run_visual_review.py`, `run_visual_review_harness.gd`, `run_ward_duel_presentation.gd`, FX-ERA layout captures and G11 folders. Add phase/output/manifest options to those tools if needed, not another simulation. Preserve old G11 evidence; write new evidence under `Pack/DuelMasterBattle_Build_Pack/tracking/polish/Pn/<source-sha>/`.

The matrix below defines individual logical frames. **Every row expands into separate 450×800 and 1280×720 PNG requirements.** Rows marked responsive also require 960×540, preserving the existing check. P0 discovers and retains any additional current narrow/landscape checks; it does not quietly replace them. Capture filename: `<id>_<width>x<height>.png`. The CSV enumerates each expansion explicitly.

All `CP-*` names are **proposed checkpoint IDs**, not claims that files already exist. P0 records readiness; the owning later phase produces and replay-verifies each checkpoint. An arranged production fixture may diagnose an unreachable mechanism, but cannot fill a missing normal-play checkpoint or certify the final journey.

| ID / phase | Resolutions / subframes | Scene / fixture | Starting state | Exact actions | Expected visible result | PASS evidence | Obvious failure signs | Authoritative state evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B01 / P0 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | Fresh seed507; node35; no old save | Launch Play Latest; wait for world-ready receipt; capture before input | Whole normal area, wizard, exits, buildings, people and controls | Correct normal scene and source revision; honest baseline defect annotations | Wrong fixture; blank scene; hidden overlays; stale PNG | Initial board19/54/72, turn0, initial identities |
| B02 / P0 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | B01 | Open map using its visible button; capture; close | Board, legend and underlying modal boundary | Baseline records actual legibility and any discovery leak; does not declare it fixed | Map is a different fixture; unreadable screenshot not recorded as defect | Player projection versus privileged world map |
| B03 / P0 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | B01; nearby existing worker | Use actual single-pointer selection, Observe and Talk; capture attached card | Selected actor and attached conversation/actions | Input receipt corresponds to selected real Person; record collisions | Direct semantic service call presented as pointer success | Person ID, observed/learned fields, interaction/range receipts |
| T01 / P1 | 450×800; 1280×720; subframes: normal, qa_hands | FX-MVP / g05_shell | Fresh seed507 after command/state repairs | Capture before first Wait; open QA technology view in a separate capture session | Normal starting world; QA companion shows seven-card hands | One initial deal; normal view has no hand-management panel | Empty draft; duplicate deal; hands in ordinary view | RNG counter, initial roster and exact hand instance IDs |
| T02 / P1 | 450×800; 1280×720 | FX-MVP / g05_shell | T01 normal view | Press/release Wait twice with acknowledged receipts; capture | Same place, clear turn change; permitted local consequences | Exactly two turns/one round; same actor identities | Double turn; vanished actors; repeated constant RNG stream | Q01/Q04 dice sequence and two acquired cards; no pixel-only claim |
| T03 / P1 | 450×800; 1280×720; 960×540; subframes: person, qa_durable | FX-MVP / g05_shell | CP-SAVE-P1 arranged production save with nonempty research/diplomacy | Save through coordinator; quit; relaunch/load; capture same selected actor | Same person/world; QA companion retains draft/relation | No visible reset; full durable comparison succeeds | Lost name, hands, war relation or cargo; fresh game loaded | Q02 before/after independently enumerated fields |
| U01 / P2 | 450×800; 1280×720; 960×540; subframes: world, selected_card | FX-MVP / g05_shell | Fresh507 and B03 interaction state | Repeat B01/B03 inputs after layout changes | Readable selected card; bounded labels; all essential controls visible | No overlaps with pad/header; ≥48px essential hit areas; readable native-size text | Tiny/stacked labels; clipped action; covered exit | Widget bounds, hit test and selection entity |
| U02 / P2 | 450×800; 1280×720; 960×540; subframes: worker, cart, soldier, hazard | FX-MVP / g05_shell | CP-DENSE from production play; diagnostic FX-WORLD-LAYERS separately | Select worker, cart, soldier and hazard in four successive captures using suffixes a–d | Each selected category distinct; one full attached card at a time | Silhouette, faction pattern and selected state understood without raw IDs | Cart resembles person; selected identity ambiguous; stack of cards | Actor IDs/types, same registry source, protected-control bounds |
| U03 / P2 | 450×800; 1280×720; 960×540; subframes: visited, unseen | FX-MVP / g05_shell | CP-KNOWN-MAP; one visited and one unseen changed place | Open map; select visited then unseen place in suffixes a/b | Known/remembered facts, readable legend; unseen updates concealed | Player payload and pixels respect knowledge/time of visit | Live hidden hazards/ownership/strength or technical IDs shown | Q06 knowledge projection and unobserved mutation counterfactual |
| U04 / P2 | 450×800; 1280×720; 960×540; subframes: inventory, grimoire, restored | FX-MVP / g05_shell | U01 | Open inventory then close; open grimoire then close; lose/regain focus; capture each modal with suffixes a/b | Readable paused screens and restored world controls | No clicks pass through; modal close restores exactly one world view | Hidden world interaction; modal under labels; catch-up on resume | Pause-token set, game clock and hit-test receipts |
| E01 / P3 | 450×800; 1280×720; subframes: source, target | FX-MVP / g05_shell | CP-CARGO before load; original source and destination identified | Inspect source warehouse and under-construction target in suffixes a/b | Actual stocked warehouse and visible site needing goods | Local explanation names goods/purpose without global stock tables | Instant free completion or omniscient warehouse table | Stock/reservation/order IDs and legal-policy decision |
| E02 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-CARGO after actual co-located loading, before next edge | Select loaded cart and capture | Distinct cart with cargo cue and contextual destination | Goods visibly associated with this cart; no worker/duplicate cart confusion | Empty-looking load; cargo removed from remote warehouse | Source decrease equals actual cart cargo lots; current node = source |
| E03 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | E02 | Press Wait once; capture acknowledged departure/next-node entry at journey barrier | Same cart leaving via correct exit/road | One-edge move; one exit presentation for same journey | Teleport beyond route; duplicate entrance; two carts same ID | Journey ID, previous/current node, one movement receipt |
| E04 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-CARGO one edge before destination; wizard at destination via replay | Press Wait once; capture arrival before completion consequence | Same cargo-bearing cart reaches destination | Identity retained and arrival presented once | Cargo changes category; cart appears before authoritative arrival | Cart/destination co-location; delivery receipt and container transfer |
| E05 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | E04 | Advance only receipt-completion frame; inspect completed structure | Scaffold changes into road/building; concise local completion cue | Visual completion agrees with fully delivered/consumed cost | Finished site while missing goods; duplicate notice or refund | Order complete once; ledger conservation, owner and VP |
| E06 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-BLOCKED-CART; legal hazard/road break ahead | Press Wait once; Inspect stalled cart | Cart stopped with local reason and cargo still shown | Blockage location/cause is understandable | Cart moves through block; invisible cargo loss; technical route ID | Blocked edge, unchanged cargo, no arrival receipt |
| E07 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | E06 with obstruction legally removed in replay | Press Wait; capture next movement/arrival | Previously stopped cart resumes | Same cart/cargo continues; reason no longer falsely blocked | New cart minted; goods doubled; stale blocked badge | Same journey lineage and conserved goods |
| E08 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-TRADE with legal bilateral acceptance and first leg arriving | Inspect receiving cart/warehouse after one acknowledged delivery | Arrival activity; no false claim full trade finished | Player sees delivery; reserved exchange stays unavailable to construction | One leg presented as settled; free replacement cart | Both contracts, first-leg escrow, available stock unchanged |
| E09 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | Same trade before second arrival | Press bounded replayed Wait sequence from manifest; inspect receiver | Second arrival and one locally known trade-complete cue | Both legs settled exactly once, with physical origin | Repeated payment; unilateral gift; unlimited free carts | Trade receipt, both escrow transfers, conserved totals and deadline |
| E10 / P3 | 450×800; 1280×720; subframes: road_before, road_after, settlement_before, settlement_after | FX-MVP / g05_shell | CP-EXPANSION before frontier road/settlement complete | Inspect proposed site; capture after delivery in suffixes a/b | Road/site progresses from work to completed frontier | Changed connectivity/ownership is visibly grounded in construction | Ownership appears without work/cost | Legal placement, road endpoints, delivered order/owner/VP |
| E11 / P3 | 450×800; 1280×720; subframes: settlement, city | FX-MVP / g05_shell | CP-CITY before funded upgrade | Capture settlement; execute manifest final Wait; capture city as suffixes a/b | Same civic footprint gains double-border city state | Readable upgrade with same identity and one notice | Extra city actor; footprint jumps; wrong faction | Same building ID; exact cost; VP1→2; flow modifier |
| I01 / P4 | 450×800; 1280×720; subframes: primary, processor, factory | FX-MVP / g05_shell | CP-INDUSTRY with real primary/processor/factory active | Inspect each facility and worker in suffixes a/b/c | Semantic shapes show distinct purposes and real activity | Player can follow source→processing→yard without processor IDs | Three indistinguishable blobs; raw constraint table | Resource layers/routes and real workplace Persons |
| I02 / P4 | 450×800; 1280×720 | FX-MVP / g05_shell | Same factory just below completion, reached by exact AdvanceGame trace | Run recorded unpaused interval; capture pre-threshold at clock barrier | Concise progress/activity cue; QA meter companion | No completion before meter reaches threshold; other bottleneck explained | Fake progress unrelated to meter; paused process runs | Input/deposit balances, shared allocation, rational meter; Q13 |
| I03 / P4 | 450×800; 1280×720 | FX-MVP / g05_shell | I02 | Advance remaining exact interval across one threshold; capture birth/departure | One soldier emerges from actual yard | One unique soldier; archetype/faction distinct from workers | Duplicate birth; worker turns into unrelated ID | Factory receipt, one Unit ID and person_id, active formation membership |
| I04 / P4 | 450×800; 1280×720 | FX-MVP / g05_shell | I03 | Select new soldier; Observe/Talk if allowed; capture card | Same persistent Person represented as soldier | Learned name/profile and combat role agree; no dual actors | Anonymous replacement; two actors for same Person | Person/Unit bidirectional link and known profile |
| I05 / P4 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | I04 | Travel away/back along manifest adjacent route; save/reload; capture soldier and yard | Same soldier; continued meters; no repeated entrance | Identity/count/meter continuity survives boundaries | Reset meter; resurrected casualty; duplicated cart/soldier | Q12/Q14 before/after IDs, meters and journey ACKs |
| D01 / P5 | 450×800; 1280×720 | FX-MVP / g05_shell + explicit QA technology_view | CP-ROUND before final seat; privileged technology_view | Capture all faction hands; execute final valid Wait through normal shell | QA-only seven/legal remaining hands and round marker | Every active faction present; private panel unmistakably QA | Player is asked to select cards; missing faction hand | Common pre-draft snapshot hash; hand/card instance IDs |
| D02 / P5 | 450×800; 1280×720 | FX-MVP / g05_shell + explicit QA technology_view | D01 after round boundary | Capture same QA view after receipt | One choice each; remainder passes clockwise | Card IDs prove pass direction/acquisition once | Sequential information advantage; duplicate picks | Q15 snapshot/pick/pass map; activated versus archived status |
| D03 / P5 | 450×800; 1280×720 | FX-MVP / g05_shell + explicit QA technology_view | CP-DRAFT7 before seventh complete round | Execute final seat; capture QA hands | New seven-card hands after pick7 | Previous seven acquisitions retained; new instance IDs | Empty draft; 6/8 cards; reused instance IDs | Pick count/redeal count/round receipt |
| D04 / P5 | 450×800; 1280×720; subframes: archive, activated | Declared production research arrangement + QA technology_view | Declared arranged later-era production fixture: missing then active predecessor | Capture archive; acquire eligible predecessor by production ResearchService; capture activation, suffixes a/b | QA differentiates inactive/active with plain explanation | Predecessor history governs activation; no stacking on refresh | Archived card grants effect early; visual-only activation | Q15 prerequisite/duplicate-cap/era scope oracle |
| D05 / P5 | 450×800; 1280×720; subframes: primary_before, primary_after, processor_before, processor_after, factory_before, factory_after, cart_before, cart_after, hp_before, hp_after, attack_before, attack_after | Declared production effect arrangements + existing QA views | Six controlled production effect cases, one per suffix primary/processor/factory/cart/hp/attack | Capture before/after relevant QA consumer and affected actor | Relevant capacity/stat consequence is visible in QA | All six actual consumers change under nonbinding alternate constraints | Only observation value changes; HP refresh heals; wrong-era asset | Q16 exact effective value, throughput/cargo/HP/damage counterfactual |
| D06 / P5 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | CP-TECH normal player view; known affected facility/cart/soldier | Inspect witnessed change; read locally justified notice | Plain explanation of new methods/capability; changed activity | Effect understandable without hands, scores or management buttons | Raw model/card table; promised throughput despite binding bottleneck | Known fact origin plus same Q16 committed effect |
| M01 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-CONTACT before legal hostile movement | Inspect frontier formations; capture | Faction patterns, distinct archetypes, observable hostility | Opponents readable; legitimate war/intent cause | Allied forces described as enemy; hidden strength shown | Diplomacy graph, observed targets, formation objectives |
| M02 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | M01 wizard remains present | Press required Wait once; capture contact at lease-ready receipt | Formation arrival and clear battle-start cue | Production g05 shell owns exactly one bound local battle | RefCounted host error; battle only in separate G04 fixture | Battle ID/participants/lease owner; no offscreen resolver concurrently |
| M03 / P6 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | M02 | Allow recorded unpaused local combat ticks; capture active combat | Readable opposing action/health cues; wizard remains independent | Distinct units and safe controls; no faction command buttons | Stacked HP text; wizard army HP/death; missing controller tick | 50ms tick sequence, Unit health/damage and wizard immunity |
| M04 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | Same contact after deterministic resolved tick count | Capture aftermath; Inspect affected centre and surviving Person | Retreat/casualties/damaged or destroyed building persist | Changed world agrees with outcome; no captured settlement magic | Dead actor remains active; faction ownership flips on battle win | Casualty Person tombstones, withdrawal, buildingHP/owner/VP |
| M05 / P6 | 450×800; 1280×720; subframes: hazard, blocked_work | FX-MVP / g05_shell | CP-HAZARD source/road genuinely suppressed | Inspect manifestation and blocked source/cart in suffixes a/b | Typed danger connected to stopped work/transit | Cause is locally understandable without cube IDs | Hazard decorative while source still produces; source destroyed incorrectly | Suppression queries, matched Catan roll/industry window, cargo retained |
| M06 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-RESPONSE eligible adjacent formation before its active seat | Inspect formation and target; capture | Responder poised near danger with appropriate archetype cue | Correct active faction/capability; no manual army order | Remote or engaged/ineligible formation assigned | Legal candidate, adjacency, unspent activation and selected cube |
| M07 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | M06 | Press Wait to its seat; capture treatment outcome barrier | Brief treatment state/cue at correct hazard | Committed treatment is visible before disappearance; no attack/move | Generic proposal with no effect; marching and treating same turn | Spent-turn equals current turn; treatment receipt; zero move/attack |
| M08 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | M07 | Capture updated world and Inspect affected area | Exactly selected hazard gone/changed | Other cubes remain as authoritative; no ghost manifestation | All cubes vanish; targeted cube stays; duplicate result notice | Exact cube active flag/count; actor registry matches state |
| M09 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | M08 after final relevant blocker removed | Run recorded production window/next valid cart turn; capture source/cart | Previously suppressed activity resumes | Same source/cart recovers; output is real, not just animation | Remaining blocker ignored; deposit refilled; cargo respawned | Q22 matched grant/flow/route recovery; conserved resources |
| M10 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | Replay CP-CONTACT in separate branch | Enter battle then Travel away legally; run prescribed turns; return | Persistent off-screen aftermath, with learned/local account | No second fight or resurrected actors after return | Local lease left running; duplicate casualties; frozen unresolved battle | Exclusive handoff, bounded resolver receipt, resulting IDs/buildings |
| W01 / P7 | 450×800; 1280×720 | FX-MVP / g05_shell | Fresh507 route35→30→36→31→37 or validated successor CP-WARD | Walk via recorded live input path to cube1 manifestation | Hazard in same world; wizard visibly in interaction range | Exact target and world-local position match | Teleported wizard; fixture switched without disclosure | Accepted Travel receipts and local pose; selected cube1 |
| W02 / P7 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | W01 | Observe then select Challenge from attached interaction card | Readable Challenge affordance on selected manifestation | Real input opens retained duel once, allowed visit | Hidden/debug shortcut; direct result call; wrong cube | Observe/range/visit eligibility and lease result |
| W03 / P7 | 450×800; 1280×720; 960×540; subframes: ward_setup, active_board | FX-MVP lease → retained game_board.tscn | W02 retained game_board | Use real pointer to enter four ward spells/secret and play recorded moves; capture setup and active board as suffixes a/b | Full production Ward Duel, clean background, usable spell controls | No world labels/hitboxes; pointer receipts; ward actually entered | Simplified Mastermind panel; forced rival defeat; world bleed | DmbBattleSim ward/history/RNG, mode/pause/lease identity |
| W04 / P7 | 450×800; 1280×720; 960×540; subframes: win, draw, loss | Retained game_board.tscn result | W03 played result | Capture result after actual win/draw/loss branch; suffix each branch | Correct result, readable return affordance | No domain success helper bypass; outcome acknowledged once | Auto-win injected; ambiguous result; frozen return | Production duel result/command and selected-cube receipt |
| W05 / P7 | 450×800; 1280×720; 960×540; subframes: win_return, loss_return, cancel_return | FX-MVP / g05_shell | W04 win plus independent loss/cancel branches | Return through visible control; capture normal world | Exact chosen hazard removed only on valid success; world clean | Single actors; controls restored; no extra visit allowance from Wait/reload | Ghost duel/world actors; substitute cube removed; all hazards cleared | Cube/visit/actorID sets and pause tokens before/after |
| W06 / P7 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-BUFF with locally observed allied/eligible soldier | Apply permitted buff via real card; Inspect; run paused then unpaused interval | Clear bounded buff cue on same soldier | UI agrees with real modifier and remaining Game Time | Buff expires while paused; stacks past cap; stale target accepted | Q23 cap/range/current-target and clock-expiry oracle |
| W07 / P7 | 450×800; 1280×720; 960×540; subframes: inventory, grimoire, puzzle | FX-MVP / g05_shell | CP-ITEM existing personal item/puzzle; no new quest content | Use inventory/grimoire and existing puzzle interaction; capture each as suffixes a/b/c | Personal tools integrated with attached interactions | Real item/slot semantics; readable mobile controls; world pauses correctly | Item duplicated; spend personal item as faction stock; new quest scope | Inventory single-container record and existing puzzle solution regression |
| R01 / P8 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-ERA replay-reached9VP; FX-ERA separately labelled diagnostic | Inspect relevant current centre/site before final delivery | Coherent place awaiting real completion; QA verifies9VP | Normal checkpoint has legal lineage; arranged fixture is labelled | VP written directly in purported normal journey | Full replay, ledger, old roster and winner9VP |
| R02 / P8 | 450×800; 1280×720 | FX-MVP / g05_shell | R01 | Perform manifest final accepted Wait/Travel; capture winning completion | Finished construction and beginning era cue | Exactly one threshold event; no later old-era actions | Transition delayed; extra production/attack/old draft after win | First winning receipt and stopped stage trace |
| R03 / P8 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | R02 | Capture existing transition at receipt-defined midpoint; test skip separately | Readable paused transition; same location; safe skip | Four-second/skip presentation does not reapply conversion | Labels under modal; tiny summary; double transition | Single atomic conversion; clock paused; one presentation token |
| R04 / P8 | 450×800; 1280×720 | FX-MVP / g05_shell | R03 completed | Inspect transformed core; capture | Same anchor with recognisable new-era civic/faction identity | Same core footprint and ID; no duplication | Shifted building; duplicate starter goods; missing people | Core/layer upgrades, starter-grant receipt, roster/policy/draft |
| R05 / P8 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-LEGACY same transition branch | Travel along replayed route to surviving old non-core site; inspect | Old-era legacy marker and continuing old facilities | Site feels historical, operates legally, contributes no currentVP | Old site disappears; inert ruin collision; new-era rules applied blindly | Legacy flag, meter/recipe continuity, zeroVP and active old layers |
| R06 / P8 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | R04/R05 known surviving Person | Select same Person and open learned history | Same identity with appropriate changed affiliation/history | Knowledge persists; history explains known change without IDs | Person replaced; unknown private history revealed | Person ID/name/relations/lineage and filtered chronicle |
| R07 / P8 | 450×800; 1280×720; subframes: person, cart, unit, hazard, tech, history | FX-MVP / g05_shell | CP-SAVE with representative Person/cart+cargo/soldier/hazard/tech/history | Save through visible control; capture selected targets across suffixes person/cart/unit/hazard/tech/history | Representative world/UI state before quit | All six domains covered; tech exact hands only in QA companion | Empty cargo chosen as persistence proof; omitted domain | Q29 full independently enumerated before-state; save digest |
| R08 / P8 | 450×800; 1280×720; subframes: person, cart, unit, hazard, tech, history | FX-MVP / g05_shell | R07 saved snapshot | Quit Godot and sidecar; relaunch/load; repeat same six views and next command | Same entities and remembered world after load | Before/after fields and next-command hash match uninterrupted branch | New IDs; repeated arrivals/picks; lost diplomacy; reset meter | Q29 after-state, actor registry and command continuation hash |
| R09 / P8 | 450×800; 1280×720; subframes: before, trigger | FX-MVP / g05_shell | CP-CYCLE legally reached Future threshold; arranged regression separate | Capture pre-boundary and trigger as suffixes a/b | Future world and cause of final transition | Correct era/cycle; real political/economic precursor | Skin switch with no political state conversion | Old factions/military/research, layers, people/knowledge IDs |
| R10 / P8 | 450×800; 1280×720 | FX-MVP / g05_shell | R09 completed new Prehistoric cycle | Inspect same place/Person/history and new factions | Familiar physical world with new political competition and scars | New cycle is explicit; persistent identities/places recognisable | Everything resets; old army keeps marching; research carries unlawfully | Q28 roster reseed/retirements, fresh layers/cubes, persistent identity/world |
| G01 / P9 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | Final accepted SHA; fresh507 | Replay owner opening using visible controls; capture | Readable whole game opening | Final output matches tested revision and manifest | Older screenshots copied into final folder | Final SHA/config hash and CP-START replay |
| G02 / P9 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | Final golden replay busy area after cart/industry/battle/duel returns | Return to same area and Inspect changed objects; capture | Causal activity, damage and people remain readable together | No cross-system label/control collisions or ghost actors | Individually good fixtures but broken combined scene | Merged actorID set, events/ACK dedupe and committed receipts |
| G03 / P9 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | Final CP-SAVE/ERA branch | Load then open known history and map; capture | Continuous world and understandable historical change | Known-only facts and readable controls across transitions | Raw model/route IDs; missing names; hidden-history leak | Final persistence/knowledge/lineage and image inspection report |


## H. Automated and integration test matrix

Use four independent evidence layers: logic/state, command/bridge integration, presentation assertions, and actual screenshot review. Windows launcher verification is separate. All new test IDs below are **planned**, not existing green tests. Reuse/extend the listed tests and owners; do not add tests that merely reproduce current implementation. Stateful comparisons must enumerate durable fields independently of the serializer.

| ID | Phase | Exact planned test / oracle | Existing coverage to extend | Required authoritative evidence |
| --- | --- | --- | --- | --- |
| Q01 | P1 | New test_polish_command_boundary.py: test_dispatch_rng_continues_like_direct_runner; test_retransmit_and_rejected_travel_do_not_draw | test_t010_rng_replay.py; test_t011_commands.py; test_t020_playable.py | Same seeded 12-command dice stream across dispatch/control/reload; each turn reaching production exactly two Catan die draws (zero after an earlier interrupt); stable receipts and zero extra mutation on retries. |
| Q02 | P1 | New test_polish_command_boundary.py: test_all_durable_fields_survive_save_load_and_rollback | test_t009_state.py; test_t014_persistence.py; test_t018_leases.py; test_t019_recovery.py | Independently populated research, hands, diplomacy, people, units, carts/cargo, meters, hazards, items, visits/history, policies, RNG and receipts; compare fields before/after real coordinator and failed transaction. |
| Q03 | P1 | Extend test_t046_seat_round.py: test_cyclic_completion_order_and_first_win_interrupt; test_recovery_precedes_active_seat | test_t013_turns.py; test_t032_orders.py; test_t046_seat_round.py | A/B/C cyclic order from B is B,C,A; dissolved seats skip; first 10-VP receipt prevents old-era force/hazard/draft work; zero-active recovery before seat selection. |
| Q04 | P1/P5 | Extend test_t041_draft.py: test_normal_boot_deals_once; test_transition_keeps_new_era_hands | test_t041_draft.py; test_t104_era_service.py | FX-MVP starts seven/faction; exactly one pick per complete round; old hands discarded once, new seven active after FX-ERA Wait and reload. |
| Q05 | P2/P7 | New run_polish_input_pause.gd plus Python clock regression | test_t012_clock.py; test_t022_clock_driver.py; run_g05_playable.gd | One Wait per press incl held/repeated input; invalid Travel no turn/RNG; independent modal/focus/duel pause tokens; 60 paused seconds no world quanta/buff expiry/catch-up. |
| Q06 | P2 | New test_polish_player_evidence.py: test_player_view_excludes_privileged_fields; test_known_map_ages_and_events_dedupe | test_t021_semantic.py; test_t079_semantic_coverage.py; test_t105_chronicle.py; test_world_map_geometry.py | Unknown enemy changes cannot alter player payload; own/known facts only; debug request explicit; same event ID once across refresh/reload; no raw internal identifiers rendered. |
| Q07 | P2/P4 | Extend existing Godot visual harness: assert_layout_and_actor_registry | test_semantic_visuals.py; run_fx_era_layout_capture.gd; run_mira_semantic_label.gd | All essential hit areas ≥48 logical px, on-screen and disjoint from protected controls; one actor per entity/Person; images inspected for clipping, not only rectangles. |
| Q08 | P3 | New test_polish_economy_chain.py: test_cart_source_co_location_and_exactly_once_delivery; test_blocked_resume | test_t030_stock.py; test_t033_carts.py; test_t034_routes.py; test_t035_director.py; test_presentation_journeys.py | Existing cart physically visits source before loading; conserved lots through one-edge turns; blocked cargo retained; resume/delivery/replay/ACK at most once. |
| Q09 | P3 | New test_polish_economy_chain.py: test_bilateral_trade_normal_policy_to_settlement | test_t044_diplomacy.py; test_t045_trade.py | Legal shortage/routes; mutual acceptance; existing or paid replacement carts; split loads; first-leg escrow not spendable; both legs release once; real-distance deadline/default/return, no gifts. |
| Q10 | P3 | New test_polish_economy_chain.py: test_delivered_frontier_road_settlement_city_chain | test_t031_placement_score.py; test_t032_orders.py; test_t036_setup.py; test_t037_destruction.py | Exact location of timber/brick/wool/grain/ore; no completion with missing cost; ownership/adjacency revalidation; unit-cost consumption once; VP 1/2/legacy0; cancelled/ruined orders conserved. |
| Q11 | P3/P6 | Extend test_t029_catan_grants.py through dispatch and ledger | test_t029_catan_grants.py; test_t071_disruption.py | Roll7/desert/no-warehouse cases; shared matching hex; hazard vs industrial depletion distinction; same controlled roll before/after removal grants correct good without changing natural RNG. |
| Q12 | P4 | Extend test_canonical_ontology.py: test_factory_birth_to_person_to_formation_on_real_commands | test_t053_factories.py; test_t054_industry_service.py; test_t059_units.py | One completion→one Unit→one living Person→one active formation; repeated view/reinforcement cannot mint; unit death gives one linked Person death/tombstone. |
| Q13 | P4/P5 | Extend test_t054_industry_service.py with damaged/shared/tech integration | test_t050_layers_primary.py; test_t051_routes_constraints.py; test_t052_allocation.py; test_t056_industry_repairs_routes.py | Shared 0.1 processor with costs2/3/5 gives .6 meters at60s, one each at100s, 10 inputs each; finite balance590 from600; damage/global scarcity/paused/visible-offscreen continuation conserved. |
| Q14 | P4 | Extend worker/presentation journey tests and Godot harness for same actor | test_t055_workers_projection.py; test_presentation_journeys.py; test_canonical_ontology.py | Blocking a worker sprite cannot change authoritative output; one existing workplace Person per carrier activity; learn/return/reload preserve name and ID; no repeated entrance ACK. |
| Q15 | P5 | Extend test_t041_draft.py: test_common_predraft_snapshot_pass_seventh_redeal_and_archive | test_t039_tech_defs.py; test_t040_research.py; test_t041_draft.py | Common snapshot hash; one choice/faction; ordered clockwise instance-ID pass; singleton self-pass; pick7 redeal; duplicate caps; inactive predecessor does not qualify; activated historical predecessor does. |
| Q16 | P5 | New test_polish_technology_consumers.py: six parameterised production-effect cases | test_t040_research.py; test_t054_industry_service.py; test_t059_units.py; test_t066_buffs.py | Each effect reaches correct consumer: primary/processor/factory capacity, cart+1, unit HP and damage; binding constraints tested independently; era scope; HP proportion/no refresh heal; repeated refresh/reload no stacking. |
| Q17 | P5 | Extend leadership tests for production initial/era assignment and observation schema | test_t042_legal_obs.py; test_t067_military_ai.py; test_t143_t150_leadership.py; test_neural_family_primary.py | Own actual warehouse/cargo/rate fields present; truly unobserved enemy state masked; legal target schema matches objectives; pinned model hash/assignment survives save/era; fallback explicit. |
| Q18 | P5/P9 | Extend tools/run_long_world.py and training evaluation adapters; add executed-outcome report | test_training_budget.py; test_t143_t150_leadership.py | Paired fixed-seed committed behaviour, opportunity-normalized shares, no illegal/stalled runs; snapshots and SHA/model/config hashes; no fabricated win/screenshot-based distribution claim. |
| Q19 | P5/P6 | Extend test_t044_diplomacy.py / test_t061_movement.py: alliance_neutral_war_contact_matrix | test_t044_diplomacy.py; test_t067_military_ai.py | Allies never engage; neutral contact follows explicit policy/war rule; war relation emitted once; observed target/1.25 threshold; one construction/proposal plus per-formation budgets; active faction only. |
| Q20 | P6 | New test_polish_military_chain.py and run_polish_local_battle.gd | test_t060_combat_math.py; test_t061_movement.py; test_t062_offscreen.py; test_t063_local_battle.py; test_t064_handoffs.py | Production-generated soldiers→objectives→contact→proper Node host+RefCounted controller→lease ticks→casualties/building damage; Wait retains lease; Travel closes then off-screen; 120s bound; no ownership capture. |
| Q21 | P6 | New test_polish_hazard_chain.py: test_normal_turn_cadence_types_overflow_terminal_order | test_t069_hazards.py; test_t070_propagation.py; test_t116_modern_future.py; test_t118_pollution.py; test_t119_aliens.py; test_t120_nuclear_machines.py | Normal dispatch calls placement once when due; three initial cubes under valid setup; era reset/retained types; each propagation hex once; eighth outbreak stops; first earlier VP win suppresses old hazard draw. |
| Q22 | P6 | New test_polish_hazard_chain.py: test_selected_treatment_spends_activation_and_restores_economy | test_t071_disruption.py; test_t073_responders.py | Actual policy-selected eligible adjacent cube removed; zero strategic movement/attack same activation; no inactive/engaged/ineligible/remote treatment; pollution cleanup; exact source/cart recovery only when last blocker gone. |
| Q23 | P7 | Extend semantic/magic/duel bridge tests with production-shell commands | test_r04_semantic_magic.py; test_t065_magic.py; test_t066_buffs.py; test_t072_visits.py; test_t074_hazard_duels.py; test_u05_retained_ward_duel.py | Moving-target range checked at open+commit; no caller-observed privilege; Destroy ordinary entity only; buffs cap/freeze; successful exact-cube result once; Wait/reload no new allowance; world-resolved target no substitute cube. |
| Q24 | P7 | Extend run_ward_duel_presentation.gd with actual pointer ward and return branches | run_g04_spellbook_pointer.gd; run_g04_lease_return.gd; run_ward_duel_presentation.gd | Real board configured before startup; pointer chooses four spells/secret; no forced defeat; mid-duel resume preserves ward/history/RNG; win/draw/loss/cancel/reload result; world hidden/noninteractive, restored once. |
| Q25 | P7 | Repair current regression failures and retain inventory/puzzle/quest smoke | test_t087_inventory.py; test_t088_inventory_use.py; test_t089_puzzles.py; test_t090_sluice.py; test_t095_village_panel.py; test_boulder_quest.py | Required item single container; dropped item and mechanisms persist; existing sluice solution validates; production fixture uses same engine; no quest-content expansion. |
| Q26 | P8 | Extend era tests: first_winner_new_roster_pause_receipt | test_t097_era_planner.py; test_t100_core_upgrade.py; test_t103_continuity.py; test_t104_era_service.py | One threshold event, no later old-era work, stable core IDs/anchors, single starter grant, only new-era meters reset, seven new cards persist; four-second/skip presentation cannot repeat conversion. |
| Q27 | P8 | Extend collapse/fission/legacy tests through save and returned projection | test_t098_collapse.py; test_t099_fission.py; test_t101_legacy.py; test_t102_safeguards.py | 10/9/8/7/6/5 oracle; ties and sole winner; true minimum core pairs; last-faction protection; disband/retirement versus living Person continuity; no inert ruin collision or magical ownership; legacy factories operate. |
| Q28 | P8 | Extend cycle/history tests: three_production_replays_same_continuation | test_t125_cycles.py; test_t126_legacy.py; test_t127_full_cycle_continuity.py; test_t128_chronicle_pins.py; test_t129_path_selection.py | Future→Prehistoric reseeds factions, retires old military/research, new cycle layers/cubes; world coordinates/wizard memory/living people/items/puzzles persist; three-cycle hashes/pinned live references; no forced Utopia scope. |
| Q29 | P8 | New test_polish_continuity.py plus headed snapshot/actor comparisons | test_t014_persistence.py; test_t019_recovery.py; test_t064_handoffs.py; test_presentation_journeys.py | Before/after real quit/relaunch: Person/name, cart/cargo/journey ACK, soldier, hazard/visit, research/hand, diplomacy, era/history, meters, destroyed assets; next commands match uninterrupted control. |
| Q30 | P9 | Final golden journey replay/manifest validation and cumulative run | All tests/sim; affected Godot suites; tools/check.py; tools/run_g12_aggregate.py | Correct final SHA; replay-hash checkpoints; all required frames personally inspected; no missing/empty suites or unexpected skips; scoped invariants and owner review separate; Windows Godot launcher verified, packaging claim separate. |


Required runtime commands use the project environment, not this audit’s temporary dependency path. From the checkout root:

```powershell
# Use the repository's verified interpreter and the Godot path verified in P0.
& .\.venv\Scripts\python.exe -m pytest tests/sim -q
& .\.venv\Scripts\python.exe tools\windows_playtest.py play-latest
& .\.venv\Scripts\python.exe tools\run_visual_review.py --resolutions 450x800,1280x720,960x540
& $env:GODOT --headless --path godot_project --script res://client/tests/run_ward_duel_presentation.gd
```

`run_visual_review.py` currently captures arranged scenarios and does not implement this manifest; extending it is P0 work. Headless Godot may verify structure but **cannot substitute for headed frames**. On Linux, equivalent script invocation is valid for Linux checks; it does not certify the Windows launcher. Keep the existing `tools/check.py --gate Gxx --json-report ...` and auto-gate runners as regressions, while inspecting which suites they actually run. The P9 gate requires the full simulation suite, not only the small G11 semantic subset.

### AI/policy report contract

Use fixed checked-in inference artifacts and hashes; no retraining in this pass. Assign policies once through the authoritative initial/era setup, persist the assignment, and verify the artifact really loads. A fallback is legal only when logged with its reason; never label heuristic fallback as trained inference.

First run six smoke seeds **507–512**, 60 turns each, advancing exactly **30,000 ms of unpaused Game Time per turn** through production commands (actual time chunks/sequence recorded). After repairs, run each of heuristic/build/trade/war on the first **20 seeds of the repository’s fixed `PROMOTION_SEEDS`**, paired by seed and faction position, up to **200 turns**, or earlier real transition/catastrophe. This is a new full-world behaviour evaluation, not a replacement claim for the historical 200-seed FX-ERA promotion. Validate every seed normally; an unloadable seed is a reported failure, not silently removed. For six-faction worlds reuse `BoardBuilder`/`WorldSetupService` and the same bootstrap/services; the normal FX-MVP launcher remains two-faction unless separately designed otherwise.

Report per seed/policy: eligible opportunities, proposals versus committed outcomes, completed roads/settlements/cities, deliveries and settled trades, unit production, formation distance and objectives, treatments, battles/casualties, VP/era time, idle streak with reason, illegal/stale candidates, fallback counts, stalls/crashes, catastrophe rate and wall-time/latency. Normalize action shares by eligible opportunities; a primary-action label is insufficient. Record distributions and uncertainty, not just one representative screenshot.

Proposed behavioural gate: zero illegal committed actions, hidden-information reads, crashes or lost assignments; no unexplained **10 consecutive active seats** with a useful feasible action but no progress; distinct specialists must show at least **0.10 absolute pairwise distance** in at least one executed action-family share over sufficient opportunities, with seed-level counts alongside it. If opportunities are too few, report INCONCLUSIVE and extend bounded runs, not train to the test or manufacture conflicts. Document intentional hold/blocked states. Use the existing C14 promotion standard unchanged when claiming promotion, and do not use its success as evidence for natural FX-MVP behaviour.

## I. Golden integrated journey

**Seed 507 is a useful geographical/identity baseline, but current main cannot yet supply the complete golden journey.** It can generate the whole board, produce soldiers, move formations and expose a real manifestation. Initial drafting, hazard cadence/treatment, trade progression, command-path RNG and save continuity block full acceptance.

### Verified starting route and measurements

- FX-MVP starts at node:35, settlement:3, faction:2. Other initial cores are node:2, node:12 and node:27. Four roads and eight carts exist.
- Production Travel commands accepted the sequence **node:35 → node:30 → node:36 → node:31 → node:37**, advancing exactly four turns. Node:37 touches `hex:1,-2`, carrying active `cube:1`. The existing G11 Ward harness uses this same route. This audit did not perform pointer walking or win the duel.
- 120,000 ms of Game Time at the starting area creates 12 soldiers, four formations and linked Persons without a turn. This is measured current behaviour, not a proposed pacing target. Follow the actual updated meters after technology/bottleneck repairs.
- Current FX-ERA can commit 9→10→Historic in one Wait, but is **arranged setup**, not proof of an ordinary legal expansion route. Its draft then disappears. Keep it as a fast transition regression while creating a replay-reached alternative.

### Target golden route after repairs

| Segment | Exact approach | Evidence / stop condition |
|---|---|---|
| CP-START | Launch fresh FX-MVP 507 in g05_shell; record initial snapshot. Observe and Talk to a reachable existing worker; use shared attached card. | One Person ID, learned-name change only after valid Observe; actual input receipt. |
| CP-INDUSTRY | Stay unpaused until the chosen real factory crosses a meter; do not change meters/stock. Inspect worker and yard. | Accounted Game Time and one new Unit/Person; no strategic movement from waiting in real time. |
| CP-ROUND | Two valid Wait presses from a clean two-seat roster, with explicitly scheduled Game Time between turns. | One complete round, two picks, correct pass/activation; brief player-safe consequence when witnessed. |
| CP-CARGO / CP-EXPANSION | Replay production actions from CP-START until a faction legally dispatches supply and completes a road/settlement/city. Observe source, next road node and destination. | Full command trace and conserved cargo. If not reached within P0's bounded search, mark missing and let P3 repair the blocker. Do not give stock. |
| CP-TECH | Continue complete rounds; select a replay point with an activated card and an asset whose relevant constraint can change. | Same card instance/history and actual effect at consumer; known local explanation. |
| CP-HAZARD / CP-RESPONSE | Use a replay point with a scheduled hazard affecting a real source/road and a capable nearby formation. Observe its next faction activation. | Cube→blocked work→spent activation→one removal→economic/transit recovery. Other cubes can continue blocking; clear them only legally. |
| CP-WARD | Follow the verified strategic route if unchanged; P0 resolves live local exits/approach cells and validates them. Approach cube:1 manifestation, Observe, Challenge, set ward and finish retained duel through real input. | Explicit local grid/input trace, lease/checkpoint, chosen cube and clean return. Deterministic rival setup may stabilize QA without bypassing the production duel. |
| CP-CONTACT | Use a replay-reached frontier containing two legitimately hostile factions; arrive before contact. | Attended local battle; then repeat from checkpoint, leave legally, and verify bounded off-screen continuation separately. Outcomes need not be identical. |
| CP-SAVE | Save with representative person/cart cargo/unit/hazard/research/history present. Quit client/sidecar completely; relaunch and load. | Field-level identity/value comparison and paired frames; continue next commands without duplicate consequences. |
| CP-ERA / CP-CYCLE | Load replay-reached 9-VP checkpoint; execute the real final funded action. Optional later-era/cycle checkpoint. | First winning event, transformed core, legacy site, same Person/history; final cycle reseeds organisations correctly. |

A legal replay checkpoint must contain the originating normal seed/config, content/policy hashes, ordered accepted/rejected commands, exact clock advances, result receipts and a replay hash equal to its full save. Prohibit direct writes to VP, stocks, positions, relationship/war state, hazards, units, meters or draft hands in this route. Arranged production fixtures remain separate test cases with their arrangement declared. Generated checkpoint IDs resolve to actual entity IDs, approach grids and pointer targets in `journey_manifest.json`; no fabricated coordinates or “wait until something happens” owner instructions.

The owner’s journey is a curated selection of these checkpoints, not a requirement to wait for years of simulated history in one sitting. The integration run proves their shared production origin and persistence; loading a checkpoint for an owner review is not a new mini-game.

## J. Complete Cursor prompts

Each prompt below includes its objective, current evidence, classified gaps, implementation, non-goals, tests, exact interactive recipe, screenshot manifest, state evidence, regressions and acceptance gate. Proposed tools/test files are marked as new work. **Paste one prompt at a time.**

### P0 — Current truth, baseline and evidence harness

Copy everything in the following block.

````text
# P0 — Current truth, baseline and evidence harness

You are implementing one gated phase of the existing DuelMasterBattle project. Complete only the named phase, preserve evidence, and STOP. Do not begin the next phase, merge, publish, or claim Joe's approval. Make small reviewable changes using existing services. No quest development, finished art, model retraining, player faction-command UI, replacement Ward Duel or parallel simulation.

Read MORNING_HANDOFF.md, docs/CANONICAL_GAME_ONTOLOGY.md, docs/INTEGRATED_RUNTIME_ARCHITECTURE.md, docs/review/PLAYER_WORLD_MODEL.md, current accepted decisions, Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md and the relevant C00/C03–C13 contracts. Precedence: this brief > accepted canonical decisions > current contracts/amendments > implementation > historical docs. Report a material unresolved design conflict instead of silently changing the rule. The wizard does not order factions and has no ordinary-army combat HP. People remain persistent; a soldier is a Person linked to UnitState/CombatantState. Worker motion is illustrative. Catan cargo is physical. Exact hands, AI scores, hidden strengths and production internals stay in explicit QA mode. Reuse semantic_visuals.py, content/source/presentation/semantic_visuals.json, semantic_placeholder.gd, visual_language.gd and world_layer_presenters.gd; shapes/text only.

Verify git SHA/tree, OS and project toolchain before editing. Preserve user work and saves; use an isolated worktree/save slot if needed. Do not reset to historical main. The base rule below identifies the required accepted predecessor. A missing approval means you may inspect/prepare a concrete handoff, but cannot call the gate accepted or begin its successor. Existing Gxx AUTO_READY is not owner PASS. Use a new tracking/polish ledger, keeping historical evidence intact.

Use the real production WorldSim and g05_shell with FX-MVP seed507. The Windows entry point is Play Latest Integrated Game.bat / tools/windows_playtest.py play-latest. Resolve the repository interpreter and Godot version first; run `python -m pytest tests/sim -q` in that environment. Use tools/run_visual_review.py and existing Godot harnesses, extended in place. Every phase runs its exact tests below and affected regressions; the full Python suite is cheap enough to run at the gate. Do not mask failures, skip substantive coverage or weaken canonical assertions for green output.

For EACH screenshot row below: capture 450x800 AND 1280x720. Responsive rows also require960x540 and any additional retained sizes. Rows with suffixes require every named subframe at every required size. Load the specified full production checkpoint, verify its replay hash, then perform the recorded real input through the actual shell. CP-* names are proposed IDs, not existing files. Record fixture/seed, entity IDs, local approach cells, control identity, actual pixel coordinate per resolution, accepted command receipts and precise Game Time advances in journey_manifest.json. Use state predicates/receipts plus rendering barriers, never a fixed delay as evidence of readiness. If a normal checkpoint remains unreachable, report the blocker; an explicitly arranged production fixture can diagnose it but cannot pass normal reachability.

Save under Pack/DuelMasterBattle_Build_Pack/tracking/polish/P0/SOURCE_SHA/ with manifest, commands.jsonl, full saves, state assertions, tests/logs, iterations/, final/, and review.md. Use a clean capture directory; reject missing/blank/stale/wrong-size images, wrong scenes, timeouts and engine errors. Personally open EVERY final image at native scale. Report filename, actual dimensions, expected condition, observed condition, PASS/FAIL/MANUAL REVIEW REQUIRED, visible problems, iteration count and fix/retest references. Fix visible defects and recapture affected sequences. Image existence/exit0 is not PASS. If you cannot inspect pixels, or cannot reliably judge readability, explicitly mark MANUAL REVIEW REQUIRED and leave that visual gate unaccepted. Do not infer state, reachability or persistence from pixels alone.

Normal witnesses must originate from recorded legal production commands/clock advances, with no direct writes to stocks, VP, units, hazards, diplomacy, positions or hands. Arranged tests are separately labelled. Extend existing run_long_world/evaluation tools for full reloadable saves/replays; summary snapshots are insufficient. Bound searches and report unreachable events rather than waiting indefinitely or inventing owner coordinates. Keep QA data inaccessible to ordinary player projections, not merely hidden by a panel toggle.

At completion report: base/final SHA and tree; changed files and reasons; exact tests and counts; each screenshot review; state/replay evidence; unresolved risks/design decisions; a short owner procedure. Separate automated readiness, manual review and owner acceptance. STOP after the phase. Do not amend the next phase's scope to avoid a failure.

## Required starting commit

Start from verified current main. The audited baseline is 9c66ce00342698dc2900c9f7b03c18101221f799. Fetch/recheck main; if it moved, record the new SHA and repeat affected tracing/tests before relying on this audit. Planning has not authorized any gameplay repairs in P0.

## Objective

Make every later integration claim reproducible from the real game, and give Joe a clear baseline of what works and what is blocked.

## Current evidence

Inspect core/world.py::dispatch, core/state.py::WorldState, time/turns.py::TurnRunner, testing/fixtures.py and world/prehistoric_world.py. Read tools/run_visual_review.py, tools/run_long_world.py, tools/evaluate_mvp.py, client/tests/run_visual_review_harness.gd and G11/G12 evidence. Paths under core/time/world refer to sim/dmb; client paths are under godot_project. Audit reproduced 471 passes/15 failures. The ordinary twelve-Wait dice stream repeats [1,1]; research/draft/diplomacy disappear on save/load; no initial draft, no scheduled hazards, and treatment falls through. Historical PNGs are not current interactive acceptance.

## Defects and gaps

Actual bugs: R01–R08. Integration gaps: proposals do not form a complete physical trade chain; trained policies are not selected in normal setup. Visual clutter: G11 settlement/battle label collisions. Test gaps: service tests bypass dispatch, serializer equality misses omitted fields, visual harness checks files rather than observations. Classify all fifteen failures individually; do not treat them as harmless just because this is a baseline.

## Implementation

Make only harness/documentation changes. Extend existing capture tool with exact source/scenario/seed/checkpoint/output manifest support, fresh output directories, receipt/state readiness checks, nonzero exit on missing required captures, and an explicit per-image review report. Add full production snapshot plus replay recording to existing long-world tooling; preserve summary outputs for their current callers. Create a defect ledger with source symbol, reproduction, normal reachability and owning phase. Reproduce the included probes without adding them as alternate gameplay. Classify expected new-unit/autoformation regressions separately from archived fixture regressions. Do not restore six total unit definitions or permit duplicate formation membership to satisfy obsolete tests. Record actual Windows Godot version; reconcile the 4.4.1 historical pin versus 4.5.1 handoff without an incidental upgrade.

## Explicit non-goals

No gameplay repairs or UX redesign; classify and reproduce defects only. Harness/schema improvements are allowed. The common scope limits above also apply.

## Automated tests

Run `python -m pytest tests/sim -q`; preserve the complete baseline output. Run existing `run_g05_smoke.gd`, `run_g05_playable.gd`, `run_visual_review_harness.gd` and semantic checks through the repository launchers. Add planned `tests/sim/test_polish_capture_manifest.py` for fresh-output isolation, wrong-source metadata, missing required frame, wrong decoded dimensions and explicit unreviewed status. These tests validate the harness failure contract, not screenshot aesthetics. Baseline gameplay failures remain open with owners.

## Deterministic interactive procedure

1. Fresh FX-MVP507 in g05_shell; capture B01–B03 through real pointer input. 2. Record exact local input route corresponding to node35→30→36→31→37 and validate cube1/hex1,-2; do not teleport. 3. In a separate reproducible production run issue twelve Waits and 120000ms AdvanceGame; record dice/draft/industry/identity changes. 4. Search seed507 for planned CP-* events for at most60 turns with30000ms unpaused Game Time per turn. Record reached and blocked checkpoints; stop after the bound. 5. Capture fresh baseline at all required sizes. Freeze ready state with the existing capture mechanism and identify its pause token. Produce a machine-readable journey_manifest schema; each reachable entry must contain actual local cells, input targets, receipts and replay hash.

## Screenshot manifest

All listed resolutions and named subframes are mandatory. Filename is `<ID>_<subframe-if-any>_<width>x<height>.png`. The CSV in the pack expands these into individual filenames. A QA companion is captured in a separate explicitly privileged session; it is never presented as ordinary player UI.

| ID / phase | Resolutions / subframes | Scene / fixture | Starting state | Exact actions | Expected visible result | PASS evidence | Obvious failure signs | Authoritative state evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B01 / P0 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | Fresh seed507; node35; no old save | Launch Play Latest; wait for world-ready receipt; capture before input | Whole normal area, wizard, exits, buildings, people and controls | Correct normal scene and source revision; honest baseline defect annotations | Wrong fixture; blank scene; hidden overlays; stale PNG | Initial board19/54/72, turn0, initial identities |
| B02 / P0 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | B01 | Open map using its visible button; capture; close | Board, legend and underlying modal boundary | Baseline records actual legibility and any discovery leak; does not declare it fixed | Map is a different fixture; unreadable screenshot not recorded as defect | Player projection versus privileged world map |
| B03 / P0 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | B01; nearby existing worker | Use actual single-pointer selection, Observe and Talk; capture attached card | Selected actor and attached conversation/actions | Input receipt corresponds to selected real Person; record collisions | Direct semantic service call presented as pointer success | Person ID, observed/learned fields, interaction/range receipts |

## State evidence

Baseline SHA/toolchain/config/model hashes; full pytest log; field-level persistence probe; dice stream; roster/seats/rounds; actor IDs; initial cubes; world/clock versions; all checkpoint replay results. Keep source defects marked SOURCE until interactive reproduction. Existing 24 PNG dimensions and seven audit-inspected historical frames remain labelled historical.

## Regression checks

Run full tests/sim and the existing visual harness, semantic/ontology checks and g05 smoke. Expected baseline failures remain named open defects with phase owners. Validate the new harness fails on one deliberately missing frame and one wrong-size frame; a stale previous PNG must not satisfy it. Do not change game semantics or generate new art.

## Acceptance gate

P0 baseline can be READY WITH KNOWN GAME DEFECTS only if every baseline image is actually reviewed, every test failure is classified, toolchain/HEAD are verified and fresh capture/replay contracts work. Visual defects are recorded, not falsely passed. No CP reachability is invented. Stop and report; P1 requires Joe to request it.

END OF P0. STOP AND REPORT EVIDENCE. Do not start the next phase.
````

### P1 — Command, save and draft continuity

Copy everything in the following block.

````text
# P1 — Command, save and draft continuity

You are implementing one gated phase of the existing DuelMasterBattle project. Complete only the named phase, preserve evidence, and STOP. Do not begin the next phase, merge, publish, or claim Joe's approval. Make small reviewable changes using existing services. No quest development, finished art, model retraining, player faction-command UI, replacement Ward Duel or parallel simulation.

Read MORNING_HANDOFF.md, docs/CANONICAL_GAME_ONTOLOGY.md, docs/INTEGRATED_RUNTIME_ARCHITECTURE.md, docs/review/PLAYER_WORLD_MODEL.md, current accepted decisions, Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md and the relevant C00/C03–C13 contracts. Precedence: this brief > accepted canonical decisions > current contracts/amendments > implementation > historical docs. Report a material unresolved design conflict instead of silently changing the rule. The wizard does not order factions and has no ordinary-army combat HP. People remain persistent; a soldier is a Person linked to UnitState/CombatantState. Worker motion is illustrative. Catan cargo is physical. Exact hands, AI scores, hidden strengths and production internals stay in explicit QA mode. Reuse semantic_visuals.py, content/source/presentation/semantic_visuals.json, semantic_placeholder.gd, visual_language.gd and world_layer_presenters.gd; shapes/text only.

Verify git SHA/tree, OS and project toolchain before editing. Preserve user work and saves; use an isolated worktree/save slot if needed. Do not reset to historical main. The base rule below identifies the required accepted predecessor. A missing approval means you may inspect/prepare a concrete handoff, but cannot call the gate accepted or begin its successor. Existing Gxx AUTO_READY is not owner PASS. Use a new tracking/polish ledger, keeping historical evidence intact.

Use the real production WorldSim and g05_shell with FX-MVP seed507. The Windows entry point is Play Latest Integrated Game.bat / tools/windows_playtest.py play-latest. Resolve the repository interpreter and Godot version first; run `python -m pytest tests/sim -q` in that environment. Use tools/run_visual_review.py and existing Godot harnesses, extended in place. Every phase runs its exact tests below and affected regressions; the full Python suite is cheap enough to run at the gate. Do not mask failures, skip substantive coverage or weaken canonical assertions for green output.

For EACH screenshot row below: capture 450x800 AND 1280x720. Responsive rows also require960x540 and any additional retained sizes. Rows with suffixes require every named subframe at every required size. Load the specified full production checkpoint, verify its replay hash, then perform the recorded real input through the actual shell. CP-* names are proposed IDs, not existing files. Record fixture/seed, entity IDs, local approach cells, control identity, actual pixel coordinate per resolution, accepted command receipts and precise Game Time advances in journey_manifest.json. Use state predicates/receipts plus rendering barriers, never a fixed delay as evidence of readiness. If a normal checkpoint remains unreachable, report the blocker; an explicitly arranged production fixture can diagnose it but cannot pass normal reachability.

Save under Pack/DuelMasterBattle_Build_Pack/tracking/polish/P1/SOURCE_SHA/ with manifest, commands.jsonl, full saves, state assertions, tests/logs, iterations/, final/, and review.md. Use a clean capture directory; reject missing/blank/stale/wrong-size images, wrong scenes, timeouts and engine errors. Personally open EVERY final image at native scale. Report filename, actual dimensions, expected condition, observed condition, PASS/FAIL/MANUAL REVIEW REQUIRED, visible problems, iteration count and fix/retest references. Fix visible defects and recapture affected sequences. Image existence/exit0 is not PASS. If you cannot inspect pixels, or cannot reliably judge readability, explicitly mark MANUAL REVIEW REQUIRED and leave that visual gate unaccepted. Do not infer state, reachability or persistence from pixels alone.

Normal witnesses must originate from recorded legal production commands/clock advances, with no direct writes to stocks, VP, units, hazards, diplomacy, positions or hands. Arranged tests are separately labelled. Extend existing run_long_world/evaluation tools for full reloadable saves/replays; summary snapshots are insufficient. Bound searches and report unreachable events rather than waiting indefinitely or inventing owner coordinates. Keep QA data inaccessible to ordinary player projections, not merely hidden by a panel toggle.

At completion report: base/final SHA and tree; changed files and reasons; exact tests and counts; each screenshot review; state/replay evidence; unresolved risks/design decisions; a short owner procedure. Separate automated readiness, manual review and owner acceptance. STOP after the phase. Do not amend the next phase's scope to avoid a failure.

## Required starting commit

Start at the exact P0 final SHA recorded in its accepted handoff. Verify P0 baseline/reproduction artifacts; do not use an unverified historical G12 gate.

## Objective

A real Travel/Wait advances the intended simulation once, and saving preserves the world the wizard inhabited.

## Current evidence

sim/dmb/core/world.py::dispatch overwrites state.rng from a cached bank; sim/dmb/core/state.py serializers omit research/tech_draft/diplomacy; persistence/coordinator.py uses those snapshots. world/prehistoric_world.py does not deal initial hands. time/turns.py interrupt cleanup discards the new hands created by eras/service.py. Existing completion ordering puts active first then sorts IDs, which is not cyclic order for three factions.

## Defects and gaps

Actual bugs: repeated command-path RNG, incomplete save/rollback, empty initial draft and loss of new-era hands. Integration gap: turn stages do not match the full contract. This phase repairs boundary/order/lifecycle infrastructure; P6 owns currently absent forces/hazard stage integrations. Test gap: missing direct-vs-command parity and independent durable-field oracle.

## Implementation

Establish one authoritative RNG ownership/synchronization path across dispatch, transactions, reload and domain services; avoid reseeding or changing the algorithm to hide repeated draws. Serialize every durable field with schema-aware defaults/migration for prior saves; enumerate them independently in tests. Repair snapshot/rollback completeness. Deal exactly seven per initial faction after valid roster setup. Discard old-era hands before conversion or by old-generation identity, never discard newly committed hands. Resolve round choices exactly once after completed captured roster; retain singleton/removed-seat rules. Make completion order truly cyclic from the active faction, and run immediate first-10VP/zero-active recovery barriers. Preserve command idempotency and distinguish rejected inputs from committed world effects.

## Explicit non-goals

No economy/policy redesign, broad HUD work, or premature P6 hazard/combat wiring. The common scope limits above also apply.

## Automated tests

| ID | Phase | Exact planned test / oracle | Existing coverage to extend | Required authoritative evidence |
| --- | --- | --- | --- | --- |
| Q01 | P1 | New test_polish_command_boundary.py: test_dispatch_rng_continues_like_direct_runner; test_retransmit_and_rejected_travel_do_not_draw | test_t010_rng_replay.py; test_t011_commands.py; test_t020_playable.py | Same seeded 12-command dice stream across dispatch/control/reload; each turn reaching production exactly two Catan die draws (zero after an earlier interrupt); stable receipts and zero extra mutation on retries. |
| Q02 | P1 | New test_polish_command_boundary.py: test_all_durable_fields_survive_save_load_and_rollback | test_t009_state.py; test_t014_persistence.py; test_t018_leases.py; test_t019_recovery.py | Independently populated research, hands, diplomacy, people, units, carts/cargo, meters, hazards, items, visits/history, policies, RNG and receipts; compare fields before/after real coordinator and failed transaction. |
| Q03 | P1 | Extend test_t046_seat_round.py: test_cyclic_completion_order_and_first_win_interrupt; test_recovery_precedes_active_seat | test_t013_turns.py; test_t032_orders.py; test_t046_seat_round.py | A/B/C cyclic order from B is B,C,A; dissolved seats skip; first 10-VP receipt prevents old-era force/hazard/draft work; zero-active recovery before seat selection. |
| Q04 | P1/P5 | Extend test_t041_draft.py: test_normal_boot_deals_once; test_transition_keeps_new_era_hands | test_t041_draft.py; test_t104_era_service.py | FX-MVP starts seven/faction; exactly one pick per complete round; old hands discarded once, new seven active after FX-ERA Wait and reload. |

Extend existing tests at the listed paths under tests/sim; names labelled new are planned additions, not existing green tests. Godot test scripts belong under godot_project/client/tests. Run the exact affected files plus the full `python -m pytest tests/sim -q` gate.

## Deterministic interactive procedure

Fresh FX-MVP507: capture T01, press/release Wait twice, capture T02. Separately replay twelve Waits via dispatch, direct runner control and a save/reload branch; compare all draws/receipts. Arrange nonempty research/diplomacy only for the labelled persistence test, save via production coordinator, quit/relaunch and capture T03. Launch existing FX-ERA507, Wait once from9VP; assert Historic has active new hands. Add three-faction cyclic completion test using production setup. Exercise rejected Travel and retransmitted command IDs without advancing clock.

## Screenshot manifest

All listed resolutions and named subframes are mandatory. Filename is `<ID>_<subframe-if-any>_<width>x<height>.png`. The CSV in the pack expands these into individual filenames. A QA companion is captured in a separate explicitly privileged session; it is never presented as ordinary player UI.

| ID / phase | Resolutions / subframes | Scene / fixture | Starting state | Exact actions | Expected visible result | PASS evidence | Obvious failure signs | Authoritative state evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T01 / P1 | 450×800; 1280×720; subframes: normal, qa_hands | FX-MVP / g05_shell | Fresh seed507 after command/state repairs | Capture before first Wait; open QA technology view in a separate capture session | Normal starting world; QA companion shows seven-card hands | One initial deal; normal view has no hand-management panel | Empty draft; duplicate deal; hands in ordinary view | RNG counter, initial roster and exact hand instance IDs |
| T02 / P1 | 450×800; 1280×720 | FX-MVP / g05_shell | T01 normal view | Press/release Wait twice with acknowledged receipts; capture | Same place, clear turn change; permitted local consequences | Exactly two turns/one round; same actor identities | Double turn; vanished actors; repeated constant RNG stream | Q01/Q04 dice sequence and two acquired cards; no pixel-only claim |
| T03 / P1 | 450×800; 1280×720; 960×540; subframes: person, qa_durable | FX-MVP / g05_shell | CP-SAVE-P1 arranged production save with nonempty research/diplomacy | Save through coordinator; quit; relaunch/load; capture same selected actor | Same person/world; QA companion retains draft/relation | No visible reset; full durable comparison succeeds | Lost name, hands, war relation or cargo; fresh game loaded | Q02 before/after independently enumerated fields |

## State evidence

Q01–Q04 exact receipts, RNG streams/draw counts, independently listed saved fields, failure rollback, initial/new-era hand identities, pre/post era IDs, complete stage trace and winner barrier. Fixes must improve next-command continuation as well as immediate equality.

## Regression checks

All core command, clock, lease, persistence, RNG, era and draft tests; full tests/sim. Do not allow existing failures unrelated to P1 to disappear from the ledger. Preserve accepted local walking/WorldTurn semantics and full Ward state. Existing checkpoint hashes may change legitimately; regenerate from legal actions and record why.

## Acceptance gate

All P1 planned tests pass through production dispatch/coordinator, not only services. No lost durable field or duplicate draw/pick/transition. Current and legacy-save behavior documented. All T frames reviewed; unresolved unreadability remains assigned to P2 with baseline evidence, while P1 continuity criteria pass. Stop.

END OF P1. STOP AND REPORT EVIDENCE. Do not start the next phase.
````

### P2 — Readable wizard view and meaningful events

Copy everything in the following block.

````text
# P2 — Readable wizard view and meaningful events

You are implementing one gated phase of the existing DuelMasterBattle project. Complete only the named phase, preserve evidence, and STOP. Do not begin the next phase, merge, publish, or claim Joe's approval. Make small reviewable changes using existing services. No quest development, finished art, model retraining, player faction-command UI, replacement Ward Duel or parallel simulation.

Read MORNING_HANDOFF.md, docs/CANONICAL_GAME_ONTOLOGY.md, docs/INTEGRATED_RUNTIME_ARCHITECTURE.md, docs/review/PLAYER_WORLD_MODEL.md, current accepted decisions, Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md and the relevant C00/C03–C13 contracts. Precedence: this brief > accepted canonical decisions > current contracts/amendments > implementation > historical docs. Report a material unresolved design conflict instead of silently changing the rule. The wizard does not order factions and has no ordinary-army combat HP. People remain persistent; a soldier is a Person linked to UnitState/CombatantState. Worker motion is illustrative. Catan cargo is physical. Exact hands, AI scores, hidden strengths and production internals stay in explicit QA mode. Reuse semantic_visuals.py, content/source/presentation/semantic_visuals.json, semantic_placeholder.gd, visual_language.gd and world_layer_presenters.gd; shapes/text only.

Verify git SHA/tree, OS and project toolchain before editing. Preserve user work and saves; use an isolated worktree/save slot if needed. Do not reset to historical main. The base rule below identifies the required accepted predecessor. A missing approval means you may inspect/prepare a concrete handoff, but cannot call the gate accepted or begin its successor. Existing Gxx AUTO_READY is not owner PASS. Use a new tracking/polish ledger, keeping historical evidence intact.

Use the real production WorldSim and g05_shell with FX-MVP seed507. The Windows entry point is Play Latest Integrated Game.bat / tools/windows_playtest.py play-latest. Resolve the repository interpreter and Godot version first; run `python -m pytest tests/sim -q` in that environment. Use tools/run_visual_review.py and existing Godot harnesses, extended in place. Every phase runs its exact tests below and affected regressions; the full Python suite is cheap enough to run at the gate. Do not mask failures, skip substantive coverage or weaken canonical assertions for green output.

For EACH screenshot row below: capture 450x800 AND 1280x720. Responsive rows also require960x540 and any additional retained sizes. Rows with suffixes require every named subframe at every required size. Load the specified full production checkpoint, verify its replay hash, then perform the recorded real input through the actual shell. CP-* names are proposed IDs, not existing files. Record fixture/seed, entity IDs, local approach cells, control identity, actual pixel coordinate per resolution, accepted command receipts and precise Game Time advances in journey_manifest.json. Use state predicates/receipts plus rendering barriers, never a fixed delay as evidence of readiness. If a normal checkpoint remains unreachable, report the blocker; an explicitly arranged production fixture can diagnose it but cannot pass normal reachability.

Save under Pack/DuelMasterBattle_Build_Pack/tracking/polish/P2/SOURCE_SHA/ with manifest, commands.jsonl, full saves, state assertions, tests/logs, iterations/, final/, and review.md. Use a clean capture directory; reject missing/blank/stale/wrong-size images, wrong scenes, timeouts and engine errors. Personally open EVERY final image at native scale. Report filename, actual dimensions, expected condition, observed condition, PASS/FAIL/MANUAL REVIEW REQUIRED, visible problems, iteration count and fix/retest references. Fix visible defects and recapture affected sequences. Image existence/exit0 is not PASS. If you cannot inspect pixels, or cannot reliably judge readability, explicitly mark MANUAL REVIEW REQUIRED and leave that visual gate unaccepted. Do not infer state, reachability or persistence from pixels alone.

Normal witnesses must originate from recorded legal production commands/clock advances, with no direct writes to stocks, VP, units, hazards, diplomacy, positions or hands. Arranged tests are separately labelled. Extend existing run_long_world/evaluation tools for full reloadable saves/replays; summary snapshots are insufficient. Bound searches and report unreachable events rather than waiting indefinitely or inventing owner coordinates. Keep QA data inaccessible to ordinary player projections, not merely hidden by a panel toggle.

At completion report: base/final SHA and tree; changed files and reasons; exact tests and counts; each screenshot review; state/replay evidence; unresolved risks/design decisions; a short owner procedure. Separate automated readiness, manual review and owner acceptance. STOP after the phase. Do not amend the next phase's scope to avoid a failure.

## Required starting commit

Start at accepted P1 final SHA. Preserve the repaired state and command invariants.

## Objective

Joe can identify places, actors, exits and meaningful local changes without a faction-management HUD.

## Current evidence

Reuse sim/dmb/presentation/semantic_visuals.py, godot_project/content/source/presentation/semantic_visuals.json and client/world/{semantic_placeholder,visual_language,world_layer_presenters}.gd. Inspect g05_shell.gd, shared bridge interaction presenter, ui/semantic_labels.gd, ui/world_map_panel.gd, sim/dmb/world/world_map.py and WorldState.player_view. G11 pictures show label collisions and a tiny map legend; player_view can expose privileged extras and map reveal_all=False is not discovery filtering.

## Defects and gaps

Visual clutter: simultaneous labels, unsafe pad/header overlap, weak selected state, tiny legends. Poor feedback: no coherent cause/outcome hierarchy. Actual information-boundary defect: unseen current world/AI state can enter normal projections. Test gap: geometry checks alone do not establish readable pixels or single-pointer input.

## Implementation

Preserve the existing shape vocabulary: people circles, carts distinct cargo-bearing rectangles, archetype triangle/square/hex, typed hazards diamond/state treatment, civic double-border city, scaffold before complete structure. Verify actual registry mappings before changing one. Use colour plus stable faction pattern including successors. Limit full labels to selected/nearby objects; keep pad/header/menu protected regions; make essential targets at least48 logical pixels. Provide contextual plain-language Inspect, selection and blocked-action feedback. Fix discovery/knowledge filtering at the projection boundary; explicit QA scope for hands/plans/scores/hidden enemy details. Add committed causal-event records/presentation through existing history/semantic owners, with stable IDs and visibility provenance. Ambient cues show carts/work; noticeable cues show nearby completion/blockage/first technology consequence; important cues show known war/battle/destruction; critical one-shot transition pauses remain dominant. At most one important banner and two short notices visible; coalesce repeated causes per turn, dedupe across reload. Wire only real existing outcomes; P3–P8 add missing domain producers. Never emit a success notice from an intent.

## Explicit non-goals

No invented gameplay success, omniscient map, exact enemy strengths, card management, or art assets. The common scope limits above also apply.

## Automated tests

| ID | Phase | Exact planned test / oracle | Existing coverage to extend | Required authoritative evidence |
| --- | --- | --- | --- | --- |
| Q05 | P2/P7 | New run_polish_input_pause.gd plus Python clock regression | test_t012_clock.py; test_t022_clock_driver.py; run_g05_playable.gd | One Wait per press incl held/repeated input; invalid Travel no turn/RNG; independent modal/focus/duel pause tokens; 60 paused seconds no world quanta/buff expiry/catch-up. |
| Q06 | P2 | New test_polish_player_evidence.py: test_player_view_excludes_privileged_fields; test_known_map_ages_and_events_dedupe | test_t021_semantic.py; test_t079_semantic_coverage.py; test_t105_chronicle.py; test_world_map_geometry.py | Unknown enemy changes cannot alter player payload; own/known facts only; debug request explicit; same event ID once across refresh/reload; no raw internal identifiers rendered. |
| Q07 | P2/P4 | Extend existing Godot visual harness: assert_layout_and_actor_registry | test_semantic_visuals.py; run_fx_era_layout_capture.gd; run_mira_semantic_label.gd | All essential hit areas ≥48 logical px, on-screen and disjoint from protected controls; one actor per entity/Person; images inspected for clipping, not only rectangles. |

Extend existing tests at the listed paths under tests/sim; names labelled new are planned additions, not existing green tests. Godot test scripts belong under godot_project/client/tests. Run the exact affected files plus the full `python -m pytest tests/sim -q` gate.

## Deterministic interactive procedure

Repeat P0 real-input baseline at450x800,1280x720,960x540. Capture U01–U04. Use a legally reached busy checkpoint; additionally label FX-WORLD-LAYERS as arrangement for layout stress. Select worker/cart/soldier/hazard individually. Open/close map, inventory, grimoire with pointer only. Mutate an unseen enemy in a separate QA branch and prove normal payload does not change. Hold Wait, release, repeat; invalid Travel; pause by overlapping modal/focus tokens for60000ms; resume with no accumulated catch-up.

## Screenshot manifest

All listed resolutions and named subframes are mandatory. Filename is `<ID>_<subframe-if-any>_<width>x<height>.png`. The CSV in the pack expands these into individual filenames. A QA companion is captured in a separate explicitly privileged session; it is never presented as ordinary player UI.

| ID / phase | Resolutions / subframes | Scene / fixture | Starting state | Exact actions | Expected visible result | PASS evidence | Obvious failure signs | Authoritative state evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U01 / P2 | 450×800; 1280×720; 960×540; subframes: world, selected_card | FX-MVP / g05_shell | Fresh507 and B03 interaction state | Repeat B01/B03 inputs after layout changes | Readable selected card; bounded labels; all essential controls visible | No overlaps with pad/header; ≥48px essential hit areas; readable native-size text | Tiny/stacked labels; clipped action; covered exit | Widget bounds, hit test and selection entity |
| U02 / P2 | 450×800; 1280×720; 960×540; subframes: worker, cart, soldier, hazard | FX-MVP / g05_shell | CP-DENSE from production play; diagnostic FX-WORLD-LAYERS separately | Select worker, cart, soldier and hazard in four successive captures using suffixes a–d | Each selected category distinct; one full attached card at a time | Silhouette, faction pattern and selected state understood without raw IDs | Cart resembles person; selected identity ambiguous; stack of cards | Actor IDs/types, same registry source, protected-control bounds |
| U03 / P2 | 450×800; 1280×720; 960×540; subframes: visited, unseen | FX-MVP / g05_shell | CP-KNOWN-MAP; one visited and one unseen changed place | Open map; select visited then unseen place in suffixes a/b | Known/remembered facts, readable legend; unseen updates concealed | Player payload and pixels respect knowledge/time of visit | Live hidden hazards/ownership/strength or technical IDs shown | Q06 knowledge projection and unobserved mutation counterfactual |
| U04 / P2 | 450×800; 1280×720; 960×540; subframes: inventory, grimoire, restored | FX-MVP / g05_shell | U01 | Open inventory then close; open grimoire then close; lose/regain focus; capture each modal with suffixes a/b | Readable paused screens and restored world controls | No clicks pass through; modal close restores exactly one world view | Hidden world interaction; modal under labels; catch-up on resume | Pause-token set, game clock and hit-test receipts |

## State evidence

Selection and actor IDs; player payload allowlist; knowledge provenance/timestamps; event causal IDs, source receipts and visibility; control/hit-test bounds; pause clocks and token ownership; before/after actor sets. Normal UI must never request chronicle_debug or privileged extras to compose ordinary text.

## Regression checks

Observe/Talk/attached-card semantics; existing knowledge/name memory; boulder progression only as regression; retained Ward mode isolation; P1 command/draft/save tests; existing narrow/landscape checks. No global current-stock tables or army/build/worker/draft controls.

## Acceptance gate

No clipped essential control, label collision in protected areas, duplicate selected card or privileged ordinary payload at required sizes. Every U frame inspected. Event dedupe and click/pause tests pass. Subjective shape comprehension marked MANUAL REVIEW REQUIRED if uncertain. Stop.

END OF P2. STOP AND REPORT EVIDENCE. Do not start the next phase.
````

### P3 — Physical economy, bilateral trade and construction

Copy everything in the following block.

````text
# P3 — Physical economy, bilateral trade and construction

You are implementing one gated phase of the existing DuelMasterBattle project. Complete only the named phase, preserve evidence, and STOP. Do not begin the next phase, merge, publish, or claim Joe's approval. Make small reviewable changes using existing services. No quest development, finished art, model retraining, player faction-command UI, replacement Ward Duel or parallel simulation.

Read MORNING_HANDOFF.md, docs/CANONICAL_GAME_ONTOLOGY.md, docs/INTEGRATED_RUNTIME_ARCHITECTURE.md, docs/review/PLAYER_WORLD_MODEL.md, current accepted decisions, Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md and the relevant C00/C03–C13 contracts. Precedence: this brief > accepted canonical decisions > current contracts/amendments > implementation > historical docs. Report a material unresolved design conflict instead of silently changing the rule. The wizard does not order factions and has no ordinary-army combat HP. People remain persistent; a soldier is a Person linked to UnitState/CombatantState. Worker motion is illustrative. Catan cargo is physical. Exact hands, AI scores, hidden strengths and production internals stay in explicit QA mode. Reuse semantic_visuals.py, content/source/presentation/semantic_visuals.json, semantic_placeholder.gd, visual_language.gd and world_layer_presenters.gd; shapes/text only.

Verify git SHA/tree, OS and project toolchain before editing. Preserve user work and saves; use an isolated worktree/save slot if needed. Do not reset to historical main. The base rule below identifies the required accepted predecessor. A missing approval means you may inspect/prepare a concrete handoff, but cannot call the gate accepted or begin its successor. Existing Gxx AUTO_READY is not owner PASS. Use a new tracking/polish ledger, keeping historical evidence intact.

Use the real production WorldSim and g05_shell with FX-MVP seed507. The Windows entry point is Play Latest Integrated Game.bat / tools/windows_playtest.py play-latest. Resolve the repository interpreter and Godot version first; run `python -m pytest tests/sim -q` in that environment. Use tools/run_visual_review.py and existing Godot harnesses, extended in place. Every phase runs its exact tests below and affected regressions; the full Python suite is cheap enough to run at the gate. Do not mask failures, skip substantive coverage or weaken canonical assertions for green output.

For EACH screenshot row below: capture 450x800 AND 1280x720. Responsive rows also require960x540 and any additional retained sizes. Rows with suffixes require every named subframe at every required size. Load the specified full production checkpoint, verify its replay hash, then perform the recorded real input through the actual shell. CP-* names are proposed IDs, not existing files. Record fixture/seed, entity IDs, local approach cells, control identity, actual pixel coordinate per resolution, accepted command receipts and precise Game Time advances in journey_manifest.json. Use state predicates/receipts plus rendering barriers, never a fixed delay as evidence of readiness. If a normal checkpoint remains unreachable, report the blocker; an explicitly arranged production fixture can diagnose it but cannot pass normal reachability.

Save under Pack/DuelMasterBattle_Build_Pack/tracking/polish/P3/SOURCE_SHA/ with manifest, commands.jsonl, full saves, state assertions, tests/logs, iterations/, final/, and review.md. Use a clean capture directory; reject missing/blank/stale/wrong-size images, wrong scenes, timeouts and engine errors. Personally open EVERY final image at native scale. Report filename, actual dimensions, expected condition, observed condition, PASS/FAIL/MANUAL REVIEW REQUIRED, visible problems, iteration count and fix/retest references. Fix visible defects and recapture affected sequences. Image existence/exit0 is not PASS. If you cannot inspect pixels, or cannot reliably judge readability, explicitly mark MANUAL REVIEW REQUIRED and leave that visual gate unaccepted. Do not infer state, reachability or persistence from pixels alone.

Normal witnesses must originate from recorded legal production commands/clock advances, with no direct writes to stocks, VP, units, hazards, diplomacy, positions or hands. Arranged tests are separately labelled. Extend existing run_long_world/evaluation tools for full reloadable saves/replays; summary snapshots are insufficient. Bound searches and report unreachable events rather than waiting indefinitely or inventing owner coordinates. Keep QA data inaccessible to ordinary player projections, not merely hidden by a panel toggle.

At completion report: base/final SHA and tree; changed files and reasons; exact tests and counts; each screenshot review; state/replay evidence; unresolved risks/design decisions; a short owner procedure. Separate automated readiness, manual review and owner acceptance. STOP after the phase. Do not amend the next phase's scope to avoid a failure.

## Required starting commit

Start at accepted P2 final SHA; use its knowledge and event contracts.

## Objective

Visible carts explain how autonomous faction plans become actual roads, settlements, cities and exchanges.

## Current evidence

sim/dmb/logistics/{stock,carts,routes,director,trade}.py; sim/dmb/construction/{orders,scoring,production}.py; sim/dmb/world/setup.py and existing tests t029–t037/t045. sim/dmb/ai/policy.py currently proposes trades without normal acceptance/settlement orchestration. TradeService.dispatch creates free carts and lacks a physical route; deadline estimates are hardcoded. Director can load before an assignment rejection; CartService.load does not establish source co-location. Normal probe showed eight idle carts and24 proposed trades with no expansion.

## Defects and gaps

Integration gap: proposals→acceptance→physical dispatch→escrow→settlement. Actual conservation risks: remote load, free carts, failed routing after reservation/load. Poor feedback: stock/cargo/site consequence is not a visible sequence. Test gap: arranged delivered orders alone do not prove normal policy completion.

## Implementation

Connect legal normal policy decisions to validated production services. Compute needs/routes from actual available stock and accepted knowledge. Require an existing or legitimately purchased cart to physically reach each source before loading; validate both legs before committing, rollback on assignment failure, split across capacity and multiple sources safely. Do not directly wire unsafe dormant TradeService.dispatch. Make trade mutually accepted with real route distances/deadlines, first-leg nonspendable escrow, both-leg release exactly once, default/return/destruction rules. Reuse one-edge-per-turn cart progression and journey ACK presentation. Keep construction reservations, delivery, cost consumption, cancellation and destruction conserved; revalidate legal ownership/adjacency at completion. Reuse building/road semantic presenters and P2 events for departure, blocked state, arrival and completion. No teleporting Catan goods. Preserve industry accounting abstraction; do not invent physical industrial supply carts.

## Explicit non-goals

No industrial physical-cargo redesign, free stock/carts, faction build buttons or new trade currencies. The common scope limits above also apply.

## Automated tests

| ID | Phase | Exact planned test / oracle | Existing coverage to extend | Required authoritative evidence |
| --- | --- | --- | --- | --- |
| Q08 | P3 | New test_polish_economy_chain.py: test_cart_source_co_location_and_exactly_once_delivery; test_blocked_resume | test_t030_stock.py; test_t033_carts.py; test_t034_routes.py; test_t035_director.py; test_presentation_journeys.py | Existing cart physically visits source before loading; conserved lots through one-edge turns; blocked cargo retained; resume/delivery/replay/ACK at most once. |
| Q09 | P3 | New test_polish_economy_chain.py: test_bilateral_trade_normal_policy_to_settlement | test_t044_diplomacy.py; test_t045_trade.py | Legal shortage/routes; mutual acceptance; existing or paid replacement carts; split loads; first-leg escrow not spendable; both legs release once; real-distance deadline/default/return, no gifts. |
| Q10 | P3 | New test_polish_economy_chain.py: test_delivered_frontier_road_settlement_city_chain | test_t031_placement_score.py; test_t032_orders.py; test_t036_setup.py; test_t037_destruction.py | Exact location of timber/brick/wool/grain/ore; no completion with missing cost; ownership/adjacency revalidation; unit-cost consumption once; VP 1/2/legacy0; cancelled/ruined orders conserved. |
| Q11 | P3/P6 | Extend test_t029_catan_grants.py through dispatch and ledger | test_t029_catan_grants.py; test_t071_disruption.py | Roll7/desert/no-warehouse cases; shared matching hex; hazard vs industrial depletion distinction; same controlled roll before/after removal grants correct good without changing natural RNG. |

Extend existing tests at the listed paths under tests/sim; names labelled new are planned additions, not existing green tests. Godot test scripts belong under godot_project/client/tests. Run the exact affected files plus the full `python -m pytest tests/sim -q` gate.

## Deterministic interactive procedure

Generate CP-CARGO/EXPANSION/CITY/TRADE/BLOCKED-CART with production commands from FX-MVP507. Search bound initially200 turns at30000ms GameTime/turn; if unreachable inspect and repair the actual decision/route bottleneck, then rerun from start. Capture E01–E11 sequences using manifest local inputs. Paired shots must retain same cart/order lineage. For blocked/resume use a legally spawned hazard or legal destruction in normal witness; use a declared fixture for edge-case default tests. Before final delivery verify missing-one-good order cannot complete. Rerun after save/reload during transit.

## Screenshot manifest

All listed resolutions and named subframes are mandatory. Filename is `<ID>_<subframe-if-any>_<width>x<height>.png`. The CSV in the pack expands these into individual filenames. A QA companion is captured in a separate explicitly privileged session; it is never presented as ordinary player UI.

| ID / phase | Resolutions / subframes | Scene / fixture | Starting state | Exact actions | Expected visible result | PASS evidence | Obvious failure signs | Authoritative state evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E01 / P3 | 450×800; 1280×720; subframes: source, target | FX-MVP / g05_shell | CP-CARGO before load; original source and destination identified | Inspect source warehouse and under-construction target in suffixes a/b | Actual stocked warehouse and visible site needing goods | Local explanation names goods/purpose without global stock tables | Instant free completion or omniscient warehouse table | Stock/reservation/order IDs and legal-policy decision |
| E02 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-CARGO after actual co-located loading, before next edge | Select loaded cart and capture | Distinct cart with cargo cue and contextual destination | Goods visibly associated with this cart; no worker/duplicate cart confusion | Empty-looking load; cargo removed from remote warehouse | Source decrease equals actual cart cargo lots; current node = source |
| E03 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | E02 | Press Wait once; capture acknowledged departure/next-node entry at journey barrier | Same cart leaving via correct exit/road | One-edge move; one exit presentation for same journey | Teleport beyond route; duplicate entrance; two carts same ID | Journey ID, previous/current node, one movement receipt |
| E04 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-CARGO one edge before destination; wizard at destination via replay | Press Wait once; capture arrival before completion consequence | Same cargo-bearing cart reaches destination | Identity retained and arrival presented once | Cargo changes category; cart appears before authoritative arrival | Cart/destination co-location; delivery receipt and container transfer |
| E05 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | E04 | Advance only receipt-completion frame; inspect completed structure | Scaffold changes into road/building; concise local completion cue | Visual completion agrees with fully delivered/consumed cost | Finished site while missing goods; duplicate notice or refund | Order complete once; ledger conservation, owner and VP |
| E06 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-BLOCKED-CART; legal hazard/road break ahead | Press Wait once; Inspect stalled cart | Cart stopped with local reason and cargo still shown | Blockage location/cause is understandable | Cart moves through block; invisible cargo loss; technical route ID | Blocked edge, unchanged cargo, no arrival receipt |
| E07 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | E06 with obstruction legally removed in replay | Press Wait; capture next movement/arrival | Previously stopped cart resumes | Same cart/cargo continues; reason no longer falsely blocked | New cart minted; goods doubled; stale blocked badge | Same journey lineage and conserved goods |
| E08 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-TRADE with legal bilateral acceptance and first leg arriving | Inspect receiving cart/warehouse after one acknowledged delivery | Arrival activity; no false claim full trade finished | Player sees delivery; reserved exchange stays unavailable to construction | One leg presented as settled; free replacement cart | Both contracts, first-leg escrow, available stock unchanged |
| E09 / P3 | 450×800; 1280×720 | FX-MVP / g05_shell | Same trade before second arrival | Press bounded replayed Wait sequence from manifest; inspect receiver | Second arrival and one locally known trade-complete cue | Both legs settled exactly once, with physical origin | Repeated payment; unilateral gift; unlimited free carts | Trade receipt, both escrow transfers, conserved totals and deadline |
| E10 / P3 | 450×800; 1280×720; subframes: road_before, road_after, settlement_before, settlement_after | FX-MVP / g05_shell | CP-EXPANSION before frontier road/settlement complete | Inspect proposed site; capture after delivery in suffixes a/b | Road/site progresses from work to completed frontier | Changed connectivity/ownership is visibly grounded in construction | Ownership appears without work/cost | Legal placement, road endpoints, delivered order/owner/VP |
| E11 / P3 | 450×800; 1280×720; subframes: settlement, city | FX-MVP / g05_shell | CP-CITY before funded upgrade | Capture settlement; execute manifest final Wait; capture city as suffixes a/b | Same civic footprint gains double-border city state | Readable upgrade with same identity and one notice | Extra city actor; footprint jumps; wrong faction | Same building ID; exact cost; VP1→2; flow modifier |

## State evidence

Initial/current stock+reservations+cargo+escrow+consumed/lost ledger per good; source/cart co-location; route edge per turn; available fleet and paid replacement receipts; bilateral trade IDs/deadlines; order validity/cost/owner/VP. Report proposals separately from accepted dispatches and completed outcomes.

## Regression checks

Catan five goods, roll7/desert/hazard suppression; warehouse storage and capacity; placement/distance rules; roads/buildings/destruction; save/reload and arrival ACK; P1/P2. Archived quest fixtures remain regressions only.

## Acceptance gate

Normal replay proves loaded cart→journey→arrival→completion, bilateral settled exchange and road/settlement/city results. Zero unexplained goods creation/loss, remote loads, free carts or duplicate receipts. Every E subframe reviewed at both sizes. Unreachable normal chain blocks acceptance even if arranged unit tests pass. Stop.

END OF P3. STOP AND REPORT EVIDENCE. Do not start the next phase.
````

### P4 — Industry, persistent people and manufactured soldiers

Copy everything in the following block.

````text
# P4 — Industry, persistent people and manufactured soldiers

You are implementing one gated phase of the existing DuelMasterBattle project. Complete only the named phase, preserve evidence, and STOP. Do not begin the next phase, merge, publish, or claim Joe's approval. Make small reviewable changes using existing services. No quest development, finished art, model retraining, player faction-command UI, replacement Ward Duel or parallel simulation.

Read MORNING_HANDOFF.md, docs/CANONICAL_GAME_ONTOLOGY.md, docs/INTEGRATED_RUNTIME_ARCHITECTURE.md, docs/review/PLAYER_WORLD_MODEL.md, current accepted decisions, Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md and the relevant C00/C03–C13 contracts. Precedence: this brief > accepted canonical decisions > current contracts/amendments > implementation > historical docs. Report a material unresolved design conflict instead of silently changing the rule. The wizard does not order factions and has no ordinary-army combat HP. People remain persistent; a soldier is a Person linked to UnitState/CombatantState. Worker motion is illustrative. Catan cargo is physical. Exact hands, AI scores, hidden strengths and production internals stay in explicit QA mode. Reuse semantic_visuals.py, content/source/presentation/semantic_visuals.json, semantic_placeholder.gd, visual_language.gd and world_layer_presenters.gd; shapes/text only.

Verify git SHA/tree, OS and project toolchain before editing. Preserve user work and saves; use an isolated worktree/save slot if needed. Do not reset to historical main. The base rule below identifies the required accepted predecessor. A missing approval means you may inspect/prepare a concrete handoff, but cannot call the gate accepted or begin its successor. Existing Gxx AUTO_READY is not owner PASS. Use a new tracking/polish ledger, keeping historical evidence intact.

Use the real production WorldSim and g05_shell with FX-MVP seed507. The Windows entry point is Play Latest Integrated Game.bat / tools/windows_playtest.py play-latest. Resolve the repository interpreter and Godot version first; run `python -m pytest tests/sim -q` in that environment. Use tools/run_visual_review.py and existing Godot harnesses, extended in place. Every phase runs its exact tests below and affected regressions; the full Python suite is cheap enough to run at the gate. Do not mask failures, skip substantive coverage or weaken canonical assertions for green output.

For EACH screenshot row below: capture 450x800 AND 1280x720. Responsive rows also require960x540 and any additional retained sizes. Rows with suffixes require every named subframe at every required size. Load the specified full production checkpoint, verify its replay hash, then perform the recorded real input through the actual shell. CP-* names are proposed IDs, not existing files. Record fixture/seed, entity IDs, local approach cells, control identity, actual pixel coordinate per resolution, accepted command receipts and precise Game Time advances in journey_manifest.json. Use state predicates/receipts plus rendering barriers, never a fixed delay as evidence of readiness. If a normal checkpoint remains unreachable, report the blocker; an explicitly arranged production fixture can diagnose it but cannot pass normal reachability.

Save under Pack/DuelMasterBattle_Build_Pack/tracking/polish/P4/SOURCE_SHA/ with manifest, commands.jsonl, full saves, state assertions, tests/logs, iterations/, final/, and review.md. Use a clean capture directory; reject missing/blank/stale/wrong-size images, wrong scenes, timeouts and engine errors. Personally open EVERY final image at native scale. Report filename, actual dimensions, expected condition, observed condition, PASS/FAIL/MANUAL REVIEW REQUIRED, visible problems, iteration count and fix/retest references. Fix visible defects and recapture affected sequences. Image existence/exit0 is not PASS. If you cannot inspect pixels, or cannot reliably judge readability, explicitly mark MANUAL REVIEW REQUIRED and leave that visual gate unaccepted. Do not infer state, reachability or persistence from pixels alone.

Normal witnesses must originate from recorded legal production commands/clock advances, with no direct writes to stocks, VP, units, hazards, diplomacy, positions or hands. Arranged tests are separately labelled. Extend existing run_long_world/evaluation tools for full reloadable saves/replays; summary snapshots are insufficient. Bound searches and report unreachable events rather than waiting indefinitely or inventing owner coordinates. Keep QA data inaccessible to ordinary player projections, not merely hidden by a panel toggle.

At completion report: base/final SHA and tree; changed files and reasons; exact tests and counts; each screenshot review; state/replay evidence; unresolved risks/design decisions; a short owner procedure. Separate automated readiness, manual review and owner acceptance. STOP after the phase. Do not amend the next phase's scope to avoid a failure.

## Required starting commit

Start at accepted P3 final SHA. Do not change industrial design to match an animation.

## Objective

The wizard can see industry at work, identify the resulting soldier as a persistent person, and find that same individual again.

## Current evidence

sim/dmb/industry/{layers,primary,routes,constraints,allocation,factories,service,projection}.py; military/{units,formations}.py; people services and canonical ontology. Normal120000ms probe produced12 units/12 linked Persons/four formations. Existing tests fail where they assume six total definitions or manually regroup autoformed units. Reuse client/world/world_layer_presenters.gd, actor registry and journey presenters.

## Defects and gaps

Poor feedback: facilities and workers do not yet explain production→soldier linkage. Integration risk: visible worker/unit projection duplicates a persistent Person. Actual regression: old test setup fights current automatic formation allocation. Test gap: shared constraints, offscreen continuity and repeated scene entry must be checked together.

## Implementation

Keep exact resource layers, finite depletion/renewal, cross-terrain recipes and global/shared constraints. Surface concise facility activity/bottleneck cues from actual state; expose exact meters/routes only in industry_view QA. Bind illustrative worker journeys to real workplace Persons; blocking visual motion cannot change accounting. On factory completion publish one production receipt, create one Unit and one linked Person, then one legal formation membership. Reuse the same actor identity when that soldier is inspected, moves or returns. Preserve name/relationship knowledge, meter remainders, death tombstones and offscreen progress. Repair obsolete test setups to use existing formation or explicitly disband/reform through legal APIs; never allow two formations to own one unit.

## Explicit non-goals

No new military archetypes, decorative fake people, sprite production or worker-controlled accounting. The common scope limits above also apply.

## Automated tests

| ID | Phase | Exact planned test / oracle | Existing coverage to extend | Required authoritative evidence |
| --- | --- | --- | --- | --- |
| Q07 | P2/P4 | Extend existing Godot visual harness: assert_layout_and_actor_registry | test_semantic_visuals.py; run_fx_era_layout_capture.gd; run_mira_semantic_label.gd | All essential hit areas ≥48 logical px, on-screen and disjoint from protected controls; one actor per entity/Person; images inspected for clipping, not only rectangles. |
| Q12 | P4 | Extend test_canonical_ontology.py: test_factory_birth_to_person_to_formation_on_real_commands | test_t053_factories.py; test_t054_industry_service.py; test_t059_units.py | One completion→one Unit→one living Person→one active formation; repeated view/reinforcement cannot mint; unit death gives one linked Person death/tombstone. |
| Q13 | P4/P5 | Extend test_t054_industry_service.py with damaged/shared/tech integration | test_t050_layers_primary.py; test_t051_routes_constraints.py; test_t052_allocation.py; test_t056_industry_repairs_routes.py | Shared 0.1 processor with costs2/3/5 gives .6 meters at60s, one each at100s, 10 inputs each; finite balance590 from600; damage/global scarcity/paused/visible-offscreen continuation conserved. |
| Q14 | P4 | Extend worker/presentation journey tests and Godot harness for same actor | test_t055_workers_projection.py; test_presentation_journeys.py; test_canonical_ontology.py | Blocking a worker sprite cannot change authoritative output; one existing workplace Person per carrier activity; learn/return/reload preserve name and ID; no repeated entrance ACK. |

Extend existing tests at the listed paths under tests/sim; names labelled new are planned additions, not existing green tests. Godot test scripts belong under godot_project/client/tests. Run the exact affected files plus the full `python -m pytest tests/sim -q` gate.

## Deterministic interactive procedure

From normal seed507 stay unpaused at starting industry, with precisely recorded GameTime increments and no Wait. Save CP-INDUSTRY just before an actual meter crossing. Capture I01–I04 through real Inspect/Observe controls. Capture I05 after adjacent Travel return and save/reload. For accounting use production test setup with shared processor0.1, unit costs2/3/5: meters0.6 at60s and one each at100s;10 inputs each, finite600→590. Block an animated worker for the same interval and compare authoritative outputs. Repeat visible versus absent-player branches with equal GameTime.

## Screenshot manifest

All listed resolutions and named subframes are mandatory. Filename is `<ID>_<subframe-if-any>_<width>x<height>.png`. The CSV in the pack expands these into individual filenames. A QA companion is captured in a separate explicitly privileged session; it is never presented as ordinary player UI.

| ID / phase | Resolutions / subframes | Scene / fixture | Starting state | Exact actions | Expected visible result | PASS evidence | Obvious failure signs | Authoritative state evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| I01 / P4 | 450×800; 1280×720; subframes: primary, processor, factory | FX-MVP / g05_shell | CP-INDUSTRY with real primary/processor/factory active | Inspect each facility and worker in suffixes a/b/c | Semantic shapes show distinct purposes and real activity | Player can follow source→processing→yard without processor IDs | Three indistinguishable blobs; raw constraint table | Resource layers/routes and real workplace Persons |
| I02 / P4 | 450×800; 1280×720 | FX-MVP / g05_shell | Same factory just below completion, reached by exact AdvanceGame trace | Run recorded unpaused interval; capture pre-threshold at clock barrier | Concise progress/activity cue; QA meter companion | No completion before meter reaches threshold; other bottleneck explained | Fake progress unrelated to meter; paused process runs | Input/deposit balances, shared allocation, rational meter; Q13 |
| I03 / P4 | 450×800; 1280×720 | FX-MVP / g05_shell | I02 | Advance remaining exact interval across one threshold; capture birth/departure | One soldier emerges from actual yard | One unique soldier; archetype/faction distinct from workers | Duplicate birth; worker turns into unrelated ID | Factory receipt, one Unit ID and person_id, active formation membership |
| I04 / P4 | 450×800; 1280×720 | FX-MVP / g05_shell | I03 | Select new soldier; Observe/Talk if allowed; capture card | Same persistent Person represented as soldier | Learned name/profile and combat role agree; no dual actors | Anonymous replacement; two actors for same Person | Person/Unit bidirectional link and known profile |
| I05 / P4 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | I04 | Travel away/back along manifest adjacent route; save/reload; capture soldier and yard | Same soldier; continued meters; no repeated entrance | Identity/count/meter continuity survives boundaries | Reset meter; resurrected casualty; duplicated cart/soldier | Q12/Q14 before/after IDs, meters and journey ACKs |

## State evidence

Resource/input balances, constraint allocations, rational factory meters, completion receipts, Unit.person_id/Person combat role, birth/death identity, exactly one active formation membership, actor registry and journey ACKs. Time chunks and pause state accompany captures.

## Regression checks

Finite/renewable and both-input hazard suppression; repairs/damage capacity; Catan ledger unaffected by industrial accounting; personal inventory separate; military base archetypes remain three; known names and old meter saves migrate correctly. Full sim suite and affected Godot presenters.

## Acceptance gate

Real-time normal production has a visually reviewed source→processor→factory→soldier→same Person sequence. No strategic turn merely from local waiting, no animation-gated economy, duplicate identity or reset meter. Accounting/identity tests and return/reload frames pass. Stop.

END OF P4. STOP AND REPORT EVIDENCE. Do not start the next phase.
````

### P5 — Autonomous policies, diplomacy and meaningful technology

Copy everything in the following block.

````text
# P5 — Autonomous policies, diplomacy and meaningful technology

You are implementing one gated phase of the existing DuelMasterBattle project. Complete only the named phase, preserve evidence, and STOP. Do not begin the next phase, merge, publish, or claim Joe's approval. Make small reviewable changes using existing services. No quest development, finished art, model retraining, player faction-command UI, replacement Ward Duel or parallel simulation.

Read MORNING_HANDOFF.md, docs/CANONICAL_GAME_ONTOLOGY.md, docs/INTEGRATED_RUNTIME_ARCHITECTURE.md, docs/review/PLAYER_WORLD_MODEL.md, current accepted decisions, Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md and the relevant C00/C03–C13 contracts. Precedence: this brief > accepted canonical decisions > current contracts/amendments > implementation > historical docs. Report a material unresolved design conflict instead of silently changing the rule. The wizard does not order factions and has no ordinary-army combat HP. People remain persistent; a soldier is a Person linked to UnitState/CombatantState. Worker motion is illustrative. Catan cargo is physical. Exact hands, AI scores, hidden strengths and production internals stay in explicit QA mode. Reuse semantic_visuals.py, content/source/presentation/semantic_visuals.json, semantic_placeholder.gd, visual_language.gd and world_layer_presenters.gd; shapes/text only.

Verify git SHA/tree, OS and project toolchain before editing. Preserve user work and saves; use an isolated worktree/save slot if needed. Do not reset to historical main. The base rule below identifies the required accepted predecessor. A missing approval means you may inspect/prepare a concrete handoff, but cannot call the gate accepted or begin its successor. Existing Gxx AUTO_READY is not owner PASS. Use a new tracking/polish ledger, keeping historical evidence intact.

Use the real production WorldSim and g05_shell with FX-MVP seed507. The Windows entry point is Play Latest Integrated Game.bat / tools/windows_playtest.py play-latest. Resolve the repository interpreter and Godot version first; run `python -m pytest tests/sim -q` in that environment. Use tools/run_visual_review.py and existing Godot harnesses, extended in place. Every phase runs its exact tests below and affected regressions; the full Python suite is cheap enough to run at the gate. Do not mask failures, skip substantive coverage or weaken canonical assertions for green output.

For EACH screenshot row below: capture 450x800 AND 1280x720. Responsive rows also require960x540 and any additional retained sizes. Rows with suffixes require every named subframe at every required size. Load the specified full production checkpoint, verify its replay hash, then perform the recorded real input through the actual shell. CP-* names are proposed IDs, not existing files. Record fixture/seed, entity IDs, local approach cells, control identity, actual pixel coordinate per resolution, accepted command receipts and precise Game Time advances in journey_manifest.json. Use state predicates/receipts plus rendering barriers, never a fixed delay as evidence of readiness. If a normal checkpoint remains unreachable, report the blocker; an explicitly arranged production fixture can diagnose it but cannot pass normal reachability.

Save under Pack/DuelMasterBattle_Build_Pack/tracking/polish/P5/SOURCE_SHA/ with manifest, commands.jsonl, full saves, state assertions, tests/logs, iterations/, final/, and review.md. Use a clean capture directory; reject missing/blank/stale/wrong-size images, wrong scenes, timeouts and engine errors. Personally open EVERY final image at native scale. Report filename, actual dimensions, expected condition, observed condition, PASS/FAIL/MANUAL REVIEW REQUIRED, visible problems, iteration count and fix/retest references. Fix visible defects and recapture affected sequences. Image existence/exit0 is not PASS. If you cannot inspect pixels, or cannot reliably judge readability, explicitly mark MANUAL REVIEW REQUIRED and leave that visual gate unaccepted. Do not infer state, reachability or persistence from pixels alone.

Normal witnesses must originate from recorded legal production commands/clock advances, with no direct writes to stocks, VP, units, hazards, diplomacy, positions or hands. Arranged tests are separately labelled. Extend existing run_long_world/evaluation tools for full reloadable saves/replays; summary snapshots are insufficient. Bound searches and report unreachable events rather than waiting indefinitely or inventing owner coordinates. Keep QA data inaccessible to ordinary player projections, not merely hidden by a panel toggle.

At completion report: base/final SHA and tree; changed files and reasons; exact tests and counts; each screenshot review; state/replay evidence; unresolved risks/design decisions; a short owner procedure. Separate automated readiness, manual review and owner acceptance. STOP after the phase. Do not amend the next phase's scope to avoid a failure.

## Required starting commit

Start at accepted P4 final SHA. Preserve P1 draft lifecycle and P2 player-information filtering.

## Objective

Factions visibly develop and behave differently while the wizard learns consequences rather than managing cards or armies.

## Current evidence

sim/dmb/ai/{policy,observation,legal,diplomacy}.py; technology/{draft,research}.py; production consumers in industry/logistics/military. ObservationBuilder misses store:building:* ownership and actual cart current_node/cargo_lots; enemy candidate schema differs. Current effects are read by observation without reaching consumers. Three checked-in policy-im-{build,trade,war} artifacts exist, but normal setup uses heuristic. Round draft directly chooses stable-ID heuristic rather than the saved assigned policy.

## Defects and gaps

Actual bugs: observation schema and hidden-information defaults; ineffective six technology modifiers. Integration gaps: initial/era saved policy assignment, independent per-domain action budgets, consistent assigned-policy draft choice, diplomatic objective semantics. Poor feedback: no observed explanation of changed capability. Test gap: FX-ERA promotion is not full-world behaviour evaluation.

## Implementation

Repair canonical observation fields/ownership and positively filter observed enemy facts; no publicly_observed default true for unknown objects. Use one validated legal-target schema. Assign loaded heuristic/specialist policies through normal setup/era rules with deterministic saved seeds and artifact hashes; explicit logged fallback only. Do not invent a new policy mixing rule if canonical selection is unresolved—record the decision required. Preserve independent ≤1 construction+≤1 proposal+one objective per eligible formation; treatment later reserves its formation. Make war/alliance state govern objectives/contact and record causal war once. All faction picks use the same pre-draft snapshot and the assigned legal policy; preserve clockwise hands, seventh-pick redeal, duplicate caps and predecessor archive/activation. Connect primary, processor, factory, cart, unitHP and attack effects to authoritative consumers with correct era/asset scope; derived refresh must not stack or heal damaged units. Test each effect with alternate constraints nonbinding, then with real bottlenecks. Use local facility/cart/unit consequences and justified Inspect/history text; exact hands remain technology_view QA.

## Explicit non-goals

No model retraining, player deckbuilding, neural-network UI or new diplomatic rules without a canonical decision. The common scope limits above also apply.

## Automated tests

| ID | Phase | Exact planned test / oracle | Existing coverage to extend | Required authoritative evidence |
| --- | --- | --- | --- | --- |
| Q04 | P1/P5 | Extend test_t041_draft.py: test_normal_boot_deals_once; test_transition_keeps_new_era_hands | test_t041_draft.py; test_t104_era_service.py | FX-MVP starts seven/faction; exactly one pick per complete round; old hands discarded once, new seven active after FX-ERA Wait and reload. |
| Q13 | P4/P5 | Extend test_t054_industry_service.py with damaged/shared/tech integration | test_t050_layers_primary.py; test_t051_routes_constraints.py; test_t052_allocation.py; test_t056_industry_repairs_routes.py | Shared 0.1 processor with costs2/3/5 gives .6 meters at60s, one each at100s, 10 inputs each; finite balance590 from600; damage/global scarcity/paused/visible-offscreen continuation conserved. |
| Q15 | P5 | Extend test_t041_draft.py: test_common_predraft_snapshot_pass_seventh_redeal_and_archive | test_t039_tech_defs.py; test_t040_research.py; test_t041_draft.py | Common snapshot hash; one choice/faction; ordered clockwise instance-ID pass; singleton self-pass; pick7 redeal; duplicate caps; inactive predecessor does not qualify; activated historical predecessor does. |
| Q16 | P5 | New test_polish_technology_consumers.py: six parameterised production-effect cases | test_t040_research.py; test_t054_industry_service.py; test_t059_units.py; test_t066_buffs.py | Each effect reaches correct consumer: primary/processor/factory capacity, cart+1, unit HP and damage; binding constraints tested independently; era scope; HP proportion/no refresh heal; repeated refresh/reload no stacking. |
| Q17 | P5 | Extend leadership tests for production initial/era assignment and observation schema | test_t042_legal_obs.py; test_t067_military_ai.py; test_t143_t150_leadership.py; test_neural_family_primary.py | Own actual warehouse/cargo/rate fields present; truly unobserved enemy state masked; legal target schema matches objectives; pinned model hash/assignment survives save/era; fallback explicit. |
| Q18 | P5/P9 | Extend tools/run_long_world.py and training evaluation adapters; add executed-outcome report | test_training_budget.py; test_t143_t150_leadership.py | Paired fixed-seed committed behaviour, opportunity-normalized shares, no illegal/stalled runs; snapshots and SHA/model/config hashes; no fabricated win/screenshot-based distribution claim. |
| Q19 | P5/P6 | Extend test_t044_diplomacy.py / test_t061_movement.py: alliance_neutral_war_contact_matrix | test_t044_diplomacy.py; test_t067_military_ai.py | Allies never engage; neutral contact follows explicit policy/war rule; war relation emitted once; observed target/1.25 threshold; one construction/proposal plus per-formation budgets; active faction only. |

Extend existing tests at the listed paths under tests/sim; names labelled new are planned additions, not existing green tests. Godot test scripts belong under godot_project/client/tests. Run the exact affected files plus the full `python -m pytest tests/sim -q` gate.

## Deterministic interactive procedure

Capture D01–D06. Normal FX-MVP507: progress two seats per round, capture pre-boundary hands, picks/pass, seventh redeal, and one observed useful effect. Use declared production fixtures for prerequisite/archive and six isolated effect counterfactuals. Compare ally/neutral/war target matrix. Run seeds507–512 for60 turns with30000ms unpaused GameTime/turn. Then pair heuristic/build/trade/war by identical seed/faction position over first20 fixed PROMOTION_SEEDS, max200 turns or earlier genuine transition/catastrophe. Use existing long-world/training adapters and unchanged model files. Record resumable per-seed outputs and a bounded run budget from P0; incomplete runs are incomplete evidence.

## Screenshot manifest

All listed resolutions and named subframes are mandatory. Filename is `<ID>_<subframe-if-any>_<width>x<height>.png`. The CSV in the pack expands these into individual filenames. A QA companion is captured in a separate explicitly privileged session; it is never presented as ordinary player UI.

| ID / phase | Resolutions / subframes | Scene / fixture | Starting state | Exact actions | Expected visible result | PASS evidence | Obvious failure signs | Authoritative state evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D01 / P5 | 450×800; 1280×720 | FX-MVP / g05_shell + explicit QA technology_view | CP-ROUND before final seat; privileged technology_view | Capture all faction hands; execute final valid Wait through normal shell | QA-only seven/legal remaining hands and round marker | Every active faction present; private panel unmistakably QA | Player is asked to select cards; missing faction hand | Common pre-draft snapshot hash; hand/card instance IDs |
| D02 / P5 | 450×800; 1280×720 | FX-MVP / g05_shell + explicit QA technology_view | D01 after round boundary | Capture same QA view after receipt | One choice each; remainder passes clockwise | Card IDs prove pass direction/acquisition once | Sequential information advantage; duplicate picks | Q15 snapshot/pick/pass map; activated versus archived status |
| D03 / P5 | 450×800; 1280×720 | FX-MVP / g05_shell + explicit QA technology_view | CP-DRAFT7 before seventh complete round | Execute final seat; capture QA hands | New seven-card hands after pick7 | Previous seven acquisitions retained; new instance IDs | Empty draft; 6/8 cards; reused instance IDs | Pick count/redeal count/round receipt |
| D04 / P5 | 450×800; 1280×720; subframes: archive, activated | Declared production research arrangement + QA technology_view | Declared arranged later-era production fixture: missing then active predecessor | Capture archive; acquire eligible predecessor by production ResearchService; capture activation, suffixes a/b | QA differentiates inactive/active with plain explanation | Predecessor history governs activation; no stacking on refresh | Archived card grants effect early; visual-only activation | Q15 prerequisite/duplicate-cap/era scope oracle |
| D05 / P5 | 450×800; 1280×720; subframes: primary_before, primary_after, processor_before, processor_after, factory_before, factory_after, cart_before, cart_after, hp_before, hp_after, attack_before, attack_after | Declared production effect arrangements + existing QA views | Six controlled production effect cases, one per suffix primary/processor/factory/cart/hp/attack | Capture before/after relevant QA consumer and affected actor | Relevant capacity/stat consequence is visible in QA | All six actual consumers change under nonbinding alternate constraints | Only observation value changes; HP refresh heals; wrong-era asset | Q16 exact effective value, throughput/cargo/HP/damage counterfactual |
| D06 / P5 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | CP-TECH normal player view; known affected facility/cart/soldier | Inspect witnessed change; read locally justified notice | Plain explanation of new methods/capability; changed activity | Effect understandable without hands, scores or management buttons | Raw model/card table; promised throughput despite binding bottleneck | Known fact origin plus same Q16 committed effect |

## State evidence

Hand/card instance IDs; common snapshot hash; pick/pass/acquisition/activation receipts; actual effective capacities/HP/damage/cargo; era-scoped ownership; policy/artifact hashes; committed action distributions versus legal opportunities; own warehouse/cargo field values; observed enemy masks; saved assignment continuity.

## Regression checks

C12 predecessor/duplicate rules; P1 save/rollback; construction/trade conservation; own-knowledge boundaries; no allied attacks. Policy report: zero illegal commits/crashes/hidden reads; no unexplained10 active seats without progress when useful actions feasible. Report sufficient-opportunity specialist pairwise differences: target≥0.10 in at least one executed family share, with counts/uncertainty. INCONCLUSIVE low-opportunity runs cannot pass or justify retraining. Existing C14 promotion claims retain their own standard.

## Acceptance gate

All six effects change real consumers, complete drafts persist/pass correctly, saved policies genuinely execute and legal diplomatic objectives exist. D frames reviewed with no faction-management UI. Quantitative failures remain visible. P6 can strengthen war/treatment consequences, so any currently unreachable war outcome is explicitly pending P6 and must be closed at P9; do not claim full specialist behavioural acceptance prematurely. Stop.

END OF P5. STOP AND REPORT EVIDENCE. Do not start the next phase.
````

### P6 — Faction conflict, hazard response and economic recovery

Copy everything in the following block.

````text
# P6 — Faction conflict, hazard response and economic recovery

You are implementing one gated phase of the existing DuelMasterBattle project. Complete only the named phase, preserve evidence, and STOP. Do not begin the next phase, merge, publish, or claim Joe's approval. Make small reviewable changes using existing services. No quest development, finished art, model retraining, player faction-command UI, replacement Ward Duel or parallel simulation.

Read MORNING_HANDOFF.md, docs/CANONICAL_GAME_ONTOLOGY.md, docs/INTEGRATED_RUNTIME_ARCHITECTURE.md, docs/review/PLAYER_WORLD_MODEL.md, current accepted decisions, Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md and the relevant C00/C03–C13 contracts. Precedence: this brief > accepted canonical decisions > current contracts/amendments > implementation > historical docs. Report a material unresolved design conflict instead of silently changing the rule. The wizard does not order factions and has no ordinary-army combat HP. People remain persistent; a soldier is a Person linked to UnitState/CombatantState. Worker motion is illustrative. Catan cargo is physical. Exact hands, AI scores, hidden strengths and production internals stay in explicit QA mode. Reuse semantic_visuals.py, content/source/presentation/semantic_visuals.json, semantic_placeholder.gd, visual_language.gd and world_layer_presenters.gd; shapes/text only.

Verify git SHA/tree, OS and project toolchain before editing. Preserve user work and saves; use an isolated worktree/save slot if needed. Do not reset to historical main. The base rule below identifies the required accepted predecessor. A missing approval means you may inspect/prepare a concrete handoff, but cannot call the gate accepted or begin its successor. Existing Gxx AUTO_READY is not owner PASS. Use a new tracking/polish ledger, keeping historical evidence intact.

Use the real production WorldSim and g05_shell with FX-MVP seed507. The Windows entry point is Play Latest Integrated Game.bat / tools/windows_playtest.py play-latest. Resolve the repository interpreter and Godot version first; run `python -m pytest tests/sim -q` in that environment. Use tools/run_visual_review.py and existing Godot harnesses, extended in place. Every phase runs its exact tests below and affected regressions; the full Python suite is cheap enough to run at the gate. Do not mask failures, skip substantive coverage or weaken canonical assertions for green output.

For EACH screenshot row below: capture 450x800 AND 1280x720. Responsive rows also require960x540 and any additional retained sizes. Rows with suffixes require every named subframe at every required size. Load the specified full production checkpoint, verify its replay hash, then perform the recorded real input through the actual shell. CP-* names are proposed IDs, not existing files. Record fixture/seed, entity IDs, local approach cells, control identity, actual pixel coordinate per resolution, accepted command receipts and precise Game Time advances in journey_manifest.json. Use state predicates/receipts plus rendering barriers, never a fixed delay as evidence of readiness. If a normal checkpoint remains unreachable, report the blocker; an explicitly arranged production fixture can diagnose it but cannot pass normal reachability.

Save under Pack/DuelMasterBattle_Build_Pack/tracking/polish/P6/SOURCE_SHA/ with manifest, commands.jsonl, full saves, state assertions, tests/logs, iterations/, final/, and review.md. Use a clean capture directory; reject missing/blank/stale/wrong-size images, wrong scenes, timeouts and engine errors. Personally open EVERY final image at native scale. Report filename, actual dimensions, expected condition, observed condition, PASS/FAIL/MANUAL REVIEW REQUIRED, visible problems, iteration count and fix/retest references. Fix visible defects and recapture affected sequences. Image existence/exit0 is not PASS. If you cannot inspect pixels, or cannot reliably judge readability, explicitly mark MANUAL REVIEW REQUIRED and leave that visual gate unaccepted. Do not infer state, reachability or persistence from pixels alone.

Normal witnesses must originate from recorded legal production commands/clock advances, with no direct writes to stocks, VP, units, hazards, diplomacy, positions or hands. Arranged tests are separately labelled. Extend existing run_long_world/evaluation tools for full reloadable saves/replays; summary snapshots are insufficient. Bound searches and report unreachable events rather than waiting indefinitely or inventing owner coordinates. Keep QA data inaccessible to ordinary player projections, not merely hidden by a panel toggle.

At completion report: base/final SHA and tree; changed files and reasons; exact tests and counts; each screenshot review; state/replay evidence; unresolved risks/design decisions; a short owner procedure. Separate automated readiness, manual review and owner acceptance. STOP after the phase. Do not amend the next phase's scope to avoid a failure.

## Required starting commit

Start at accepted P5 final SHA with remaining conflict-specific policy evidence explicitly identified.

## Objective

Autonomous conflict and hazard response leave visible, consequential changes in the same world and its economy.

## Current evidence

sim/dmb/time/turns.py lacks normal catastrophe placement call; ai/policy.py hazard_treat falls through. hazards/{service,propagation,queries,responders}.py contain reusable services. Starting setup clears one of three seed507 cubes. military/{movement,offscreen,units,formations}.py handle forces. client/scenes/g05_shell.gd::_maybe_host_local_battle treats client/combat/local_battle.gd RefCounted as a Node and does not bind/tick it. Reuse g04_battle_shell ownership and lease/handoff architecture.

## Defects and gaps

Actual bugs: nonexecuted treatment and hazard cadence; incompatible integrated host; diplomacy-blind hostile contact. Integration gaps: ordered force/treatment/placement/consequences stages; complete hostility snapshot; treatment activation exclusion. Poor feedback: overlapping battle labels; invisible hazard→blockage→recovery. Test gap: fixture battles do not establish ordinary-shell contact.

## Implementation

Wire active-faction force and responder work into C03 stage order. Preserve one objective per formation, ≤2 strategic edges, newly manufactured activation rule, allied nonengagement and explicit neutral/war semantics. Use an actual Node owner with the retained RefCounted local controller; bind/tick/save/release exactly one lease, reusing G04 presenter. Wait keeps local combat, Travel closes/checkpoints then enables offscreen resolution; avoid dual advancement. Preserve deterministic bounded offscreen rules, casualties linked to Person, withdrawals, building destruction and no ownership capture. Execute validated hazard_treat through HazardResponder, revalidating active faction, adjacency, capability, disengagement and unspent activation; reserve it before any move/attack. Implement due era-relative placement/overflow once, stable hex visitation and terminal eighth-outbreak stop, respecting earlier10VP interruption. Reconcile initial three-cube contract with clear-at-core setup: seek an already accepted exception; otherwise implement valid contracted setup, documenting resulting seed/checkpoint changes. Include typed modern cleanup as capability, not a fourth military archetype. Add readable conflict/treatment/source-block/resume cues from receipts.

## Explicit non-goals

No magical capture, wizard combat HP, simplified tactical engine, new hazard genre or fourth military archetype. The common scope limits above also apply.

## Automated tests

| ID | Phase | Exact planned test / oracle | Existing coverage to extend | Required authoritative evidence |
| --- | --- | --- | --- | --- |
| Q11 | P3/P6 | Extend test_t029_catan_grants.py through dispatch and ledger | test_t029_catan_grants.py; test_t071_disruption.py | Roll7/desert/no-warehouse cases; shared matching hex; hazard vs industrial depletion distinction; same controlled roll before/after removal grants correct good without changing natural RNG. |
| Q19 | P5/P6 | Extend test_t044_diplomacy.py / test_t061_movement.py: alliance_neutral_war_contact_matrix | test_t044_diplomacy.py; test_t067_military_ai.py | Allies never engage; neutral contact follows explicit policy/war rule; war relation emitted once; observed target/1.25 threshold; one construction/proposal plus per-formation budgets; active faction only. |
| Q20 | P6 | New test_polish_military_chain.py and run_polish_local_battle.gd | test_t060_combat_math.py; test_t061_movement.py; test_t062_offscreen.py; test_t063_local_battle.py; test_t064_handoffs.py | Production-generated soldiers→objectives→contact→proper Node host+RefCounted controller→lease ticks→casualties/building damage; Wait retains lease; Travel closes then off-screen; 120s bound; no ownership capture. |
| Q21 | P6 | New test_polish_hazard_chain.py: test_normal_turn_cadence_types_overflow_terminal_order | test_t069_hazards.py; test_t070_propagation.py; test_t116_modern_future.py; test_t118_pollution.py; test_t119_aliens.py; test_t120_nuclear_machines.py | Normal dispatch calls placement once when due; three initial cubes under valid setup; era reset/retained types; each propagation hex once; eighth outbreak stops; first earlier VP win suppresses old hazard draw. |
| Q22 | P6 | New test_polish_hazard_chain.py: test_selected_treatment_spends_activation_and_restores_economy | test_t071_disruption.py; test_t073_responders.py | Actual policy-selected eligible adjacent cube removed; zero strategic movement/attack same activation; no inactive/engaged/ineligible/remote treatment; pollution cleanup; exact source/cart recovery only when last blocker gone. |

Extend existing tests at the listed paths under tests/sim; names labelled new are planned additions, not existing green tests. Godot test scripts belong under godot_project/client/tests. Run the exact affected files plus the full `python -m pytest tests/sim -q` gate.

## Deterministic interactive procedure

Produce CP-CONTACT/HAZARD/RESPONSE from normal507 replay. Capture M01–M10. Attended contact uses actual g05 shell; repeat branch leaving legally for offscreen result. Observe a hazard suppressing actual source/transit; formation must remove chosen cube on its next eligible seat, spend activation, then recover work only after last blocker. Use declared production setups for alliance/neutral matrix, cascade terminal, all era hazard types and building destruction. No source refill or forced battle win. Repeat load during local lease, before treatment and after economic recovery.

## Screenshot manifest

All listed resolutions and named subframes are mandatory. Filename is `<ID>_<subframe-if-any>_<width>x<height>.png`. The CSV in the pack expands these into individual filenames. A QA companion is captured in a separate explicitly privileged session; it is never presented as ordinary player UI.

| ID / phase | Resolutions / subframes | Scene / fixture | Starting state | Exact actions | Expected visible result | PASS evidence | Obvious failure signs | Authoritative state evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M01 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-CONTACT before legal hostile movement | Inspect frontier formations; capture | Faction patterns, distinct archetypes, observable hostility | Opponents readable; legitimate war/intent cause | Allied forces described as enemy; hidden strength shown | Diplomacy graph, observed targets, formation objectives |
| M02 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | M01 wizard remains present | Press required Wait once; capture contact at lease-ready receipt | Formation arrival and clear battle-start cue | Production g05 shell owns exactly one bound local battle | RefCounted host error; battle only in separate G04 fixture | Battle ID/participants/lease owner; no offscreen resolver concurrently |
| M03 / P6 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | M02 | Allow recorded unpaused local combat ticks; capture active combat | Readable opposing action/health cues; wizard remains independent | Distinct units and safe controls; no faction command buttons | Stacked HP text; wizard army HP/death; missing controller tick | 50ms tick sequence, Unit health/damage and wizard immunity |
| M04 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | Same contact after deterministic resolved tick count | Capture aftermath; Inspect affected centre and surviving Person | Retreat/casualties/damaged or destroyed building persist | Changed world agrees with outcome; no captured settlement magic | Dead actor remains active; faction ownership flips on battle win | Casualty Person tombstones, withdrawal, buildingHP/owner/VP |
| M05 / P6 | 450×800; 1280×720; subframes: hazard, blocked_work | FX-MVP / g05_shell | CP-HAZARD source/road genuinely suppressed | Inspect manifestation and blocked source/cart in suffixes a/b | Typed danger connected to stopped work/transit | Cause is locally understandable without cube IDs | Hazard decorative while source still produces; source destroyed incorrectly | Suppression queries, matched Catan roll/industry window, cargo retained |
| M06 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-RESPONSE eligible adjacent formation before its active seat | Inspect formation and target; capture | Responder poised near danger with appropriate archetype cue | Correct active faction/capability; no manual army order | Remote or engaged/ineligible formation assigned | Legal candidate, adjacency, unspent activation and selected cube |
| M07 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | M06 | Press Wait to its seat; capture treatment outcome barrier | Brief treatment state/cue at correct hazard | Committed treatment is visible before disappearance; no attack/move | Generic proposal with no effect; marching and treating same turn | Spent-turn equals current turn; treatment receipt; zero move/attack |
| M08 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | M07 | Capture updated world and Inspect affected area | Exactly selected hazard gone/changed | Other cubes remain as authoritative; no ghost manifestation | All cubes vanish; targeted cube stays; duplicate result notice | Exact cube active flag/count; actor registry matches state |
| M09 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | M08 after final relevant blocker removed | Run recorded production window/next valid cart turn; capture source/cart | Previously suppressed activity resumes | Same source/cart recovers; output is real, not just animation | Remaining blocker ignored; deposit refilled; cargo respawned | Q22 matched grant/flow/route recovery; conserved resources |
| M10 / P6 | 450×800; 1280×720 | FX-MVP / g05_shell | Replay CP-CONTACT in separate branch | Enter battle then Travel away legally; run prescribed turns; return | Persistent off-screen aftermath, with learned/local account | No second fight or resurrected actors after return | Local lease left running; duplicate casualties; frozen unresolved battle | Exclusive handoff, bounded resolver receipt, resulting IDs/buildings |

## State evidence

Diplomacy/hostility graph, candidate/objective and active budgets, battle/lease/tick identities, casualties/buildingHP/VP/owner, hazard placement ordinal/deck/counters/visited set, selected cube and formation spent turn, zero move/attack, exact suppressed and recovered flow/route. Matching-roll Catan counterfactual is a labelled logic test, not tampered normal RNG.

## Regression checks

Three archetypes and linked people; same local/offscreen clocks/lease boundaries; wizard immunity; first-win interruption; typed demon/monster/modern/future rules, pollution cleanup; retained Ward selected-cube/visit semantics; physical Catan/industry preservation; P1–P5.

## Acceptance gate

Real normal-shell conflict and real policy-selected treatment both commit and are visible. Correct cube removed, activation spent, blocked economic/transit activity resumes. All M frames inspected with no allied fire, world capture, duplicate lease/actor or missing cause. Cadence/overflow/terminal tests pass. Close P5 conflict-specific policy gaps or explicitly fail the phase. Stop.

END OF P6. STOP AND REPORT EVIDENCE. Do not start the next phase.
````

### P7 — Wizard intervention and retained Ward Duel

Copy everything in the following block.

````text
# P7 — Wizard intervention and retained Ward Duel

You are implementing one gated phase of the existing DuelMasterBattle project. Complete only the named phase, preserve evidence, and STOP. Do not begin the next phase, merge, publish, or claim Joe's approval. Make small reviewable changes using existing services. No quest development, finished art, model retraining, player faction-command UI, replacement Ward Duel or parallel simulation.

Read MORNING_HANDOFF.md, docs/CANONICAL_GAME_ONTOLOGY.md, docs/INTEGRATED_RUNTIME_ARCHITECTURE.md, docs/review/PLAYER_WORLD_MODEL.md, current accepted decisions, Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md and the relevant C00/C03–C13 contracts. Precedence: this brief > accepted canonical decisions > current contracts/amendments > implementation > historical docs. Report a material unresolved design conflict instead of silently changing the rule. The wizard does not order factions and has no ordinary-army combat HP. People remain persistent; a soldier is a Person linked to UnitState/CombatantState. Worker motion is illustrative. Catan cargo is physical. Exact hands, AI scores, hidden strengths and production internals stay in explicit QA mode. Reuse semantic_visuals.py, content/source/presentation/semantic_visuals.json, semantic_placeholder.gd, visual_language.gd and world_layer_presenters.gd; shapes/text only.

Verify git SHA/tree, OS and project toolchain before editing. Preserve user work and saves; use an isolated worktree/save slot if needed. Do not reset to historical main. The base rule below identifies the required accepted predecessor. A missing approval means you may inspect/prepare a concrete handoff, but cannot call the gate accepted or begin its successor. Existing Gxx AUTO_READY is not owner PASS. Use a new tracking/polish ledger, keeping historical evidence intact.

Use the real production WorldSim and g05_shell with FX-MVP seed507. The Windows entry point is Play Latest Integrated Game.bat / tools/windows_playtest.py play-latest. Resolve the repository interpreter and Godot version first; run `python -m pytest tests/sim -q` in that environment. Use tools/run_visual_review.py and existing Godot harnesses, extended in place. Every phase runs its exact tests below and affected regressions; the full Python suite is cheap enough to run at the gate. Do not mask failures, skip substantive coverage or weaken canonical assertions for green output.

For EACH screenshot row below: capture 450x800 AND 1280x720. Responsive rows also require960x540 and any additional retained sizes. Rows with suffixes require every named subframe at every required size. Load the specified full production checkpoint, verify its replay hash, then perform the recorded real input through the actual shell. CP-* names are proposed IDs, not existing files. Record fixture/seed, entity IDs, local approach cells, control identity, actual pixel coordinate per resolution, accepted command receipts and precise Game Time advances in journey_manifest.json. Use state predicates/receipts plus rendering barriers, never a fixed delay as evidence of readiness. If a normal checkpoint remains unreachable, report the blocker; an explicitly arranged production fixture can diagnose it but cannot pass normal reachability.

Save under Pack/DuelMasterBattle_Build_Pack/tracking/polish/P7/SOURCE_SHA/ with manifest, commands.jsonl, full saves, state assertions, tests/logs, iterations/, final/, and review.md. Use a clean capture directory; reject missing/blank/stale/wrong-size images, wrong scenes, timeouts and engine errors. Personally open EVERY final image at native scale. Report filename, actual dimensions, expected condition, observed condition, PASS/FAIL/MANUAL REVIEW REQUIRED, visible problems, iteration count and fix/retest references. Fix visible defects and recapture affected sequences. Image existence/exit0 is not PASS. If you cannot inspect pixels, or cannot reliably judge readability, explicitly mark MANUAL REVIEW REQUIRED and leave that visual gate unaccepted. Do not infer state, reachability or persistence from pixels alone.

Normal witnesses must originate from recorded legal production commands/clock advances, with no direct writes to stocks, VP, units, hazards, diplomacy, positions or hands. Arranged tests are separately labelled. Extend existing run_long_world/evaluation tools for full reloadable saves/replays; summary snapshots are insufficient. Bound searches and report unreachable events rather than waiting indefinitely or inventing owner coordinates. Keep QA data inaccessible to ordinary player projections, not merely hidden by a panel toggle.

At completion report: base/final SHA and tree; changed files and reasons; exact tests and counts; each screenshot review; state/replay evidence; unresolved risks/design decisions; a short owner procedure. Separate automated readiness, manual review and owner acceptance. STOP after the phase. Do not amend the next phase's scope to avoid a failure.

## Required starting commit

Start at accepted P6 final SHA. Preserve all autonomous systems and their time/state invariants.

## Objective

Wizard interactions, local magic and the full Ward Duel feel naturally connected to the surrounding simulation and return cleanly.

## Current evidence

sim/dmb/player/{magic,visits}.py, adventure/duels.py and semantic bridge; client/scenes/game_board.tscn, client/scripts/game_board.gd, DmbBattleSim; run_ward_duel_presentation.gd, run_g04_spellbook_pointer.gd and run_g04_lease_return.gd. Historical portrait Ward frame is a positive baseline, but it does not prove real pointer ward entry. Existing t078/t090/t095 failures involve exit/mechanism/archived-fixture expectations.

## Defects and gaps

Integration/test gaps: actual single-pointer ward setup, stale moving targets, exact-cube results, paused clocks and clean world return across all outcomes. Visual risk: world actors under modal board or duplicate actors on return. Regression gap: existing inventory/puzzle/quest checks fail; preserve them without extending quests.

## Implementation

Use shared attached Observe/Talk/Inspect/Destroy/Buff/Challenge controls and validate local range/observed target at open and commit. Preserve ordinary-entity versus manifestation targeting rules, buff caps and GameTime expiry. Challenge must lease the selected eligible cube and retain that identity; no substitute after world resolution. Visit allowances survive Wait/reload and refresh only at legitimate visit boundaries. Configure retained board/ward before startup, use actual pointer spell selection and production duel result, keep world paused/hidden/noninteractive. On win/draw/loss/cancel/save-resume, apply authoritative result once and restore prior world/pause/actor state once. Repair obsolete archived fixture tests by loading intended current fixture or repairing lost production regressions; do not add narrative content or resurrect the archived shortage quest into FX-MVP.

## Explicit non-goals

No quest templates/dialogue/branches, replacement duel, forced-win shortcut or personal inventory funding faction construction. The common scope limits above also apply.

## Automated tests

| ID | Phase | Exact planned test / oracle | Existing coverage to extend | Required authoritative evidence |
| --- | --- | --- | --- | --- |
| Q05 | P2/P7 | New run_polish_input_pause.gd plus Python clock regression | test_t012_clock.py; test_t022_clock_driver.py; run_g05_playable.gd | One Wait per press incl held/repeated input; invalid Travel no turn/RNG; independent modal/focus/duel pause tokens; 60 paused seconds no world quanta/buff expiry/catch-up. |
| Q23 | P7 | Extend semantic/magic/duel bridge tests with production-shell commands | test_r04_semantic_magic.py; test_t065_magic.py; test_t066_buffs.py; test_t072_visits.py; test_t074_hazard_duels.py; test_u05_retained_ward_duel.py | Moving-target range checked at open+commit; no caller-observed privilege; Destroy ordinary entity only; buffs cap/freeze; successful exact-cube result once; Wait/reload no new allowance; world-resolved target no substitute cube. |
| Q24 | P7 | Extend run_ward_duel_presentation.gd with actual pointer ward and return branches | run_g04_spellbook_pointer.gd; run_g04_lease_return.gd; run_ward_duel_presentation.gd | Real board configured before startup; pointer chooses four spells/secret; no forced defeat; mid-duel resume preserves ward/history/RNG; win/draw/loss/cancel/reload result; world hidden/noninteractive, restored once. |
| Q25 | P7 | Repair current regression failures and retain inventory/puzzle/quest smoke | test_t087_inventory.py; test_t088_inventory_use.py; test_t089_puzzles.py; test_t090_sluice.py; test_t095_village_panel.py; test_boulder_quest.py | Required item single container; dropped item and mechanisms persist; existing sluice solution validates; production fixture uses same engine; no quest-content expansion. |

Extend existing tests at the listed paths under tests/sim; names labelled new are planned additions, not existing green tests. Godot test scripts belong under godot_project/client/tests. Run the exact affected files plus the full `python -m pytest tests/sim -q` gate.

## Deterministic interactive procedure

Capture W01–W07. Follow verified strategic route35→30→36→31→37 if unchanged, with recorded actual local exits. Approach cube1 manifestation via real input, Observe, Challenge, enter four spells/ward through pointer, play full retained duel and return. Deterministic rival input may stabilize fixture QA but never force health/result or call resolve_hazard_success as input proof. Run separate win/draw/loss/cancel/mid-duel reload branches. Test stationary then moving target range, capped buff, paused expiry, real item/grimoire/puzzle interactions. Wait/reload at same visit must not renew allowance.

## Screenshot manifest

All listed resolutions and named subframes are mandatory. Filename is `<ID>_<subframe-if-any>_<width>x<height>.png`. The CSV in the pack expands these into individual filenames. A QA companion is captured in a separate explicitly privileged session; it is never presented as ordinary player UI.

| ID / phase | Resolutions / subframes | Scene / fixture | Starting state | Exact actions | Expected visible result | PASS evidence | Obvious failure signs | Authoritative state evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| W01 / P7 | 450×800; 1280×720 | FX-MVP / g05_shell | Fresh507 route35→30→36→31→37 or validated successor CP-WARD | Walk via recorded live input path to cube1 manifestation | Hazard in same world; wizard visibly in interaction range | Exact target and world-local position match | Teleported wizard; fixture switched without disclosure | Accepted Travel receipts and local pose; selected cube1 |
| W02 / P7 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | W01 | Observe then select Challenge from attached interaction card | Readable Challenge affordance on selected manifestation | Real input opens retained duel once, allowed visit | Hidden/debug shortcut; direct result call; wrong cube | Observe/range/visit eligibility and lease result |
| W03 / P7 | 450×800; 1280×720; 960×540; subframes: ward_setup, active_board | FX-MVP lease → retained game_board.tscn | W02 retained game_board | Use real pointer to enter four ward spells/secret and play recorded moves; capture setup and active board as suffixes a/b | Full production Ward Duel, clean background, usable spell controls | No world labels/hitboxes; pointer receipts; ward actually entered | Simplified Mastermind panel; forced rival defeat; world bleed | DmbBattleSim ward/history/RNG, mode/pause/lease identity |
| W04 / P7 | 450×800; 1280×720; 960×540; subframes: win, draw, loss | Retained game_board.tscn result | W03 played result | Capture result after actual win/draw/loss branch; suffix each branch | Correct result, readable return affordance | No domain success helper bypass; outcome acknowledged once | Auto-win injected; ambiguous result; frozen return | Production duel result/command and selected-cube receipt |
| W05 / P7 | 450×800; 1280×720; 960×540; subframes: win_return, loss_return, cancel_return | FX-MVP / g05_shell | W04 win plus independent loss/cancel branches | Return through visible control; capture normal world | Exact chosen hazard removed only on valid success; world clean | Single actors; controls restored; no extra visit allowance from Wait/reload | Ghost duel/world actors; substitute cube removed; all hazards cleared | Cube/visit/actorID sets and pause tokens before/after |
| W06 / P7 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-BUFF with locally observed allied/eligible soldier | Apply permitted buff via real card; Inspect; run paused then unpaused interval | Clear bounded buff cue on same soldier | UI agrees with real modifier and remaining Game Time | Buff expires while paused; stacks past cap; stale target accepted | Q23 cap/range/current-target and clock-expiry oracle |
| W07 / P7 | 450×800; 1280×720; 960×540; subframes: inventory, grimoire, puzzle | FX-MVP / g05_shell | CP-ITEM existing personal item/puzzle; no new quest content | Use inventory/grimoire and existing puzzle interaction; capture each as suffixes a/b/c | Personal tools integrated with attached interactions | Real item/slot semantics; readable mobile controls; world pauses correctly | Item duplicated; spend personal item as faction stock; new quest scope | Inventory single-container record and existing puzzle solution regression |

## State evidence

Player pose/knowledge/range receipts, exact cube/visit allowance, exclusive lease, ward/secret/history/RNG, result receipt, pause tokens, actor ID/hitbox sets, item container and mechanism state. Screenshot requires matching authoritative state version.

## Regression checks

Full production Ward visuals/gameplay; local battle handoff; autonomous faction clocks frozen by retained encounter; personal inventory separation; existing boulder/sluice/puzzle checks only; no new quest templates/dialogue/branches. Full sim suite plus real headed pointer/return suites at all retained resolutions.

## Acceptance gate

Complete production Ward sequence and valid local magic work through actual controls, with exact outcome once and clean return. No world bleed, ghost actor, extra allowance or reset clocks/items. W subframes reviewed; unresolved aesthetic criteria require owner review rather than automatic acceptance. Stop.

END OF P7. STOP AND REPORT EVIDENCE. Do not start the next phase.
````

### P8 — Eras, history and complete persistence

Copy everything in the following block.

````text
# P8 — Eras, history and complete persistence

You are implementing one gated phase of the existing DuelMasterBattle project. Complete only the named phase, preserve evidence, and STOP. Do not begin the next phase, merge, publish, or claim Joe's approval. Make small reviewable changes using existing services. No quest development, finished art, model retraining, player faction-command UI, replacement Ward Duel or parallel simulation.

Read MORNING_HANDOFF.md, docs/CANONICAL_GAME_ONTOLOGY.md, docs/INTEGRATED_RUNTIME_ARCHITECTURE.md, docs/review/PLAYER_WORLD_MODEL.md, current accepted decisions, Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md and the relevant C00/C03–C13 contracts. Precedence: this brief > accepted canonical decisions > current contracts/amendments > implementation > historical docs. Report a material unresolved design conflict instead of silently changing the rule. The wizard does not order factions and has no ordinary-army combat HP. People remain persistent; a soldier is a Person linked to UnitState/CombatantState. Worker motion is illustrative. Catan cargo is physical. Exact hands, AI scores, hidden strengths and production internals stay in explicit QA mode. Reuse semantic_visuals.py, content/source/presentation/semantic_visuals.json, semantic_placeholder.gd, visual_language.gd and world_layer_presenters.gd; shapes/text only.

Verify git SHA/tree, OS and project toolchain before editing. Preserve user work and saves; use an isolated worktree/save slot if needed. Do not reset to historical main. The base rule below identifies the required accepted predecessor. A missing approval means you may inspect/prepare a concrete handoff, but cannot call the gate accepted or begin its successor. Existing Gxx AUTO_READY is not owner PASS. Use a new tracking/polish ledger, keeping historical evidence intact.

Use the real production WorldSim and g05_shell with FX-MVP seed507. The Windows entry point is Play Latest Integrated Game.bat / tools/windows_playtest.py play-latest. Resolve the repository interpreter and Godot version first; run `python -m pytest tests/sim -q` in that environment. Use tools/run_visual_review.py and existing Godot harnesses, extended in place. Every phase runs its exact tests below and affected regressions; the full Python suite is cheap enough to run at the gate. Do not mask failures, skip substantive coverage or weaken canonical assertions for green output.

For EACH screenshot row below: capture 450x800 AND 1280x720. Responsive rows also require960x540 and any additional retained sizes. Rows with suffixes require every named subframe at every required size. Load the specified full production checkpoint, verify its replay hash, then perform the recorded real input through the actual shell. CP-* names are proposed IDs, not existing files. Record fixture/seed, entity IDs, local approach cells, control identity, actual pixel coordinate per resolution, accepted command receipts and precise Game Time advances in journey_manifest.json. Use state predicates/receipts plus rendering barriers, never a fixed delay as evidence of readiness. If a normal checkpoint remains unreachable, report the blocker; an explicitly arranged production fixture can diagnose it but cannot pass normal reachability.

Save under Pack/DuelMasterBattle_Build_Pack/tracking/polish/P8/SOURCE_SHA/ with manifest, commands.jsonl, full saves, state assertions, tests/logs, iterations/, final/, and review.md. Use a clean capture directory; reject missing/blank/stale/wrong-size images, wrong scenes, timeouts and engine errors. Personally open EVERY final image at native scale. Report filename, actual dimensions, expected condition, observed condition, PASS/FAIL/MANUAL REVIEW REQUIRED, visible problems, iteration count and fix/retest references. Fix visible defects and recapture affected sequences. Image existence/exit0 is not PASS. If you cannot inspect pixels, or cannot reliably judge readability, explicitly mark MANUAL REVIEW REQUIRED and leave that visual gate unaccepted. Do not infer state, reachability or persistence from pixels alone.

Normal witnesses must originate from recorded legal production commands/clock advances, with no direct writes to stocks, VP, units, hazards, diplomacy, positions or hands. Arranged tests are separately labelled. Extend existing run_long_world/evaluation tools for full reloadable saves/replays; summary snapshots are insufficient. Bound searches and report unreachable events rather than waiting indefinitely or inventing owner coordinates. Keep QA data inaccessible to ordinary player projections, not merely hidden by a panel toggle.

At completion report: base/final SHA and tree; changed files and reasons; exact tests and counts; each screenshot review; state/replay evidence; unresolved risks/design decisions; a short owner procedure. Separate automated readiness, manual review and owner acceptance. STOP after the phase. Do not amend the next phase's scope to avoid a failure.

## Required starting commit

Start at accepted P7 final SHA. Keep complete P1 serialization and new-era draft lifecycle.

## Objective

An era change feels like history happening to recognisable places and people; saves and returns preserve that continuity.

## Current evidence

sim/dmb/eras/{planner,service,collapse,fission,upgrades,continuity,safeguards,cycles}.py; history/{legacy,chronicle,compaction}.py; persistence coordinator; client/world/era_transition.gd. FX-ERA is a fast arranged9VP regression. Existing t097–t105/t125–t129 cover pieces, but ordinary full-chain reachability and current images are not established.

## Defects and gaps

Integration gaps: natural funded first-win→political conversion→new competition and complete source-to-known-history event coverage. Poor feedback: test panel collisions, unclear successor/legacy identity. Persistence risks: carts/ACKs/people/meters/retired units across several boundaries. Test gap: summary snapshots and pixel similarity are insufficient.

## Implementation

Preserve immediate atomic first10VP barrier and one transition receipt. Revalidate collapse/survival/fission/core pair/safeguard rules against C11, including score10/9/8/7/6/5 fixture oracle, ties and sole remaining winner. Apply cargo/orders/diplomacy/research/people dispositions once. Upgrade eligible cores in place; retain old non-core legacy sites with zero currentVP and functioning old recipes/layers. Preserve living people/relations/learned names/items/puzzles/world coordinates; distinguish soldier retirement from Person death. New era gets correct roster/policies/seven-card hands; reset only specified new-era meters. Retain existing paused four-second/skip presentation but improve semantic before/after cues and concise known history. Future→Prehistoric explicitly reseeds political competition, retires old military/research, creates correct cycle layers/hazards and preserves historical continuity; no Utopia-path expansion. Complete fresh-process save/load and next-command continuation across representative boundaries.

## Explicit non-goals

No new victory path/Utopia expansion, historical identity reset, replacement era engine or invented fission rules. The common scope limits above also apply.

## Automated tests

| ID | Phase | Exact planned test / oracle | Existing coverage to extend | Required authoritative evidence |
| --- | --- | --- | --- | --- |
| Q26 | P8 | Extend era tests: first_winner_new_roster_pause_receipt | test_t097_era_planner.py; test_t100_core_upgrade.py; test_t103_continuity.py; test_t104_era_service.py | One threshold event, no later old-era work, stable core IDs/anchors, single starter grant, only new-era meters reset, seven new cards persist; four-second/skip presentation cannot repeat conversion. |
| Q27 | P8 | Extend collapse/fission/legacy tests through save and returned projection | test_t098_collapse.py; test_t099_fission.py; test_t101_legacy.py; test_t102_safeguards.py | 10/9/8/7/6/5 oracle; ties and sole winner; true minimum core pairs; last-faction protection; disband/retirement versus living Person continuity; no inert ruin collision or magical ownership; legacy factories operate. |
| Q28 | P8 | Extend cycle/history tests: three_production_replays_same_continuation | test_t125_cycles.py; test_t126_legacy.py; test_t127_full_cycle_continuity.py; test_t128_chronicle_pins.py; test_t129_path_selection.py | Future→Prehistoric reseeds factions, retires old military/research, new cycle layers/cubes; world coordinates/wizard memory/living people/items/puzzles persist; three-cycle hashes/pinned live references; no forced Utopia scope. |
| Q29 | P8 | New test_polish_continuity.py plus headed snapshot/actor comparisons | test_t014_persistence.py; test_t019_recovery.py; test_t064_handoffs.py; test_presentation_journeys.py | Before/after real quit/relaunch: Person/name, cart/cargo/journey ACK, soldier, hazard/visit, research/hand, diplomacy, era/history, meters, destroyed assets; next commands match uninterrupted control. |

Extend existing tests at the listed paths under tests/sim; names labelled new are planned additions, not existing green tests. Godot test scripts belong under godot_project/client/tests. Run the exact affected files plus the full `python -m pytest tests/sim -q` gate.

## Deterministic interactive procedure

Capture R01–R10. Use legally reached CP-ERA9VP from normal replay and perform recorded final funded action. Run FX-ERA separately as labelled diagnostic. Inspect transformed core, legacy site, same known Person/history. Save before/after era with real cargo, soldier, hazard, research and learned state; quit both client and sidecar, relaunch/load and compare next commands with uninterrupted branch. Reach/record later-era and cycle checkpoints with production replay; run three complete cycles in automated continuity tests using declared fast setups when necessary, clearly separating them from organic reachability. Bound normal searches; unreached checkpoint remains a blocking final journey gap, not a reason to writeVP.

## Screenshot manifest

All listed resolutions and named subframes are mandatory. Filename is `<ID>_<subframe-if-any>_<width>x<height>.png`. The CSV in the pack expands these into individual filenames. A QA companion is captured in a separate explicitly privileged session; it is never presented as ordinary player UI.

| ID / phase | Resolutions / subframes | Scene / fixture | Starting state | Exact actions | Expected visible result | PASS evidence | Obvious failure signs | Authoritative state evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R01 / P8 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-ERA replay-reached9VP; FX-ERA separately labelled diagnostic | Inspect relevant current centre/site before final delivery | Coherent place awaiting real completion; QA verifies9VP | Normal checkpoint has legal lineage; arranged fixture is labelled | VP written directly in purported normal journey | Full replay, ledger, old roster and winner9VP |
| R02 / P8 | 450×800; 1280×720 | FX-MVP / g05_shell | R01 | Perform manifest final accepted Wait/Travel; capture winning completion | Finished construction and beginning era cue | Exactly one threshold event; no later old-era actions | Transition delayed; extra production/attack/old draft after win | First winning receipt and stopped stage trace |
| R03 / P8 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | R02 | Capture existing transition at receipt-defined midpoint; test skip separately | Readable paused transition; same location; safe skip | Four-second/skip presentation does not reapply conversion | Labels under modal; tiny summary; double transition | Single atomic conversion; clock paused; one presentation token |
| R04 / P8 | 450×800; 1280×720 | FX-MVP / g05_shell | R03 completed | Inspect transformed core; capture | Same anchor with recognisable new-era civic/faction identity | Same core footprint and ID; no duplication | Shifted building; duplicate starter goods; missing people | Core/layer upgrades, starter-grant receipt, roster/policy/draft |
| R05 / P8 | 450×800; 1280×720 | FX-MVP / g05_shell | CP-LEGACY same transition branch | Travel along replayed route to surviving old non-core site; inspect | Old-era legacy marker and continuing old facilities | Site feels historical, operates legally, contributes no currentVP | Old site disappears; inert ruin collision; new-era rules applied blindly | Legacy flag, meter/recipe continuity, zeroVP and active old layers |
| R06 / P8 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | R04/R05 known surviving Person | Select same Person and open learned history | Same identity with appropriate changed affiliation/history | Knowledge persists; history explains known change without IDs | Person replaced; unknown private history revealed | Person ID/name/relations/lineage and filtered chronicle |
| R07 / P8 | 450×800; 1280×720; subframes: person, cart, unit, hazard, tech, history | FX-MVP / g05_shell | CP-SAVE with representative Person/cart+cargo/soldier/hazard/tech/history | Save through visible control; capture selected targets across suffixes person/cart/unit/hazard/tech/history | Representative world/UI state before quit | All six domains covered; tech exact hands only in QA companion | Empty cargo chosen as persistence proof; omitted domain | Q29 full independently enumerated before-state; save digest |
| R08 / P8 | 450×800; 1280×720; subframes: person, cart, unit, hazard, tech, history | FX-MVP / g05_shell | R07 saved snapshot | Quit Godot and sidecar; relaunch/load; repeat same six views and next command | Same entities and remembered world after load | Before/after fields and next-command hash match uninterrupted branch | New IDs; repeated arrivals/picks; lost diplomacy; reset meter | Q29 after-state, actor registry and command continuation hash |
| R09 / P8 | 450×800; 1280×720; subframes: before, trigger | FX-MVP / g05_shell | CP-CYCLE legally reached Future threshold; arranged regression separate | Capture pre-boundary and trigger as suffixes a/b | Future world and cause of final transition | Correct era/cycle; real political/economic precursor | Skin switch with no political state conversion | Old factions/military/research, layers, people/knowledge IDs |
| R10 / P8 | 450×800; 1280×720 | FX-MVP / g05_shell | R09 completed new Prehistoric cycle | Inspect same place/Person/history and new factions | Familiar physical world with new political competition and scars | New cycle is explicit; persistent identities/places recognisable | Everything resets; old army keeps marching; research carries unlawfully | Q28 roster reseed/retirements, fresh layers/cubes, persistent identity/world |

## State evidence

Pre/post full field snapshots and independent invariants: first-winner receipt, core anchors, lineage/successors/fission pair, asset/cargo disposition, Person survival/retirement, legacy meters, known-history provenance, policy/hand IDs, cycle world coordinates and retirement/reseed. Replay hashes and next-command hashes must agree after true reload.

## Regression checks

No repeated starter grant/transition/arrival/draft; no resurrected destruction or lost name; safe ruins/pathing; retained hazards per rule; all era hazard types; P3 conservation and P7 lease return. Three-cycle compaction/pinned references preserve live identities; historical IDs in QA never become raw player text.

## Acceptance gate

All required R sequences reviewed with authoritative continuity assertions. Normal funded threshold reached, era conversion/history understandable, and full-cycle reseed verified. Same-world identity survives travel, duel, battle, save and era/cycle boundaries. Every unresolved rare-event reachability claim is explicit and blocks final pass. Stop.

END OF P8. STOP AND REPORT EVIDENCE. Do not start the next phase.
````

### P9 — Golden journey, multi-seed robustness and final evidence

Copy everything in the following block.

````text
# P9 — Golden journey, multi-seed robustness and final evidence

You are implementing one gated phase of the existing DuelMasterBattle project. Complete only the named phase, preserve evidence, and STOP. Do not begin the next phase, merge, publish, or claim Joe's approval. Make small reviewable changes using existing services. No quest development, finished art, model retraining, player faction-command UI, replacement Ward Duel or parallel simulation.

Read MORNING_HANDOFF.md, docs/CANONICAL_GAME_ONTOLOGY.md, docs/INTEGRATED_RUNTIME_ARCHITECTURE.md, docs/review/PLAYER_WORLD_MODEL.md, current accepted decisions, Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md and the relevant C00/C03–C13 contracts. Precedence: this brief > accepted canonical decisions > current contracts/amendments > implementation > historical docs. Report a material unresolved design conflict instead of silently changing the rule. The wizard does not order factions and has no ordinary-army combat HP. People remain persistent; a soldier is a Person linked to UnitState/CombatantState. Worker motion is illustrative. Catan cargo is physical. Exact hands, AI scores, hidden strengths and production internals stay in explicit QA mode. Reuse semantic_visuals.py, content/source/presentation/semantic_visuals.json, semantic_placeholder.gd, visual_language.gd and world_layer_presenters.gd; shapes/text only.

Verify git SHA/tree, OS and project toolchain before editing. Preserve user work and saves; use an isolated worktree/save slot if needed. Do not reset to historical main. The base rule below identifies the required accepted predecessor. A missing approval means you may inspect/prepare a concrete handoff, but cannot call the gate accepted or begin its successor. Existing Gxx AUTO_READY is not owner PASS. Use a new tracking/polish ledger, keeping historical evidence intact.

Use the real production WorldSim and g05_shell with FX-MVP seed507. The Windows entry point is Play Latest Integrated Game.bat / tools/windows_playtest.py play-latest. Resolve the repository interpreter and Godot version first; run `python -m pytest tests/sim -q` in that environment. Use tools/run_visual_review.py and existing Godot harnesses, extended in place. Every phase runs its exact tests below and affected regressions; the full Python suite is cheap enough to run at the gate. Do not mask failures, skip substantive coverage or weaken canonical assertions for green output.

For EACH screenshot row below: capture 450x800 AND 1280x720. Responsive rows also require960x540 and any additional retained sizes. Rows with suffixes require every named subframe at every required size. Load the specified full production checkpoint, verify its replay hash, then perform the recorded real input through the actual shell. CP-* names are proposed IDs, not existing files. Record fixture/seed, entity IDs, local approach cells, control identity, actual pixel coordinate per resolution, accepted command receipts and precise Game Time advances in journey_manifest.json. Use state predicates/receipts plus rendering barriers, never a fixed delay as evidence of readiness. If a normal checkpoint remains unreachable, report the blocker; an explicitly arranged production fixture can diagnose it but cannot pass normal reachability.

Save under Pack/DuelMasterBattle_Build_Pack/tracking/polish/P9/SOURCE_SHA/ with manifest, commands.jsonl, full saves, state assertions, tests/logs, iterations/, final/, and review.md. Use a clean capture directory; reject missing/blank/stale/wrong-size images, wrong scenes, timeouts and engine errors. Personally open EVERY final image at native scale. Report filename, actual dimensions, expected condition, observed condition, PASS/FAIL/MANUAL REVIEW REQUIRED, visible problems, iteration count and fix/retest references. Fix visible defects and recapture affected sequences. Image existence/exit0 is not PASS. If you cannot inspect pixels, or cannot reliably judge readability, explicitly mark MANUAL REVIEW REQUIRED and leave that visual gate unaccepted. Do not infer state, reachability or persistence from pixels alone.

Normal witnesses must originate from recorded legal production commands/clock advances, with no direct writes to stocks, VP, units, hazards, diplomacy, positions or hands. Arranged tests are separately labelled. Extend existing run_long_world/evaluation tools for full reloadable saves/replays; summary snapshots are insufficient. Bound searches and report unreachable events rather than waiting indefinitely or inventing owner coordinates. Keep QA data inaccessible to ordinary player projections, not merely hidden by a panel toggle.

At completion report: base/final SHA and tree; changed files and reasons; exact tests and counts; each screenshot review; state/replay evidence; unresolved risks/design decisions; a short owner procedure. Separate automated readiness, manual review and owner acceptance. STOP after the phase. Do not amend the next phase's scope to avoid a failure.

## Required starting commit

Start at accepted P8 final SHA, with P0–P8 handoffs and source revisions linked. Verify no phase remains falsely marked accepted with missing evidence.

## Objective

Deliver one coherent, repeatable wizard experience with trustworthy evidence and a20–30-minute owner review.

## Current evidence

Use the polish ledger, all Q01–Q29 outputs, journey_manifest, CP-* replay saves, tools/run_long_world.py, existing full-world evaluation adapters, G11 capture harness and Windows launcher. Historical main was9c66ce00342698dc2900c9f7b03c18101221f799 with471/15 tests; final claims must cite the new tested SHA. tools/evaluate_mvp.py booting six seeds and stepping arranged FX-ERA is not organic victory evidence.

## Defects and gaps

Cross-system risks: individually working fixture demos can still collide in normal play; saved model fallback, rare stalled policies, event floods, repeat arrivals and late-era projection drift. Test gap: stale images, subset-only green suites or unreviewed pictures falsely presented as final acceptance.

## Implementation

Polish only defects exposed by the integrated journey and regressions; do not introduce new workstreams. Finalize normal production replay and complete checkpoint manifest with actual controls, local cells and pointer targets at each resolution. Curate owner save slots without replacing real seed/config lineage. Complete exact source-to-state-to-image manifests and clean final evidence index. Close all fifteen baseline regressions with justified contract-preserving fixes; no deleted assertions to hide missing mechanics. Retain all previously accepted narrow/landscape checks. Make Windows Play Latest launch the tested checkout and verify engine version. Keep executable packaging/certification a separate claim unless actually built and tested.

## Explicit non-goals

No new feature workstreams; no final-art/quest/retraining work; no untested executable/shipping claims. The common scope limits above also apply.

## Automated tests

| ID | Phase | Exact planned test / oracle | Existing coverage to extend | Required authoritative evidence |
| --- | --- | --- | --- | --- |
| Q18 | P5/P9 | Extend tools/run_long_world.py and training evaluation adapters; add executed-outcome report | test_training_budget.py; test_t143_t150_leadership.py | Paired fixed-seed committed behaviour, opportunity-normalized shares, no illegal/stalled runs; snapshots and SHA/model/config hashes; no fabricated win/screenshot-based distribution claim. |
| Q30 | P9 | Final golden journey replay/manifest validation and cumulative run | All tests/sim; affected Godot suites; tools/check.py; tools/run_g12_aggregate.py | Correct final SHA; replay-hash checkpoints; all required frames personally inspected; no missing/empty suites or unexpected skips; scoped invariants and owner review separate; Windows Godot launcher verified, packaging claim separate. |

Extend existing tests at the listed paths under tests/sim; names labelled new are planned additions, not existing green tests. Godot test scripts belong under godot_project/client/tests. Run the exact affected files plus the full `python -m pytest tests/sim -q` gate.

## Deterministic interactive procedure

From fresh FX-MVP507 perform recorded opening Observe/Talk/Travel, industry birth, round draft, loaded-cart delivery/construction, hazard treatment/recovery or Wizard Ward, actual conflict aftermath, save/reload and legal era checkpoint. Never force all rare events into one artificial five-minute run. Capture G01–G03 plus final-SHA recaptures of every previous mandatory sequence using same manifest IDs. Run six smoke seeds507–512 for60 turns with30000ms GameTime/turn, then paired heuristic/build/trade/war first20 fixed PROMOTION_SEEDS to200 turns or genuine early terminal. Record bounded/resumable wall-time budget and all failures; do not replace failing seeds. Run full sim suite, affected/cumulative Godot suites and tools/check.py/aggregate gates; inspect nonempty suite counts and unexpected skips. Finally execute Windows launcher and owner sequence against final SHA.

## Screenshot manifest

All listed resolutions and named subframes are mandatory. Filename is `<ID>_<subframe-if-any>_<width>x<height>.png`. The CSV in the pack expands these into individual filenames. A QA companion is captured in a separate explicitly privileged session; it is never presented as ordinary player UI.

| ID / phase | Resolutions / subframes | Scene / fixture | Starting state | Exact actions | Expected visible result | PASS evidence | Obvious failure signs | Authoritative state evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G01 / P9 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | Final accepted SHA; fresh507 | Replay owner opening using visible controls; capture | Readable whole game opening | Final output matches tested revision and manifest | Older screenshots copied into final folder | Final SHA/config hash and CP-START replay |
| G02 / P9 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | Final golden replay busy area after cart/industry/battle/duel returns | Return to same area and Inspect changed objects; capture | Causal activity, damage and people remain readable together | No cross-system label/control collisions or ghost actors | Individually good fixtures but broken combined scene | Merged actorID set, events/ACK dedupe and committed receipts |
| G03 / P9 | 450×800; 1280×720; 960×540 | FX-MVP / g05_shell | Final CP-SAVE/ERA branch | Load then open known history and map; capture | Continuous world and understandable historical change | Known-only facts and readable controls across transitions | Raw model/route IDs; missing names; hidden-history leak | Final persistence/knowledge/lineage and image inspection report |

## State evidence

Final commit/tree/content/model hashes; replay checkpoint hashes; full field and next-command comparisons; per-seed eligible opportunities/proposals/committed outcomes, unit/battle/treatment/VP/catastrophe/stall metrics. Require zero illegal actions/crashes/hidden reads/lost assignments, no unexplained10-seat inactivity with feasible useful action, and specialist≥0.10 pairwise distinction in executed-family shares with sufficient opportunities. Low opportunity is INCONCLUSIVE, not PASS or permission to retrain.

## Regression checks

Re-run Q01–Q29 on final source where code changed and all mandatory cumulative suites. Recapture dynamic sequences on final SHA; historical phase images remain iteration history, not final evidence. Include player-information boundary, goods conservation, Person continuity, all six technology consumers, alliances, hazard exclusivity, retained Ward and full-cycle retirements. No art/quest/management UI expansion.

## Acceptance gate

Zero failing required tests, no missing/uninspected/wrong-size frames, no unreachable mandatory normal checkpoint, no unresolved critical/high defect, no unjustified skip or false trained-policy claim. All planned authoritative oracles satisfied. Package ready evidence plus owner procedure; report MANUAL REVIEW REQUIRED for subjective criteria and leave Joe’s acceptance blank. STOP. Do not merge, ship or start another phase.

END OF P9. STOP AND REPORT EVIDENCE. Do not start the next phase.
````


## K. Final owner playtest — 28 minutes

This is the **post-implementation** owner test, not a claim that current main can complete it. Cursor must first supply the tested build SHA, working launcher, isolated save slots and a one-page route card generated from `journey_manifest.json`. Each card must name the actual place/character/control and show the actual approach route. Do not ask Joe to enter Python, inspect debug panels or wait indefinitely for a rare event. A checkpoint should load through the existing normal game loader; a clearly labelled QA launcher can choose the save, but must not become an in-game management screen.

For each segment mark **CLEAR / UNCLEAR / BLOCKED**, with one sentence about the moment of confusion. Cursor has already checked the arithmetic; Joe judges understanding and continuity.

| Time | What Joe does | Subjective questions |
|---|---|---|
| 0–3 min | Launch the final normal seed507 build. Move locally, select a nearby person, Observe/Talk, open map, Travel once. | Do I know where I am and how to leave? Are the shapes, selection and controls readable? Does this feel like a place? |
| 3–7 min | Load the replay-reached cargo checkpoint. Follow the route card from loaded cart to destination; see a funded site complete. Inspect the site/cart. | Can I tell what the cart carries and why it matters? Does construction feel caused by faction activity? |
| 7–10 min | At the industry checkpoint inspect a worker/yard, watch the prepared meter cross naturally, then meet the produced soldier. Read the nearby technological-change explanation. | Can I connect work to soldiers? Does technology feel like something factions are doing, without asking me to manage cards? |
| 10–14 min | Load the hazard-response checkpoint. Inspect stopped work/cart, advance the recorded faction seat, see soldiers treat the danger and activity recover. | Did I notice the problem, the response and its economic consequence? Do factions seem to act for themselves? |
| 14–18 min | Load the frontier checkpoint; witness contact and its prepared short battle/aftermath. Inspect a damaged site or surviving person. | Can I tell who is hostile and why? Does conflict change the world? Am I still the wizard rather than an army commander? |
| 18–23 min | Load the Ward checkpoint, Observe/Challenge through the attached card, enter a ward in the full duel, play and return. If the duel runs longer, use the separately supplied mid-duel save to finish this review segment. | Does intervention belong in this world? Is the Ward board clean and usable? Does returning feel continuous, with a clear outcome? |
| 23–26 min | Save the current world, quit completely, relaunch/load. Revisit the selected person and changed object. | Do I recognise the same world and people? Did anything reset, duplicate, reappear or repeat? |
| 26–28 min | Load the legal near-era checkpoint; perform the supplied final action; inspect the transformed core and same known person/history. | Does this feel like history happening to the same world? Do important events stand out without overwhelming me? |

Finish with one answer: **Which moment still felt like a separate technical demo?** Capture that moment and return it to the relevant phase; do not respond by adding another dashboard.

Optional focused review, separate from the 28 minutes: 3–5 minutes each for a legacy-site return, Future→new Prehistoric reseed, or a narrow landscape/mobile session. These use verified checkpoints and test subjective historical/visual continuity, not hundreds of rule assertions. An unclear owner judgment is valid even when automated checks pass.

## L. Definition of Done

- [ ] Final source/tree/content/model hashes are recorded; the tested Windows `Play Latest Integrated Game` launches that source. Engine/interpreter versions are explicit. Linux/headless evidence is never described as Windows/executable certification.
- [ ] All required simulation tests pass; the 15 audited failures are individually closed with contract-preserving fixes. Required Godot suites contain actual tests, with no unexplained skips, errors or empty-success runs.
- [ ] Travel/Wait, RNG, Game Time, faction seats/rounds, rollback and save/load satisfy Q01–Q05 through real production commands. Every durable domain survives and next-command continuation matches the uninterrupted control.
- [ ] The normal seed507 journey has legally reached, replay-verified checkpoints for cargo/construction, industry/Person birth, drafting/effects, hazard response/recovery, conflict, Ward return, persistence and an era threshold. Arranged fixtures are identified separately. No direct state injection passes for normal reachability.
- [ ] Goods are conserved through reservation, source co-location, cargo, arrival, escrow, delivery, consumption, cancellation and destruction. No remote loading, free replacement fleet, premature construction, duplicate settlement or ownership capture.
- [ ] Factory accounting respects shared constraints, finite resources, damage, pauses and offscreen continuity. One manufactured Unit links to one living Person and one active formation. Actor movement never controls economic output.
- [ ] Seven-card faction drafting starts at every era, chooses once per completed round from one snapshot, passes/redeals correctly, applies prerequisites/caps and persists. All six technology categories change their actual authoritative consumers with correct scope; player evidence describes observed consequences.
- [ ] Saved policy assignments load the intended fixed artifacts; hidden information stays hidden, legal useful opportunities produce progress, and paired multi-seed reports establish specialist differences with sufficient opportunity. No retraining is smuggled into this pass.
- [ ] Allies do not fight; legitimate hostile contact uses one local or offscreen combat owner, retains consequences and respects wizard immunity. Military objectives and construction/proposal allowances follow their independent budgets.
- [ ] Hazard cadence, typed overflow and terminal conditions work in normal turns. Eligible treatment removes the selected cube and spends activation instead of movement/attack. Suppressed sources/transit resume only when their real blockers are gone.
- [ ] Actual pointer input operates shared wizard actions and the retained full Ward Duel. Selected-cube results/visit allowances are exact and idempotent; all outcome/reload branches return without ghost actors, hidden hitboxes or world-layer leakage.
- [ ] First 10 VP causes one atomic era conversion. Collapse/fission/core/legacy rules, living identities/history and subsequent full-cycle political reseed pass continuity oracles. Old military/research retire where specified; legacy industry remains lawful.
- [ ] Every screenshot/subframe exists at 450×800 and 1280×720; responsive cases include 960×540 and any additional existing sizes. Each is decoded, matched to source/state, personally inspected and individually reported. Missing, stale, wrong-state or uninspected images cannot pass.
- [ ] Dynamic systems have reviewed before/after sequences plus authoritative assertions. Final acceptance uses final-SHA captures, with earlier failed iterations preserved. No required MANUAL REVIEW item is silently turned into PASS.
- [ ] Essential controls have ≥48 logical-pixel targets, remain visible and usable by one pointer, and avoid label overlap. Persons/carts/archetypes/factions/hazards/scaffolds are distinguishable with shapes/patterns/text. Normal UI contains no privileged hands, model scores, hidden stock/strength or faction-order controls.
- [ ] All listed major events have a real outcome source and a tested visibility/salience decision. Notices deduplicate across refresh/reload and do not announce hidden facts or unexecuted intents.
- [ ] No critical/high integration defect remains open. Owner subjective review is recorded separately from automated readiness; Joe accepts or returns specific concerns. No phase starts its successor without an explicit request.
- [ ] Existing quests/puzzles are preserved as regressions; there is no quest-content, final-art, replacement-engine, replacement-Ward or management-HUD workstream.

## Audit appendix — reproducibility and limits

The final `git ls-remote origin refs/heads/main` recheck during report preparation still returned **9c66ce00342698dc2900c9f7b03c18101221f799**. The checkout remained clean. This report and its diagnostic scripts were written outside the game checkout; no implementation has begun.

### The 15 current failures

| Test group | Count | Observed reason | Planned disposition |
|---|---:|---|---|
| `test_t027_buildings` | 2 | Tests expect exactly six total unit definitions; catalogue now contains 13 across eras. | P4: test the correct era/archetype contract; do not delete legitimate content. |
| `test_t059_units`, `test_t061_movement`, `test_t067_military_ai`, `test_t073_responders` | 10 | Existing setup manually forms units that the current spawn path already autoformed, causing `already in formation`. The military-AI test therefore does not reach its intended hidden-information assertion. | P4/P5/P6: repair setup using real formation APIs while retaining the one-membership invariant, then test the original behaviours. |
| `test_t078_village_projection` | 1 | Required exit reachability expectation fails against the changed full-world village projection. | P0 triage; P2/P7 restore intended playable exits or correctly scope archived fixture assertions. |
| `test_t090_sluice`, `test_t095_village_panel` | 2 | Expected sluice mechanisms are absent from the fixture being loaded. | P7: distinguish archived FX-VILLAGE-QUEST from current FX-MVP; preserve actual puzzle regression, no new quest work. |

Exact test names, tracebacks and counts are in `audit/pytest-sim-full.log` in the ZIP. These are failures, not evidence that every affected gameplay rule is wrong. Conversely, the newly reproduced command/save/wiring bugs are not excused by the 471 passing tests.

### Reproducing the diagnostic evidence

Use an environment with the repository's Python dependencies and NumPy. From the extracted pack, the read-only probes accept a checkout path:

```bash
python audit/production_probe.py /absolute/path/to/DuelMasterBattle
python audit/persistence_probe.py /absolute/path/to/DuelMasterBattle
```

The first probe wraps the production dice method only to record its returned values; it does not change the return or RNG algorithm. Normal commands, the direct-runner diagnostic control, and arranged treatment/technology experiments are separately labelled. The second arranges a real draft acquisition and war through production services, then uses `SaveCoordinator`/`SaveRepository` to save and load. Probe outputs are written beside the scripts and the diagnostic save goes in `audit/probe_saves/`; use a scratch copy if preserving the enclosed originals.

The complete test command used in this audit was:

```bash
PYTHONPATH=/workspace/scratch/835608356cae/dmb-test-env/lib/python3.12/site-packages \
  python3 -m pytest tests/sim -q --disable-warnings
```

That PYTHONPATH was an audit-only dependency arrangement, not a recommended project setup. The first attempt failed collection because its interpreter lacked NumPy; only the subsequent complete 486-test run supplies the reported 471/15 result. Generated compiler-test output was restored/moved out of the checkout afterward.

The seven inspected historical images are included under `audit/historical_G11/` with a dated review index. They establish the described visible issues at the time of capture. They do not prove current pointer input, natural encounterability, mode transitions, true return cleanliness or final acceptance. Screenshots of exact technology hands are privileged QA evidence and must never become the normal player UI.

### Pinned source index

All links below refer to the audited SHA, not a moving `main`. Source symbols and existing tests are starting points for Cursor; they do not substitute for the new production-path acceptance evidence.

| ID | Purpose | Pinned source files |
| --- | --- | --- |
| S01 | Current handoff and gate provenance | [MORNING_HANDOFF.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/MORNING_HANDOFF.md); [Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md) |
| S02 | Canonical ontology, accepted decisions and architecture | [docs/CANONICAL_GAME_ONTOLOGY.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/docs/CANONICAL_GAME_ONTOLOGY.md); [docs/review/JOE_DESIGN_DECISIONS.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/docs/review/JOE_DESIGN_DECISIONS.md); [docs/INTEGRATED_RUNTIME_ARCHITECTURE.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/docs/INTEGRATED_RUNTIME_ARCHITECTURE.md); [docs/review/PLAYER_WORLD_MODEL.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/docs/review/PLAYER_WORLD_MODEL.md) |
| S03 | Scope, time, board, logistics and industry contracts | [Pack/DuelMasterBattle_Build_Pack/contracts/C00_scope.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/contracts/C00_scope.md); [Pack/DuelMasterBattle_Build_Pack/contracts/C03_time.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/contracts/C03_time.md); [Pack/DuelMasterBattle_Build_Pack/contracts/C04_board_building.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/contracts/C04_board_building.md); [Pack/DuelMasterBattle_Build_Pack/contracts/C05_logistics.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/contracts/C05_logistics.md); [Pack/DuelMasterBattle_Build_Pack/contracts/C06_industry.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/contracts/C06_industry.md) |
| S04 | Normal fixture, world bootstrap and setup | [sim/dmb/testing/fixtures.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/testing/fixtures.py); [sim/dmb/world/prehistoric_world.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/world/prehistoric_world.py); [sim/dmb/world/setup.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/world/setup.py); [sim/dmb/world/industry_bootstrap.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/world/industry_bootstrap.py) |
| S05 | Authoritative command/state/turn boundary | [sim/dmb/core/world.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/core/world.py); [sim/dmb/core/state.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/core/state.py); [sim/dmb/time/turns.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/time/turns.py); [sim/dmb/time/clock.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/time/clock.py) |
| S06 | Catan, stock, carts, trade and construction | [sim/dmb/construction/production.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/construction/production.py); [sim/dmb/construction/orders.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/construction/orders.py); [sim/dmb/construction/scoring.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/construction/scoring.py); [sim/dmb/logistics/stock.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/logistics/stock.py); [sim/dmb/logistics/carts.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/logistics/carts.py); [sim/dmb/logistics/director.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/logistics/director.py); [sim/dmb/logistics/trade.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/logistics/trade.py) |
| S07 | Industrial accounting and factory birth | [sim/dmb/industry/service.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/industry/service.py); [sim/dmb/industry/constraints.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/industry/constraints.py); [sim/dmb/industry/allocation.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/industry/allocation.py); [sim/dmb/industry/factories.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/industry/factories.py); [sim/dmb/industry/primary.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/industry/primary.py) |
| S08 | Autonomous decisions, observation, legal actions and diplomacy | [sim/dmb/ai/policy.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/ai/policy.py); [sim/dmb/ai/observation.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/ai/observation.py); [sim/dmb/ai/legal.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/ai/legal.py); [sim/dmb/ai/diplomacy.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/ai/diplomacy.py) |
| S09 | Draft and research effect definitions/consumers | [sim/dmb/technology/draft.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/technology/draft.py); [sim/dmb/technology/research.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/technology/research.py); [Pack/DuelMasterBattle_Build_Pack/contracts/C12_strategy_technology.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/contracts/C12_strategy_technology.md) |
| S10 | Hazard placement, suppression and response | [sim/dmb/hazards/service.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/hazards/service.py); [sim/dmb/hazards/responders.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/hazards/responders.py); [sim/dmb/hazards/queries.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/hazards/queries.py); [sim/dmb/hazards/propagation.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/hazards/propagation.py); [Pack/DuelMasterBattle_Build_Pack/contracts/C08_catastrophe.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/contracts/C08_catastrophe.md) |
| S11 | Military identities, movement and resolution | [sim/dmb/military/units.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/military/units.py); [sim/dmb/military/formations.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/military/formations.py); [sim/dmb/military/movement.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/military/movement.py); [sim/dmb/military/offscreen.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/military/offscreen.py); [Pack/DuelMasterBattle_Build_Pack/contracts/C07_combat.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/contracts/C07_combat.md) |
| S12 | Integrated shell, local controller and wizard bridge | [godot_project/client/scenes/g05_shell.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/scenes/g05_shell.gd); [godot_project/client/scenes/g04_battle_shell.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/scenes/g04_battle_shell.gd); [godot_project/client/combat/local_battle.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/combat/local_battle.gd); [godot_project/client/encounters/duel_lease_adapter.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/encounters/duel_lease_adapter.gd); [sim/dmb/player/magic.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/player/magic.py); [sim/dmb/player/visits.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/player/visits.py) |
| S13 | People, learned semantic knowledge and personal tools | [sim/dmb/people/registry.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/people/registry.py); [sim/dmb/narrative/semantic.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/narrative/semantic.py); [godot_project/client/ui/inventory_panel.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/ui/inventory_panel.gd); [godot_project/client/ui/grimoire.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/ui/grimoire.gd); [Pack/DuelMasterBattle_Build_Pack/contracts/C09_people_dialogue.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/contracts/C09_people_dialogue.md); [Pack/DuelMasterBattle_Build_Pack/contracts/C10_adventure.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/contracts/C10_adventure.md) |
| S14 | Policy artifacts and evaluation tooling | [godot_project/content/policies/policy-im-build.json](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/content/policies/policy-im-build.json); [godot_project/content/policies/policy-im-trade.json](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/content/policies/policy-im-trade.json); [godot_project/content/policies/policy-im-war.json](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/content/policies/policy-im-war.json); [tools/evaluate_full_world.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/tools/evaluate_full_world.py); [training/datasets/promotion_seeds_loadable.json](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/training/datasets/promotion_seeds_loadable.json); [Pack/DuelMasterBattle_Build_Pack/contracts/C14_validation_release.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/contracts/C14_validation_release.md) |
| S15 | Eras, collapse/fission, legacy and full cycles | [sim/dmb/eras/service.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/eras/service.py); [sim/dmb/eras/planner.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/eras/planner.py); [sim/dmb/eras/collapse.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/eras/collapse.py); [sim/dmb/eras/fission.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/eras/fission.py); [sim/dmb/eras/cycles.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/eras/cycles.py); [sim/dmb/history/legacy.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/history/legacy.py); [sim/dmb/history/chronicle.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/history/chronicle.py); [Pack/DuelMasterBattle_Build_Pack/contracts/C11_eras.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/contracts/C11_eras.md) |
| S16 | Production persistence and migrations | [sim/dmb/persistence/coordinator.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/persistence/coordinator.py); [sim/dmb/persistence/repository.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/persistence/repository.py); [sim/dmb/persistence/migrate.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/persistence/migrate.py); [sim/dmb/core/state.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/core/state.py) |
| S17 | Shared semantic placeholder system and presentation contract | [sim/dmb/presentation/semantic_visuals.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/presentation/semantic_visuals.py); [godot_project/content/source/presentation/semantic_visuals.json](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/content/source/presentation/semantic_visuals.json); [godot_project/client/world/semantic_placeholder.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/world/semantic_placeholder.gd); [godot_project/client/world/visual_language.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/world/visual_language.gd); [godot_project/client/world/world_layer_presenters.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/world/world_layer_presenters.gd); [Pack/DuelMasterBattle_Build_Pack/contracts/C13_content_presentation.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/contracts/C13_content_presentation.md) |
| S18 | Visual capture and G11 report | [tools/run_visual_review.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/tools/run_visual_review.py); [godot_project/client/tests/run_visual_review_harness.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/tests/run_visual_review_harness.gd); [Pack/DuelMasterBattle_Build_Pack/tracking/gates/G11/visual_review/REPORT.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/tracking/gates/G11/visual_review/REPORT.md); [Pack/DuelMasterBattle_Build_Pack/tracking/gates/G11/visual_review/report.json](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/tracking/gates/G11/visual_review/report.json) |
| S19 | Retained Ward implementation and input/presentation regressions | [godot_project/client/scenes/game_board.tscn](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/scenes/game_board.tscn); [godot_project/client/scripts/game_board.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/scripts/game_board.gd); [godot_project/sim/battle_sim.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/sim/battle_sim.gd); [godot_project/client/tests/run_ward_duel_presentation.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/tests/run_ward_duel_presentation.gd); [godot_project/client/tests/run_g04_spellbook_pointer.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/tests/run_g04_spellbook_pointer.gd) |
| S20 | Normal launch and smoke evaluation | [Play Latest Integrated Game.bat](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Play%20Latest%20Integrated%20Game.bat); [tools/windows_playtest.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/tools/windows_playtest.py); [tools/evaluate_mvp.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/tools/evaluate_mvp.py) |
| S21 | Full-world diagnostics and production map projection | [tools/run_long_world.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/tools/run_long_world.py); [sim/dmb/world/world_map.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/sim/dmb/world/world_map.py); [godot_project/client/ui/world_map_panel.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/ui/world_map_panel.gd) |
| S22 | Source GDD; consult sections cited by contracts | [Pack/DuelMasterBattle_Build_Pack/source/GDD_v0.3.md](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/Pack/DuelMasterBattle_Build_Pack/source/GDD_v0.3.md) |
| S23 | Representative integration regressions | [tests/sim/test_canonical_ontology.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/tests/sim/test_canonical_ontology.py); [tests/sim/test_t041_draft.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/tests/sim/test_t041_draft.py); [tests/sim/test_t073_responders.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/tests/sim/test_t073_responders.py); [tests/sim/test_t127_full_cycle_continuity.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/tests/sim/test_t127_full_cycle_continuity.py); [tests/sim/test_t143_t150_leadership.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/tests/sim/test_t143_t150_leadership.py) |
| S24 | Responsive and era capture regressions | [tests/sim/test_t154_a11y_release.py](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/tests/sim/test_t154_a11y_release.py); [godot_project/client/tests/run_fx_era_layout_capture.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/tests/run_fx_era_layout_capture.gd); [godot_project/client/tests/run_fx_era_ui.gd](https://github.com/Joesalmon1985/DuelMasterBattle/blob/9c66ce00342698dc2900c9f7b03c18101221f799/godot_project/client/tests/run_fx_era_ui.gd) |

