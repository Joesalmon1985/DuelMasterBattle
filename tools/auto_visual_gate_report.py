#!/usr/bin/env python3
"""Validate auto-gate screenshot + semantic-state evidence; build montages.

Usage:
  python tools/auto_visual_gate_report.py --gate G06
  python tools/auto_visual_gate_report.py --gate G06 --strict

Checks (where practical):
  exists, non-zero, dimensions, near-blank, matching state JSON,
  semantic IDs, viewport controls, touch mins, overlap flags,
  modal open, era match, script errors.

Does NOT invent human PASS — preserves AUTO_READY_FOR_OWNER_REVIEW.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageStat
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageStat = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
TRACKING = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "gates"

NEAR_BLANK_STDDEV = 6.0
NEAR_BLANK_GREY_FRAC = 0.97


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _near_blank(path: Path) -> tuple[bool, dict]:
    if Image is None or ImageStat is None:
        return False, {"skipped": "no_pil"}
    img = Image.open(path).convert("RGB")
    small = img.resize((min(160, img.width), min(160, img.height)))
    stat = ImageStat.Stat(small)
    stddev = sum(stat.stddev) / max(1, len(stat.stddev))
    # Grey dominance
    grey = 0
    total = small.width * small.height
    for r, g, b in small.getdata():
        if max(r, g, b) - min(r, g, b) < 8:
            grey += 1
    grey_frac = grey / total if total else 1.0
    blank = stddev < NEAR_BLANK_STDDEV and grey_frac >= NEAR_BLANK_GREY_FRAC
    return blank, {"stddev": round(stddev, 3), "grey_frac": round(grey_frac, 4)}


def _parse_res_from_name(name: str) -> tuple[int, int] | None:
    m = re.search(r"_(\d+)x(\d+)\.png$", name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _validate_shot(png: Path, meta: dict | None, *, strict: bool) -> dict:
    issues: list[str] = []
    warnings: list[str] = []
    info: dict = {"file": str(png.relative_to(ROOT)), "status": "PASS"}

    if not png.is_file():
        return {"file": str(png), "status": "FAIL", "issues": ["missing_file"]}
    size = png.stat().st_size
    info["bytes"] = size
    if size <= 0:
        issues.append("zero_byte")

    dims_name = _parse_res_from_name(png.name)
    if Image is not None:
        with Image.open(png) as im:
            w, h = im.size
        info["image_width"] = w
        info["image_height"] = h
        if dims_name and (w, h) != dims_name:
            issues.append(f"dimension_mismatch_name={dims_name[0]}x{dims_name[1]}_actual={w}x{h}")
        blank, blank_info = _near_blank(png)
        info["near_blank"] = blank_info
        if blank:
            issues.append("near_blank")
    else:
        warnings.append("pil_unavailable_skip_image_checks")

    if meta is None:
        issues.append("missing_state_json")
    else:
        info["checkpoint"] = meta.get("checkpoint")
        info["era"] = meta.get("era")
        info["modal_open"] = meta.get("modal_open")
        # Script errors during capture
        for err in meta.get("script_errors") or []:
            issues.append(f"script_error:{err}")
        # Touch mins — only real button targets; container panel roles are soft warnings.
        panel_roles = {
            "world_map",
            "chronicle",
            "inventory",
            "grimoire",
            "knowledge",
            "fx_era_panel",
        }
        for role in meta.get("touch_below_min") or []:
            if str(role) in panel_roles:
                warnings.append(f"touch_below_min_panel:{role}")
            else:
                issues.append(f"touch_below_min:{role}")
        # Viewport controls
        for role in meta.get("controls_outside_viewport") or []:
            # Stale close buttons when parent modal is not open → warning
            modal = str(meta.get("modal_open") or "")
            role_s = str(role)
            if role_s.endswith("_close") and modal and not role_s.startswith(modal):
                warnings.append(f"stale_close_outside:{role_s}")
            elif role_s.endswith("_close") and not modal:
                warnings.append(f"stale_close_outside:{role_s}")
            else:
                issues.append(f"control_outside_viewport:{role}")
        # Overlaps
        for ov in meta.get("overlap_flags") or []:
            issues.append(f"severe_overlap:{ov.get('a')}+{ov.get('b')}")
        # Modal expectation
        expected_modal = meta.get("expected_modal")
        if expected_modal and str(meta.get("modal_open") or "") != str(expected_modal):
            issues.append(f"modal_mismatch_expected={expected_modal}_got={meta.get('modal_open')}")
        # Era expectation
        expected_era = meta.get("expected_era")
        if expected_era:
            got = str(meta.get("era") or "").lower()
            if got != str(expected_era).lower():
                issues.append(f"era_mismatch_expected={expected_era}_got={got}")
        # Semantic IDs — soft unless strict: missing expected IDs warn by default
        missing = meta.get("missing_semantic_ids") or []
        if missing:
            msg = f"missing_semantic_ids:{','.join(str(x) for x in missing)}"
            if strict:
                issues.append(msg)
            else:
                warnings.append(msg)
        # Viewport dims vs metadata
        vp = meta.get("viewport") or {}
        if Image is not None and vp:
            mw = int(vp.get("width") or 0)
            mh = int(vp.get("height") or 0)
            if mw and mh and (abs(mw - info.get("image_width", mw)) > 2 or abs(mh - info.get("image_height", mh)) > 2):
                warnings.append(
                    f"viewport_meta_vs_image={mw}x{mh}_vs_{info.get('image_width')}x{info.get('image_height')}"
                )
        if meta.get("capture_ok") is False:
            issues.append("capture_ok_false")

    if issues:
        info["status"] = "FAIL"
    info["issues"] = issues
    info["warnings"] = warnings
    return info


def _make_montage(shots: list[Path], out_path: Path, cols: int = 3) -> bool:
    if Image is None or ImageDraw is None or not shots:
        return False
    thumb_w, thumb_h = 280, 200
    rows = (len(shots) + cols - 1) // cols
    grid = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (24, 22, 28))
    draw = ImageDraw.Draw(grid)
    for i, p in enumerate(shots):
        try:
            img = Image.open(p).convert("RGB")
        except OSError:
            continue
        img.thumbnail((thumb_w - 8, thumb_h - 24))
        x = (i % cols) * thumb_w + (thumb_w - img.width) // 2
        y = (i // cols) * thumb_h + 18
        grid.paste(img, (x, y))
        draw.text(((i % cols) * thumb_w + 4, (i // cols) * thumb_h + 2), p.stem[:40], fill=(240, 230, 180))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(out_path)
    return True


def validate_gate(gate: str, *, strict: bool = False) -> dict:
    gate = gate.upper()
    auto = TRACKING / gate / "auto"
    shots_dir = auto / "screenshots"
    result_path = auto / "result.json"
    result = _load_json(result_path) or {}
    pngs = sorted(shots_dir.glob("*.png")) if shots_dir.is_dir() else []
    shot_reports: list[dict] = []
    for png in pngs:
        meta_path = png.with_suffix(".json")
        meta = _load_json(meta_path)
        shot_reports.append(_validate_shot(png, meta, strict=strict))

    failed = [s for s in shot_reports if s.get("status") != "PASS"]
    montage_path = auto / "montages" / f"{gate.lower()}_storyboard.png"
    montage_ok = _make_montage(pngs, montage_path) if pngs else False

    # Preserve overnight auto status; never invent PASS.
    auto_status = result.get("status") or (
        "AUTO_READY_FOR_OWNER_REVIEW" if pngs and not failed else "AUTO_FAILED"
    )
    if auto_status not in {
        "AUTO_READY_FOR_OWNER_REVIEW",
        "AUTO_FAILED",
        "PARTIAL",
        "PARTIAL_BLOCKED",
    }:
        auto_status = "AUTO_READY_FOR_OWNER_REVIEW" if not failed and pngs else "AUTO_FAILED"

    # Visual validation can fail independently without rewriting a prior AUTO_READY
    # unless --strict and there are hard image failures.
    visual_status = "PASS" if pngs and not failed else ("FAIL" if failed else "NO_SHOTS")
    if visual_status == "FAIL" and strict:
        auto_status = "AUTO_FAILED"

    report = {
        "gate": gate,
        "generated_at": _now(),
        "auto_status": auto_status,
        "human_acceptance": "PENDING — never invent PASS",
        "visual_status": visual_status,
        "screenshot_count": len(pngs),
        "shots_passed": sum(1 for s in shot_reports if s.get("status") == "PASS"),
        "shots_failed": len(failed),
        "shots": shot_reports,
        "montage": str(montage_path.relative_to(ROOT)) if montage_ok else None,
        "result_json": str(result_path.relative_to(ROOT)) if result_path.is_file() else None,
    }
    out = auto / "visual_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    md_lines = [
        f"# {gate} visual evidence report",
        "",
        f"**Auto status:** `{auto_status}`",
        f"**Visual status:** `{visual_status}`",
        f"**Screenshots:** {len(pngs)} ({report['shots_passed']} pass / {report['shots_failed']} fail)",
        "",
        "Human acceptance remains PENDING. Automation is not PASS.",
        "",
    ]
    if montage_ok:
        md_lines.append(f"Montage: `{montage_path.relative_to(ROOT)}`")
        md_lines.append("")
    md_lines += ["| Shot | Status | Issues |", "|---|---|---|"]
    for s in shot_reports:
        md_lines.append(
            f"| `{Path(s['file']).name}` | {s.get('status')} | {', '.join(s.get('issues') or []) or '—'} |"
        )
    (auto / "visual_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", required=True)
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Treat soft semantic misses as failures and demote auto_status on visual FAIL",
    )
    args = ap.parse_args()
    report = validate_gate(args.gate, strict=args.strict)
    print(
        json.dumps(
            {
                "gate": report["gate"],
                "auto_status": report["auto_status"],
                "visual_status": report["visual_status"],
                "shots": report["screenshot_count"],
                "failed": report["shots_failed"],
                "report": f"Pack/DuelMasterBattle_Build_Pack/tracking/gates/{args.gate.upper()}/auto/visual_report.json",
            },
            indent=2,
        )
    )
    if report["visual_status"] == "NO_SHOTS":
        return 2
    return 0 if report["visual_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
