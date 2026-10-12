# Owner's success criteria — long civilisation implementation run

Use this as the short acceptance sheet alongside `DuelMasterBattle_Claude_Autonomous_Civilisation_Implementation_Run.md`. This is an **evaluation target**; boxes remain unchecked until real evidence exists.

## Must be observable by the owner (normal AI + 16× God Mode)
- [ ] **Single command** launches a six-faction **spectator** game on Ubuntu; selecting a faction to inspect **does not disable its AI**.
- [ ] All six begin with primitive, real Widelands economies and visibly produce/carry construction goods.
- [ ] The AI builds useful new production chains, drafts era-appropriate technology, and card choices/unlocks/countdowns are readable. Draft hand contains **up to seven eligible options**.
- [ ] At least one **natural VP-driven** Prehistoric → Historic transition is shown on the same physical world with newly unlocked buildings/units. Later eras are observable in longer runs.
- [ ] AI creates and deploys MCVs, opens functioning new settlements, attacks, defends, recruits valid military, destroys settlements and receives correct VP.
- [ ] Real economic/political faction **splits and collapses** emerge in documented long-run cases without forced owner commands.
- [ ] Outbreak locations/types/cubes are labelled; outbreaks **measurably disrupt production or unrest**; a legal wizard agent can reduce cubes; the faction AIs take legitimate mitigations.
- [ ] Widelands mineral mines and Mindustry drills **never exhaust** suitable existing sites. Other genuine constraints (power, inputs, logistics, war) remain.
- [ ] No new Mindustry-only resource squares. No two independent economies or armament systems.
- [ ] Available appropriately licensed original Widelands/OpenRA/Mindustry art and animations used where practical; missing assets have readable placeholders.
- [ ] Wizard cannot walk through trees/rocks. Crowded passive labels and overlapping fire-magic responses fixed. Miner story, dungeon, duel and healer/outbreak interaction navigable manually without teleport cheats.

## Must be proven statistically
- [ ] 3-seed smoke campaign and 10+ seed long normal-game tournament, with exact SHA/config/seeds and all failures retained.
- [ ] Separate **peace, war, catastrophe and historical** modes; reports distinguish natural events from scripted fixtures or stall guards.
- [ ] Real-time plot of faction stocks/production, construction, VP/eras, armies, settlements, conflicts, splits, outbreak intensity and performance; per-faction CSV and full event log.
- [ ] All actual buildings/units have source-based, buildable/operational/AI-used/tested/visible coverage status; missing mechanics named. Importing a definition alone does not count.
- [ ] Deterministic replay, save/load, no negative inventory, no free unit production, idempotent VP/conquest and split accounting. Infinite source ledger for mineral inputs, conservation thereafter.
- [ ] Paired-seed balance report identifies genuine faults and demonstrates fixes with regression tests; battle winners may legitimately eliminate opponents.
- [ ] T460-headed evidence screenshots of primitive economy, tech drafting, later tech, MCV expansion, warfare, catastrophe and natural era advancement.

## Important scope reminder
The checked-in catalogue last had approximately 903 source definitions, of which a minority had actual behaviour; making **all** relevant Widelands/OpenRA/Mindustry buildings and units functional is a large multi-session project. **Don't mark this fully done** unless tests verify each type. A successful individual autonomous run may finish only part of that scope; its exact residual backlog must be published.
