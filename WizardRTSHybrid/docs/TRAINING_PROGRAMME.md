# Training programme: a faction controller that learns to play the real game

Goal (Joe): a neural network that controls a faction the way Joe does in God Mode, expands with MCVs, builds an economy, fights.
Status: the **interface and evaluation framework are ready and measured**; no claim is made that any learned policy plays well.
A small numpy-only experiment is recorded below to show the loop works end to end and to give an honest comparison.

## What exists (all on the one authoritative simulation)

| Need | Where | Notes |
| --- | --- | --- |
| Same rules as God Mode | `sim_api.HybridEnv.apply` | Actions are `build, road, queue, cancel, move, order, demolish, rally, stop, deploy`: the commands God Mode and the scripted AI use. A rejected action returns the simulation's reason. No separate simplified game. |
| Per-faction observations | `HybridEnv.observe`, `flatten` | Stocks, buildings and sites by kind, units, territory (cells covered by command-centre squares), production, threats, deposits, command centres (tile, radius, store), MCVs (with cargo), known enemy buildings, stuck entities. `flatten` is a fixed-order vector (50 numbers). |
| Legal action masks | `HybridEnv.legal_actions` | Affordable build kinds with sampled legal sites, roads still missing, queueable units (including `mcv`), movable units, attackable enemy buildings, **deploy** (per MCV: ok or the reason) and **expansion_sites** (a legal, reachable, resource-rich tile for an MCV that cannot deploy where it stands). |
| Rewards | `HybridEnv._score_of`, `DEFAULT_WEIGHTS` | Per-faction score deltas: wealth, territory (now rewards deployed command centres), kill value, loss value, building kills/losses, elimination penalty. Weights are parameters. |
| Reset, termination | `reset(seed)`, `step` | Fixed game-time steps (5 s), episode ends when a faction is eliminated, one faction is left, or `max_game_ms`. |
| Determinism and replay | `state_hash`, `replay`, `tests/test_sim_api.py`, `tests/test_determinism.py` | Same seed and actions give the same hash, also across processes under different `PYTHONHASHSEED`s, also through an MCV expansion. |
| Save/load | `save`, `load` | Pickles the whole world including rng; continuing gives the identical hash. |
| Self-play and multi-agent | `agent_factions=(...)` | Any subset of the six factions can be agents; the rest are the scripted AI (`world.ai_factions`). `step({"Red": [...], "Blue": [...]})` takes one action list per agent. |
| Throughput | `scripts/ai_report.py`, `scripts/bench_sim.py` | Six scripted factions at war: 40 game minutes in about 6 wall minutes on the T460 (about 6x real time); the small map is faster. One core per environment; run several in a `multiprocessing.Pool`. |
| Scripted baseline | `ai.py` (built-in), `scripts/rl_experiment.py baseline` | The same faction played by the scripted AI under the same seeds and score. |
| Behaviour evidence | `scripts/ai_report.py` | Per-faction time series (expansion, recruitment, movement, attacks, kills, MCVs, navy, blocked tasks) with periodic snapshots. |

## The experiment (`scripts/rl_experiment.py`)

- One faction is an agent; five are the scripted AI. Every 30 game seconds the agent picks one of seven macros through a mask
  (wait, build economy, build military, recruit, expand with an MCV, attack, defend). A foreman routine connects new buildings by road.
- Policy: linear + softmax over the flat observation, trained with the cross-entropy method (numpy only; no torch, gym or sklearn are
  installed and none was added).
- Training on seeds 1-2 (small map), judged on held-out seeds 101-106 where the agent faction differs from the training ones, against
  the scripted AI playing the same faction on the same seed with the same score, paired per seed.

### Measured (14-minute episodes, small map, held-out seeds 101-106, score = `HybridEnv._score_of` at the end)

| Controller | Score mean ± sd | Kills | Command centres | Alive |
| --- | --- | --- | --- | --- |
| Scripted AI (built-in, same faction, same seeds) | 50.1 ± 7.2 | 3.3 | 1.83 | 6/6 |
| Do nothing (always `wait`) | 42.5 ± 4.0 | 0 | 1.00 | 6/6 |
| Random masked macros | 31.6 ± 19.2 | 2.7 | 0.83 | 5/6 |
| **Learned linear policy** (CEM, 3 generations x 8 candidates x training seeds 1-2, 17.5 minutes on 3 cores) | **52.2 ± 3.7** | 0 | 1.83 | 6/6 |

Training curve (best / mean candidate score): 48.5 / 45.0, 49.9 / 43.9, 50.9 / 47.2. Paired against the scripted AI per held-out seed the
learned policy wins 5 of 6 (mean difference +2.1; a two-sided sign test gives p = 0.22).

