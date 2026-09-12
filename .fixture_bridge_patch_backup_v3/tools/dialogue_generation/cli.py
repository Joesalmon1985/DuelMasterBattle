from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import config
from .database import DialogueDatabase
from .exporter import export_cast
from .fixture_builder import build_fixture, cmd_build_fixture
from .ollama_client import OllamaClient
from .pipeline import generate_cast, ingest_cast, review_cast
from .worldviews import load_worldviews


def _logging(verbose: bool):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _apply(args):
    if getattr(args, "workbook", None):
        config.workbook_path = Path(args.workbook)
    if getattr(args, "database", None):
        config.database_path = Path(args.database)
    if getattr(args, "model", None):
        config.model_name = args.model
    if getattr(args, "output_dir", None):
        config.output_dir = Path(args.output_dir)
    _logging(bool(getattr(args, "verbose", False)))


def _client() -> OllamaClient:
    return OllamaClient(model=config.resolve_model())


def cmd_doctor(args) -> int:
    _apply(args)
    client = _client()
    print("DUEL MASTER BATTLE — DIALOGUE FACTORY DIAGNOSTICS")
    print("=" * 55)
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok_python = sys.version_info >= (3, 11)
    print(f"Python {version:<20} {'OK' if ok_python else 'UNSUPPORTED'}")
    if not ok_python:
        return 1
    service = client.check_service()
    print(f"Ollama service....... {'OK' if service.success else 'FAIL'}")
    if not service.success:
        print(service.error)
        return 1
    model = client.model_ready(config.resolve_model())
    print(f"Model '{config.resolve_model()}'........ {'OK' if model.success else 'FAIL'}")
    if not model.success:
        print(model.error)
        return 1
    schema = {
        "type": "object",
        "properties": {"test": {"type": "string", "enum": ["ok"]}, "number": {"type": "integer", "enum": [42]}},
        "required": ["test", "number"],
        "additionalProperties": False,
    }
    resp = client.generate_with_retry(
        'Return {"test":"ok","number":42}.',
        temperature=0.0,
        num_predict=80,
        format_schema=schema,
    )
    json_ok = resp.success and resp.data == {"test": "ok", "number": 42}
    print(f"JSON generation...... {'OK' if json_ok else 'FAIL'}")
    if not json_ok:
        print(resp.error or f"Unexpected result: {resp.data}")
        return 1
    try:
        worldviews = load_worldviews()
        print(f"Worldviews........... OK ({worldviews.version}, 7 definitions)")
    except Exception as exc:
        print(f"Worldviews........... FAIL ({exc})")
        return 1
    print("\nAll checks passed. Ready for dialogue generation.")
    return 0


def _open_db() -> DialogueDatabase:
    return DialogueDatabase(config.resolve_database())


def cmd_ingest(args) -> int:
    _apply(args)
    with _open_db() as db:
        stats = ingest_cast(db, config.resolve_workbook(), args.cast_id)
    print(json.dumps(stats, indent=2))
    return 0


def cmd_status(args) -> int:
    _apply(args)
    with _open_db() as db:
        stats = db.cast_stats(args.cast_id)
    print(json.dumps(stats, indent=2))
    return 0


def cmd_generate(args) -> int:
    _apply(args)
    with _open_db() as db:
        if db.cast_stats(args.cast_id)["source_rows"] == 0:
            print(f"No ingested rows for {args.cast_id}. Run ingest first.")
            return 2
        result = generate_cast(db, args.cast_id, _client())
    print(json.dumps(result, indent=2))
    return 0 if result.get("needs_review", 0) == 0 else 3


def cmd_review(args) -> int:
    _apply(args)
    with _open_db() as db:
        result = review_cast(db, args.cast_id, _client())
    print(json.dumps(result, indent=2))
    return 0 if result.get("needs_review", 0) == 0 else 3


def cmd_export(args) -> int:
    _apply(args)
    try:
        with _open_db() as db:
            result = export_cast(db, args.cast_id, config.resolve_output_dir())
    except RuntimeError as exc:
        print(f"Export blocked: {exc}")
        return 4
    print(json.dumps(result, indent=2))
    return 0


def _add_common(parser, *, cast: bool = False, ollama: bool = False, output: bool = False, fixture: bool = False):
    if cast:
        parser.add_argument("--cast-id", default="E36B", help="Village Cast ID (vertical-slice default: E36B)")
        parser.add_argument("--database", type=Path, help="SQLite database path")
    if ollama:
        parser.add_argument("--model", help="Ollama model override")
    if output:
        parser.add_argument("--output-dir", type=Path, help="Export directory")
    if fixture:
        parser.add_argument("--output-root", type=Path, help="Fixture output root (default: godot_project/content/village_tests)")
        parser.add_argument("--force", action="store_true", help="Overwrite existing fixture")
        parser.add_argument("--validate-only", action="store_true", help="Validate without writing")
    parser.add_argument("-v", "--verbose", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dialogue-factory", description="DMB local village dialogue generation factory")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="Check Python, Ollama, model, structured output and worldview configuration")
    _add_common(p, ollama=True)
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("ingest", help="Read one Cast ID from the canonical workbook and extract response beats")
    _add_common(p, cast=True)
    p.add_argument("--workbook", type=Path, help="Canonical workbook path")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("status", help="Show persisted pipeline status for one Cast ID")
    _add_common(p, cast=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("generate", help="Classify banks, generate seven worldview exchanges and review them")
    _add_common(p, cast=True, ollama=True)
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("review", help="Re-review generated/needs-review banks without regenerating approved work")
    _add_common(p, cast=True, ollama=True)
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("export", help="Export a fully approved Cast ID to JSON and CSV")
        _add_common(p, cast=True, output=True)
        p.set_defaults(func=cmd_export)

        p = sub.add_parser("build-fixture", help="Build a Test Village fixture from approved dialogue and canonical source")
        _add_common(p, cast=True, fixture=True)
        p.add_argument("--workbook", type=Path, help="Canonical workbook path")
        p.set_defaults(func=cmd_build_fixture)
        return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nInterrupted safely. Completed database work is preserved; rerun the same command to resume.")
        return 130
    except Exception as exc:
        logging.getLogger(__name__).exception("Dialogue factory command failed")
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
