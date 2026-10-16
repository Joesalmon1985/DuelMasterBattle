"""A Wizard World session without sockets or wall time: a real world, a real `MultiplayerSession`, humans (and optionally the AI companion) who act by
sending the same messages a connection would, and a clock the test advances. Used by test_wizard_party.py and test_ai_wizard.py."""
from __future__ import annotations

import os
import sys
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
for entry in (str(HYB), str(HYB.parent), str(HYB / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)
os.environ.setdefault("DMB_NO_NATIVE", "1")

import _nh as nh  # noqa: E402
from wizard_rts import narrative, story  # noqa: E402
from wizard_rts.narrative import campaign, party, tutorial, wizard  # noqa: E402
from wizard_rts.net import protocol  # noqa: E402
from wizard_rts.net.host import new_world  # noqa: E402
from wizard_rts.net.session import MultiplayerSession  # noqa: E402

SECRET, CODE = "party-secret", "5150"


class Human:
    """One connected wizard: sends messages to the session and keeps its own move sequence."""

    def __init__(self, table: "Table", name: str, host: bool) -> None:
        self.table = table
        self.conn = object()
        self.name = name
        r = table.session.handle(self.conn, {"op": "hello", "protocol": protocol.PROTOCOL_VERSION, "game": protocol.GAME_VERSION, "name": name,
                                             **({"secret": SECRET} if host else {"code": CODE})}, table.now)
        assert r["status"] == "ok", r
        self.id = r["player_id"]
        self.token = r["token"]
        self.link = table.session.links[self.id]
        self.seq = 0

    def drop(self) -> None:
        self.table.session.disconnect(self.conn, self.table.now)

    def reconnect(self) -> dict:
        """Come back on a new connection with the secret token (the phone woke up again)."""
        self.conn = object()
        r = self.table.session.handle(self.conn, {"op": "hello", "protocol": protocol.PROTOCOL_VERSION, "game": protocol.GAME_VERSION, "name": self.name, "token": self.token}, self.table.now)
        assert r["status"] == "ok" and r["reconnect"] is True, r
        return r

    def op(self, op: str, **kw):
        return self.table.session.handle(self.conn, {"op": op, **kw}, self.table.now)

    @property
    def pose(self):
        return self.table.world.players[self.id]

    def stand_by(self, kind: str, eid: str) -> None:
        row = nh.body(self.table.world, kind, eid)
        self.pose["tx"], self.pose["ty"] = row["tx"] + 1, row["ty"]

    def stand_by_resident(self, pid: str) -> None:
        from wizard_rts.narrative import residents

        t = residents.table(self.table.world)[pid]["tile"]
        self.pose["tx"], self.pose["ty"] = t[0] + 1, t[1]

    def seat_state(self):
        """Read this wizard's private narrative state (the acting context the session itself uses)."""
        return party.as_player(self.table.world, self.id)

    def state(self):
        return self.op("state", seq=1, full=False)


class Table:
    def __init__(self, humans: int = 1, ai: int = 0, seed: int = 507, enable_after: int = 40, start: bool = True) -> None:
        self.now = 0.0
        self.world = new_world(seed, "small", "campaign")
        self.world.ai_enabled = False
        self.seq = 0
        self.advance(enable_after)  # workers exist and are working
        self.session = MultiplayerSession(self.world, name="table", join_code=CODE, host_secret=SECRET, max_players=max(1, humans), ai_companions=ai,
                                          clock=lambda: self.now)
        self.people: list[Human] = []
        self.add("Joe", True)
        for i in range(1, humans):
            self.add(["Ann", "Bo", "Cy"][i - 1], False)
        if start:
            assert self.people[0].op("start")["status"] == "ok"

    def add(self, name: str, host: bool = False) -> Human:
        h = Human(self, name, host)
        self.people.append(h)
        return h

    def advance(self, seconds: float, step_ms: int = 100) -> None:
        """Advance the world and the session's wall-clock rules together (the host loop's body)."""
        n = int(round(seconds * 1000 / step_ms))
        for _ in range(n):
            self.seq += 1
            self.now += step_ms / 1000.0
            self.world.advance(step_ms, self.seq, snapshot=False)
            if getattr(self, "session", None) is not None:
                self.session.tick(self.now)

    # ---- helpers for the story
    @property
    def mentor(self) -> str:
        return tutorial.state(self.world)["teacher"]

    def learn(self, h: Human) -> None:
        """The lessons done the way the mentor does them, for one wizard."""
        with party.as_player(self.world, h.id):
            for lesson in ("meet", "colours", "told_ward", "hidden_ward"):
                wizard.complete_lesson(self.world, lesson)
            wizard.learn(self.world, [0, 1, 6], 3)

    def meet_people(self, h: Human, n: int = 3) -> int:
        done = 0
        for kind, table in (("worker", self.world.workers), ("carrier", self.world.carriers)):
            for eid, row in sorted(table.items()):
                if row["faction_name"] != "Red" or done >= n:
                    continue
                h.stand_by(kind, eid)
                r = h.op("talk", npc=eid)
                if r["status"] == "ok":
                    h.op("end_talk", npc=eid)
                    done += 1
        return done

    def scene(self, h: Human):
        with party.as_player(self.world, h.id):
            return campaign.scene_view(self.world)

    def through_scene(self, h: Human, pick: str | None = None):
        last = {}
        for _ in range(40):
            v = self.scene(h)
            if v is None:
                return last
            if v["needs_answer"]:
                cid = next((c["id"] for c in v["choices"] if pick and c["id"].endswith(":" + pick)), None) or v["choices"][0]["id"]
                assert h.op("scene_choose", choice=cid)["status"] == "ok"
            last = h.op("scene_next")
            assert last["status"] == "ok", last
        raise AssertionError("the scene never ended")

    def wait_for_stage(self, stage: str, seconds: float = 400) -> None:
        for _ in range(int(seconds)):
            if campaign.stage(self.world) == stage:
                return
            self.advance(1)
        raise AssertionError("stage %s never came; at %s: %s" % (stage, campaign.stage(self.world), campaign.explore_due(self.world)))
