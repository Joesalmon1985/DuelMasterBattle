from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ensemble.policies import WRITER_POLICIES
from .ensemble.profiles import load_profiles
from .ensemble.quality import build_quality_report, write_quality_report
from .ensemble.relationship_graph import (
    RelationshipEdge,
    build_relationship_graph,
    edge_from_mapping,
    write_relationship_csv,
    write_relationship_json,
)
from .ensemble.scene_manifest_generator import (
    generate_scene_manifests,
    write_manifests_json,
    write_manifests_jsonl,
)
from .ensemble.summary import coverage_report, write_scene_summary
from .ensemble.validation import validate_ensemble

DEFAULT_PROFILES = Path("docs/characters/DMB_Character_Profiles_88_Disco_Elysium_Depth.csv")
DEFAULT_OUTPUT = Path("generated/dialogue/ensemble")


def _paths(output_dir: Path) -> dict[str, Path]:
    return {
        "relationships_csv": output_dir / "relationship_graph.csv",
        "relationships_json": output_dir / "relationship_graph.json",
        "scenes_jsonl": output_dir / "scene_manifests.jsonl",
        "scenes_json": output_dir / "scene_manifests.json",
        "scene_summary": output_dir / "scene_manifest_summary.csv",
        "coverage": output_dir / "coverage_report.json",
        "validation": output_dir / "validation_report.json",
        "quality_json": output_dir / "quality_report.json",
        "quality_txt": output_dir / "quality_report.txt",
        "policies": output_dir / "writer_policies.json",
    }


def build_all(profiles_path: Path, output_dir: Path, target_scenes: int, seed: int) -> dict:
    profiles = load_profiles(profiles_path)
    edges = build_relationship_graph(profiles)
    manifests = generate_scene_manifests(profiles, edges, target_scenes=target_scenes, seed=seed)
    report = validate_ensemble(profiles, edges, manifests)
    paths = _paths(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_relationship_csv(edges, paths["relationships_csv"])
    write_relationship_json(profiles, edges, paths["relationships_json"])
    write_manifests_jsonl(manifests, paths["scenes_jsonl"])
    write_manifests_json(manifests, paths["scenes_json"])
    write_scene_summary(manifests, paths["scene_summary"])
    paths["coverage"].write_text(
        json.dumps(coverage_report(manifests, [p.id for p in profiles]), indent=2) + "\n",
        encoding="utf-8",
    )
    paths["validation"].write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    paths["policies"].write_text(json.dumps(WRITER_POLICIES, indent=2) + "\n", encoding="utf-8")
    quality = build_quality_report(profiles, edges, manifests, baseline=_load_baseline())
    write_quality_report(quality, output_dir)

    if not report["valid"]:
        raise RuntimeError("Ensemble generation failed validation: " + "; ".join(report["errors"]))
    if quality["flags"]:
        raise RuntimeError("Ensemble quality gates failed: " + "; ".join(quality["flags"]))

    return {
        "profiles": len(profiles),
        "relationship_edges": len(edges),
        "scenes": len(manifests),
        "seed": seed,
        "output_dir": str(output_dir),
        "validation": report,
        "quality_flags": quality["flags"],
    }


BASELINE_PATH = Path("tools/dialogue_generation/ensemble/quality_baseline.json")


def _load_baseline() -> dict | None:
    if BASELINE_PATH.exists():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return None


def _edges_from_payload(payload: dict) -> list[RelationshipEdge]:
    return [edge_from_mapping(row) for row in payload.get("edges", [])]


def validate_existing(profiles_path: Path, output_dir: Path) -> dict:
    profiles = load_profiles(profiles_path)
    paths = _paths(output_dir)

    missing = [str(path) for path in (paths["relationships_json"], paths["scenes_json"]) if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing generated ensemble file(s): " + ", ".join(missing))

    relationship_payload = json.loads(paths["relationships_json"].read_text(encoding="utf-8"))
    scene_payload = json.loads(paths["scenes_json"].read_text(encoding="utf-8"))

    edges = _edges_from_payload(relationship_payload)
    manifests = scene_payload.get("scenes", [])
    if not isinstance(manifests, list):
        raise ValueError("scene_manifests.json must contain a 'scenes' list")

    report = validate_ensemble(profiles, edges, manifests)
    paths["validation"].write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def quality_existing(profiles_path: Path, output_dir: Path, *, persist_baseline: bool = False) -> dict:
    profiles = load_profiles(profiles_path)
    paths = _paths(output_dir)
    missing = [str(path) for path in (paths["relationships_json"], paths["scenes_json"]) if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing generated ensemble file(s): " + ", ".join(missing))
    relationship_payload = json.loads(paths["relationships_json"].read_text(encoding="utf-8"))
    scene_payload = json.loads(paths["scenes_json"].read_text(encoding="utf-8"))
    edges = _edges_from_payload(relationship_payload)
    manifests = scene_payload.get("scenes", [])
    report = build_quality_report(profiles, edges, manifests, baseline=_load_baseline())
    write_quality_report(report, output_dir)
    if persist_baseline:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        snapshot = {key: value for key, value in report.items() if key != "delta_from_baseline"}
        BASELINE_PATH.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def _add_common_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES, help="Character profile CSV")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="Ensemble output directory")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dmb-ensemble",
        description="Build and validate the offline DMB character relationship graph and scene manifest catalogue",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("build-all", help="Build graph, scene manifests, coverage and validation outputs")
    _add_common_paths(p)
    p.add_argument("--target-scenes", type=int, default=300)
    p.add_argument("--seed", type=int, default=1337)

    p = sub.add_parser("validate-output", help="Validate already generated relationship and scene files")
    _add_common_paths(p)

    p = sub.add_parser("quality-report", help="Write a quality/diversity report for profiles, graph and scenes")
    _add_common_paths(p)
    p.add_argument("--persist-baseline", action="store_true", help="Store this report as the committed quality baseline")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "build-all":
            result = build_all(args.profiles, args.output_dir, args.target_scenes, args.seed)
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "validate-output":
            report = validate_existing(args.profiles, args.output_dir)
            print(json.dumps(report, indent=2))
            return 0 if report.get("valid") else 1
        if args.command == "quality-report":
            report = quality_existing(args.profiles, args.output_dir, persist_baseline=args.persist_baseline)
            print(json.dumps({"pass": report.get("pass"), "flags": report.get("flags"), "delta_from_baseline": report.get("delta_from_baseline")}, indent=2))
            return 0 if report.get("pass") else 1
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted safely.")
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
