#!/usr/bin/env python3
"""Visual QA metrics and montage generator. See docs/VISUAL_QA.md."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "qa" / "screenshots" / "current"
BASELINE = ROOT / "qa" / "screenshots" / "baseline"
MONTAGES = ROOT / "qa" / "montages"
REPORTS = ROOT / "qa" / "reports"

SHOT_ORDER = [
    "01_main_menu.png",
    "02_difficulty_select.png",
    "03_encounter_select.png",
    "04_ward_setup.png",
    "05_duel_start.png",
    "06_duel_mid.png",
    "07_duel_dense_history.png",
    "08_cast_ready.png",
    "09_auto_cast_warning.png",
    "10_attack_impact.png",
    "11_feedback_reveal.png",
    "12_last_stand.png",
    "13_victory.png",
    "14_defeat.png",
    "15_clash.png",
]

THEME = {
    "text_primary": (0.95, 0.95, 1.0),
    "panel_bg": (0.12, 0.10, 0.22),
    "cast_min": 96,
    "essence_min": 72,
    "utility_min": 48,
}


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def grey_dominance(path: Path, threshold: float = 0.15) -> float:
    if Image is None or not path.exists():
        return 0.0
    img = Image.open(path).convert("RGB")
    img = img.resize((min(360, img.width), min(640, img.height)))
    grey = 0
    total = img.width * img.height
    for r, g, b in img.getdata():
        mx, mn = max(r, g, b), min(r, g, b)
        sat = (mx - mn) / 255.0 if mx else 0.0
        if sat < threshold:
            grey += 1
    return grey / total if total else 0.0


def load_audit() -> dict:
    p = REPORTS / "capture_audit.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"screenshots": [], "touch_targets": [], "text_nodes": []}


def audit_touch_targets(targets: list) -> list[str]:
    warnings: list[str] = []
    for t in targets:
        name = t.get("name", "?")
        w = float(t.get("width", 0))
        h = float(t.get("height", 0))
        role = t.get("role", "utility")
        min_sz = THEME["utility_min"]
        if role == "cast":
            min_sz = THEME["cast_min"]
        elif role in ("essence", "locus"):
            min_sz = THEME["essence_min"]
        elif role == "secondary":
            min_sz = 56
        if w < min_sz or h < min_sz:
            warnings.append(f"Touch target '{name}' {w:.0f}x{h:.0f} below min {min_sz}")
    return warnings


def audit_text_nodes(nodes: list) -> dict:
    visible = [n for n in nodes if n.get("visible", True)]
    char_count = sum(len(str(n.get("text", ""))) for n in visible)
    return {
        "visible_text_nodes": len(visible),
        "visible_char_count": char_count,
        "warnings": [],
    }


def audit_non_leak(repo: Path) -> list[str]:
    warnings: list[str] = []
    patterns = [
        r"per_locus_feedback",
        r"locus_results",
        r"feedback_by_locus",
    ]
    for gd in (repo / "godot_project" / "client").rglob("*.gd"):
        text = gd.read_text(errors="ignore")
        for pat in patterns:
            if re.search(pat, text):
                warnings.append(f"Possible per-locus leak reference in {gd.relative_to(repo)}")
    return warnings


def make_grid(folder: Path, out_path: Path, cols: int = 3) -> bool:
    if Image is None:
        return False
    paths = [folder / name for name in SHOT_ORDER if (folder / name).exists()]
    if not paths:
        return False
    thumb_w, thumb_h = 240, 427
    rows = (len(paths) + cols - 1) // cols
    grid = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (20, 18, 35))
    draw = ImageDraw.Draw(grid)
    for i, p in enumerate(paths):
        img = Image.open(p).convert("RGB")
        img.thumbnail((thumb_w, thumb_h))
        x = (i % cols) * thumb_w + (thumb_w - img.width) // 2
        y = (i // cols) * thumb_h + (thumb_h - img.height) // 2
        grid.paste(img, (x, y))
        draw.text((x + 4, y + 4), p.stem, fill=(255, 255, 200))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(out_path)
    return True


def make_before_after(before: Path, after: Path, out: Path) -> bool:
    if Image is None or not before.exists() or not after.exists():
        return False
    left = Image.open(before).convert("RGB")
    right = Image.open(after).convert("RGB")
    h = max(left.height, right.height)
    w = left.width + right.width
    canvas = Image.new("RGB", (w, h), (20, 18, 35))
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width, 0))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return True


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    MONTAGES.mkdir(parents=True, exist_ok=True)
    audit = load_audit()
    touch_warnings = audit_touch_targets(audit.get("touch_targets", []))
    text_stats = audit_text_nodes(audit.get("text_nodes", []))
    if text_stats["visible_text_nodes"] > 30:
        text_stats["warnings"].append(
            f"Visible text nodes {text_stats['visible_text_nodes']} > 30"
        )
    if text_stats["visible_char_count"] > 500:
        text_stats["warnings"].append(
            f"Visible char count {text_stats['visible_char_count']} > 500"
        )
    grey: dict[str, float] = {}
    for name in SHOT_ORDER:
        p = CURRENT / name
        if p.exists():
            g = grey_dominance(p)
            grey[name] = round(g, 3)
            if "duel" in name and g > 0.6:
                text_stats["warnings"].append(f"{name}: grey dominance {g:.0%} > 60%")
    contrast = round(contrast_ratio(THEME["text_primary"], THEME["panel_bg"]), 2)
    leak_warnings = audit_non_leak(ROOT)
    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "screenshots_found": sum(1 for n in SHOT_ORDER if (CURRENT / n).exists()),
        "text": text_stats,
        "touch_target_warnings": touch_warnings,
        "grey_dominance": grey,
        "contrast_text_on_panel": contrast,
        "non_leak_warnings": leak_warnings,
    }
    (REPORTS / "visual_metrics_latest.json").write_text(json.dumps(metrics, indent=2))
    made_current = make_grid(CURRENT, MONTAGES / "current_grid.png")
    made_baseline = make_grid(BASELINE, MONTAGES / "baseline_grid.png")
    if made_current and made_baseline:
        make_before_after(
            MONTAGES / "baseline_grid.png",
            MONTAGES / "current_grid.png",
            MONTAGES / "before_after_grid.png",
        )
    md = [
        "# Visual QA report",
        "",
        f"Generated: {metrics['generated_at']}",
        "",
        f"Screenshots captured: {metrics['screenshots_found']}/15",
        "",
        "## Automated metrics",
        "",
        f"- Visible text nodes: {text_stats['visible_text_nodes']}",
        f"- Visible character count: {text_stats['visible_char_count']}",
        f"- Text/panel contrast ratio: {contrast}",
        "",
        "## Warnings",
        "",
    ]
    all_warnings = (
        touch_warnings
        + text_stats["warnings"]
        + leak_warnings
    )
    if all_warnings:
        md.extend(f"- {w}" for w in all_warnings)
    else:
        md.append("- None")
    md.extend(
        [
            "",
            "## Rubric (manual — score 1–5)",
            "",
            "| Screen | Read | Hierarchy | Mobile | Juice | Magic | Density | Feedback | A11y | Polish |",
            "|--------|------|-----------|--------|-------|-------|---------|----------|------|--------|",
        ]
    )
    for name in SHOT_ORDER:
        if (CURRENT / name).exists():
            md.append(f"| {name} | | | | | | | | | |")
    md.append("")
    md.append("Pass threshold: ≥4 in all categories for core duel screens.")
    (REPORTS / "visual_qa_latest.md").write_text("\n".join(md))
    print(f"Wrote {REPORTS / 'visual_metrics_latest.json'}")
    print(f"Wrote {REPORTS / 'visual_qa_latest.md'}")


if __name__ == "__main__":
    main()