**Reading it honestly.** This is *not* evidence that the learned policy plays better, and the experiment says why. The policy
spends 120 of its 168 decisions waiting, builds some economy, and expands with the MCV 29 times; it **never recruits, attacks or
defends**, ends with fewer buildings (17-23 against 28-32) and fewer units (2-4 against 5-11), and avoids the losses the scripted AI
takes in the first fights. It found the cheapest part of the score: territory (command centres) pays, losses cost, and a 14-minute
episode barely reaches the first battle. So the finding is about the **reward and the horizon**, not about the policy: before real
training the score must value buildings completed, army strength and the economy, and the episodes must be long enough (25+ game
minutes) to contain the first fights. The pipeline itself (masks, deploy, expansion sites, determinism, paired held-out evaluation)
worked as intended and is what this experiment was for.

Reproduce: `python3 scripts/rl_experiment.py baseline`, `train --generations 3 --population 8 --workers 3`, `eval`. Files in `docs/evidence/rl/`.


## Recommended long-term approach

1. **Hierarchy, not raw clicks.** Keep the action space as the God Mode commands but give the learner macro-actions with parameters
   (what to build, where from the mask's sites, which squad to which target, when to expand). The experiment's seven macros are the
   starting set; the AI's own helpers (`_find_expansion_site`, `_station`, `_pick_target`) are the natural macro implementations.
2. **Imitation first.** Record the scripted AI's decisions as macro labels (it already logs structured `ai_*` events per faction) and
   train a masked policy to imitate them; this gives a learner that already expands, recruits and defends.
3. **Then reinforcement learning against the scripted AI and itself** (PPO with action masking, one environment per core, league
   self-play across the six asymmetric tribes), starting from the imitation weights. Needs a framework: adding PyTorch is a decision for
   Joe (about 800 MB) and is not made here.
4. **Evaluation discipline.** Always paired held-out seeds and factions against the scripted baseline, several maps (the two imported
   Widelands maps `wmf:The_Big_Lake`, `wmf:Egyptian_Mandala_v1.2` and generated seeds), report mean, spread and paired wins, never
   training reward alone.
5. **Throughput work that pays for itself:** the per-step observation and mask building are Python and dominate when the agent acts
   every 30 s; a batched (numpy) local map and a cached site sweep would double throughput. The route search is the other cost (see
   the budget notes in DECISIONS D8).

## Known gaps before real training

- The scripted AI is the only opponent; league self-play needs several agents sharing one world (supported by `agent_factions`) and a runner.
- No curriculum scenarios (small starting economies, forced early fights); the 14-minute episodes of the experiment barely reach the
  first battle, because the scripted AI's attack delay is 12 minutes.
- Observations carry no image-like map beyond a 25x25 coarse local view; a learner that scouts needs fog-of-war observations (the
  scripted AI's `_known_targets` is the intended visibility model).
- Naval and wizard actions are not in the macro set.

## Standard-budget run, 2026-10-12 (`scripts/train.py --budget standard --seed 0`)

Raw results: `docs/evidence/training/<domain>.result.json` (weights stay under `~/dmb_runs`, not committed). All numbers are held-out seeds, never training seeds. The game does not require any trained weights.

| Domain | Policy | Held-out result | Baselines | Verdict |
|---|---|---|---|---|
| Mastermind duel (150 secrets) | BC MLP | solves 73% vs random opponent, 87% vs rule-based | solver 100%, random 0.7% | Beats random by a wide margin (CI 0.65-0.79); **does not match the solver**. |
| Outbreak | BC/PG MLP | default: return 2.51, 0 outbreaks, 0% loss; hard: 4.44, 0% loss | greedy 2.51 / 4.45; no-op -13.5 / -27.2 (100% loss on hard) | Equals greedy (it imitates it); does not exceed it. |
| Quest | BC MLP | matches the expert on all 5 variants (216 samples) | expert | Small, deterministic; a memorised script, not general learning. |
| Dungeon | BC + DAgger MLP | **greedy 5%, sampled 10%** solved | expert 100%, random 0% | **Failed to learn.** Failures by first unsolved puzzle: switch_chain 17, mosaic 11, timed_gate 10. Needs a better observation/action design or more budget; do not cite as a working controller. |
| Cross-system (12 held-out) | REINFORCE MLP | return -21.0, loses every run (10.75 outbreaks) | story_first +4.25, treat_first +4.26, wait -23.8 | **Worse than all scripted baselines**; the REINFORCE curve is noisy and did not improve in 5 iterations. Scripted skills remain the reference. |

What this means: the environments, baselines and statistics are sound and reproducible; the dungeon and cross-system learners are not yet competent and are reported as such. Next steps are in `NEXT_AGENT_HANDOFF.md`.
