# Joe’s playtest and handoff guide

You do not need to answer more game-design questions to start. Put the build pack beside the actual checkout and give the coding agent START_PROMPT.md. It will first verify the repository/branch and existing code, then work in order. If it lacks the checkout, that path or repository/branch is the first execution input it needs.

The default is a Windows desktop game with a bundled Python sidecar and Godot client. Android/mobile export is a later extension; single-pointer controls are built now. Existing compatible engine versions are audited and pinned. No game code was written or run while preparing this pack.

You should be asked to play at the following ten breaks, not after every task. Routine successful tasks continue automatically. A concrete access/tooling failure or an unexplained defect after three focused repair attempts may require an earlier short intervention.

| Gate | After | What you try | Suggested time |
|---|---|---|---|
| [G01](gates/G01.md) | T024 | Local controls, clocks and reliable startup | 10–15 minutes |
| [G02](gates/G02.md) | T048 | Autonomous factions, construction and carts | 15–20 minutes |
| [G03](gates/G03.md) | T058 | Industry and persistent workers | 15–20 minutes |
| [G04](gates/G04.md) | T076 | Battles, wizard power and catastrophe | 20–30 minutes |
| [G05](gates/G05.md) | T096 | The procedural village and quest test | 30–40 minutes |
| [G06](gates/G06.md) | T114 | Integrated MVP through Historic transition | 45–60 minutes; use supplied near-transition save for focused recheck |
| [G07](gates/G07.md) | T132 | All eras and repeated historical cycles | 25–35 minutes |
| [G08](gates/G08.md) | T142 | Narrative breadth, presentation and authoring tools | 30–45 minutes |
| [G09](gates/G09.md) | T150 | Trained faction leadership | 20–30 minutes plus review of evaluation summary |
| [G10](gates/G10.md) | T160 | Packaged full-baseline acceptance | 45–60 minutes |

G05 is your requested village-testing milestone. G06 is the complete playable MVP. G07–G10 finish the full baseline. A “working MVP” message does not close the remaining tasks.

At each gate the agent owes you a build that it has actually launched, a seed/save, simple steps, automated results and known defects. You should not have to diagnose raw stack traces before you can play. If it only supplies a list of classes or says the tests pass, ask for the gate packet.

To accept, reply “G05 PASS — build <identifier>” (substitute the current gate). To request fixes, say “G05 FIX_REQUIRED” and describe what you saw and expected. It will repair, rerun affected checks and bring back the same gate. You can also give a direct instruction revising a design choice; it must record that revision and update affected tests.

To resume with a fresh/low-context agent, provide the same folder and checkout and say: “Read AGENT_START_HERE.md and tracking/progress.json; resume the first unmet task and stop at the next manual gate.” Keep progress and receipts in the repository so context resets do not lose the build state.

If the agent reports BLOCKED, it must give the task ID, smallest reproduction, expected/actual result, attempted fixes, relevant files/logs and one next diagnostic. You can hand that packet to a stronger model without sending the whole project history. Do not reward a blocked run by allowing it to skip the failed acceptance requirement.

Training is the main empirical uncertainty. The pack includes bounded training, a held-out evaluation contract and three-policy acceptance, but no promise that any specific credit allowance produces competent networks. Missing target-platform tooling may also need a Windows runner or your Windows machine at packaging time. These are execution constraints, not unanswered game-design choices.

Full completion means all 160 task receipts, all ten explicit manual passes, all four eras and repeatable cycles, the complete catalogue/content baseline, three accepted trained policies and a tested offline Windows bundle. Utopia, mobile export, additional culture packs, full voice acting and expansion toward 100,000+ dialogue lines remain later optional work.
