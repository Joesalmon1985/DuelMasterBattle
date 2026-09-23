# Morning handoff — overnight G06–G12

**Final branch:** `overnight/g12-visual-training-finish`  
**Final SHA:** `6bc0a23f26d7ea0203dc213f25fb4e389b12c504`
**Note:** After this handoff commit, tip may be one commit ahead; run `git rev-parse HEAD`.
**Started from:** `1aa2205` on `phase/g06-g12-autoqa`  
**Platform:** Windows · Godot 4.5.1 · `.venv\Scripts\python.exe`  
**Human acceptance:** PENDING for every gate — automation is `AUTO_READY_FOR_OWNER_REVIEW` only. Never treat this as PASS.

## Play the latest integrated game (one click)

```bat
Play Latest Integrated Game.bat
```

Launches **FX-MVP seed 507** at **450×800** via `g05_shell.tscn` (strategic world, not main-menu story alone).

Or:

```bat
Playtest.bat
```

| Menu key | What you get |
|----------|----------------|
| **L** | Latest integrated world / FX-MVP (recommended) |
| **E** | Near-era-transition / FX-ERA |
| **3** | Unit production / G03 |
| **1** | Local combat / G04 battle |
| **2** | Hazard/manifestation combat / G04 hazard |
| **6** | Main story / menu |
| **V** | In-world visual review harness |
| **W** | Ward Duel presentation review (headed) |

## Battle visual-leak fix

**Bug:** Opening a Ward Duel from FX-MVP left overworld/local-combat presentation visible (rocks, signs, labels, sprites) under the duel UI.

**Fix:** Central `DmbPresentationMode` (`WORLD` / `LOCAL_BATTLE` / `WARD_DUEL` / `MODAL`) owned by `g05_shell`. On Ward Duel lease, world-space presentation roots become invisible and non-interactive; duel uses a high `CanvasLayer`. On leave, world presentation restores once (no duplicate actors). Simulation is not destroyed to hide art.

**Regression:** `godot_project/client/tests/run_ward_duel_presentation.gd` asserts visibility before / during / after duel.

## Screenshot paths

**Ward Duel leak (before / clean duel / returned):**

- `Pack/DuelMasterBattle_Build_Pack/tracking/gates/G11/ward_duel_leak/`
  - `01_before_encounter_{450x800,1280x720}.png`
  - `02_clean_ward_duel_{450x800,1280x720}.png`
  - `03_returned_world_{450x800,1280x720}.png`

**In-world legibility review:**

- `Pack/DuelMasterBattle_Build_Pack/tracking/gates/G11/visual_review/`
- Owner report: `.../visual_review/REPORT.md`

## Gate status (automated only)

| Gate | Auto status |
|------|-------------|
| G06 | `AUTO_READY_FOR_OWNER_REVIEW` |
| G07 | `AUTO_READY_FOR_OWNER_REVIEW` |
| G08 | `AUTO_READY_FOR_OWNER_REVIEW` |
| G09 | `AUTO_READY_FOR_OWNER_REVIEW` |
| G10 | `AUTO_READY_FOR_OWNER_REVIEW` |
| G11 | `AUTO_READY_FOR_OWNER_REVIEW` |
| G12 | `AUTO_READY_FOR_OWNER_REVIEW` |

Umbrella report: `Pack/DuelMasterBattle_Build_Pack/tracking/OVERNIGHT_G06_G12_REPORT.md`

## G09 — qualified policies (3 / 3)

Selected by `training/select_library.py` from real 200-seed held-out `PROMOTION_SEEDS` evals. Heuristic remains `trained: false`.

