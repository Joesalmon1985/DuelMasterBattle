# C12 — Technology and faction decision contracts

Source: GDD §§114–123 and technology handoff record. Strategy selects among legal actions; it never owns costs, combat or victory rules.

## Technology

`TechnologyCatalog` (`sim/dmb/technology/definitions.py`) loads `TechDef`: id, era, allowed_predecessor_ids, prerequisite_mode=`any_previously_activated`, effect kind/value, compatibility scope, repeatable flag, max stacks, pool weight and display keys. Validate references, acyclic activation and reachable baseline capabilities.

`TechnologyService` (`technology/research.py`): `acquire(faction,card_instance)`, `activate_eligible`, `effective_modifiers`, `inherit_to_successor`. Own `ResearchState`: owned card instances, active technology stacks, inactive archive, acquisition/activation receipts and prerequisite history.

`DraftService` (`technology/draft.py`): `deal`, `collect_choices(snapshot)`, `resolve_round(choices)`, `discard_for_era`. Own hand IDs, ordered card instances, seat ownership, pick index 0–6 and pool RNG. Card instances distinguish duplicate copies of the same definition.

Deal seven per faction with replacement at era start. At completed round each faction selects exactly one from its current hand based on one common pre-draft snapshot. Acquire all chosen cards, then activate eligible effects, then pass remaining hands clockwise in stable seat order. After seventh pick redeal seven immediately for future rounds. One faction passes to itself. Era interruption discards remaining hands without old-era picks.

Unplayable cards are still picked and archived. Activate once any listed predecessor has been validly activated in this faction's research history. An inactive archived predecessor does not qualify; a previously activated old-era predecessor still qualifies even when its effects do not apply to current-era assets. Drain newly enabled activations in topological order until stable. Nonstackable duplicates remain inert; baseline stackable cap 3. Old tech effects apply only to matching era assets and declared logistics scope. Fission copies history/research; new-cycle factions start new research.

Baseline six cards per era: +10% primary flow; +10% processor cap; +10% factory ceiling; +1 cart capacity; +10% unit health; +10% unit attack. Caps three copies. Prehistoric has no prerequisite. For each later era use predecessor pairs from previous era: primary←primary/processor; processor←processor/factory; factory←factory/primary; cart←cart/primary; health←health/attack; attack←attack/health. All baseline buildings/routes work without luck-dependent tech. Logistics bonuses apply to current faction carts as declared; old unit health/attack tech remains unit-era scoped.

## Policy interface

| Class / file under `sim/dmb/ai/` | Contract |
|---|---|
| `ObservationBuilder` / `observation.py` | `build(faction,decision_kind) -> ObservationV1`; immutable versioned public/own/observed state |
| `LegalActionGenerator` / `legal.py` | `enumerate(view,decision_kind) -> ordered ActionCandidate[]`; canonical IDs and action masks |
| `FactionBrain` / `interface.py` | `choose(observation,candidates) -> candidate_id`; one choice, no mutation |
| `HeuristicBrain` / `heuristic.py` | Deterministic scoring/ties, baseline policy |
| `ScriptedBrain` / `scripted.py` | Fixture-supplied legal choices; fails loudly if intended choice unavailable |
| `NeuralBrain` / `neural.py` | Pinned local candidate scorer; returns same contract with deadline/fallback |
| `PolicyService` / `policy.py` | Saved policy assignment and typed commitments; record actual selected choices |
| `DiplomacyService` / `diplomacy.py` | Relations, proposals/acceptance, hostility and transit permissions |

`ObservationV1`: current time/era/seat, own stocks/reservations/cargo, centres/roads/VP, installed route rates/bottlenecks, shared source availability, own units and observed enemies, public ownership/catastrophe/relations, hand/research, durable commitments, entry/lost military strength. Exclude wizard private knowledge/conversations and unobserved enemy tactical secrets. Fixed feature schema includes missing/observed masks rather than encoding unknown as zero.

`ActionCandidate`: id, action kind, bound stable IDs, typed parameters, legal preconditions/version, cost/delivery estimate, benefit features, expiry and debug explanation. Candidate generation is bounded and sorted; always include a legal no-op when the seat cannot act. Revalidate at commit. Illegal/stale neural output invokes the best legal heuristic, without free resources or expanded action allowance.

