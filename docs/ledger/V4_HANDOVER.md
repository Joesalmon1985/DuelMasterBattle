# V4 handover (branch `work/mechanics-completion-v4`)

Plan: `docs/PLAN_MECHANICS_COMPLETION_V4.md`. Decisions: `docs/DECISION_REGISTER.md` section 5 (D26-D32). Not merged to `main`. No neural-network work started.

## State at this handover
- Test suite: all green on the branch (run `python3 -m pytest WizardRTSHybrid/tests -q -n 2 -p no:cacheprovider --ignore=WizardRTSHybrid/tests/test_five_minutes.py`, about 13 minutes on 2 CPUs).
- Long games (`scripts/long_stability.py --minutes 120`, campaign profile, v2 draft, plus AI, diplomacy, nests): seeds 7 and 11 finished with no invariant failures (ware ledger, negative stocks, VP replay). Seed 7 ended in the Historic era with 8 factions, seed 11 in the Modern era with 7. Throughput about 9x real time late in the game. Nothing in these runs reached Dystopian.
- Hash baselines: `docs/perf/hash_baseline_v4.json` (showcase world, baseline AI, 3 seeds, 20 min) and `docs/perf/hash_baseline_v4_campaign_plus.json` (campaign profile, plus AI, 2 seeds, 20 min). `tests/test_hash_baseline.py` checks the first 3 minutes. A gameplay change must re-record them (`scripts/hash_gate.py record ...`) under a new label.

## Done (all pushed)
- **P1 cards and drafting.** `wizard_rts/content/cards.py`: 168 cards, four eras of 42, 1-4 entities each, essential-card tags, a perfect-matching audit (`graph.check()` returns `[]`). The dealer puts the era's essential cards a seat can use in its first pack (`draft.deal`). Short packs are topped up; bonus hands fall back to copies when the reserve is empty. The baseline AI picks generated cards by usability and missing capability (`tech._ai_pick_generated`). Monte Carlo test: `tests/test_draft_reachability.py`.
- **Faction floor (D28).** `history.MIN_FACTIONS = 6`, `MAX_FACTIONS = 8`, floor splits after `FLOOR_DELAY_MS`; a collapsed faction's pack returns to the reserve.
- **P0.** `state_hash` now also covers the raw building, unit, stock, worker, carrier, tech, stat, history and draft records. Baselines re-recorded. Vacuous assertions replaced. Stale status files carry a "superseded" banner.
- **P2 defects fixed.** Per-tribe ship cost; a failed sub-programme no longer resets the main programme (smelting works starvation); landmines are their own building kind; pillboxes carry their rifle; assemblers accept real unit and block payloads (tecta, collaris, quell, disrupt, vanquish, conquer buildable by delivery); five weaponless Mindustry combat units get tier-peer weapons; an aircraft with an empty ammunition pool stops attacking; fake OpenRA buildings excluded (D27).
- **P3 (OpenRA half of decision C).** `wizard_rts/ware_classes.py`: armour, tool and pack-animal wares of each tribe stand in for iron or planks in OpenRA recipes; the building asks for them when the warehouses hold them. Nothing blocks.
- **P4.** Faction command tier (`world._not_mine`, faction argument on queue/cancel/move/stop/rally/demolish/deploy/order/ability); minimal visibility layer (`wizard_rts/visibility.py`; observations list only what is seen or explored, attacks only on visible targets); `legal_actions` covers the faction's own `wl:` buildings and all `mdy:` machines; saves are versioned and hash-checked, with a fresh-process load test.

## Done since the last handover (not yet merged to main)
- Mindustry half of decision C: construction sites of `mdy:` blocks ask for the tribe's armour/tool wares in place of iron and animals in place of planks when the warehouses hold them, pay with them, and fall back to the raw wares after 120 s (`ware_classes.site_ask`, `construction._class_site`).
- Mindustry: doors open for their own faction and block enemies; armoured conveyors and ducts accept from non-conveyors only from directly behind.
- OpenRA: engineer repair (`ability repair`), Tanya C4 (`ability c4`), crushing by tracked and heavy wheeled vehicles, minimum range honoured on explicit attack orders.
- AI builds and recruits what its cards unlock (`ai_plus.unlocked_step`); `HybridEnv` has `era_max_ms` / `era_vp` for training pacing.
- Evidence catalogue generated (`docs/ENTITY_EVIDENCE.md/.json`, from a full junit run): 582 entities, 166 with no passing test that names them (down from 261). Widelands production sites have a 152-case sweep.
- Full suite: 1036 passed, 12 skipped. Hash baselines re-recorded after these rules changes.

## Not done (honest list, in suggested order)
1. **Evidence.** 166 entities still have no passing test that names them (`docs/ENTITY_EVIDENCE.md`); the L3/L4 completion gate of the plan is not met.
2. **Widelands.** Transfers are not re-routed when a road is cut; dismantling mid-carry and enhancement can lose booked stock; markets and sea trade are still flags; the Frisian recycling centre has no input producer; resident workers (decision E) are not done; machine feeding from a warehouse is missing.
3. **OpenRA.** Not modelled: chrono teleport of single units, spy disguise, parabombs, GPS, phase transport cargo; spread damage hits the primary target only; Mk2 variants lose abilities and Mk2 aircraft cannot rearm; no attack-unit, guard or stance command. (The spy plane and chrono support powers exist in `openra_abilities`.)
4. **Mindustry.** No unit abilities; plastanium and stack conveyor variants; payload router code unreachable; turret bullet effects and all ammo types; tractor beam; logic `control` gaps. `state_hash` is wider but turret ammunition, memory cells and pipe contents are not specifically asserted.
5. **AI use of content.** About half of the buildings the cards unlock are still unbuilt (limit: resources and affordability). Nothing reached Dystopian in 120 minutes; the era pacing study (decision G) was not run.
6. **Draft limits.** Historic readiness is about 92% for a sensible drafter; in rings above six the dealer hands out copies.
7. **Headed Godot proof, partly done.** PASS under Xvfb: walk, duel, forestry, food, war, terrain, campaign, campaign_dev, eras. FAIL under Xvfb (identical on `main`): visual, god, naval, playtest, wizard, mcv, industry, story, outbreak, inspector. They need a real display on the owner's machine.

## Resume
- Re-run the long game: `python3 WizardRTSHybrid/scripts/long_stability.py --minutes 120 --seed 7 --out ~/dmb_runs/stab7`.
- Re-record baselines after a rules change: `python3 WizardRTSHybrid/scripts/hash_gate.py record --out docs/perf/hash_baseline_v4.json --minutes 20` and `HYBRID_AI_POLICY=plus python3 WizardRTSHybrid/scripts/hash_gate.py record --profile campaign --out docs/perf/hash_baseline_v4_campaign_plus.json --seeds 507 11 --minutes 20`.
