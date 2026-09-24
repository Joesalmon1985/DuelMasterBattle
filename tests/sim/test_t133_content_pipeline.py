"""T133 offline content authoring pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from tools.content.compile import CONTENT_MANIFEST, compile_content_pack
from tools.content.make_batch import make_batch, validate_batch
from tools.content.quality_report import build_report, write_report

ROOT = Path(__file__).resolve().parents[2]


def _lines(n: int = 30, *, bad_effect: bool = False) -> list[dict]:
    out = []
    for i in range(n):
        effect_kind = "UNKNOWN_API" if bad_effect and i == 0 else "noop"
        out.append(
            {
                "schema_version": 1,
                "id": f"dialogue.t133.{i:03d}",
                "scope": "normal",
                "speaker_role": "worker",
                "era_id": "historic",
                "text": f"T133 pipeline sample {i}: harvest carts still need watching.",
                "fallback": "They shrug.",
                "choices": [
                    {
                        "id": f"ok_{i}",
                        "label": "Alright",
                        "effects": [{"kind": effect_kind, "effect_id": f"effect.t133.{i}"}],
                    }
                ],
            }
        )
    return out


def test_make_batch_valid_and_persists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    result = make_batch(batch_id="batch.t133.valid", lines=_lines(30), write=True)
    assert result["ok"]
    assert result["written"]
    path = ROOT / result["path"]
    assert path.is_file()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["content_hash"] == result["content_hash"]
    assert loaded["provenance"]["api_dependency"] is False
    assert loaded["provenance"]["credentials"] is None


def test_malformed_batch_blocks_and_preserves_manifest(monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    prior_hash = None
    if CONTENT_MANIFEST.is_file():
        prior_hash = json.loads(CONTENT_MANIFEST.read_text(encoding="utf-8")).get("content_hash")

    bad = make_batch(batch_id="batch.t133.bad", lines=_lines(30, bad_effect=True), write=True)
    assert not bad["ok"]
    assert bad["written"] is False
    assert any("unsupported effect" in e for e in bad["validate"]["errors"])

    # Failed content compile must not rewrite manifest.
    compile_result = compile_content_pack(include_dialogue=False)
    # May fail for other reasons if templates incomplete; either way prior stays or new valid write.
    if not compile_result["ok"]:
        assert compile_result["prior_manifest_intact"] is True
        if prior_hash is not None and CONTENT_MANIFEST.is_file():
            current = json.loads(CONTENT_MANIFEST.read_text(encoding="utf-8")).get("content_hash")
            assert current == prior_hash


def test_too_few_lines_rejected() -> None:
    report = validate_batch(
        {
            "schema_version": 1,
            "id": "batch.tiny",
            "lines": _lines(10),
            "provenance": {"api_dependency": False},
        }
    )
    assert not report["ok"]
    assert any("25-50" in e for e in report["errors"])


def test_quality_report_runs() -> None:
    report = build_report()
    assert "quests" in report and "dialogue" in report
    path = write_report(report)
    assert path.is_file()
