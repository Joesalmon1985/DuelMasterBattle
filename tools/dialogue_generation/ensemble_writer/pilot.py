from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import config
from ..ensemble.policies import WRITER_POLICIES
from ..ollama_client import OllamaClient
from .auditors import emotional_audit, mechanics_audit, normalize_speakers, subjectivity_audit
from .beat_writer import generate_beat_plan
from .dialogue_writer import generate_dialogue
from .packet_compiler import compile_scene_packet
from .reviser import revise_dialogue
from .selector import DEFAULT_COUNT, MAX_COUNT, select_pilot_scenes, selection_record, validate_count

PASS_FILES = (
    "packet",
    "beats",
    "draft",
    "mechanics_audit",
    "subjectivity_audit",
    "emotional_audit",
    "final",
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def scene_pass_path(output_dir: Path, scene_id: str, pass_name: str) -> Path:
    return output_dir / f"{scene_id}_{pass_name}.json"


def load_manifests(path: Path) -> list[dict]:
    payload = _load_json(path)
    if isinstance(payload, dict):
        scenes = payload.get("scenes")
        if isinstance(scenes, list):
            return scenes
    if isinstance(payload, list):
        return payload
    raise ValueError(f"{path} does not contain a scene catalogue")


def _lookup(manifests: list[dict], scene_ids: list[str]) -> list[dict]:
    by_id = {scene["scene_id"]: scene for scene in manifests}
    missing = [sid for sid in scene_ids if sid not in by_id]
    if missing:
        raise ValueError("Recorded pilot selection references missing scenes: " + ", ".join(missing))
    return [by_id[sid] for sid in scene_ids]


def resolve_selection(manifests: list[dict], output_dir: Path, *, count: int, force: bool) -> tuple[list[dict], dict]:
    selection_path = output_dir / "pilot_selection.json"
    if selection_path.exists() and not force:
        record = _load_json(selection_path)
        scenes = _lookup(manifests, list(record.get("scene_ids") or []))
        if len(scenes) != count:
            raise ValueError(
                f"Existing pilot_selection.json has {len(scenes)} scenes; requested {count}. "
                "Use --force to reselect rather than silently substituting."
            )
        return scenes, record
    scenes = select_pilot_scenes(manifests, count=count)
    record = selection_record(scenes)
    record["selected_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(selection_path, record)
    return scenes, record


def _should_skip(path: Path, force: bool) -> bool:
    return path.exists() and not force


def process_scene(
    scene: dict,
    manifests: list[dict],
    output_dir: Path,
    client: OllamaClient | None,
    *,
    model: str | None,
    force: bool,
    offline: bool = False,
    reaudit: bool = False,
    local_audits: bool = False,
) -> dict:
    scene_id = scene["scene_id"]
    result = {
        "scene_id": scene_id,
        "scene_type": scene.get("scene_type"),
        "primary_character_id": scene.get("primary_character_id"),
        "status": "incomplete",
        "canon_block_before_revision": None,
        "canon_block_after_revision": None,
        "approved": False,
        "skipped_passes": [],
        "error": None,
    }

    packet_path = scene_pass_path(output_dir, scene_id, "packet")
    if _should_skip(packet_path, force):
        packet = _load_json(packet_path)
        result["skipped_passes"].append("packet")
    else:
        packet = compile_scene_packet(scene, catalogue=manifests, policies=WRITER_POLICIES)
        _write_json(packet_path, packet)

    final_path = scene_pass_path(output_dir, scene_id, "final")
    if _should_skip(final_path, force or reaudit):
        final = _load_json(final_path)
        result.update({
            "status": "skipped_complete" if final.get("approved") else "skipped_unapproved",
            "approved": bool(final.get("approved")),
            "canon_block_before_revision": final.get("canon_block_before_revision"),
            "canon_block_after_revision": final.get("canon_block_after_revision"),
        })
        result["skipped_passes"].append("final")
        return result

    beats_path = scene_pass_path(output_dir, scene_id, "beats")
    draft_path = scene_pass_path(output_dir, scene_id, "draft")
    can_resume_without_llm = beats_path.exists() and draft_path.exists() and not force
    if (offline or client is None) and not can_resume_without_llm:
        result["status"] = "packet_only"
        result["error"] = "Ollama client unavailable; packet compiled only"
        return result

    if _should_skip(beats_path, force):
        beats = _load_json(beats_path)
        result["skipped_passes"].append("beats")
    else:
        resp = generate_beat_plan(client, packet, model=model)
        if not resp.success:
            result["status"] = "failed_beats"
            result["error"] = resp.error
            _write_json(output_dir / f"{scene_id}_error.json", {"pass": "beats", "error": resp.error})
            return result
        beats = resp.data or {}
        beats.setdefault("scene_id", scene_id)
        _write_json(beats_path, beats)

    if _should_skip(draft_path, force):
        draft = _load_json(draft_path)
        result["skipped_passes"].append("draft")
    else:
        resp = generate_dialogue(client, packet, beats, model=model)
        if not resp.success:
            result["status"] = "failed_draft"
            result["error"] = resp.error
            _write_json(output_dir / f"{scene_id}_error.json", {"pass": "draft", "error": resp.error})
            return result
        draft = resp.data or {}
        draft.setdefault("scene_id", scene_id)
        _write_json(draft_path, draft)

    draft = normalize_speakers(draft, packet)
    _write_json(draft_path, draft)

    audit_client = None if local_audits else client

    def _audit_file(name: str, fn) -> dict:
        path = scene_pass_path(output_dir, scene_id, name)
        if _should_skip(path, force or reaudit):
            result["skipped_passes"].append(name)
            return _load_json(path)
        report = fn(audit_client, packet, draft, model=model)
        _write_json(path, report)
        return report

    mechanics = _audit_file("mechanics_audit", mechanics_audit)
    subjectivity = _audit_file("subjectivity_audit", subjectivity_audit)
    emotional = _audit_file("emotional_audit", emotional_audit)
    result["canon_block_before_revision"] = bool(mechanics.get("canon_block"))

    revision_path = scene_pass_path(output_dir, scene_id, "revision")
    if _should_skip(revision_path, force) and revision_path.exists():
        revision = _load_json(revision_path)
        result["skipped_passes"].append("revision")
    elif client is None:
        revision = {"scene_id": scene_id, "revision_notes": ["Local-audit pass reused existing draft; no LLM revision."], "lines": draft.get("lines") or []}
        _write_json(revision_path, revision)
    else:
        resp = revise_dialogue(
            client,
            packet,
            draft,
            {"mechanics": mechanics, "subjectivity": subjectivity, "emotional": emotional},
            model=model,
        )
        if not resp.success:
            result["status"] = "failed_revision"
            result["error"] = resp.error
            _write_json(output_dir / f"{scene_id}_error.json", {"pass": "revision", "error": resp.error})
            return result
        revision = resp.data or {}
        revision.setdefault("scene_id", scene_id)
        _write_json(revision_path, revision)

    revision = dict(revision)
    revision["lines"] = normalize_speakers({"lines": revision.get("lines") or []}, packet)["lines"]
    _write_json(revision_path, revision)

    revised_draft = {"scene_id": scene_id, "lines": revision.get("lines") or draft.get("lines") or []}
    mechanics_after = mechanics_audit(audit_client, packet, revised_draft, model=model)
    _write_json(scene_pass_path(output_dir, scene_id, "mechanics_audit_after"), mechanics_after)
    result["canon_block_after_revision"] = bool(mechanics_after.get("canon_block"))
    approved = not mechanics_after.get("canon_block")

    final = {
        "schema_version": "dmb-ensemble-pilot-final-v1",
        "scene_id": scene_id,
        "scene_type": scene.get("scene_type"),
        "approved": approved,
        "canon_block_before_revision": result["canon_block_before_revision"],
        "canon_block_after_revision": result["canon_block_after_revision"],
        "packet_ref": str(packet_path),
        "lines": revised_draft["lines"],
        "revision_notes": revision.get("revision_notes") or [],
        "mechanics_after": mechanics_after,
        "python_owns_canonical_state": True,
    }
    _write_json(final_path, final)
    result["status"] = "approved" if approved else "canon_block"
    result["approved"] = approved
    return result


def _speaker_labels(packet: dict) -> dict[str, str]:
    labels = {"PLAYER": "Player"}
    for profile in packet.get("participants") or []:
        cid = str(profile.get("character_id") or "")
        if cid:
            labels[cid] = str(profile.get("display_name") or cid)
    return labels


def _format_lines(lines: list[dict], labels: dict[str, str] | None = None) -> str:
    labels = labels or {}
    chunks = []
    for line in lines:
        speaker = str(line.get("speaker_id") or "?")
        name = labels.get(speaker, speaker)
        tag = f" (`{speaker}`)" if name != speaker else ""
        action = f" *{line.get('action')}*" if line.get("action") else ""
        chunks.append(f"- **{name}**{tag}{action}: {line.get('text')}")
    return "\n".join(chunks) if chunks else "_No lines._"


def _notable_findings(report: dict, limit: int = 8) -> list[str]:
    rows = []
    for finding in report.get("findings") or []:
        if str(finding.get("category") or "").endswith("_preserved"):
            continue
        rows.append(f"  - `{finding.get('severity')}` {finding.get('category')}: {finding.get('detail')}")
        if len(rows) >= limit:
            break
    return rows


def write_review_markdown(output_dir: Path, selection: dict, scene_results: list[dict], manifests: list[dict], model: str) -> Path:
    by_id = {scene["scene_id"]: scene for scene in manifests}
    lines = [
        "# Ensemble writer pilot review",
        "",
        "Offline LLM authoring only. Python still owns canonical game state.",
        "",
        f"- Model: `{model}`",
        f"- Scene IDs: {', '.join(selection.get('scene_ids') or [])}",
        f"- Types: {', '.join(selection.get('scene_types') or [])}",
        "",
        "Mechanics PASS means spoken lines did not invent identity, leak writer-only secrets, or break predecessor bindings. It is not a quality judgement.",
        "",
    ]
    for result in scene_results:
        scene = by_id.get(result["scene_id"], {})
        packet_path = scene_pass_path(output_dir, result["scene_id"], "packet")
        final_path = scene_pass_path(output_dir, result["scene_id"], "final")
        packet = _load_json(packet_path) if packet_path.exists() else {}
        final = _load_json(final_path) if final_path.exists() else {}
        names = ", ".join(
            f"{p.get('display_name')} ({p.get('character_id')})"
            for p in packet.get("participants") or []
        )
        mech = _load_json(scene_pass_path(output_dir, result["scene_id"], "mechanics_audit")) if scene_pass_path(output_dir, result["scene_id"], "mechanics_audit").exists() else {}
        mech_after = _load_json(scene_pass_path(output_dir, result["scene_id"], "mechanics_audit_after")) if scene_pass_path(output_dir, result["scene_id"], "mechanics_audit_after").exists() else final.get("mechanics_after") or {}
        subj = _load_json(scene_pass_path(output_dir, result["scene_id"], "subjectivity_audit")) if scene_pass_path(output_dir, result["scene_id"], "subjectivity_audit").exists() else {}
        emo = _load_json(scene_pass_path(output_dir, result["scene_id"], "emotional_audit")) if scene_pass_path(output_dir, result["scene_id"], "emotional_audit").exists() else {}
        labels = _speaker_labels(packet)
        lines += [
            f"## {result['scene_id']} — {result.get('scene_type')}",
            "",
            f"- Characters: {names or result.get('primary_character_id')}",
            f"- Premise: {(packet.get('SCENE_FUNCTION') or {}).get('dramatic_problem') or scene.get('dramatic_problem')}",
            f"- Status: {result.get('status')}",
            f"- Mechanics before revision: {'CANON_BLOCK' if result.get('canon_block_before_revision') else 'clear'}",
            f"- Mechanics after revision: {'CANON_BLOCK' if result.get('canon_block_after_revision') else 'PASS' if result.get('approved') else 'unknown'}",
            "",
            "### Final dialogue",
            "",
            _format_lines(final.get("lines") or [], labels),
            "",
            "### Auditor findings",
            "",
            f"- Mechanics before: {mech.get('verdict') or 'n/a'} — {mech.get('summary') or ''}",
            f"- Mechanics after: {mech_after.get('verdict') or 'n/a'} — {mech_after.get('summary') or ''}",
            f"- Subjectivity: {subj.get('verdict') or 'n/a'} — {subj.get('summary') or ''}",
            f"- Emotional craft: {emo.get('verdict') or 'n/a'} — {emo.get('summary') or ''}",
        ]
        notable = _notable_findings(mech) + _notable_findings(subj) + _notable_findings(emo) + _notable_findings(mech_after)
        lines.extend(notable[:12] or ["  - No actionable findings after preservation notes were filtered."])
        notes = final.get("revision_notes") or []
        if notes:
            lines.append("")
            lines.append("### Revisions")
            lines.append("")
            for note in notes:
                lines.append(f"- {note}")
        lines.append("")

    lines += [
        "## Human score sheet",
        "",
        "For each scene answer PASS / MIXED / FAIL plus notes.",
        "",
        "| Scene | 1 Different voices | 2 Each wants something | 3 Info revealed naturally | 4 Subtext | 5 Contradicts facts | 6 Quest terminal | 7 Scene changes something | 8 Want to continue | Notes |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in scene_results:
        lines.append(f"| {result['scene_id']} |  |  |  |  |  |  |  |  |  |")
    lines += [
        "",
        "Questions:",
        "1. Do the characters sound recognisably different?",
        "2. Does each character appear to want something?",
        "3. Is information revealed naturally?",
        "4. Does the scene contain subtext?",
        "5. Does anything contradict established facts?",
        "6. Is any character behaving like a quest terminal?",
        "7. Does the scene change something?",
        "8. Would I want to continue the conversation?",
        "",
    ]
    path = output_dir / "pilot_review.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_pilot(
    *,
    manifest_path: Path,
    output_dir: Path,
    model: str | None,
    count: int = DEFAULT_COUNT,
    force: bool = False,
    allow_more: bool = False,
    offline: bool = False,
    client: OllamaClient | None = None,
    reaudit: bool = False,
    local_audits: bool = False,
) -> dict:
    count = validate_count(count, allow_more=allow_more)
    manifests = load_manifests(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    scenes, selection = resolve_selection(manifests, output_dir, count=count, force=force)

    resolved_model = model or config.resolve_model()
    active_client = client
    if not offline and not local_audits and active_client is None:
        active_client = OllamaClient(model=resolved_model)
        ready = active_client.model_ready(resolved_model)
        if not ready.success:
            raise RuntimeError(ready.error or f"Ollama model {resolved_model} is not ready")

    results = [
        process_scene(scene, manifests, output_dir, active_client, model=resolved_model, force=force, offline=offline, reaudit=reaudit, local_audits=local_audits)
        for scene in scenes
    ]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": resolved_model,
        "count": count,
        "offline": offline,
        "local_audits": local_audits,
        "selection": selection,
        "scenes": results,
        "canon_blocks_before_revision": sum(1 for item in results if item.get("canon_block_before_revision")),
        "canon_blocks_after_revision": sum(1 for item in results if item.get("canon_block_after_revision")),
        "approved": sum(1 for item in results if item.get("approved")),
        "python_owns_canonical_state": True,
    }
    _write_json(output_dir / "pilot_summary.json", summary)
    write_review_markdown(output_dir, selection, results, manifests, resolved_model)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a bounded offline ensemble dialogue pilot")
    parser.add_argument("--manifest", type=Path, default=Path("generated/dialogue/ensemble/scene_manifests.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("generated/dialogue/ensemble_pilot"))
    parser.add_argument("--model", default=None, help="Ollama model name (defaults to configured model)")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--force", action="store_true", help="Regenerate completed passes")
    parser.add_argument("--allow-more", action="store_true", help=f"Allow up to {20} scenes; still will not generate the catalogue")
    parser.add_argument("--offline", action="store_true", help="Compile packets/selection only; do not call Ollama")
    parser.add_argument("--reaudit", action="store_true", help="Reuse drafts/beats and rerun audits/final without regenerating dialogue")
    parser.add_argument("--local-audits", action="store_true", help="Run deterministic local audits only; do not call Ollama for audit/revision passes already on disk")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = run_pilot(
            manifest_path=args.manifest,
            output_dir=args.output_dir,
            model=args.model,
            count=args.count,
            force=args.force,
            allow_more=args.allow_more,
            offline=args.offline,
            reaudit=args.reaudit,
            local_audits=args.local_audits,
        )
        print(json.dumps({
            "output_dir": str(args.output_dir),
            "scene_ids": summary["selection"]["scene_ids"],
            "approved": summary["approved"],
            "canon_blocks_before_revision": summary["canon_blocks_before_revision"],
            "canon_blocks_after_revision": summary["canon_blocks_after_revision"],
            "scenes": [
                {"scene_id": item["scene_id"], "status": item["status"], "approved": item["approved"]}
                for item in summary["scenes"]
            ],
        }, indent=2))
        failed = [item for item in summary["scenes"] if str(item.get("status", "")).startswith("failed")]
        return 1 if failed else 0
    except KeyboardInterrupt:
        print("\nInterrupted safely. Completed pass files were kept.")
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
