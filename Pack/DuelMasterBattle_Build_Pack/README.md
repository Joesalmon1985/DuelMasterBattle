# DuelMasterBattle — implementation build pack

**160 ordered task cards, 15 implementation contracts and 10 manual playtest gates.** This pack translates the supplied v0.3 design into a complete baseline-game build sequence. It contains specifications and reference data; it does not contain newly implemented game code.

Give your coding agent [START_PROMPT.md](START_PROMPT.md) and point it to [AGENT_START_HERE.md](AGENT_START_HERE.md). Keep this folder beside the actual checkout, or copy it into the repository's documentation area. The first tasks audit and map the actual branch before code changes. No further game-design answers are required to begin.

For you, use [OWNER_PLAYTEST_GUIDE.md](OWNER_PLAYTEST_GUIDE.md). For the full sequence, use [BUILD_SEQUENCE.md](BUILD_SEQUENCE.md). The agent uses [task_index.json](reference/task_index.json) and [progress.json](tracking/progress.json) to resume after context/session changes.

## What is included

| Folder/file | Purpose |
|---|---|
| `tasks/T001.md` … `T160.md` | Bounded scope, required reading, exact work, test oracles, receipt and next step |
| `contracts/C00` … `C14` | Classes, methods, records, ownership, clocks, protocol, economics, combat, narrative, era rules, AI, content and release |
| `gates/G01.md` … `G10.md` | Playable build requirements, human actions, expected observations, pass/fix procedure |
| `reference/fixtures.md` | Reproducible scenario setup and independent expected outcomes |
| `reference/resources.json`, `recipes.json` | Normalized reference data, including all 240 prior recipe/building/output names |
| `reference/source_coverage.json` | Every numbered source section mapped to implementation owners/tasks/gates |
| `tracking/` | Initial progress plus repository, handoff and defect templates |
| `source/` | Unchanged v0.3 design and original recipe workbook |
| `PACK_VALIDATION.md` | Checks performed on this document pack, distinct from future game tests |

The MVP is accepted at G06. The later phases complete Modern/Future, repeated cycles, all catalogue/content requirements, authoring tools, three evaluated neural policies and a Windows desktop package. Utopia, mobile exports, additional culture packs, full voice acting and very large corpus expansion remain optional extensions.

The current repository/branch was not attached. Its actual classes, engine versions and existing test health therefore remain unverified; T001–T004 explicitly resolve that before migration. Technical implementation defaults are listed in C00, including small content release floors and desktop packaging. They are distinguished from your locked design decisions.

This sequence supports a long autonomous run broken by reviewable checkpoints. It does not guarantee that a particular model or credit budget will finish every stage. Training quality, play quality and target-platform builds must pass their real gates.
