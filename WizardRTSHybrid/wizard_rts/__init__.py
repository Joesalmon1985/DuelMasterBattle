"""WizardRTSHybrid authoritative simulation package."""

import sys
from pathlib import Path

__version__ = "0.1.0"

# The legacy `sim.dmb` packages (quests, people, duels, clock) live at the repository root; every module may import them.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
