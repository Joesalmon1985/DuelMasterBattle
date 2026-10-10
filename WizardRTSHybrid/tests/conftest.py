"""Unit tests isolate one system at a time, so the faction AIs are off unless a test turns them on."""

import os

os.environ.setdefault("HYBRID_AI", "0")
