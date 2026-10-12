"""Five real minutes of idle simulation.

A faster advance() test guards the same stock invariant. This file is the
wall-clock run and is not part of the quick suite. Run it directly:

    py -3 WizardRTSHybrid/tests/test_five_minutes.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from wizard_rts.world import HybridWorld


def main() -> int:
    world = HybridWorld()
    # The red road stays blocked. Blue can still produce and deliver.
    start = time.monotonic()
    last = start
    sequence = 0
    while time.monotonic() - start < 300.0:
        now = time.monotonic()
        elapsed_ms = int((now - last) * 1000)
        last = now
        if elapsed_ms > 0:
            sequence += 1
            world.advance(elapsed_ms, sequence)
        time.sleep(0.2)
    elapsed = time.monotonic() - start
    produced = int(world.stats["produce"])
    delivered = int(world.stats["deliver"])
    print(f"FIVE_MINUTES elapsed={elapsed:.1f} produce={produced} deliver={delivered} game_ms={world.dmb.clock.get('game_ms')}")
    if elapsed < 300.0 or produced <= 0 or delivered <= 0:
        print("FIVE_MINUTES_FAIL")
        return 1
    print("FIVE_MINUTES_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
