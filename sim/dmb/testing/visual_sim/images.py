"""Layer 3 helpers — decode / nonblank / region checks (no aesthetic PASS)."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageStat = None  # type: ignore

NEAR_BLANK_STDDEV = 4.0
NEAR_BLANK_GREY_FRAC = 0.92


def png_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w, h = struct.unpack(">II", data[16:24])
    return int(w), int(h)


def check_image(path: str | Path, *, expect_size: tuple[int, int] | None = None) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {"status": "FAIL", "code": "blank_or_missing_screenshot", "reason": "missing_file", "path": str(p)}
    size = p.stat().st_size
    if size <= 0:
        return {"status": "FAIL", "code": "blank_or_missing_screenshot", "reason": "zero_byte", "path": str(p)}
    dims = png_size(p)
    out: dict[str, Any] = {
        "status": "PASS",
        "path": str(p),
        "bytes": size,
        "dims": list(dims) if dims else None,
    }
    if dims is None:
        return {"status": "FAIL", "code": "blank_or_missing_screenshot", "reason": "not_png", "path": str(p)}
    if expect_size and tuple(dims) != tuple(expect_size):
        out["status"] = "FAIL"
        out["code"] = "wrong_resolution"
        out["reason"] = f"dims={dims} expected={expect_size}"
        return out
    if Image is None:
        out["status"] = "INCONCLUSIVE"
        out["reason"] = "no_pil"
        return out
    img = Image.open(p).convert("RGB")
    small = img.resize((min(160, img.width), min(160, img.height)))
    stat = ImageStat.Stat(small)
    stddev = sum(stat.stddev) / max(1, len(stat.stddev))
    grey = 0
    total = small.width * small.height
    for r, g, b in small.getdata():
        if max(r, g, b) - min(r, g, b) < 8:
            grey += 1
    grey_frac = grey / total if total else 1.0
    near_blank = stddev < NEAR_BLANK_STDDEV and grey_frac >= NEAR_BLANK_GREY_FRAC
    out["near_blank"] = near_blank
    out["stddev"] = round(stddev, 3)
    out["grey_frac"] = round(grey_frac, 4)
    if near_blank:
        out["status"] = "FAIL"
        out["code"] = "blank_or_missing_screenshot"
        out["reason"] = "near_blank"
    return out


def region_delta(
    before: str | Path,
    after: str | Path,
    *,
    box: tuple[int, int, int, int] | None = None,
    min_mean_delta: float = 2.0,
) -> dict[str, Any]:
    """Bounded before/after mean absolute difference in a region."""
    if Image is None:
        return {"status": "INCONCLUSIVE", "reason": "no_pil"}
    a = Image.open(before).convert("RGB")
    b = Image.open(after).convert("RGB")
    if box:
        a = a.crop(box)
        b = b.crop(box)
    if a.size != b.size:
        return {"status": "FAIL", "reason": "size_mismatch", "a": a.size, "b": b.size}
    pa = list(a.getdata())
    pb = list(b.getdata())
    if not pa:
        return {"status": "FAIL", "reason": "empty"}
    acc = 0.0
    for (r1, g1, b1), (r2, g2, b2) in zip(pa, pb):
        acc += (abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)) / 3.0
    mean = acc / len(pa)
    ok = mean >= min_mean_delta
    return {
        "status": "PASS" if ok else "FAIL",
        "mean_delta": round(mean, 4),
        "min_mean_delta": min_mean_delta,
        "box": box,
    }
