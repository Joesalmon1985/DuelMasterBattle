# DuelMasterBattle — execution amendments

Authoritative supplement approved by Joe Salmon on 16 September 2026. These
instructions refine the v0.3 build pack without renumbering tasks or weakening
its contracts. Current explicit user instructions still have highest
precedence.

## Staged Python ownership cutover

Use a constrained version of preflight option B:

1. **T001–T006:** preserve and measure the existing Godot application.
2. **T007–T014:** build and verify the Python identity, state, command, clock
   and save core with isolated test worlds.
3. **T015–T024:** connect the normal launcher and a small playable G01 slice.
   In that running campaign Python exclusively owns durable world state.
   Disable the former Godot strategic tick, persistent mutation and campaign
   world-save writers for that runtime.

A temporary adapter may translate calls or projections, but Godot must not
simulate or save fields also owned by Python. Old code may remain as reference,
isolated regression tests or offline comparison. Do not expose an old-sim
backend in the new production entrypoint.

G01 certifies this migration slice, not complete village gameplay. G05 remains
the complete procedural village/quest/puzzle/duel gate.

## Toolchain and pack location

- Initially pin Godot 4.4.1, subject to T003 confirming the executable and
  baseline tests. Pin Python 3.12.3 and actual dependencies found by T003.
- Align Windows launchers and export templates with Godot 4.4.1. Record Windows
  verification separately; Linux does not certify Windows.
- Any engine upgrade is a separate measured and tested change.
- Keep and commit this pack at `Pack/DuelMasterBattle_Build_Pack/`.
- Keep one authoritative progress ledger under this pack's `tracking/`.
- Ignore only the duplicate root `DuelMasterBattle_Build_Pack.zip` and
  appropriate generated caches, logs, saves and build outputs. Do not delete
  them or broadly hide source assets.

## T001–T004 additions

T001 confirms `BuildPackV03` ancestry and records the immutable original base
`a0936dd41f00ee7393067b1f800411800175d23e`. Later task commits may advance
HEAD; do not rebase automatically.

T002 adds an ownership table for world position/turns, factions, Catan
stocks/carts, worker/NPC identity, quest outcomes, encounter results and
campaign saves. For each group record current mutation/save entrypoints, target
owner and command boundary, adapting callers, intended regression or v0.3
difference, disconnect task and proof that the old writer is disconnected.
RETIRE means after callers and regressions are handled, never bulk deletion.

T003 records exact commands, versions, exit codes and test counts. Attempt
existing normal launch, E17A/E36B village, puzzle, dialogue and save/load flows
where available. Preserve semantic behavioural expectations separately from
intentional v0.3 changes. A relevant failure or missing suite is not a pass.

T004 wraps real runners and preserves exit status. Unknown tasks, missing or
empty required suites, unexpected skips and subprocess failures return
nonzero. Do not create placeholder scenarios or miniature alternate
simulations. Use focused checks per task and cumulative suites at gates.

## Cursor and execution discipline

Use one implementation agent editing this branch at a time. The root rule
`.cursor/rules/dmb-build-pack.mdc` points to the current task, progress,
repository map and this amendment; it must not inline the GDD or task deck.

Continue automatically through dependency-ready tasks. For each accepted task,
record files/symbols, actual commands/results, defects, commit and next task;
commit only task-owned changes. Stop at manual gates, a material unresolved
design requirement or a concrete blocker after three focused repair attempts.
The blocker packet must include reproducer/seed, assertion/log excerpt,
expected versus observed state, suspected owner, changed files and attempted
fixes. Never weaken assertions to avoid escalation.

Meaningful behavioural checks accompany Godot import checks. All ten human
gates remain mandatory and only Joe's explicit PASS clears one.

## Strengthened G01 evidence

Before requesting G01, automated and manual evidence must establish:

- one valid Travel causes exactly one durable node change and World Turn;
- retransmission after a lost reply returns the same receipt without mutation;
- one Wait press causes one turn; holding it and invalid travel cause none;
- save, complete exit, relaunch and load preserve IDs, position, clocks and
  command receipts;
- sidecar stop/disconnect pauses the client with no fallback to Godot sim;
- checkpoint recovery reports rollback honestly with no duplicate result or
  catch-up time;
- former Godot strategic tick/save writers cannot run in the new runtime;
- lease checkpoint/result retransmission has exclusive ownership and
  exactly-once persistent consequences.

The authenticated loopback Python/Godot bridge is permitted. "No network at
runtime" means no internet or LLM dependency.
