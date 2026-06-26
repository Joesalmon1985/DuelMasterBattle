# Visual QA workflow

Evidence-based screenshot capture and scoring for the Visual Polish PRD.

## Prerequisites

```bash
export GODOT="$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64"
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
```

## Capture screenshots

```bash
# Current build → qa/screenshots/current/
tools/capture_visual_qa.sh

# Baseline (run before a visual pass, copy current → baseline)
tools/capture_visual_qa.sh --baseline
```

Runs headed Godot at **720×1280** (not headless). Output: 15 named PNGs plus `qa/reports/capture_audit.json`.

## Generate metrics report

```bash
python3 tools/visual_qa_report.py
```

Writes `qa/reports/visual_qa_latest.md` and `qa/reports/visual_metrics_latest.json`.

## Montages

After capture, `visual_qa_report.py` builds:

- `qa/montages/current_grid.png`
- `qa/montages/baseline_grid.png` (if baseline exists)
- `qa/montages/before_after_grid.png` (if both exist)

## Screenshot states

| File | State |
|------|-------|
| `01_main_menu.png` | Title screen |
| `02_difficulty_select.png` | Difficulty row visible |
| `03_encounter_select.png` | Encounter detail |
| `04_ward_setup.png` | Ward setup before lock |
| `05_duel_start.png` | Just after lock |
| `06_duel_mid.png` | Mid duel, 2–3 attacks |
| `07_duel_dense_history.png` | Expanded history |
| `08_cast_ready.png` | Cast available |
| `09_auto_cast_warning.png` | ≤3s to auto-cast |
| `10_attack_impact.png` | Mid impact animation |
| `11_feedback_reveal.png` | Latest result cluster |
| `12_last_stand.png` | Unstable ward (scripted) |
| `13_victory.png` | Victory result |
| `14_defeat.png` | Defeat result |
| `15_clash.png` | Clash/stalemate result |

## Rubric (score 1–5 per category)

| Category | Pass threshold |
|----------|----------------|
| Readability | ≥4 |
| Visual hierarchy | ≥4 |
| Mobile usability | ≥4 |
| Excitement / juice | ≥4 |
| Magical identity | ≥4 |
| Information density | ≥4 |
| Feedback clarity | ≥4 |
| Accessibility | ≥4 |
| Overall polish | ≥4 |

Record scores in `qa/reports/visual_qa_latest.md` after each capture pass.

## Automated metrics

| Metric | Target (duel screen) |
|--------|------------------------|
| Visible text nodes | <30 |
| Visible character count | <500 |
| Default history rows | ≤3 player peek |
| Touch targets | none <48px; Cast ≥96px; locus/essence ≥72px |
| Grey dominance | not >60% low-saturation grey |
| Non-leak | aggregate feedback counts only |

## Baseline policy

Baseline screenshots live in `qa/screenshots/baseline/`. Re-capture baseline only when intentionally resetting the comparison point.
