"""Write the inspector catalogue the Godot panel test reads: godot_project/client/tests/fixtures/inspector_catalogue.json (server-free test).

    python3 scripts/export_inspector_fixture.py
"""
import json
import os
import sys
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HYB))
sys.path.insert(0, str(HYB.parent))
os.environ.setdefault("HYBRID_AI", "0")

from wizard_rts import inspector  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402

w = HybridWorld(507, profile="developer")
w.cardset = "v2"
out = HYB.parent / "godot_project" / "client" / "tests" / "fixtures" / "inspector_catalogue.json"
data = inspector.catalogue(w)
out.write_text(json.dumps(data, indent=1))
print("wrote", out, len(data["cards"]), "cards")
