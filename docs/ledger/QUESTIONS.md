# Decision queue (recommended default applies unless the owner says otherwise)

- Q-A: Run moved from Windows to the Ubuntu laptop. Default: Windows-specific items (probe on that PC, `.ps1` supervisor wrapper, power-plan sleep prevention) are written but marked untested until the PC is back.
- Q3-Q14 from the plan: plan defaults used (Mindustry v146, RA only, PyTorch learner-only later, pure-Python MIX decryption, etc.).

## Defaults chosen during the 12-13 Oct 2026 run (reversible; revisit with the studies)

| Topic | Default used | Where | Evidence |
| --- | --- | --- | --- |
| Era bar | first era ends when one faction's current VP reaches 8 (held 60 s); later bars = leader's VP + 4 so a standing lead cannot end every era at once | `vp.ERA_VP_END`, `ERA_VP_STEP` | `docs/evidence/p3_draft/summary.md`: no game reached Modern in 90 min with +4; P12 study to choose |
| Foundation set (no cards needed) | primitive kit + settlers + tavern + caravan + clinic | `tech.FOUNDATION_*` | `docs/evidence/p2_nocards/summary.md` |
| Settlement quota | removed whenever the foundation is on (nocards or cards v2); frontier expansion from any settlement | `ai.py`, `ai_plus.py` | same |
| Paper | 1 plank + 1 water per sheet at a scriptorium; 2 sheets per bonus pick (hand of three from a reserve deck) | `draft.py`, `programs_data.py` | `tests/test_paper_bonus.py` |
| Military recipes | new units priced from OpenRA credits at 75 credits per ware value; earlier hand-set recipes untouched | `calibrate.py` | `tests/test_calibrate.py` |
| New units gated | card-only; ungated profiles keep the earlier roster so recorded baselines stay valid | `tech.unit_allowed` | hash gate |
| Collective loss | per-era limit defaults to the cumulative limit (8); thresholds still to be calibrated | `data/outbreaks.json` | `docs/evidence/p10_catastrophe/summary.md` |
| Diplomacy | cooperative truce rule exists but is OFF (`world.diplomacy_enabled`) until the study | `diplomacy.py` | `tests/test_diplomacy.py` |
| OpenRA art source | the player's own content on this machine (decrypted with `mix_crypto.py`) | `import_openra_*.py` | `docs/evidence/assets/` |
| Widelands art states | installed Widelands 1.3.1 package (pinned checkout has no images) | `import_widelands_states.py` | `docs/evidence/assets/widelands_state_gaps.json` |

## Questions for the owner raised by the evidence (recommended default in brackets)
* Should every start position be guaranteed room for three settlements (Blue is hemmed in on the standard map)? [Yes: relax the separation buffer for the boxed-in faction, or move the start.]
* Era pace: settlement VP saturates at 8-9 and the AIs rarely attack, so eras after the first need conquest. [Raise AI aggression and test bar 9 with step 2 before changing the rule.]
* Cadence of outbreaks for the catastrophe study: the design default (one cube per 10 minutes) never threatened the world in 90 minutes, a 72-second cadence kills it by minute 42. [Study scales 0.2-0.5.]
