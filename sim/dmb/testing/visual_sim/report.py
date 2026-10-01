"""Deterministic reports + offline review table for Visual Sim QA."""

from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict
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
    (out / "checkpoints").mkdir(exist_ok=True)
    (out / "failure_packets").mkdir(exist_ok=True)
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


CSV_FIELDS = [
    "capture_id",
    "scenario_id",
    "scenario_class",
    "checkpoint",
    "seed",
    "resolution",
    "action",
    "command_receipt",
    "should_be_visible",
    "should_be_absent",
    "should_change",
    "assertions",
    "authority_summary",
    "render_summary",
    "state_verdict",
    "render_verdict",
    "image_verdict",
    "image_result",
    "overall",
    "human_review",
    "failure_signature",
    "retention",
    "image_rel",
    "auth_rel",
    "render_rel",
    "log_rel",
]


def write_review_table(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    """Write screenshots.jsonl, screenshots.csv, and offline index.html."""
    jsonl = run_dir / "screenshots.jsonl"
    if jsonl.exists():
        jsonl.unlink()
    slim_rows = []
    for row in rows:
        slim = {k: row.get(k) for k in CSV_FIELDS}
        # Keep failed assertions in JSONL for gallery filters
        slim["failed_assertions"] = row.get("failed_assertions") or []
        slim["assertion_count"] = row.get("assertion_count", 0)
        slim["session_id"] = row.get("session_id", "")
        slim["turn_or_time"] = row.get("turn_or_time", "")
        append_jsonl(jsonl, slim)
        slim_rows.append(slim)

    csv_path = run_dir / "screenshots.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in CSV_FIELDS})

    write_combined_gallery(run_dir, rows)


def write_combined_gallery(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    """Offline HTML gallery with filters and before/after pairing."""
    scenarios = sorted({str(r.get("scenario_id") or "") for r in rows})
    checkpoints = sorted({str(r.get("checkpoint") or "") for r in rows})
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>Visual Sim QA Review</title>",
        "<style>",
        "body{font-family:system-ui,sans-serif;margin:1rem;background:#f7f7f5;color:#1a1a1a}",
        "table{border-collapse:collapse;width:100%}",
        "th,td{border:1px solid #ccc;padding:4px 6px;vertical-align:top;font-size:12px}",
        "img.thumb{max-width:140px;max-height:100px;background:#222}",
        "img.compare{max-width:320px;max-height:200px;margin:2px}",
        ".fail{background:#ffe0e0}.pass{background:#e8ffe8}.pending{background:#fff8e0}.missing{background:#f0e0ff}",
        ".filters{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0;align-items:center}",
        ".pair{display:flex;gap:8px;flex-wrap:wrap}",
        "pre{white-space:pre-wrap;max-width:260px;margin:0}",
        "</style></head><body>",
        f"<h1>Visual Sim QA — {run_dir.name}</h1>",
        "<p>Human review is separate from structural PASS. Filters are client-side only.</p>",
        "<div class='filters'>",
        "<label>Scenario <select id='fScenario'><option value=''>all</option>",
    ]
    for s in scenarios:
        parts.append(f"<option value='{s}'>{s}</option>")
    parts.append("</select></label>")
    parts.append("<label>Checkpoint <select id='fCheckpoint'><option value=''>all</option>")
    for c in checkpoints:
        parts.append(f"<option value='{c}'>{c}</option>")
    parts.append("</select></label>")
    parts.append(
        "<label>Verdict <select id='fVerdict'><option value=''>all</option>"
        "<option value='PASS'>PASS</option><option value='FAIL'>FAIL</option></select></label>"
    )
    parts.append("<label>Class <select id='fClass'><option value=''>all</option>"
                 "<option value='PRODUCTION_JOURNEY'>PRODUCTION_JOURNEY</option>"
                 "<option value='ARRANGED_STATE'>ARRANGED_STATE</option></select></label>")
    parts.append("<label><input type='checkbox' id='fFailOnly'> Failures only</label>")
    parts.append("</div>")
    parts.append("<table id='gallery'><thead><tr>")
    headers = [
        "Screenshot",
        "Before/After",
        "Scenario / class",
        "Seed / res / checkpoint",
        "Action / receipt",
        "Should see / absent / change",
        "Authority",
        "Render",
        "State/Render/Image",
        "Failures / signature",
        "Overall / human / retention",
        "Links",
    ]
    parts.append("".join(f"<th>{h}</th>" for h in headers))
    parts.append("</tr></thead><tbody>")

    # Index for before/after pairing by scenario+seed+resolution
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = (row.get("scenario_id"), row.get("seed"), row.get("resolution"))
        by_key[key].append(row)

    for row in rows:
        overall = str(row.get("overall") or "")
        cls = "fail" if overall == "FAIL" else ("pass" if overall == "PASS" else "pending")
        if not row.get("image_rel"):
            cls = "missing"
        img = row.get("image_rel") or ""
        shot = (
            f"<a href='{img}'><img class='thumb' src='{img}' alt='{row.get('capture_id')}'></a>"
            if img
            else "<em>MISSING</em>"
        )
        # Find a sibling before/after
        pair_html = ""
        key = (row.get("scenario_id"), row.get("seed"), row.get("resolution"))
        siblings = by_key.get(key) or []
        before = next((s for s in siblings if s.get("checkpoint") == "before"), None)
        after = next((s for s in siblings if s.get("checkpoint") in {"after", "aftermath"}), None)
        if before and after and before.get("image_rel") and after.get("image_rel"):
            pair_html = (
                f"<div class='pair'>"
                f"<div>before<br><a href='{before['image_rel']}'><img class='compare' src='{before['image_rel']}'></a></div>"
                f"<div>after<br><a href='{after['image_rel']}'><img class='compare' src='{after['image_rel']}'></a></div>"
                f"</div>"
            )
        fails = row.get("failed_assertions") or []
        fail_txt = json.dumps(fails, default=str)[:400] if fails else ""
        links = " ".join(
            f"<a href='{row[k]}'>{k}</a>"
            for k in ("auth_rel", "render_rel", "log_rel", "image_rel")
            if row.get(k)
        )
        parts.append(
            f"<tr class='{cls}' data-scenario='{row.get('scenario_id','')}' "
            f"data-checkpoint='{row.get('checkpoint','')}' data-verdict='{overall}' "
            f"data-class='{row.get('scenario_class','')}'>"
        )
        parts.append(f"<td>{shot}<br>{row.get('capture_id','')}</td>")
        parts.append(f"<td>{pair_html}</td>")
        parts.append(f"<td>{row.get('scenario_id','')}<br>{row.get('scenario_class','')}</td>")
        parts.append(
            f"<td>seed={row.get('seed','')}<br>{row.get('resolution','')}<br>{row.get('checkpoint','')}"
            f"<br>t={row.get('turn_or_time','')}</td>"
        )
        parts.append(f"<td>{row.get('action','')}<br>{row.get('command_receipt','')}</td>")
        parts.append(
            f"<td><b>see:</b> {row.get('should_be_visible','')}<br>"
            f"<b>absent:</b> {row.get('should_be_absent','')}<br>"
            f"<b>change:</b> {row.get('should_change','')}</td>"
        )
        parts.append(f"<td><pre>{row.get('authority_summary','')}</pre></td>")
        parts.append(f"<td><pre>{row.get('render_summary','')}</pre></td>")
        parts.append(
            f"<td>S:{row.get('state_verdict', row.get('image_result',''))} "
            f"R:{row.get('render_verdict','')} I:{row.get('image_verdict', row.get('image_result',''))}</td>"
        )
        parts.append(f"<td><pre>{fail_txt}</pre><br>sig={row.get('failure_signature','')}</td>")
        parts.append(
            f"<td>{overall}<br>human={row.get('human_review','PENDING')}<br>ret={row.get('retention','')}</td>"
        )
        parts.append(f"<td>{links}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    parts.append(
        """<script>
const rows=[...document.querySelectorAll('#gallery tbody tr')];
function apply(){
  const s=document.getElementById('fScenario').value;
  const c=document.getElementById('fCheckpoint').value;
  const v=document.getElementById('fVerdict').value;
  const cl=document.getElementById('fClass').value;
  const fo=document.getElementById('fFailOnly').checked;
  rows.forEach(r=>{
    let show=true;
    if(s && r.dataset.scenario!==s) show=false;
    if(c && r.dataset.checkpoint!==c) show=false;
    if(v && r.dataset.verdict!==v) show=false;
    if(cl && r.dataset.class!==cl) show=false;
    if(fo && r.dataset.verdict==='PASS') show=false;
    r.style.display=show?'':'none';
  });
}
['fScenario','fCheckpoint','fVerdict','fClass','fFailOnly'].forEach(id=>{
  document.getElementById(id).addEventListener('change', apply);
  document.getElementById(id).addEventListener('input', apply);
});
</script></body></html>"""
    )
    (run_dir / "index.html").write_text("".join(parts), encoding="utf-8")


def cluster_failures(run_dir: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cluster by signature; write one representative packet per signature."""
    packets_dir = run_dir / "failure_packets"
    packets_dir.mkdir(exist_ok=True)
    by_sig: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        sig = str(row.get("failure_signature") or "")
        if not sig:
            continue
        by_sig[sig].append(row)
    packets = []
    for sig, occ in by_sig.items():
        rep = occ[0]
        shots = []
        for r in occ[:3]:
            rel = r.get("image_rel") or ""
            if not rel:
                continue
            src = run_dir / rel
            if src.is_file():
                dest = packets_dir / f"{sig}_{Path(rel).name}"
                try:
                    shutil.copy2(src, dest)
                    shots.append(str(dest.relative_to(run_dir)))
                except OSError:
                    shots.append(rel)
            else:
                shots.append(rel)
        packet = {
            "signature": sig,
            "occurrences": len(occ),
            "scenario_id": rep.get("scenario_id"),
            "capture_id": rep.get("capture_id"),
            "checkpoint": rep.get("checkpoint"),
            "seed": rep.get("seed"),
            "resolution": rep.get("resolution"),
            "action": rep.get("action"),
            "failed_assertions": rep.get("failed_assertions"),
            "authority_summary": rep.get("authority_summary"),
            "render_summary": rep.get("render_summary"),
            "auth_rel": rep.get("auth_rel"),
            "render_rel": rep.get("render_rel"),
            "log_rel": rep.get("log_rel"),
            "screenshots": shots,
            "all_occurrence_ids": [o.get("capture_id") for o in occ],
            "reproduction": {
                "scenario_id": rep.get("scenario_id"),
                "seed": rep.get("seed"),
                "resolution": rep.get("resolution"),
                "session_id": rep.get("session_id"),
            },
        }
        write_json(packets_dir / f"{sig}.json", packet)
        packets.append(packet)
    write_json(run_dir / "failure_clusters.json", {"signatures": list(by_sig.keys()), "packet_count": len(packets)})
    return packets
