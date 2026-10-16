"""An AI wizard: a participant that stands in for a wizard the world is missing (the second seat of a single-player game).

It is not a script that completes things. It is a player that happens to be driven by a small policy: it has a seat in the world (a record in
`world.players`, an avatar the clients draw, a private wizard record in the party), and everything it does goes through the same entry point a
person's connection uses, `MultiplayerSession.dispatch`: it walks one validated tile at a time (`move`), answers a challenge (`pvp_respond`),
locks a hidden Ward (`pvp_ward`) and casts guesses one at a time (`pvp_cast`) in real time against the same host-side rules as a human, with the
same cast allowance and no knowledge of the rival's Ward, and brings a dead friend back with the same `resurrect` channel a human uses. Its
decisions come from its character (`data/ai_wizards.json`) and from what has happened between it and the human it keeps company with:

* **Personality** sets how long it thinks between casts (a patient wizard takes 5 to 11 seconds, so a quick human can make several guesses in the
  time it makes one), how closely it follows, and what it says.
* **Provocation**: it never challenges anybody, and it declines the first `accept_after_challenges` challenges from a human with a line each; a human
  who keeps asking gets their duel, fought seriously. A duel settles the account: the next one has to be provoked again.
* **Relationship** with each human wizard starts at the character's baseline, rises when they are beaten fairly, falls when it is beaten, falls hard
  when it is killed and recovers when it is brought back; it is kept in the party's private record, so it is saved with the world.
* **Knowledge and ability** are its wizard record's (spells and weave, as for anybody), and its guesses are the retained Ward-solving heuristic
  (`duel.ward.WeaveBot`, the same candidate filter that plays the stranger and the mentor): it narrows the possible Wards from its own feedback.
* **Death**: it can die like anybody (a lost duel), and then it lies where it fell until somebody brings it back; it does nothing while dead. A human
  it has killed, or finds dead, it walks to and resurrects, unless the session has already ended for that human (a private session ends with its
  human's death; the brief's revision says so).
* **Cooperation**: it keeps near the person it travels with and, standing in an outbreak, treats it with the same `treat` action the wizard has.

The module is deliberately small and has no hooks into the narrative: it cannot award a quest, skip a duel or edit state. Another character is another
entry in the JSON and, if it needs a new behaviour, another method here.
"""

from __future__ import annotations

import json
import random
import zlib
from collections import deque
from functools import lru_cache
from pathlib import Path
from typing import Any

from wizard_rts.duel.ward import Combatant, WeaveBot
from wizard_rts.narrative import ledger, mortality, party, residents

DATA = Path(__file__).resolve().parents[1] / "data" / "ai_wizards.json"
AI_PREFIX = "a"
FACING = {(0, -1): "up", (0, 1): "down", (-1, 0): "left", (1, 0): "right"}
SEARCH_RADIUS = 14
FOLLOW_GIVE_UP = 40  # a human this many tiles away (or unreachable) is not followed
RESCUE_GIVE_UP = 80  # a body further than this is not walked to (the Trial has its own rules)


@lru_cache(maxsize=1)
def characters() -> dict[str, Any]:
    return json.loads(DATA.read_text(encoding="utf-8"))


def companion_id() -> str:
    return str(characters()["companion"])


