"""T141 content matrix / coverage validation."""

from __future__ import annotations

from pathlib import Path

from tools.content.validate_corpus import validate_corpus, write_coverage

ROOT = Path(__file__).resolve().parents[2]
TRACKING = ROOT / "Pack" / "DuelMasterBattle_Build_Pack" / "tracking" / "content_coverage"


def test_content_matrix_passes_and_writes_coverage() -> None:
    report = validate_corpus()
    assert report["ok"], report["errors"]
    assert report["counts"]["dungeons"] == 8
    assert report["counts"]["rivals"] == 4
    assert report["counts"]["dialogue_lines"] >= 1200
    assert all(v >= 2 for v in report["counts"]["quests_by_family"].values())
    path = write_coverage(report)
    assert path.is_file()
    assert (TRACKING / "coverage_report.md").is_file()
    # Unreviewed items listed separately from hard errors
    assert "unreviewed_items" in report
