"""
Command-line interface for the Dialogue Generation Factory.

Commands:
  doctor     - Run diagnostics (Ollama, model, JSON generation)
  ingest     - Ingest workbook into SQLite
  dedupe     - Run exact deduplication
  banks      - Classify dialogue banks
  generate   - Generate seven-worldview exchanges
  review     - Run Mistral review
  status     - Show pipeline status
  retry      - Retry failed jobs
  export     - Export approved dialogue
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from .config import config
from .ollama_client import OllamaClient


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )


def cmd_doctor(args: argparse.Namespace) -> int:
    """Run diagnostics against local Ollama + Mistral."""
    setup_logging(args.verbose)
    log = logging.getLogger(__name__)

    client = OllamaClient()

    print("DUEL MASTER BATTLE — DIALOGUE FACTORY DIAGNOSTICS")
    print("=" * 55)

    # Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"Python {py_version:<20} {'OK' if sys.version_info >= (3, 11) else 'UNSUPPORTED'}")

    # Ollama service
    print("Ollama service....... ", end="", flush=True)
    resp = client.check_service()
    if resp.success:
        print("OK")
    else:
        print(f"FAIL ({resp.error})")
        return 1

    # Model availability
    model_name = config.resolve_model()
    print(f"Model '{model_name}'........ ", end="", flush=True)
    resp = client.model_ready(model_name)
    if resp.success:
        print("OK")
    else:
        print(f"FAIL ({resp.error})")
        return 1

    # JSON generation test
    print("JSON generation...... ", end="", flush=True)
    test_prompt = """Return a JSON object with exactly these keys: "test": "ok", "number": 42, "list": [1, 2, 3]. No extra text."""
    resp = client.generate_json(test_prompt, temperature=0.1)
    if resp.success and resp.data:
        expected = {"test": "ok", "number": 42, "list": [1, 2, 3]}
        if resp.data == expected:
            print("OK")
        else:
            print(f"MISMATCH (got {resp.data})")
            return 1
    else:
        print(f"FAIL ({resp.error})")
        if resp.raw_response:
            log.debug(f"Raw response: {resp.raw_response[:500]}")
        return 1

    print("\nAll checks passed. Ready for dialogue generation.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show pipeline status (placeholder)."""
    setup_logging(args.verbose)
    print("Pipeline status command — not yet implemented")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="dialogue-factory",
        description="Duel Master Battle — Village Dialogue Generation Factory"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--workbook", type=Path, help="Path to workbook file")
    parser.add_argument("--database", type=Path, help="Path to SQLite database")
    parser.add_argument("--model", help="Ollama model name")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # doctor
    subparsers.add_parser("doctor", help="Run diagnostics")

    # status
    subparsers.add_parser("status", help="Show pipeline status")

    # Placeholders for other commands
    for cmd in ["ingest", "dedupe", "banks", "generate", "review", "retry", "export"]:
        subparsers.add_parser(cmd, help=f"{cmd} — not yet implemented")

    args = parser.parse_args()

    # Apply runtime overrides
    if args.workbook:
        config.workbook_path = args.workbook
    if args.database:
        config.database_path = args.database
    if args.model:
        config.model_name = args.model
    config.verbose = args.verbose
    config.dry_run = args.dry_run

    # Dispatch
    if args.command == "doctor":
        return cmd_doctor(args)
    elif args.command == "status":
        return cmd_status(args)
    else:
        print(f"Command '{args.command}' not yet implemented")
        return 1


if __name__ == "__main__":
    sys.exit(main())