# DuelMasterBattle — Agent operating instructions

You are implementing the attached v0.3 design through the ordered build pack. Start or resume at the first unmet task in `tracking/progress.json`. **Do not implement the whole GDD in one response.** Execute one task, verify it, record evidence, then continue automatically until a required human gate or concrete blocker.

## First run

1. Read this file, `contracts/C00_scope.md`, `tracking/progress.json` and `tasks/T001.md`.
2. Ground the actual checkout and branch. Read applicable repository instructions. Preserve dirty files and prototype saves. Do not guess a repository/branch from old conversation context.
3. T001–T004 create the repository map, reuse audit and supported verification commands. The pack's code paths are proposed logical destinations until mapped. Reuse compatible existing modules, especially duels and puzzles.
4. Do not mark audit, implementation or tests complete because this pack describes them. All task statuses begin NOT_STARTED.

## Each task

Read its card, its named contract, the preceding receipt, relevant file excerpts and required current test/fixture definitions. Target ≤6,000 input tokens before editing. Do not read all task cards or the 4,465-line design into every context. Search symbols, then read the exact implementation boundary. Consult another contract only when the interface it owns is needed.

Implement every acceptance condition inside the permitted scope. Preserve state ownership, IDs, clocks, costs, knowledge filtering, receipts and save fields. No independent fixture quest engine, replacement simulation or fake economic result. Required boundary integration belongs in the same task receipt. Add meaningful tests proving changed behaviour; no trivial tests merely mirroring private methods.

Use mapped `python tools/check.py --task Tnnn` after T004. Client changes also require appropriate Godot import/scripted scene checks. Store actual commands, test results, fixture/manifest hashes and code revision. A command that discovers zero required tests, or skips them, does not pass. Do not weaken an assertion to make a failure disappear.

Record `tracking/handoffs/Tnnn.json` using the supplied receipt template. Update task status and next task. Commit task-owned work under repository instructions, excluding unrelated user changes. Continue immediately after successful tasks without asking Joe whether to proceed.

## Resume after context exhaustion or interruption

Read this file, progress, current card and most recent receipt. Verify the checkout revision and working changes against the receipt. In-progress code is not assumed correct; run the relevant checks and continue from its documented substep. Do not replay previously successful destructive commands, source grants, migrations or content generation blindly. A changed manifest invalidates affected evidence.

If a task is too large for one context, record numbered substeps inside the same task and resume them serially. Do not lower its acceptance bar. Do not spawn parallel implementation workers by default; shared contract changes need a single owner.

## Human gates

Required stops occur after T024, T048, T058, T076, T096, T114, T132, T142, T150 and at T160. Each has a guide in `gates/`. Prepare a playable candidate, seed/save, exact launch steps, automated report, code/content hashes and known defects. Mark AWAITING_HUMAN, tell Joe which gate is ready, and stop.

Only an explicit Joe PASS for the identified build clears a manual gate. Silence, a screenshot, headless import or your own judgement does not. FIX_REQUIRED reopens affected tasks; fix and rerun relevant checks/manual steps. Do not invalidate all earlier gates for unrelated minor changes, but record and retest any affected accepted behaviour.

For G10, T160 remains WAITING_HUMAN until Joe accepts the final candidate; then complete its receipt and the build ledger. Other gate-preparation tasks can be DONE while their gate remains AWAITING_HUMAN. Later tasks are blocked either way.

## Failures and design changes

Try up to three focused repairs for the same unexplained failure. If unresolved, stop with task ID, smallest reproducer, expected/actual behaviour, last valid commit, relevant logs/files, attempted fixes and one next diagnostic. Do not consume an unlimited run by repeating the same failed approach. Joe can route that report to a stronger model.

Do not disguise balance changes as bug fixes. Use existing TUNABLE fields and record before/after evidence. New mechanical assumptions must be identified against C00/GDD and recorded; a conflict with a LOCKED decision requires Joe's explicit revision. A missing executable/platform/checkout can block that task; report exactly what is absent while preserving completed work.

## Non-negotiable ownership

Python owns persistent world truth; Godot owns rendering/input/local movement and explicitly leased encounters. Worker animations do not drive production. Catan cargo and industrial flow are separate. Every worker, soldier and cart retains identity. The wizard is immune to faction military and can destroy any local ordinary unit/building. Only Travel/Wait advance strategic turns. Duels pause the world. NPCs/active quests survive era changes. Runtime has no LLM/network service dependency.

Read `docs/INTEGRATED_RUNTIME_ARCHITECTURE.md` before any cross-system village,
industry, logistics or quest work. Fixtures arrange production state; they must
not invent parallel gameplay semantics. ONE person ID = ONE visible actor.

## Completion

G06 accepts the integrated MVP. Full baseline completion requires all 160 tasks, all ten human gates, all four eras/full cycles, 240 recipes, full baseline content, three genuinely accepted trained policies and a tested Windows desktop bundle. Optional Utopia/mobile/culture/voice/content-scale extensions remain explicitly deferred. Do not call a stub, untrained model or untested export finished. Do not publish externally unless Joe separately asks.
