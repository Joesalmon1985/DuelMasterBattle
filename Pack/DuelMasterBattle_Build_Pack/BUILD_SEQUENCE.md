# Ordered build sequence

Every task is initially NOT_STARTED. All path mappings and code evidence must be produced in the actual checkout. Tasks form a strict dependency chain; the explicit human gates also block later work.

| Task | Work | Manual stop after |
|---|---|---|
| **P00 — Ground the actual project** | | |
| [T001](tasks/T001.md) | Identify checkout and protect the baseline |  |
| [T002](tasks/T002.md) | Classify reuse and reconcile existing duel rules |  |
| [T003](tasks/T003.md) | Pin tools and run existing checks |  |
| [T004](tasks/T004.md) | Establish mapped layout and verification entrypoints |  |
| [T005](tasks/T005.md) | Register implementation defaults and versioned manifests |  |
| [T006](tasks/T006.md) | Create executable progress and failure receipts |  |
| **P01 — Authoritative core and persistent state** | | |
| [T007](tasks/T007.md) | Implement typed identity and deterministic allocation |  |
| [T008](tasks/T008.md) | Implement immutable definitions and catalogue validation |  |
| [T009](tasks/T009.md) | Implement WorldState registries and read views |  |
| [T010](tasks/T010.md) | Implement gameplay RNG streams and replay inputs |  |
| [T011](tasks/T011.md) | Implement transactions, commands and event receipts |  |
| [T012](tasks/T012.md) | Implement clock tokens and fixed accounting boundaries |  |
| [T013](tasks/T013.md) | Implement turn roster and immediate outcome interrupts |  |
| [T014](tasks/T014.md) | Implement versioned save repository and migration boundary |  |
| **P02 — Bridge and first playable shell** | | |
| [T015](tasks/T015.md) | Implement framed message codecs |  |
| [T016](tasks/T016.md) | Implement loopback server and authenticated handshake |  |
| [T017](tasks/T017.md) | Implement sidecar launcher and WorldClient |  |
| [T018](tasks/T018.md) | Implement lease registry and checkpoint validation |  |
| [T019](tasks/T019.md) | Coordinate saves and bounded bridge recovery |  |
| [T020](tasks/T020.md) | Build pointer-driven local movement and exits |  |
| [T021](tasks/T021.md) | Implement semantic views and hidden-information filtering |  |
| [T022](tasks/T022.md) | Wire UI pause, focus and clock scheduling |  |
| [T023](tasks/T023.md) | Create the normal-runtime fixture loader and launch panel |  |
| [T024](tasks/T024.md) | Prepare the first playable bridge checkpoint | G01 |
| **P03 — Board, construction and physical cargo** | | |
| [T025](tasks/T025.md) | Build exact hex-node-edge topology |  |
| [T026](tasks/T026.md) | Generate validated faction starts and immutable geography |  |
| [T027](tasks/T027.md) | Define baseline settlement, building and unit records |  |
| [T028](tasks/T028.md) | Implement persistent people and job identity foundation |  |
| [T029](tasks/T029.md) | Implement Catan roll grants and source suppression queries |  |
| [T030](tasks/T030.md) | Implement conserved stores and reservations |  |
| [T031](tasks/T031.md) | Implement legal placement and derived VP |  |
| [T032](tasks/T032.md) | Implement delivered construction orders and completion |  |
| [T033](tasks/T033.md) | Implement persistent carts and load/unload transitions |  |
| [T034](tasks/T034.md) | Implement routes, permissions and turn movement |  |
| [T035](tasks/T035.md) | Implement transport assignment, reroute and returned cargo |  |
| [T036](tasks/T036.md) | Implement real construction bootstrap and replacement carts |  |
| [T037](tasks/T037.md) | Implement centre, warehouse and road destruction consequences |  |
| [T038](tasks/T038.md) | Integrate construction and cargo turn stages |  |
| **P04 — Technology, diplomacy and heuristic factions** | | |
| [T039](tasks/T039.md) | Define technology cards and prerequisite graph |  |
| [T040](tasks/T040.md) | Implement research archive and scoped modifiers |  |
| [T041](tasks/T041.md) | Implement simultaneous seven-round draft |  |
| [T042](tasks/T042.md) | Implement legal observations and candidate generation |  |
| [T043](tasks/T043.md) | Implement deterministic heuristic leadership |  |
| [T044](tasks/T044.md) | Implement diplomacy and transit agreements |  |
| [T045](tasks/T045.md) | Implement bilateral trade and escrow |  |
| [T046](tasks/T046.md) | Integrate active faction choices and round completion |  |
| [T047](tasks/T047.md) | Prove autonomous expansion without injected stock |  |
| [T048](tasks/T048.md) | Prepare faction and cargo playtest gate | G02 |
| **P05 — Real-time industrial economy** | | |
| [T049](tasks/T049.md) | Normalize resource and recipe catalogues |  |
| [T050](tasks/T050.md) | Implement shared finite layers and primary channels |  |
| [T051](tasks/T051.md) | Implement installed route selection and constraint construction |  |
| [T052](tasks/T052.md) | Implement deterministic progressive-fill allocation |  |
| [T053](tasks/T053.md) | Implement factory meters and individual unit creation |  |
| [T054](tasks/T054.md) | Integrate global Game-Time industry |  |
| [T055](tasks/T055.md) | Connect real workers to illustrative production activity |  |
| [T056](tasks/T056.md) | Implement paid industrial repair and route expansion |  |
| [T057](tasks/T057.md) | Build causal industry and depletion regression scenarios |  |
| [T058](tasks/T058.md) | Prepare economy readability playtest gate | G03 |
| **P06 — Military and world magic** | | |
| [T059](tasks/T059.md) | Complete individual unit, formation and buff state |  |
| [T060](tasks/T060.md) | Implement shared combat math and targeting oracles |  |
| [T061](tasks/T061.md) | Implement strategic formation movement and withdrawal |  |
| [T062](tasks/T062.md) | Implement bounded off-screen battle resolution |  |
| [T063](tasks/T063.md) | Implement Godot local tactical encounter |  |
| [T064](tasks/T064.md) | Implement arrival, departure and reinforcement handoff |  |
| [T065](tasks/T065.md) | Implement unrestricted local destruction magic |  |
| [T066](tasks/T066.md) | Implement stacking support buffs and pause-safe expiry |  |
| [T067](tasks/T067.md) | Connect military objectives and turn battles |  |
| [T068](tasks/T068.md) | Add battle and magic continuity scenarios |  |
| **P07 — Catastrophe and distributed pressure** | | |
| [T069](tasks/T069.md) | Implement typed cubes, deck and seeded initial pressure |  |
| [T070](tasks/T070.md) | Implement bounded outbreak propagation and terminal state |  |
| [T071](tasks/T071.md) | Wire source and cart disruption to real hazards |  |
| [T072](tasks/T072.md) | Implement persistent catastrophe visits and allowance checks |  |
| [T073](tasks/T073.md) | Implement faction treatment instead of movement |  |
| [T074](tasks/T074.md) | Integrate catastrophe manifestation entry with duel lease |  |
| [T075](tasks/T075.md) | Build pressure, ordinary failure and terminal scenarios |  |
| [T076](tasks/T076.md) | Prepare battle and catastrophe playtest gate | G04 |
| **P08 — Persistent village narrative** | | |
| [T077](tasks/T077.md) | Complete person goals, relationships and knowledge profiles |  |
| [T078](tasks/T078.md) | Implement stable village projection and layout overrides |  |
| [T079](tasks/T079.md) | Implement complete semantic observation and action filtering |  |
| [T080](tasks/T080.md) | Implement seven Aspects and repeat-safe checks |  |
| [T081](tasks/T081.md) | Implement typed condition AST and effect dispatcher |  |
| [T082](tasks/T082.md) | Implement persistent cause detection and quest binding |  |
| [T083](tasks/T083.md) | Implement quest state machine and invalidation |  |
| [T084](tasks/T084.md) | Implement offline dialogue catalogue and runtime fallback |  |
| [T085](tasks/T085.md) | Build attached speech and paused conversation UI |  |
| [T086](tasks/T086.md) | Wire the real shortage quest fixture and branch tests | *Historical — shortage scenario superseded for G05; keep tests as archived infra* |
| **P09 — Items, puzzles and personal duels** | | |
| [T087](tasks/T087.md) | Implement persistent inventory and unique ground objects |  |
| [T088](tasks/T088.md) | Implement item use, combinations and recovery routes |  |
| [T089](tasks/T089.md) | Implement leased puzzle mechanism runtime |  |
| [T090](tasks/T090.md) | Implement the sluice dungeon and bounded solution validator | *Implemented/tested infra; not exercised by current G05 narrative* |
| [T091](tasks/T091.md) | Complete retained Mastermind mechanics and progression |  |
| [T092](tasks/T092.md) | Implement duel checkpoint, recovery and outcome revalidation |  |
| [T093](tasks/T093.md) | Complete both village solutions and persistent return loop | *Historical shortage Route A/B — superseded for G05 human gate* |
| [T094](tasks/T094.md) | Author and validate the MVP dialogue bank |  |
| [T095](tasks/T095.md) | Complete the village testing panel and failure bundles |  |
| [T096](tasks/T096.md) | Prepare generated village, quest and duel playtest gate | G05 — **current:** full world + boulder quest (not shortage/sluice) |
| **P10 — Immediate era transformation and survival** | | |
| [T097](tasks/T097.md) | Implement theoretical capacity ranking and transition plans |  |
| [T098](tasks/T098.md) | Implement multi-faction collapse and inert ruin disposition |  |
| [T099](tasks/T099.md) | Implement compact fission pairing and successor ownership |  |
| [T100](tasks/T100.md) | Implement Historic core upgrades and one-time bootstrap |  |
| [T101](tasks/T101.md) | Implement operational legacy sites and paid upgrades |  |
| [T102](tasks/T102.md) | Implement sole-faction and zero-faction recovery |  |
| [T103](tasks/T103.md) | Preserve quests, people and protected items through conversion |  |
| [T104](tasks/T104.md) | Integrate immediate transition, hazards and fresh roster |  |
| [T105](tasks/T105.md) | Present recognisable local upgrades and Chronicle facts |  |
| [T106](tasks/T106.md) | Build transition, legacy and singleton regression fixtures |  |
| **P11 — Integrated playable MVP** | | |
| [T107](tasks/T107.md) | Complete all player inventory, grimoire and knowledge screens |  |
| [T108](tasks/T108.md) | Build the integrated two-era sandbox scenario |  |
| [T109](tasks/T109.md) | Implement contextual onboarding and optional hints |  |
| [T110](tasks/T110.md) | Add prototype era art, audio and accessibility pass |  |
| [T111](tasks/T111.md) | Run cumulative MVP replay and persistence suite |  |
| [T112](tasks/T112.md) | Run six-seed MVP pacing and legality evaluation |  |
| [T113](tasks/T113.md) | Build a self-contained MVP desktop candidate |  |
| [T114](tasks/T114.md) | Prepare full MVP playthrough gate | G06 |
| **P12 — Full catalogue and later-era systems** | | |
| [T115](tasks/T115.md) | Enable complete four-era resource and processing catalogue |  |
| [T116](tasks/T116.md) | Define Modern and Future facilities, units and technology |  |
| [T117](tasks/T117.md) | Implement ordinary Historic→Modern→Future continuity |  |
| [T118](tasks/T118.md) | Implement pollution response and cleanup capabilities |  |
| [T119](tasks/T119.md) | Implement alien catastrophe and encounter content |  |
| [T120](tasks/T120.md) | Implement nuclear and hostile-machine catastrophe |  |
| [T121](tasks/T121.md) | Implement later-era local visuals and semantic transformations |  |
| [T122](tasks/T122.md) | Extend economy and combat checks to every era |  |
| [T123](tasks/T123.md) | Validate all hazard response and rollover combinations |  |
| [T124](tasks/T124.md) | Validate six-faction full-board progression |  |
| **P13 — Full cycles and sustained history** | | |
| [T125](tasks/T125.md) | Implement full-cycle political reseeding transaction |  |
| [T126](tasks/T126.md) | Implement relic, scar and contamination dispositions |  |
| [T127](tasks/T127.md) | Preserve living people, promises and items across full cycles |  |
| [T128](tasks/T128.md) | Implement Chronicle summaries with pinned references |  |
| [T129](tasks/T129.md) | Implement Utopia extension validation without adding content |  |
| [T130](tasks/T130.md) | Add multi-cycle replay and save-continuation tests |  |
| [T131](tasks/T131.md) | Profile long-run state growth and stationary armies |  |
| [T132](tasks/T132.md) | Prepare full-cycle playtest gate | G07 |
| **P14 — Complete baseline content and tools** | | |
| [T133](tasks/T133.md) | Build small-batch offline content authoring pipeline |  |
| [T134](tasks/T134.md) | Author shortage, transport, catastrophe and diplomacy templates |  |
| [T135](tasks/T135.md) | Author military, personal, discovery and conflicting-interest templates |  |
| [T136](tasks/T136.md) | Complete eight dungeon layouts and four recurring rivals |  |
| [T137](tasks/T137.md) | Complete and review baseline dialogue coverage |  |
| [T138](tasks/T138.md) | Complete four era art/audio families and asset provenance |  |
| [T139](tasks/T139.md) | Implement economy, technology, culture and policy inspectors |  |
| [T140](tasks/T140.md) | Implement quest, dialogue, semantic, puzzle and era tools |  |
| [T141](tasks/T141.md) | Run corpus, dependency and gameplay coverage validation |  |
| [T142](tasks/T142.md) | Prepare narrative and presentation playtest gate | G08 |
| **P15 — Train and qualify faction leadership** | | |
| [T143](tasks/T143.md) | Expose production simulation as a training environment |  |
| [T144](tasks/T144.md) | Generate heuristic trajectories and held-out seed splits |  |
| [T145](tasks/T145.md) | Implement candidate-scoring model and imitation training |  |
| [T146](tasks/T146.md) | Implement bounded actor-critic improvement and checkpoints |  |
| [T147](tasks/T147.md) | Implement local runtime neural inference with fallback |  |
| [T148](tasks/T148.md) | Evaluate policies against held-out paired baseline |  |
| [T149](tasks/T149.md) | Select three competent distinct leadership policies |  |
| [T150](tasks/T150.md) | Prepare neural leadership playtest and acceptance gate | G09 |
| **P16 — Release hardening and completion** | | |
| [T151](tasks/T151.md) | Audit full-source and player-verb coverage |  |
| [T152](tasks/T152.md) | Harden save corruption, crashes and content compatibility |  |
| [T153](tasks/T153.md) | Measure and fix release performance bottlenecks |  |
| [T154](tasks/T154.md) | Finish touch, display, audio and accessibility verification |  |
| [T155](tasks/T155.md) | Produce Windows sidecar and Godot release bundle |  |
| [T156](tasks/T156.md) | Run clean-machine offline installation tests |  |
| [T157](tasks/T157.md) | Run release scenario and multi-cycle regression suite |  |
| [T158](tasks/T158.md) | Write player guide, known limits and release evidence index |  |
| [T159](tasks/T159.md) | Assemble final manual acceptance candidate |  |
| [T160](tasks/T160.md) | Complete final playtest gate and close the build ledger | G10 |
| **P16 — Semantic placeholder completeness (overnight G11)** | | |
| [T161](tasks/T161.md) | Define semantic visual registry and completeness contract |  |
| [T162](tasks/T162.md) | Build placeholder gallery/catalogue scenes |  |
| [T163](tasks/T163.md) | Validate all runtime-visible content against the registry |  |
| [T164](tasks/T164.md) | Prepare G11 automated visual catalogue gate | G11 |
| **P17 — Unattended functional acceptance (overnight G12)** | | |
| [T165](tasks/T165.md) | Build complete automated journey manifest |  |
| [T166](tasks/T166.md) | Run multi-seed/full-cycle unattended regression |  |
| [T167](tasks/T167.md) | Build final evidence aggregation and failure diagnosis |  |
| [T168](tasks/T168.md) | Prepare G12 owner-review candidate | G12 |

**G10 overnight note:** for the authorised `phase/g06-g12-autoqa` run, G10 is a functionally complete **semantic placeholder-art** baseline, not a production-art release (see EXECUTION_AMENDMENTS overnight section).
