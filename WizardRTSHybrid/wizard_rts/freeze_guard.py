"""Importer guard (decision D33): the content roster is frozen, so every scripts/import_*.py refuses to run by default.

To run one on purpose (a roster bump the owner approved, see docs/CONTENT_FREEZE.md):

    DMB_UNFREEZE=1 py -3 scripts/import_openra_rules.py --reason "why this import is needed" [the script's own arguments]

`--reason <text>` (or `--reason=<text>`) is removed from sys.argv here, so the importer's own argument parser never sees it.
"""
from __future__ import annotations

import os
import sys

EXIT_FROZEN = 3
REASON_ENV = "DMB_UNFREEZE_REASON"  # set once the guard has passed, so importers that import other importers are not asked twice


def _pop_reason(argv: list[str]) -> str:
    reason = ""
    i = 1
    while i < len(argv):
        if argv[i] == "--reason" and i + 1 < len(argv):
            reason = argv[i + 1]
            del argv[i:i + 2]
        elif argv[i].startswith("--reason="):
            reason = argv[i].split("=", 1)[1]
            del argv[i]
        else:
            i += 1
    return reason.strip()


def require_unfreeze(script: str) -> None:
    """Exit 3 with a notice unless DMB_UNFREEZE=1 is set and --reason <text> is in sys.argv (D33)."""
    reason = _pop_reason(sys.argv) or os.environ.get(REASON_ENV, "")
    if os.environ.get("DMB_UNFREEZE") == "1" and reason:
        os.environ[REASON_ENV] = reason
        return
    name = os.path.basename(script)
    print(f"{name}: content is frozen (decision D33, roster-1.x). Importers are kept as the provenance record and do not run by default.\n"
          f"To run one on purpose, with the owner's approval: DMB_UNFREEZE=1 py -3 scripts/{name} --reason \"why\"\n"
          f"Then record the change with scripts/freeze_content.py --bump (see docs/CONTENT_FREEZE.md).", file=sys.stderr)
    raise SystemExit(EXIT_FROZEN)
