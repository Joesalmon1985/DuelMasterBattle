# Acceptance traceability

All rows are **specified, not executed**. Task evidence will be written in the real checkout. Source section coverage is also available in `source_coverage.json`; descriptive/NOT APPLICABLE sections do not require artificial mechanics.

## GDD Volume XXIII acceptance contracts

| Source contract | Owner | Main tasks | Fixture / human gate |
|---|---|---|---|
| Time and industry | C03/C06 | T012,T054–T058 | FX-CLOCK/INDUSTRY; G03 |
| Strategic movement | C03/C07 | T013,T042,T061,T067 | FX-CLOCK/BATTLE; G04 |
| Duel pause | C02/C03/C10 | T022,T074,T091,T092 | FX-CLOCK/VILLAGE; G04/G05 |
| Two ledgers | C04/C05/C06 | T029,T030,T049–T054 | FX-CARGO/INDUSTRY; G03 |
| Shared finite source | C06 | T050–T054,T057 | FX-INDUSTRY; G03 |
| Worker representation | C06/C09 | T028,T055,T058 | FX-INDUSTRY; G03 |
| Persistent identities | C01/C09 | T007,T028,T077,T078 | FX-VILLAGE; G05 |
| Cargo | C05 | T030,T033–T038,T045 | FX-CARGO; G02 |
| Catalogue | C06/C13 | T049,T115,T141 | Catalogue validators; G08 |
| Military identity | C07 | T053,T059,T064,T068 | FX-BATTLE; G04 |
| Wizard actions | C07 | T065,T066,T068 | FX-BATTLE; G04 |
| Catastrophe visit | C08 | T072,T074,T075,T092 | FX-HAZARD; G04/G05 |
| Catastrophe cascade | C08 | T069–T075 | FX-HAZARD; G04 |
| Immediate era end | C03/C11 | T013,T032,T046,T104 | FX-ERA; G06 |
| Transition continuity | C11 | T097–T106 | FX-ERA; G06 |
| Ruins | C04/C11 | T098,T106 | FX-ERA; G06 |
| Solo faction | C11 | T102,T106 | FX-SOLO; G06/G07 |
| Technology | C12 | T039–T041,T116 | Draft singleton/cycle; G02/G07 |
| Quest concurrency | C10 | T081–T086,T093 | FX-VILLAGE; G05 |
| Save and bridge | C02 | T014–T019,T092,T111,T152 | FX-RECOVERY; G01/G05/G10 |
| Touch usability | C09/C13 | T020–T024,T085,T107,T154 | Player verb matrix; G01/G05/G10 |

## All 34 source invariants

| GDD §9 invariant numbers | Controlling contracts | Proof responsibility |
|---|---|---|
| 1: no direct worker/army commands | C00/C12/C13 | Role-restricted commands and player verb UI; G04/G10 |
| 2–5: Travel/Wait/seat/round/draft | C03/C12 | T013,T020,T038,T041,T046; FX-CLOCK |
| 6: immediate 10 VP | C03/C11 | T032,T104; FX-ERA |
| 7–10: collapse/solo/core selection/inert ruins | C11 | T097–T102,T106; FX-ERA/SOLO |
| 11–13: legacy sites/people/geography continuity | C04/C09/C11 | T101,T103,T125–T130; FX-ERA/CYCLE |
| 14–16: separate namespaces/dice/shared deposits | C04/C05/C06 | T029,T049–T054; FX-CARGO/INDUSTRY |
| 17–18: node slot cap/all 60 recipes | C06/C13 | T049,T050,T115; catalogue validator |
| 19–20: global industry/animation independence | C03/C06 | T054,T055,T057; FX-INDUSTRY |
| 21–22: worker/cart/unit persistence | C01/C05/C07/C09 | T028,T033,T053,T064,T077; save/identity properties |
| 23–24: strategic travel/local tactics | C07 | T061–T068; FX-BATTLE |
| 25–26: wizard destruction/immunity/buffs | C07 | T065,T066,T068; target matrix and expiry tests |
| 27–28: duel freeze/visit treatment | C03/C08/C10 | T072,T074,T092; FX-CLOCK/HAZARD |
| 29: only ordinary terminal catastrophe | C08/C11 | T070,T075,T102; FX-HAZARD/SOLO |
| 30–31: offline content/prose cannot write truth | C01/C09/C10/C13 | T081,T084,T133,T141,T156 |
| 32: exclusive truth ownership | C01/C02 | T011,T018,T019,T064,T152; lease/crash tests |
| 33: quest-based colours/slots/Aspects | C09/C10 | T080,T091,T092; bounded once-only reward tests |
| 34: deterministic replay including policy choices | C01/C03/C12 | T010,T111,T130,T143–T157; recorded input/time/manifest/policy replay |

## Additional finish-line checks

Full baseline counts and substantive content branches: C13, T115–T142. Three qualified trained policies: C12/C14, T143–T150. Functional village authoring/testing tools: T095,T139,T140. Windows offline distribution: T155–T160. Optional extensions remain C00-scoped; they are not hidden failed baseline tasks.