class AiWizard:
    def __init__(self, session: Any, link: Any, key: str, seed: int) -> None:
        self.session = session
        self.link = link
        self.key = key
        self.c = characters()["wizards"][key]
        self.rng = random.Random(seed)
        self.bot: WeaveBot | None = None
        self.duel_id = ""
        self.next_step_at = 0.0
        self.next_wander_at = 0.0
        self.next_cast_at = 0.0
        self.next_ward_at = 0.0
        self.answer_at: float | None = None
        self.leave_at: float | None = None
        self.treat_after = 0.0
        self.greeted: set[str] = set()
        self.last_log: list[dict[str, Any]] = []
        self.disabled = False  # set by the session if the policy ever raises
        self.was_dead = False
        self.rescue = ""  # the seat of a dead human it is walking to
        self.rescue_said = False
        self.next_rescue_step_at = 0.0
        self.next_pest_at = 0.0

    # ---------------------------------------------------------------- memory (saved with the world, in the party's private record)
    def memory(self) -> dict[str, Any]:
        w = self.session.world
        g = party.guests(w).get(self.link.id)
        if g is None:
            return {"relationship": {}, "duels": {"won": 0, "lost": 0, "drawn": 0}, "declines": {}}
        mem = g.setdefault("memory", {"relationship": {}, "duels": {"won": 0, "lost": 0, "drawn": 0}})
        mem.setdefault("declines", {})
        return mem

    def relationship(self, who: str) -> int:
        return int(self.memory()["relationship"].get(who, self.c["start_relationship"]))

    def _adjust(self, who: str, delta: int) -> None:
        mem = self.memory()
        mem["relationship"][who] = max(-100, min(100, self.relationship(who) + int(delta)))

    def say(self, to: Any, kind: str, now: float) -> None:
        """A line in the wizard's voice, delivered to the human as a notice (the client shows it as a message from this person)."""
        lines = self.c["lines"].get(kind, [])
        if not lines or to is None or not getattr(to, "connected", False):
            return
        text = lines[self.rng.randrange(len(lines))]
        to.notice("ai_says", name=self.link.name, who=self.link.id, text=text, line=kind)

    def dead(self) -> bool:
        w = self.session.world
        return "narrative" in w.__dict__ and mortality.is_dead(w, self.link.id)

    # ---------------------------------------------------------------- the loop body
    def tick(self, now: float) -> None:
        s = self.session
        link = self.link
        if s.state != "playing" or not link.spawned:
            return
        duel = s.duels.get(link.duel_id)
        if duel is not None and duel.state == "finished":
            self._after_duel(duel, now)
            return
        if self.dead():
            self.was_dead = True
            self.bot = None
            return
        if self.was_dead:  # somebody brought it back
            self.was_dead = False
            friend = self._companion_of()
            self.say(friend, "i_died", now)
            if friend is not None:
                self._adjust(self._human_key(friend), int(self.c.get("resurrected_relationship", 0)))
        if duel is not None and duel.state != "finished":
            self._duelling(duel, now)
            return
        if link.invite:
            self._answer_invite(now)
            return
        self.bot = None
        if self._rescue(now):
            return
        if self._help_pests(now):
            return
        self._greet(now)
        self._treat(now)
        self._follow(now)

    # ---------------------------------------------------------------- challenges
    def _answer_invite(self, now: float) -> None:
        link = self.link
        inv = link.invite
        if not inv:
            return
        if self.answer_at is None:
            self.answer_at = now + self.rng.uniform(1.2, 3.2)  # a person takes a moment to answer
            return
        if now < self.answer_at:
            return
        self.answer_at = None
        challenger = self.session.links.get(inv["from"])
        key = self._human_key(challenger)
        mem = self.memory()
        declines = mem["declines"]
        after = int(self.c.get("accept_after_challenges", 0))
        provoked = int(declines.get(key, 0)) >= after
        accept = provoked and self.relationship(key) >= int(self.c["accept_if_relationship_at_least"])
        if not accept:
            declines[key] = int(declines.get(key, 0)) + 1
            if "narrative" in self.session.world.__dict__:
                ledger.bump(self.session.world, "provocations", seat=key)
        else:
            declines[key] = 0  # the account is settled by this duel: the next one has to be provoked again
        self.session.dispatch(link, {"op": "pvp_respond", "duel_id": inv["duel_id"], "accept": accept}, now)
        self.say(challenger, ("provoked" if after > 0 and self.c["lines"].get("provoked") else "accept") if accept else "decline", now)

    # ---------------------------------------------------------------- the duel
    def _duelling(self, duel: Any, now: float) -> None:
        link = self.link
        s = self.session
        self.duel_id = duel.id
        self.leave_at = None
        if duel.state == "setup":
            if duel.wards[link.id] is None:
                if self.next_ward_at == 0.0:
                    self.next_ward_at = now + self.rng.uniform(1.5, 3.5)
                elif now >= self.next_ward_at:
                    ward = self._new_bot(duel, now).generate_ward()
                    s.dispatch(link, {"op": "pvp_ward", "ward": ward}, now)
            return
        if duel.state != "active":
            return
        self.next_ward_at = 0.0
        if self.bot is None:
            self._new_bot(duel, now)
        if duel.casts_left(link.id) <= 0 or now < self.next_cast_at:
            return
        bot = self.bot
        assert bot is not None
        attack = [int(v) for v in bot.make_guess()]
        reply = s.dispatch(link, {"op": "pvp_cast", "attack": attack, "cast_seq": duel.cast_seq[link.id] + 1}, now)
        if reply.get("status") == "ok":
            bot.register_feedback(attack, int(reply.get("fracture", 0)), int(reply.get("echo", 0)))
        lo, hi = self.c["think_s"]
        self.next_cast_at = now + self.rng.uniform(float(lo), float(hi))

    def _new_bot(self, duel: Any, now: float) -> WeaveBot:
        f = duel.fmt
        me = Combatant(id=self.link.id, weave_size=int(f["slots"]), attack_pool=list(f["pool"]), ward_size=int(f["slots"]), ward_pool=list(f["pool"]),
                       allow_repeats=bool(f["allow_repeats"]), max_casts=int(f["max_casts"]), bot_logic=str(self.c["guess_logic"]),
                       bot_mistake_rate=float(self.c.get("mistake_rate", 0.0)))
        seed = zlib.crc32(f"{self.session.world.seed}|{self.link.id}|{duel.id}".encode()) & 0x7FFFFFFF
        self.bot = WeaveBot(me, me, seed)
        self.next_cast_at = now + self.rng.uniform(1.5, 4.0)
        return self.bot

    def _after_duel(self, duel: Any, now: float) -> None:
        link = self.link
        if self.leave_at is None:
            self.leave_at = now + 2.5
            res = duel.result or {}
            rival = duel.rival(link.id)
            other = self.session.links.get(rival)
            key = self._human_key(other)
            mem = self.memory()
            if res.get("winner") == link.id:
                mem["duels"]["won"] += 1
                self._adjust(key, int(self.c["win_relationship"]))
                if other is not None and self.session._dead(other):
                    self.say(other, "killed_you", now)
                    self.rescue, self.rescue_said = rival, False
                else:
                    self.say(other, "win", now)
            elif res.get("winner"):
                mem["duels"]["lost"] += 1
                self._adjust(key, int(self.c["loss_relationship"]))
                self.say(other, "lose", now)  # a last word, even when the loss was to the death
                if self.dead():
                    self._adjust(key, int(self.c.get("killed_relationship", 0)))
            else:
                mem["duels"]["drawn"] += 1
                self.say(other, "draw", now)
            return
        if now >= self.leave_at:
            self.session.dispatch(link, {"op": "pvp_leave"}, now)
            self.leave_at = None
            self.bot = None
            self.duel_id = ""
            self.next_cast_at = 0.0
            self.next_ward_at = 0.0

    # ---------------------------------------------------------------- bringing a friend back
    def _find_dead_human(self) -> str:
        w = self.session.world
        for other in sorted(self.session.links.values(), key=lambda l: l.id):
            if other.ai or other is self.link:
                continue
            if mortality.is_dead(w, other.id) and mortality.body_of(w, other.id):
                return other.id
        return ""

    def _rescue(self, now: float) -> bool:
        """Walk to a dead human's body and bring them back. True while it is busy with that."""
        w = self.session.world
        if "narrative" not in w.__dict__ or self.session.ending is not None:
            return False
        if not self.rescue:
            self.rescue = self._find_dead_human()
            self.rescue_said = False
        if not self.rescue:
            return False
        friend = self.session.links.get(self.rescue)
        if friend is None or not mortality.is_dead(w, self.rescue):
            if friend is not None and self.rescue_said:
                self.say(friend, "resurrected_you", now)
            self.rescue = ""
            return False
        pid = mortality.body_of(w, self.rescue)
        if pid is None:
            self.rescue = ""
            return False
        body = residents.table(w)[pid]
        goal = (int(body["tile"][0]), int(body["tile"][1]))
        me = w.players[self.link.id]
        dist = abs(int(me["tx"]) - goal[0]) + abs(int(me["ty"]) - goal[1])
        if mortality.channel_of(w, self.link.id) is not None:
            return True  # channelling: stand still
        if dist <= mortality.resurrect_range():
            r = self.session.dispatch(self.link, {"op": "resurrect", "target": self.rescue}, now)
            if r.get("status") == "started" and not self.rescue_said:
                self.rescue_said = True
                self.say(friend, "resurrecting", now)
            return True
        if dist > RESCUE_GIVE_UP:
            self.rescue = ""
            return False
        if now >= self.next_rescue_step_at:
            lo, hi = self.c["step_s"]
            self.next_rescue_step_at = now + self.rng.uniform(float(lo), float(hi))
            path = self._path_toward(goal, 1)
            if path:
                self._step_to(path[0], now)
        return True

    # ---------------------------------------------------------------- the rats
    def _help_pests(self, now: float) -> bool:
        """Once a human has heard the keeper's complaint, she walks to the nearest rat and fights it (on the Python core, verified like a board duel).
        True while she is busy with that."""
        w = self.session.world
        if "narrative" not in w.__dict__ or now < self.next_pest_at:
            return False
        from wizard_rts.narrative import pests, residents

        inf = pests.live(w)
        if inf is None or not pests.anyone_complained(w):
            return False
        me = w.players[self.link.id]
        best = None
        for pid in pests.pests_of(w, inf):
            r = residents.table(w)[pid]
            d = abs(int(r["tile"][0]) - int(me["tx"])) + abs(int(r["tile"][1]) - int(me["ty"]))
            if d <= 40 and (best is None or d < best[0]):
                best = (d, pid, (int(r["tile"][0]), int(r["tile"][1])))
        if best is None:
            return False
        d, pid, goal = best
        if d <= pests.FIGHT_RANGE:
            reply = self.session.dispatch(self.link, {"op": "pest_fight", "target": pid}, now)
            self.next_pest_at = now + self.rng.uniform(8.0, 14.0)
            friend = self._companion_of()
            if reply.get("status") == "resolved":
                self.say(friend, "rat_won" if reply.get("killed") else "rat_lost", now)
            return True
        if now >= self.next_step_at:
            lo, hi = self.c["step_s"]
            self.next_step_at = now + self.rng.uniform(float(lo), float(hi))
            path = self._path_toward(goal, 1)
            if path:
                self._step_to(path[0], now)
        return True

    # ---------------------------------------------------------------- keeping company
    def _human_key(self, link: Any) -> str:
        return link.id if link is not None else "?"

    def _companion_of(self) -> Any:
        """The connected human it keeps company with: the nearest."""
        w = self.session.world
        me = w.players[self.link.id]
        best = None
        for other in self.session.links.values():
            if other is self.link or getattr(other, "ai", False) or not other.connected or other.id not in w.players:
                continue
            p = w.players[other.id]
            d = abs(int(p["tx"]) - int(me["tx"])) + abs(int(p["ty"]) - int(me["ty"]))
            if best is None or d < best[0]:
                best = (d, other)
        return best[1] if best else None

    def _greet(self, now: float) -> None:
        friend = self._companion_of()
        if friend is None or friend.id in self.greeted:
            return
        w = self.session.world
        a, b = w.players[self.link.id], w.players[friend.id]
        if abs(int(a["tx"]) - int(b["tx"])) + abs(int(a["ty"]) - int(b["ty"])) <= 4:
            self.greeted.add(friend.id)
            self.say(friend, "greet", now)

    def _walkable(self, t: tuple[int, int]) -> bool:
        w = self.session.world
        return w.tile_in_map(*t) and t not in w.blocked and not w.solid_for_wizard(t) and not self.session._occupied(t, self.link.id)

    def _path_toward(self, goal: tuple[int, int], within: int) -> list[tuple[int, int]]:
        w = self.session.world
        me = w.players[self.link.id]
        start = (int(me["tx"]), int(me["ty"]))
        prev: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        q: deque[tuple[int, int]] = deque([start])
        while q:
            cur = q.popleft()
            if abs(cur[0] - goal[0]) + abs(cur[1] - goal[1]) <= within:
                path = []
                node: tuple[int, int] | None = cur
                while node is not None and node != start:
                    path.append(node)
                    node = prev[node]
                return path[::-1]
            for d in FACING:
                n = (cur[0] + d[0], cur[1] + d[1])
                if n in prev or abs(n[0] - start[0]) > SEARCH_RADIUS or abs(n[1] - start[1]) > SEARCH_RADIUS or not self._walkable(n):
                    continue
                prev[n] = cur
                q.append(n)
        return []

    def _step_to(self, t: tuple[int, int], now: float) -> bool:
        link = self.link
        me = self.session.world.players[link.id]
        d = (t[0] - int(me["tx"]), t[1] - int(me["ty"]))
        reply = self.session.dispatch(link, {"op": "move", "seq": link.move_seq + 1, "tx": t[0], "ty": t[1], "facing": FACING.get(d, "down")}, now)
        return reply.get("status") == "ok"

    def _follow(self, now: float) -> None:
        if now < self.next_step_at:
            return
        lo, hi = self.c["step_s"]
        self.next_step_at = now + self.rng.uniform(float(lo), float(hi))
        friend = self._companion_of()
        if friend is None or self.session._dead(friend):
            return
        w = self.session.world
        me, you = w.players[self.link.id], w.players[friend.id]
        dist = abs(int(me["tx"]) - int(you["tx"])) + abs(int(me["ty"]) - int(you["ty"]))
        near, far = int(self.c["follow"]["near"]), int(self.c["follow"]["far"])
        if dist > FOLLOW_GIVE_UP:
            return
        if dist > far:
            path = self._path_toward((int(you["tx"]), int(you["ty"])), near)
            if path:
                self._step_to(path[0], now)
            return
        if now >= self.next_wander_at:  # close enough: now and then it shifts its weight, like somebody waiting
            self.next_wander_at = now + self.rng.uniform(6.0, 14.0)
            cands = [(int(me["tx"]) + dx, int(me["ty"]) + dy) for dx, dy in FACING]
            cands = [t for t in cands if self._walkable(t) and abs(t[0] - int(you["tx"])) + abs(t[1] - int(you["ty"])) <= far]
            if cands:
                self._step_to(cands[self.rng.randrange(len(cands))], now)

    def _treat(self, now: float) -> None:
        """Standing in an outbreak, it does what a wizard does there: it treats it (the same action, the same channel time and cooldown)."""
        if now < self.treat_after:
            return
        w = self.session.world
        try:
            from wizard_rts import regions

            s = regions.state(w)
            if s is None or not any(s.cubes):
                return
            me = w.players[self.link.id]
            if s.cubes[s.region_at(int(me["tx"]), int(me["ty"]))] <= 0:
                return
        except Exception:  # noqa: BLE001 - a world without outbreaks has nothing to treat
            return
        self.treat_after = now + 20.0
        self.session.dispatch(self.link, {"op": "treat"}, now)
