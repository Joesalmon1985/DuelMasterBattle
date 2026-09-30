"""Deterministic reports + offline review table for Visual Sim QA."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def new_run_dir(root: Path, run_id: str | None = None) -> Path:
    if not run_id:
        run_id = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
    out = root / "qa" / "visual_sim" / "out" / run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "shots").mkdir(exist_ok=True)
    (out / "authority").mkdir(exist_ok=True)
    (out / "render").mkdir(exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)
    return out


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")


def write_summary(run_dir: Path, summary: dict[str, Any]) -> None:
    write_json(run_dir / "summary.json", summary)


def write_review_table(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    """Write screenshots.jsonl, screenshots.csv, and a simple offline index.html."""
    jsonl = run_dir / "screenshots.jsonl"
    if jsonl.exists():
        jsonl.unlink()
    for row in rows:
        append_jsonl(jsonl, row)

    csv_path = run_dir / "screenshots.csv"
    fields = [
        "capture_id",
        "scenario_id",
        "scenario_class",
        "checkpoint",
        "seed",
        "resolution",
        "action",
        "should_be_visible",
        "assertions",
        "authority_summary",
        "render_summary",
        "image_result",
        "overall",
        "human_review",
        "image_rel",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})

    # Minimal offline HTML — relative assets only.
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>Visual Sim QA Review</title>",
        "<style>body{font-family:sans-serif;margin:1rem}table{border-collapse:collapse;width:100%}",
        "th,td{border:1px solid #ccc;padding:4px 6px;vertical-align:top;font-size:12px}",
        "img.thumb{max-width:120px;max-height:90px} .fail{background:#ffe0e0} .pass{background:#e8ffe8}",
        ".pending{background:#fff8e0}</style></head><body>",
        f"<h1>Visual Sim QA — {run_dir.name}</h1>",
        "<p>Human review PENDING. Python PASS is structural only, not aesthetic acceptance.</p>",
        "<table><tr>",
    ]
    headers = [
        "Screenshot",
        "Scenario / class",
        "Checkpoint",
        "Action",
        "Should be visible",
        "Testing",
        "Authority",
        "Render",
        "Image",
        "Overall",
        "Human",
    ]
    parts.append("".join(f"<th>{h}</th>" for h in headers))
    parts.append("</tr>")
    for row in rows:
        overall = str(row.get("overall") or "")
        cls = "fail" if overall == "FAIL" else ("pass" if overall == "PASS" else "pending")
        img = row.get("image_rel") or ""
        shot = (
            f"<a href='{img}'><img class='thumb' src='{img}' alt='{row.get('capture_id')}'></a>"
            if img
            else "<em>MISSING</em>"
        )
        parts.append(f"<tr class='{cls}'>")
        parts.append(f"<td>{shot}<br>{row.get('capture_id','')}</td>")
        parts.append(f"<td>{row.get('scenario_id','')}<br>{row.get('scenario_class','')}</td>")
        parts.append(f"<td>{row.get('checkpoint','')}<br>{row.get('resolution','')}</td>")
        parts.append(f"<td>{row.get('action','')}</td>")
        parts.append(f"<td>{row.get('should_be_visible','')}</td>")
        parts.append(f"<td>{row.get('assertions','')}</td>")
        parts.append(f"<td><pre>{row.get('authority_summary','')}</pre></td>")
        parts.append(f"<td><pre>{row.get('render_summary','')}</pre></td>")
        parts.append(f"<td>{row.get('image_result','')}</td>")
        parts.append(f"<td>{overall}</td>")
        parts.append(f"<td>{row.get('human_review','PENDING')}</td>")
        parts.append("</tr>")
    parts.append("</table></body></html>")
    (run_dir / "index.html").write_text("".join(parts), encoding="utf-8")
