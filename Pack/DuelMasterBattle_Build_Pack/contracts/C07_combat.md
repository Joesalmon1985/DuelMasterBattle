# C07 — Persistent soldiers, local battles and wizard magic

Source: GDD §§22, 51, 57–69, 188–190. Local tactics are real gameplay; off-screen simulation is the stated approximation, not an equivalent camera mode.

## Objects and APIs

| Class / logical file | Owns / methods |
|---|---|
| `MilitaryService` / `sim/dmb/military/units.py` | Create one UnitState per factory completion; `spawn`, `group`, `apply_casualties`, `receive_checkpoint` |
| `FormationDirector` / `military/movement.py` | Orders over unit-ID sets; `legal_objectives`, `activate`, `mark_withdrawal`; no real-time strategic travel |
| `CombatMath` / `military/math.py` and `client/combat/combat_math.gd` | Shared data/formula implementation tested with identical golden cases |
| `OffscreenBattleResolver` / `military/offscreen.py` | `resolve(snapshot) -> outcome`; deterministic bounded calculation, no global clock advance |
| `LocalBattleController` / `client/combat/local_battle.gd` | Leased 50 ms movement/LOS/target/attack steps; checkpoint and final outcome |
| `MagicService` / `sim/dmb/player/magic.py` | Validate local targets and route destruction/buff commands; apply cross-system effects once |
| `BuffService` / `military/buffs.py` | Effect IDs, remaining shield, expiry and stack caps; changes via lease when active |

`UnitState`: instance and definition IDs, faction, home settlement, strategic node, formation, alive flag, era-adjusted max/base health, current health, position, facing, target_id, remaining attack cooldown, entry strength, buff instances, lease_id/version. A corpse/tombstone keeps identity. `FormationState`: faction, ordered unit IDs, objective/node/path, engagement_id, movement_spent_turn, withdrawal target and status. Unit IDs may be in at most one formation and one encounter.

`BattleState`: id, node, participants/buildings, terrain snapshot, entry effective health per side, positions/cooldowns, state, step index, local/offscreen owner, pending reinforcement/destruction receipts, material_change_version. Multi-faction battles treat hostility as a graph; allied units do not attack each other. Target nearest hostile eligible combatant/building; never attack the wizard. Ordinary workers are not autonomous military targets in baseline combat, although wizard destruction can target them.

## Data baseline and damage

| Archetype | HP | Attack | Period ms | Range tiles | Speed tiles/s | Factory cost |
|---|---:|---:|---:|---:|---:|---:|
| Skirmisher | 60 | 10 | 1200 | 4 | 2.5 | 2 |
| Line | 100 | 15 | 1000 | 1 | 2 | 3 |
| Heavy | 180 | 25 | 1500 | 1 | 1.4 | 5 |

Apply era factor 1,10,100,1000 once to HP and attack. Store definition base attack separately from derived attack so it cannot be scaled twice. Base armour 0. Shared damage = max(1, round_half_up(base_attack × era_factor × attack_modifiers × (1−cover) − armour)). Cover is 0 or 0.25. Thus Prehistoric attack 15 into cover does 11; Historic does 113. Both implementations use these positive-value rounding cases, not language-default banker rounding.

Eligible attacks require range and line of sight. Choose nearest enemy, then lowest health, then ID. Step damage is gathered from living-at-step-start attackers, then applied simultaneously. Dead participants cannot act in the next step. Cooldowns decrement only with the appropriate encounter clock; fractional navigation uses deterministic quantized state at checkpoints.

Permanent compatible health technology updates effective max health while preserving current health proportion using a saved rounding remainder. It does not resurrect, restore shields or repeatedly heal when a projection refreshes. Unit-era compatibility is explicit; changing faction era does not upgrade old units.

## Strategic activation

Only the active faction's disengaged formations travel, at most two edges. Stop on first hostility. No roads required. New units produced during stationary Game Time can participate locally but cannot change node until a later eligible activation. Treatment consumes the responder's activation. Withdrawing units remain at their current node, cease their previous attack and move toward the reserved adjacent friendly node only at their next activation; revalidate or re-engage if blocked. Other forces can attack them meanwhile.

## Local and off-screen resolution

Local navigation, collision, terrain, range and real positions matter. C02 leases guarantee one owner. Buildings are real targets and obstacles; their destruction removes capacity/collision. Every visible soldier references a real UnitState. Rendering can omit distant sprites but not units or attacks.

Off-screen resolution begins from actual checkpoint state. Use 250 ms simulated combat steps; move toward valid range and use shared damage/cover/cooldown data. Hold buffs active at handoff constant during this instantaneous calculation, with their original global expiry retained afterward. No industry, reinforcements, quest time or global Game Time accrues. End when no active opposition remains, withdrawal occurs, unreachable groups stalemate, or 120 simulated seconds elapse. A timeout creates a saved stalemate. Re-run only on a new World Turn or material combat change.

Below 25% of entry effective health a side may withdraw if a passable friendly neighbouring node exists. Mark intent without immediate strategic movement. A group with no retreat path fights on. Attacker victory may destroy a centre but never assigns its ownership to the attacker. Report casualties/building damage with original IDs; sidecar commits consequences once. On Travel, close the outgoing local lease before the off-screen resolver starts. Wait retains local ownership. Exact casualty equality between attended/offscreen battles is not a test requirement.

## Wizard effects

Destruction: any selectable observed local ordinary unit (soldier, worker/civilian, cart) or building, any allegiance, one successful cast destroys it. A group label cannot destroy an entire group. No mana, accuracy roll or military immunity for targets. No remote map cast or self-target. Rival wizard/hazard actors use duels. The 250 ms recovery is input/visual debounce, not an economic cost. An already destroyed ID is an idempotent no-op; a new stale command gets appropriate public feedback.

Support on military units: shield +25% era-adjusted max HP, attack frequency +25%, or range +1 tile. Each application lasts 30 seconds of Game Time and has its own ID. Additive caps: remaining shields ≤2×max HP, frequency ≤3×baseline, extra range ≤4. Consume shields earliest-expiry first; expiry removes only remaining shield points. Buffs neither heal nor change armour. Duels/menus freeze duration.

The wizard has no faction-combat HP and cannot be harmed, expelled or defeated by armies. Destroying assets creates relationship/history/quest consequences. Building destruction displaces workers unless a separate explicit death is committed. Cart destruction loses actual cargo. C04 owns centre/warehouse consequences.

Required tests: individual identity/casualty conservation, repeated reinforcement, impossible lease overlap, target/allegiance matrix, shield cap and expiry order, fixed-step damage simultaneity, retreat without free travel, 120-second stalemate bound, and departure after losing half an army. Human gate G04 judges navigation, target readability and whether wizard intervention is satisfying.

## G04 amendment — MagicService validation

`MagicService` validates Destroy and Buff from current node membership, lease membership when applicable, knowledge-filtered visibility, and shared tile-unit interaction range (baseline two tiles) against synchronised local poses—including moving leased units and the wizard after SyncPose/checkpoint. Re-evaluate at commit. Caller-supplied `observed_ids` grant no authority and must not bypass same-node or range checks. A failed cast must not be repaired by a client-only kill or buff.
