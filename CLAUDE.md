# DuelMasterBattle — repository entry

The active development is the wizard-led hybrid in `WizardRTSHybrid/`. Start at `WizardRTSHybrid/CLAUDE.md` and `WizardRTSHybrid/AGENTS.md`. The approved direction is `docs/DuelMasterBattle_Design_v0_5.md`; the decision register is `docs/DECISION_REGISTER.md`.

The rest of this repository (`sim/dmb`, `godot_project`, `tests`, `DD`, `python_prototype`, older `docs/*`) is the earlier Catan-era game and its quest, dialogue, dungeon and Mastermind duel assets. Reuse them, do not delete them, and treat their economy/map rules as superseded (see `docs/CURRENT_STATUS_AND_GAPS.md` section 5). Root `README.md` is a historical Village Test note.

Approved programme (owner authorised an autonomous implementation run on 12 Oct 2026): `docs/PLAN_FULL_PROGRAMME_V2.md` (supersedes parts of `docs/PLAN_ECONOMY_TECH_ERA_PROGRAMME.md`). Its live state is `docs/ledger/LEDGER.md` (+ `RUNBOOK.md`, `QUESTIONS.md`) and the run report `docs/V2_RUN_REPORT.md`; the v2 and v3 work has since been merged into `main` (PRs #14, #15, #17).

**Direction change proposed 14 Oct 2026 (awaiting the owner's approval):** `docs/PLAN_HIERARCHICAL_NEUROEVOLUTION.md`. It freezes the imported content roster permanently (no new buildings, units, wares, items or liquids from Widelands, OpenRA, Mindustry or any other game; the content waves P6/P7/P9/P11 of plan v2 are superseded) and makes autonomous faction play by hierarchical neuroevolution the development priority. Until the owner approves, do not implement it and do not import content. Restart point for the implementer: `docs/NEXT_AGENT_HANDOFF.md`, first section.
