"""Framework for the runtime probes (see probe_runtime.py).

Small isolated checks that drive the REAL conversation code on a seeded world and record what actually happens.

Run:  python docs/DIALOGUE_STORY_AUDIT/scripts/probe_runtime.py
Writes: docs/DIALOGUE_STORY_AUDIT/generated/runtime_probes.json

These probes use the same helpers as the game's own tests (tests/_nh.py, tests/_campaign.py): they build a campaign world in memory (seed 507), talk to
people through the same `story.dispatch` messages the client sends, and read the replies. Nothing is written to disk but the result file, and no
game file is changed. A probe never aborts the run: an exception is recorded as the probe's result.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("HYBRID_AI", "0")
os.environ.setdefault("DMB_NO_NATIVE", "1")
os.environ["HYBRID_EXPLORE_MIN_MS"] = "20000"
os.environ["HYBRID_EXPLORE_FALLBACK_MS"] = "60000"
os.environ["HYBRID_AFTERMATH_FALLBACK_MS"] = "40000"

from common import OUT  # noqa: E402  (also puts the game's folders on sys.path)

import _nh as nh  # noqa: E402
from wizard_rts import story  # noqa: E402
from wizard_rts.narrative import campaign, checks, conversation, graph, ledger, personas, quests, residents, tutorial, wizard  # noqa: E402

RESULTS: list[dict[str, Any]] = []


TIMING_ENV = ("HYBRID_EXPLORE_MIN_MS", "HYBRID_EXPLORE_FALLBACK_MS", "HYBRID_AFTERMATH_FALLBACK_MS")


def probe(pid: str, title: str, claim: str, real_timing: bool = False):
    """Register and run one probe. `real_timing` removes the shortened exploration timers so the stranger does not arrive in the middle of the check."""
    def deco(fn: Callable[[], dict[str, Any]]):
        saved = {k: os.environ.get(k) for k in TIMING_ENV}
        if real_timing:
            for k in TIMING_ENV:
                os.environ.pop(k, None)
        try:
            res = fn()
            status = res.pop("verdict", "observed")
        except Exception as exc:  # noqa: BLE001
            res = {"error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-1500:]}
            status = "probe failed to run"
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
        RESULTS.append({"id": pid, "title": title, "claim": claim, "verdict": status, **res})
        print(f"{pid} [{status}] {title}")
        return fn
    return deco


def teacher_key(w) -> str:
    return tutorial.state(w)["teacher"]


def stand_at_teacher(w) -> str:
    t = teacher_key(w)
    tile = residents.table(w)[t]["tile"]
    w.player["tx"], w.player["ty"] = tile[0] + 1, tile[1]
    return t


def texts(reply: dict[str, Any]) -> dict[str, Any]:
    return {"lines": reply.get("lines", []), "text": reply.get("text", ""), "choices": [(c["id"], c["text"], c.get("available", True)) for c in reply.get("choices", [])],
            "ends": reply.get("ends", False), "check": reply.get("check")}



def finish() -> None:
    gen = OUT / "generated"
    gen.mkdir(exist_ok=True)
    (gen / "runtime_probes.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"{len(RESULTS)} probes -> generated/runtime_probes.json")
