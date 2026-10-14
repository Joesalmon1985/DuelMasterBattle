"""WizardRTSHybrid authoritative simulation package."""

import sys
from pathlib import Path

__version__ = "0.1.0"

# Bump whenever a game rule changes (a champion trained under other rules must be re-evaluated before it counts; neuro/manifest.py).
RULES_VERSION = "rules-2026-10-14"

# The legacy `sim.dmb` packages (quests, people, duels, clock) live at the repository root; every module may import them.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