At one activation: at most one new construction order, one trade/diplomacy proposal, one objective per disengaged formation. Delivered pending construction completes for all factions through C03. Choice priorities: essential catastrophe response; action reaching 10 VP; restore missing core/industry; useful city/settlement/road/legacy upgrade; extra processor/military objective; mutually deliverable trade. Candidate scoring favours resource diversity, theoretical output and short delivery distance. Stable action ID resolves score ties.

Use a lexicographic priority tier, then this tunable integer utility for construction candidates: `1000 × current_era_VP_gain + 100 × new_Catan_good_types_accessible + 20 × target_best_pips + 10 × additional_milliunits_per_second − 5 × required_cart_edge_trips − 10 × new_road_edges_needed`. Quantize rate features once from the pure forecast. Do not give an unconnected settlement zero cost in that forecast. For a road, evaluate the best distance-legal future settlement reachable through that road, assign its forecast benefit, and subtract the remaining construction/delivery route costs. Generate a bounded goal path from an owned road network to that target and propose only its first unbuilt legal edge. Recompute next activation; the policy cannot build the whole path in one turn. This two-level goal/path rule prevents aimless road construction while preserving one-order limits. Retain a valid unfinished construction commitment unless ownership/legality or a higher emergency priority changes it.

Trade candidates compare the active chosen construction shortages of both parties. Enumerate integer quantities 1–4 of distinct Catan goods, constrained by unreserved source stock and real deliverable paths, and retain the best 32 by fulfilled shortage units then shorter total distance and stable ID. Accept only if both parties reduce a shortage and neither spends already committed goods. These weights/candidate limits are initial implementation defaults reviewed at G02/G06, not claims of balanced strategy.

Baseline military orders: defend threatened home, treat blocking catastrophe if eligible, assemble at a reachable frontier, attack an observed hostile target when own effective strength ≥1.25×known defending strength, otherwise hold. This is a tunable heuristic, not secret access to enemy state. Default diplomacy is neutral and trade-permitted; attacks establish war. Alliance proposal is accepted when both have a common observed hostile threat and no conflicting commitment. Commitments from quests carry priority, clock/duration and explicit bounds; they cannot disable engine survival/fission rules.

Voluntary fission with ≥4 sites and room below six factions: split if best compact core pairs have minimum inter-pair node distance ≥4 and losses <50% of entry effective strength; honour explicit eligible veto/encouragement commitments. Mandatory solo fission is not policy-controlled. At era start one seeded accepted policy is selected per faction and saved; do not let several brains issue concurrent orders.

## Neural training specification

Use the production simulator through a headless environment. One training decision batch advances 30 seconds of unpaused Game Time and the same legal World Turn transaction; no mocked economy or instant army. Episodes finish at era transition, terminal catastrophe or 1,000 turns. Reward: +10 triggering win, −10 collapse, −10 terminal catastrophe, +0.2 net VP gained (reverse on loss), −0.001 per activation. Resolve rewards for all affected factions at a transition, including a collapsed nonacting faction.

Start with imitation trajectories from heuristic policy, then actor-critic improvement on candidate scores. Initial suggested model: shared numeric observation encoder 128→64 units and candidate-feature encoder 64→32; concatenate embeddings and score each candidate with a 64-unit head, plus a value head for training. Variable candidate lists use masks; model never emits arbitrary IDs. This is an implementation baseline to measure, not a promised successful model.

Dataset records observation schema/hash, candidate list, selected legal action, reward/next state, seed, rule version and policy provenance. Split seeds before training; never train on promotion seeds. Train reproducible bounded jobs (initial 10,000 imitation decisions, then 20,000-decision improvement batches), checkpoint optimiser/model/RNG after each batch, and measure elapsed time. Stop a batch on budget, not by setting unlimited turns. Runtime loads only inference weights and schema; training dependencies are not bundled in the game.

Promotion is defined in C14: at least 200 paired fixed seeds, legal play, no worsened catastrophe rate and competitive 10-VP results. Retain three accepted, behaviourally different policies. If only one qualifies, report one; do not relabel heuristic clones or random initial weights as trained leadership. This phase can need iterations and is an explicit human checkpoint.
