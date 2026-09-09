"""Facing audit for overworld character sprites (CORRECTIVE_PASS Phase 2).

Structural rule: for every chars/<name>_left_<f>.png there is a _right_<f>.png
that is its exact horizontal mirror. Left-facing masters were verified visually
(vision review of qa/facing_sheet*.png); mirroring makes the right view correct
by construction. Exit 1 on any missing or non-mirrored pair.
"""
from pathlib import Path
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
CHARS = ROOT / "godot_project" / "assets" / "pixel" / "chars"


def main() -> int:
    bad = []
    checked = 0
    for left in sorted(CHARS.glob("*_left_*.png")):
        right = left.with_name(left.name.replace("_left_", "_right_"))
        if not right.exists():
            bad.append(f"{right.name}: missing")
            continue
        a = Image.open(left).convert("RGBA")
        b = Image.open(right).convert("RGBA").transpose(Image.FLIP_LEFT_RIGHT)
        checked += 1
        if a.size != b.size or ImageChops.difference(a, b).getbbox() is not None:
            bad.append(f"{left.name} vs {right.name}: not mirrors")
    print(f"facing audit: {checked} left/right pairs checked, {len(bad)} wrong")
    for x in bad:
        print("  - " + x)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
