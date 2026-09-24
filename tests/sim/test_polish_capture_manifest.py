"""Polish capture/replay harness failure-contract tests (P0)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


REQUIRED_KEYS = ("source_sha", "scenario", "seed", "frames", "review_status")


def _write_manifest(path: Path, **overrides) -> dict:
    data = {
        "source_sha": "abc123",
        "scenario": "FX-MVP",
        "seed": 507,
        "checkpoint": None,
        "output_dir": str(path.parent),
        "frames": [
            {"id": "B01", "width": 450, "height": 800, "path": "B01_450x800.png"},
            {"id": "B01", "width": 1280, "height": 720, "path": "B01_1280x720.png"},
        ],
        "review_status": "unreviewed",
    }
    data.update(overrides)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def validate_capture_manifest(manifest_path: Path, *, expected_source: str, fresh_dir: Path) -> list[str]:
    """Return list of contract violations (empty = ok for harness gate)."""
    errors: list[str] = []
    if not manifest_path.is_file():
        return ["missing_manifest"]
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"missing_key:{key}")
    if data.get("source_sha") != expected_source:
        errors.append("wrong_source_metadata")
    out = Path(str(data.get("output_dir") or ""))
    if out.resolve() != fresh_dir.resolve():
        errors.append("output_not_fresh_dir")
    if data.get("review_status") == "unreviewed":
        errors.append("explicit_unreviewed_status")
    for frame in data.get("frames") or []:
        fpath = fresh_dir / str(frame.get("path") or "")
        if not fpath.is_file():
            errors.append(f"missing_frame:{frame.get('path')}")
            continue
        # Dimension check via PNG IHDR when available
        try:
            raw = fpath.read_bytes()
            if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n":
                errors.append(f"not_png:{fpath.name}")
                continue
            w = int.from_bytes(raw[16:20], "big")
            h = int.from_bytes(raw[20:24], "big")
            if w != int(frame.get("width") or -1) or h != int(frame.get("height") or -1):
                errors.append(f"wrong_dimensions:{fpath.name}:{w}x{h}")
        except OSError:
            errors.append(f"unreadable:{fpath.name}")
    return errors


def test_fresh_output_isolation(tmp_path: Path) -> None:
    man = tmp_path / "manifest.json"
    _write_manifest(man, output_dir=str(tmp_path), review_status="reviewed")
    # Missing frames → error
    errs = validate_capture_manifest(man, expected_source="abc123", fresh_dir=tmp_path)
    assert any(e.startswith("missing_frame") for e in errs)


def test_wrong_source_metadata(tmp_path: Path) -> None:
    man = tmp_path / "manifest.json"
    _write_manifest(man, review_status="reviewed")
    errs = validate_capture_manifest(man, expected_source="other", fresh_dir=tmp_path)
    assert "wrong_source_metadata" in errs


def test_missing_required_frame(tmp_path: Path) -> None:
    man = tmp_path / "manifest.json"
    _write_manifest(man, review_status="reviewed")
    (tmp_path / "B01_450x800.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    errs = validate_capture_manifest(man, expected_source="abc123", fresh_dir=tmp_path)
    assert any("missing_frame:B01_1280x720.png" in e for e in errs)


def test_wrong_decoded_dimensions(tmp_path: Path) -> None:
    man = tmp_path / "manifest.json"
    _write_manifest(man, review_status="reviewed")
    # Minimal PNG header claiming 10x10
    ihdr = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (10).to_bytes(4, "big") + (10).to_bytes(4, "big")
    (tmp_path / "B01_450x800.png").write_bytes(ihdr + b"\x00" * 8)
    (tmp_path / "B01_1280x720.png").write_bytes(ihdr + b"\x00" * 8)
    errs = validate_capture_manifest(man, expected_source="abc123", fresh_dir=tmp_path)
    assert any(e.startswith("wrong_dimensions") for e in errs)


def test_explicit_unreviewed_status(tmp_path: Path) -> None:
    man = tmp_path / "manifest.json"
    _write_manifest(man, review_status="unreviewed")
    errs = validate_capture_manifest(man, expected_source="abc123", fresh_dir=tmp_path)
    assert "explicit_unreviewed_status" in errs