| ID | prefer_family | init_seed | decisions | weights digest | 200-seed wins | catastrophe | crashes | illegal | p95 ms | action_family_share |
|----|---------------|-----------|-----------|----------------|---------------|-------------|---------|---------|--------|---------------------|
| `policy-im-build` | build | 101 | 12000 | `36461a7486b76933` | 97 (baseline 97) | 0 | 0 | 0 | ~0.30 | build ≈ 0.999, trade 0, war 0 |
| `policy-im-trade` | trade | 202 | 12000 | `946dbdf55ba4b5e3` | 97 | 0 | 0 | 0 | ~0.29 | trade = 1.0 |
| `policy-im-war` | war | 303 | 12000 | `cd314a57dd2db9a2` | 97 | 0 | 0 | 0 | ~0.32 | build ≈ 0.368, war ≈ 0.142, other ≈ 0.490 |

**Pairwise max family-share distance (≥ 0.10 required):**

| Pair | Distance |
|------|----------|
| build ↔ trade | **1.00** |
| build ↔ war | **0.63** |
| trade ↔ war | **1.00** |

Artifacts: `godot_project/content/policies/policy-im-{build,trade,war}.json`  
Evals: `Pack/.../policy_evaluations/eval_policy-im-{build,trade,war}.json`  
Manifest: `godot_project/content/policies/manifest.json` (`COMPLETE`, qualified_count=3)

Training used family primary-seat elevation so C14 specialists can emit build/trade/war as primary actions (otherwise trade never appeared in shares).

### Supplemental full-world evaluation

**Not completed overnight.** Promotion remains FX-ERA 200-seed contract. A longer FX-MVP / full-generated-world supplemental eval was not finished; treat as remaining owner follow-up if desired.

## G10 — Windows package

- Functional G10 auto: `AUTO_READY_FOR_OWNER_REVIEW`
- **`windows_certified=false`**
- No packaged `.exe` smoke on this run (`windows_scaffold.json` / `windows_status.md`)
- Play via Godot + launchers above (honest; not a shipping binary claim)

## G11

Semantic registry checks retained. Owner visual judgement uses real in-world screenshots under `visual_review/` and `ward_duel_leak/`. Automation does **not** invent aesthetic PASS.

## Commits on this overnight branch (from `1aa2205`)

1. `c206d46` — fix(G05): hide world presentation during Ward Duel  
2. `569398a` — feat(windows): latest-game launcher and portable auto-gate runner  
3. `88d8a35` — feat(overnight): resumable G06-G12 runner and family-specialist G09 pipeline  
4. `2a98dfe` — chore(G06): regenerate Windows auto-gate evidence  
5. `02f6ddc` — feat(G11): in-world visual review harness and fresh G07/G08 evidence  
6. `9cfdef1` / `a993cb1` / `423129b` — G09 family specialist training / primary-seat fixes  
7. *(plus finalize commits for G09 evidence + G12 aggregate + this handoff)*

Resume runner: `.\.venv\Scripts\python.exe tools\run_overnight_g06_g12.py --resume`

## Known remaining defects / limits

1. **Windows `.exe` packaging** — not certified; scaffold only.
2. **Supplemental full-world policy eval** — not run; FX-ERA promotion only.
3. **Placeholder art** — legible by design, not production art.
4. **G05 human gate** — still awaiting owner; overnight did not invent PASS.
5. **Owner-dirty `docs/RELEASE_NOTES.md`** — left untouched (pre-existing local edits).

## Owner manual-test checklist

1. Double-click `Play Latest Integrated Game.bat` — confirm FX-MVP loads at 450×800.
2. Travel west (seed 507) → manifestation/demon → open Ward Duel.
3. Confirm duel screen is clean (no rocks/signs/world labels/workers/carts leaking).
4. Finish or cancel duel → world restores once, correct position, no ghost sprites.
5. `Playtest.bat` → **3 / 1 / 2 / E / V / W** for production, combat, hazards, era, visual review.
6. Spot-check screenshots in `G11/ward_duel_leak/` and `G11/visual_review/`.
7. Skim G09 `manifest.json` + one eval report; confirm three trained policies, heuristic untrained.
8. Decide human PASS / reject per gate — automation only prepared review packets.
