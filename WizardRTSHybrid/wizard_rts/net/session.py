"""One multiplayer session over one authoritative HybridWorld: players, connections, commands, per-player views, PvP duels.

Transport-agnostic: the host loop (`host.py`) hands in parsed messages with an opaque connection handle and sends the reply
back; the tests call `handle()` directly as well as through real sockets.

Player identity
- Every human is a record in `world.players[pid]` (`{id, name, colour, tx, ty, facing}`). The host's own wizard *is* the
  single-player record `world.player` (the same dict object), so the single-player code paths are unchanged.
- A `Link` is the server-side identity across connections: a secret reconnect token, the current connection, sequence
  numbers, per-connection tree-delta bookkeeping, notices, and the player's own story record.
- Every command is bound to the authenticated connection; a client never names the player it acts for.
- `acting(link)` points `world.player` (and `world.story`) at that player's records for the duration of one command, so
  `magic.fire`, `story.*`, `regions.begin_treatment`, `interact` and the snapshot all see the right wizard without changes.
- Per-player story records share the world-level containers (`npcs`, `dungeons`, `quests`, `known`, `log`) by reference and
  own `inventory`, `in_dungeon` and `duel`; quest consequences are therefore shared, dialogue/dungeon state is not.

Authority
- Only the host loop advances the clock. No connection can reach `advance`, `speed`, `ai`, `spawn`, `damage`, a faction
  command, a God Mode view or a fixture (see `protocol.PLAYER_OPS`), whatever the world profile.
- Movement is one tile at a time, four directions, validated by `world.set_pose` (map, blocked, obstacles) plus player
  collision, a monotonic sequence per player (a replayed step is rejected) and a step-rate cap.
- PvP duels: `pvp.py`. The host scores every cast; a client never reports a result.
"""

from __future__ import annotations

import secrets
import time
from collections import deque
from contextlib import contextmanager, nullcontext
from typing import Any, Callable, Iterator

from sim.dmb.time.clock import ClockService

from wizard_rts import story
from wizard_rts.coords import tile_to_hex
from wizard_rts.narrative import campaign, duel_lease, party
from wizard_rts.net import ai_wizard, protocol, pvp
from wizard_rts.net.protocol import HOST_ONLY_OPS, PASSTHROUGH_OPS, PLAYER_OPS, SOLO_OPS

PLAYER_COLOURS = ["#f2c14e", "#4ec9f2", "#9ef24e", "#f24e9e"]
MAX_PLAYERS = 4
STEP_RATE_PER_S = 12  # STEP_SECONDS in overworld.gd is 0.16 s (6.25 tiles/s); anything faster is not a walking wizard
DISCONNECT_GRACE_S = 20.0  # a duelist who drops has this long to come back before forfeiting
REMOVE_AFTER_S = 600.0  # a non-host player gone this long is taken out of the world (no ghosts)
SPAWN_RADIUS = 14
MIN_SPAWN_DISTANCE = 2
FACINGS = ("up", "down", "left", "right")
NOTICE_CAP = 50


class Link:
    """A player's server-side identity across connections."""

    def __init__(self, pid: str, name: str, token: str, host: bool) -> None:
        self.id = pid
        self.name = name
        self.token = token
        self.host = host
        self.conn: Any = None
        self.connected = False
        self.last_seen = 0.0
        self.disconnected_at: float | None = None
        self.move_seq = 0
        self.step_times: deque[float] = deque()
        self.tree_sent: dict[str, Any] = {}
        self.notices: list[dict[str, Any]] = []
        self.story: dict[str, Any] | None = None
        self.duel_id = ""
        self.invite: dict[str, Any] | None = None  # a challenge waiting for my answer
        self.outgoing: str = ""  # the duel id of the challenge I sent and that is still open
        self.spawned = False
        self.joined_at = 0.0
        self.ai = False  # driven by net/ai_wizard.py through the same dispatch a connection uses

    def notice(self, kind: str, **data: Any) -> None:
        self.notices.append({"kind": kind, **data})
        del self.notices[:-NOTICE_CAP]


class MultiplayerSession:
    def __init__(self, world: Any, name: str = "DuelMasterBattle", join_code: str | None = None, host_secret: str | None = None,
                 max_players: int = 2, clock: Callable[[], float] = time.monotonic, view_radius: int = protocol.DEFAULT_VIEW_RADIUS,
                 cast_timeout_s: float = pvp.CAST_TIMEOUT_S, invite_timeout_s: float = pvp.INVITE_TIMEOUT_S,
                 disconnect_grace_s: float = DISCONNECT_GRACE_S, remove_after_s: float = REMOVE_AFTER_S, first_joiner_hosts: bool = False,
                 world_factory: Callable[[], Any] | None = None, ai_companions: int = 0) -> None:
        self.world = world
        self.world_factory = world_factory  # builds a fresh world for a single-player "New game"
        self.on_world_swap: Callable[[Any], None] | None = None  # the host loop adopts the world a New game created
        self.ai_companions = max(0, min(1, int(ai_companions)))  # AI wizards that fill a seat the session has no human for (a single-player game: one)
        self.ais: dict[str, ai_wizard.AiWizard] = {}
        # a host without a player of its own (a PC hosting for two phones): the first wizard to join with the code becomes the host player
        self.first_joiner_hosts = bool(first_joiner_hosts)
        self.name = str(name)[:40] or "DuelMasterBattle"
        self.join_code = str(join_code) if join_code is not None else "%04d" % (secrets.randbelow(10000))
        self.host_secret = host_secret or secrets.token_hex(8)
        self.max_players = max(1, min(MAX_PLAYERS, int(max_players)))
        self.clock = clock
        self.view_radius = int(view_radius)
        self.cast_timeout_s = float(cast_timeout_s)
        self.invite_timeout_s = float(invite_timeout_s)
        self.disconnect_grace_s = float(disconnect_grace_s)
        self.remove_after_s = float(remove_after_s)
        self.state = "lobby"  # lobby -> playing
        self.links: dict[str, Link] = {}
        self.by_conn: dict[Any, Link] = {}
        self.orphaned_conns: list[Any] = []  # connections the transport should close (replaced by a reconnect)
        self.duels: dict[str, pvp.PvpDuel] = {}
        self.command_log: list[dict[str, Any]] = []  # accepted world-mutating commands, in order, with game_ms (replay evidence)
        self.events: list[dict[str, Any]] = []
        self._player_counter = 0
        self._duel_counter = 0
        self.base_story = story.state(world)  # created now so every per-player record shares the same containers
        self.started_at = self.clock()

    # ------------------------------------------------------------------ info
    def game_ms(self) -> int:
        return int(self.world.dmb.clock.get("game_ms", 0))

    def info(self) -> dict[str, Any]:
        """What an unauthenticated probe (discovery, the join screen) may learn."""
        return {"status": "ok", "dmb": 1, "name": self.name, "protocol": protocol.PROTOCOL_VERSION, "game": protocol.GAME_VERSION,
                "state": self.state, "players": sum(1 for l in self.links.values() if l.connected and not l.ai), "max_players": self.max_players,
                "needs_code": True, "seed": int(self.world.seed), "map": str(self.world.map_size)}

    def lobby_view(self) -> dict[str, Any]:
        return {"name": self.name, "state": self.state, "max_players": self.max_players, "seed": int(self.world.seed), "map": str(self.world.map_size),
                "profile": str(self.world.profile), "game_ms": self.game_ms(),
                "players": [{"id": l.id, "name": l.name, "host": l.host, "connected": l.connected, "colour": self.world.players[l.id].get("colour", ""),
                             "spawned": l.spawned, "ai": l.ai} for l in self._links_in_order()]}

    def _links_in_order(self) -> list[Link]:
        return [self.links[k] for k in sorted(self.links, key=lambda k: int(k[1:]))]

    # ------------------------------------------------------------------ players
    def _new_link(self, name: str, host: bool, now: float, ai: bool = False) -> Link:
        if ai:
            pid = f"{ai_wizard.AI_PREFIX}{len(self.ais) + 1}"
            colour = "#c58cff"
        else:
            self._player_counter += 1
            pid = f"p{self._player_counter}"
            colour = PLAYER_COLOURS[(self._player_counter - 1) % len(PLAYER_COLOURS)]
        link = Link(pid, name, secrets.token_hex(12), host)
        link.ai = ai
        link.joined_at = now
        if host and self.world.players.get(pid) is None and not any(l.host for l in self.links.values()):
            rec = self.world.player  # the host's wizard is the single-player record itself
        else:
            rec = {"tx": int(self.world.player["tx"]), "ty": int(self.world.player["ty"]), "facing": "down"}
        rec.update(id=pid, name=name, colour=colour)
        if ai:
            rec["ai"] = True
        self.world.players[pid] = rec
        self.links[pid] = link
        if host:
            link.spawned = True
        self._seat(link)
        return link

    def _seat(self, link: Link) -> None:
        """Give this wizard its place in the story: a seat in the party with a private wizard record (the host's is the world's own)."""
        w = self.world
        if "narrative" not in w.__dict__:
            return
        party.enroll(w, link.id, link.name, host=link.host, human=not link.ai)
        party.set_present(w, link.id, link.connected or link.ai)
        with party.as_player(w, link.id):
            campaign.on_join(w)

    def _bind(self, link: Link, conn: Any, now: float) -> None:
        if link.conn is not None and link.conn is not conn:
            self.by_conn.pop(link.conn, None)
            self.orphaned_conns.append(link.conn)
        old = self.by_conn.get(conn)
        if old is not None and old is not link:
            old.conn, old.connected = None, False
        link.conn = conn
        link.connected = True
        link.last_seen = now
        link.disconnected_at = None
        link.tree_sent.clear()  # a fresh connection gets the forest again
        self.by_conn[conn] = link
        if "narrative" in self.world.__dict__ and link.id in party.seats(self.world):
            party.set_present(self.world, link.id, True)
            with party.as_player(self.world, link.id):
                campaign.welcome_back(self.world)  # whatever happened while they were away is in their journal

    def disconnect(self, conn: Any, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        link = self.by_conn.pop(conn, None)
        if link is None:
            return
        if link.conn is conn:
            link.conn = None
            link.connected = False
            link.disconnected_at = now
            if "narrative" in self.world.__dict__:
                party.set_present(self.world, link.id, False)  # nothing in the story waits for a wizard who is not here
            self._notify_others(link, "player_left", player=link.id, name=link.name)

    def _notify_others(self, link: Link | None, kind: str, **data: Any) -> None:
        for other in self.links.values():
            if other is not link:
                other.notice(kind, **data)

    # ------------------------------------------------------------------ acting player
    def _story_for(self, link: Link) -> dict[str, Any]:
        base = self.base_story
        if link.host:
            return base
        if link.story is None or link.story["quests"] is not base["quests"]:
            link.story = {"version": base.get("version", 1), "npcs": base["npcs"], "dungeons": base["dungeons"], "quests": base["quests"],
                          "known": base["known"], "log": base["log"], "inventory": [], "in_dungeon": "", "duel": None}
        return link.story

    @contextmanager
    def acting(self, link: Link) -> Iterator[None]:
        w = self.world
        prev_player, prev_story = w.player, w.__dict__.get("story")
        w.player = w.players[link.id]
        w.story = self._story_for(link)
        seat = party.as_player(w, link.id) if "narrative" in w.__dict__ else nullcontext()
        try:
            with seat:  # the wizard's own spells, lessons, conversations, dialogue flags and Aspect scores
                yield
        finally:
            w.player = prev_player
            w.story = prev_story if prev_story is not None else self.base_story

    # ------------------------------------------------------------------ spawn
    def _occupied(self, tile: tuple[int, int], except_pid: str = "") -> bool:
        return any(pid != except_pid and (int(p["tx"]), int(p["ty"])) == tile for pid, p in self.world.players.items())

    def _free_tile_near(self, cx: int, cy: int, except_pid: str) -> tuple[int, int] | None:
        w = self.world
        seen = {(cx, cy)}
        frontier = [(cx, cy)]
        while frontier:
            nxt: list[tuple[int, int]] = []
            for x, y in frontier:
                for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                    t = (x + dx, y + dy)
                    if t in seen or abs(t[0] - cx) > SPAWN_RADIUS or abs(t[1] - cy) > SPAWN_RADIUS:
                        continue
                    seen.add(t)
                    if not w.tile_in_map(*t):
                        continue
                    nxt.append(t)
                    if abs(t[0] - cx) + abs(t[1] - cy) >= MIN_SPAWN_DISTANCE and t not in w.blocked and not w.solid_for_wizard(t) and not self._occupied(t, except_pid):
                        return t
            frontier = nxt
        return None

    def _spawn(self, link: Link) -> bool:
        rec = self.world.players[link.id]
        if link.host:
            link.spawned = True
            return True
        host = next((self.world.players[l.id] for l in self.links.values() if l.host), None)
        anchor = (int(host["tx"]), int(host["ty"])) if host else (int(self.world.player["tx"]), int(self.world.player["ty"]))
        tile = self._free_tile_near(anchor[0], anchor[1], link.id)
        if tile is None:
            return False
        rec.update(tx=tile[0], ty=tile[1], facing="down")
        link.spawned = True
        self.events.append({"kind": "spawn", "player": link.id, "tile": list(tile), "game_ms": self.game_ms()})
        return True

    def rebind(self, world: Any) -> None:
        """A new cycle replaced the world object (history.cycle_reset carried `players` over): re-alias and re-spawn."""
        self.world = world
        self.base_story = story.state(world)
        for link in self.links.values():
            link.story = None
            link.tree_sent.clear()
            rec = world.players.get(link.id)
            if rec is None:
                rec = world.players[link.id] = {"tx": world.player["tx"], "ty": world.player["ty"], "facing": "down", "id": link.id, "name": link.name, "colour": ""}
            if link.host:
                world.player.update({k: rec[k] for k in ("id", "name", "colour") if k in rec})
                world.players[link.id] = world.player
            else:
                link.spawned = False
        for link in self.links.values():
            if self.state == "playing" and not link.spawned:
                self._spawn(link)
        if "narrative" in world.__dict__:
            for link in self.links.values():
                party.enroll(world, link.id, link.name, host=link.host, human=not link.ai)
                party.set_present(world, link.id, link.connected or link.ai)
                with party.as_player(world, link.id):
                    campaign.on_join(world)
        for duel in list(self.duels.values()):
            duel.token = ""  # the old world's pause token died with it
        self.duels.clear()
        for link in self.links.values():
            link.duel_id = ""
            link.invite = None
            link.outgoing = ""
            link.notice("cycle_reset")

    # ------------------------------------------------------------------ dispatch
    def handle(self, conn: Any, message: dict[str, Any], now: float | None = None) -> dict[str, Any]:
        now = self.clock() if now is None else now
        if not isinstance(message, dict):
            return {"status": "rejected", "reason": "bad_message"}
        op = str(message.get("op", ""))
        link = self.by_conn.get(conn)
        if link is None:
            if op == "info":
                return self.info()
            if op == "ping":
                return {"status": "ok", "pong": message.get("t"), "game_ms": self.game_ms()}
            if op == "hello":
                return self._hello(conn, message, now)
            return {"status": "rejected", "reason": "hello_first", "op": op}
        link.last_seen = now
        if op == "hello":
            return self._hello(conn, message, now)
        if op == "leave":
            self.disconnect(conn, now)
            return {"status": "ok", "left": link.id}
        return self.dispatch(link, message, now)

    def dispatch(self, link: Link, message: dict[str, Any], now: float) -> dict[str, Any]:
        """One command from an authenticated wizard, human or AI: the same checks and handlers for both."""
        op = str(message.get("op", ""))
        if op not in PLAYER_OPS:
            return {"status": "rejected", "reason": "not_allowed_in_multiplayer", "op": op}
        if op in HOST_ONLY_OPS and not link.host:
            return {"status": "rejected", "reason": "host_only", "op": op}
        if op == "ping":
            return {"status": "ok", "pong": message.get("t"), "game_ms": self.game_ms()}
        if op == "lobby":
            return {"status": "ok", "session": self.lobby_view(), "you": link.id}
        if op == "start":
            return self.start(link)
        if op in SOLO_OPS:
            return self._solo_op(link, op, message, now)
        if op == "state":
            return self.state_view(link, message, now)
        if op == "move":
            return self.move(link, message, now)
        if op.startswith("pvp_"):
            return self._pvp(link, op, message, now)
        if op in PASSTHROUGH_OPS:
            return self._passthrough(link, op, message)
        return {"status": "rejected", "reason": "unknown_op", "op": op}

    # ------------------------------------------------------------------ single-player save and New game
    def _solo_op(self, link: Link, op: str, message: dict[str, Any], now: float) -> dict[str, Any]:
        """Save and New game exist only in a one-human private session: the world is that player's own, so a save slot is theirs. A shared
        world (two or more seats) has no slot of its own; its host leaves it by leaving."""
        if self.max_players != 1:
            return {"status": "rejected", "reason": "not_allowed_in_multiplayer", "op": op}
        from wizard_rts import server  # the same save / new_game handling as the classic single-player server

        if op == "save":
            reply = server._handle(self.world, {"op": "save", "slot": str(message.get("slot", "manual"))})
            return reply if isinstance(reply, dict) else {"status": "rejected", "reason": "bad_reply"}
        if self.world_factory is None:
            return {"status": "rejected", "reason": "no_world_factory"}
        fresh = self.world_factory()
        self._swap_world(fresh)
        view = self.state_view(link, {"full": True}, now)
        return {"status": "ok", "new_game": True, "terrain": fresh.terrain.wire() if fresh.terrain is not None else None, "snapshot": view["snapshot"]}

    def _swap_world(self, world: Any) -> None:
        """Replace the world object (New game): every seat keeps its place, its duels and invites end, the host loop adopts the new object."""
        world.players = {}
        self.rebind(world)
        if self.on_world_swap is not None:
            self.on_world_swap(world)

    # ------------------------------------------------------------------ hello
    def _hello(self, conn: Any, message: dict[str, Any], now: float) -> dict[str, Any]:
        if int(message.get("protocol", -1)) != protocol.PROTOCOL_VERSION:
            return {"status": "rejected", "reason": "protocol_mismatch", "expected": protocol.PROTOCOL_VERSION, "got": message.get("protocol")}
        if not protocol.game_compatible(str(message.get("game", ""))):
            return {"status": "rejected", "reason": "version_mismatch", "expected": protocol.GAME_VERSION, "got": str(message.get("game", ""))}
        name = str(message.get("name", "")).strip()[:24] or "Wizard"
        is_host = bool(message.get("secret")) and secrets.compare_digest(str(message.get("secret")), self.host_secret)
        token = str(message.get("token", "") or "")
        link = next((l for l in self.links.values() if token and secrets.compare_digest(l.token, token)), None)
        if link is None and not is_host and str(message.get("code", "")) != self.join_code:
            return {"status": "rejected", "reason": "bad_code"}
        if link is None and not is_host and self.first_joiner_hosts and not any(l.host for l in self.links.values()):
            is_host = True
        if link is None and is_host:
            link = next((l for l in self.links.values() if l.host), None)
        reconnect = link is not None
        if link is None:
            if sum(1 for l in self.links.values() if not l.ai) >= self.max_players:
                return {"status": "rejected", "reason": "full", "max_players": self.max_players}
            link = self._new_link(name, is_host, now)
            if self.state == "playing" and not self._spawn(link):
                self.links.pop(link.id, None)
                self.world.players.pop(link.id, None)
                return {"status": "rejected", "reason": "no_spawn_tile"}
            self._notify_others(link, "player_joined", player=link.id, name=link.name)
        else:
            self._notify_others(link, "player_reconnected", player=link.id, name=link.name)
        self._bind(link, conn, now)
        self.events.append({"kind": "reconnect" if reconnect else "join", "player": link.id, "game_ms": self.game_ms()})
        return {"status": "ok", "player_id": link.id, "token": link.token, "host": link.host, "reconnect": reconnect, "name": link.name,
                "protocol": protocol.PROTOCOL_VERSION, "game": protocol.GAME_VERSION, "session": self.lobby_view(), "seed": int(self.world.seed),
                "map": str(self.world.map_size), "spawned": link.spawned, "state": self.state, "join_code_required": True,
                "pose": self._pose(link), "duel": self._duel_view(link, now)}

    def start(self, link: Link) -> dict[str, Any]:
        if self.state == "playing":
            return {"status": "ok", "idempotent": True, "state": self.state}
        self.state = "playing"
        self._ensure_companions()
        for other in self._links_in_order():
            if not other.spawned:
                self._spawn(other)
        self.events.append({"kind": "start", "game_ms": self.game_ms()})
        self._notify_others(None, "started")
        return {"status": "ok", "state": self.state, "session": self.lobby_view()}

    def _ensure_companions(self) -> None:
        """A single-player game has a second wizard in it: the fellow apprentice. A shared game (two humans) has none, and the AI never takes a
        human's seat: the seat count above is humans only."""
        if self.ai_companions <= len(self.ais) or any(not l.host for l in self.links.values() if not l.ai):
            return
        key = ai_wizard.companion_id()
        spec = ai_wizard.characters()["wizards"][key]
        link = self._new_link(spec["name"], False, self.clock(), ai=True)
        link.connected = True
        link.spawned = False
        party.set_present(self.world, link.id, True)
        seed = int(self.world.seed) * 31 + len(self.ais) + 1
        self.ais[link.id] = ai_wizard.AiWizard(self, link, key, seed)

    # ------------------------------------------------------------------ movement
    def _pose(self, link: Link) -> dict[str, Any]:
        rec = self.world.players[link.id]
        q, r = tile_to_hex(int(rec["tx"]), int(rec["ty"]))
        return {"tx": int(rec["tx"]), "ty": int(rec["ty"]), "facing": str(rec["facing"]), "hex": [q, r], "seq": link.move_seq}

    def move(self, link: Link, message: dict[str, Any], now: float) -> dict[str, Any]:
        if self.state != "playing" or not link.spawned:
            return {"status": "rejected", "reason": "not_started", **self._pose(link)}
        try:
            seq = int(message.get("seq", 0))
            tx, ty = int(message.get("tx")), int(message.get("ty"))
        except (TypeError, ValueError):
            return {"status": "rejected", "reason": "bad_move", **self._pose(link)}
        facing = str(message.get("facing", "down"))
        if facing not in FACINGS:
            return {"status": "rejected", "reason": "bad_facing", **self._pose(link)}
        if seq <= link.move_seq:
            return {"status": "rejected", "reason": "stale_seq", **self._pose(link)}
        duel = self.duels.get(link.duel_id)
        if duel is not None and duel.state != "finished":
            return {"status": "rejected", "reason": "in_duel", **self._pose(link)}
        rec = self.world.players[link.id]
        dist = abs(tx - int(rec["tx"])) + abs(ty - int(rec["ty"]))
        if dist > 1:
            return {"status": "rejected", "reason": "not_adjacent", **self._pose(link)}
        if dist == 1:
            while link.step_times and now - link.step_times[0] > 1.0:
                link.step_times.popleft()
            if len(link.step_times) >= STEP_RATE_PER_S:
                return {"status": "rejected", "reason": "too_fast", **self._pose(link)}
            if self._occupied((tx, ty), link.id):
                return {"status": "rejected", "reason": "occupied", **self._pose(link)}
            with self.acting(link):
                r = self.world.set_pose(tx, ty, facing, snapshot=False)
            if r.get("status") != "ok":
                return {"status": "rejected", "reason": str(r.get("reason", "blocked")), **self._pose(link)}
            link.step_times.append(now)
        else:
            rec["facing"] = facing
        link.move_seq = seq
        self.command_log.append({"op": "move", "player": link.id, "seq": seq, "tx": tx, "ty": ty, "facing": facing, "game_ms": self.game_ms()})
        return {"status": "ok", **self._pose(link)}

    # ------------------------------------------------------------------ views
    def state_view(self, link: Link, message: dict[str, Any], now: float) -> dict[str, Any]:
        full = bool(message.get("full", False))
        try:
            radius = max(8, min(120, int(message.get("radius", self.view_radius))))
        except (TypeError, ValueError):
            radius = self.view_radius
        rec = self.world.players[link.id]
        with self.acting(link):
            snap = self.world.snapshot(tree_sync=not full, tree_sent=link.tree_sent, view=(int(rec["tx"]), int(rec["ty"]), radius))
        if not full:
            self._lean(snap, (int(rec["tx"]), int(rec["ty"]), radius))
        for p in snap.get("players", []):
            other = self.links.get(str(p["id"]))
            p["connected"] = bool(other and other.connected)
            p["in_duel"] = bool(other and other.duel_id and self.duels.get(other.duel_id) and self.duels[other.duel_id].state != "finished")
            p["you"] = str(p["id"]) == link.id
            p["ai"] = bool(other and other.ai)
        out = {"status": "ok", "seq": message.get("seq"), "you": link.id, "session_state": self.state, "snapshot": snap, "view_radius": radius,
               "duel": self._duel_view(link, now), "invite": self._invite_view(link, now), "outgoing": link.outgoing,
               "players_online": sum(1 for l in self.links.values() if l.connected and not l.ai), "notices": list(link.notices), "pose": self._pose(link)}
        link.notices.clear()
        return out

    LEAN_DROP = ("stocks", "overview", "feed", "tech", "economy_totals", "provenance", "stats", "ai_notes", "recent_events", "neighbor_sample", "in_map", "entity_ids")

    @classmethod
    def _lean(cls, snap: dict[str, Any], view: tuple[int, int, int]) -> None:
        """A phone's poll: no God Mode read-outs, roads and blocked tiles only inside the window (a full poll keeps everything)."""
        for k in cls.LEAN_DROP:
            snap.pop(k, None)
        cx, cy, r = view
        snap["roads"] = {rid: tiles for rid, tiles in snap.get("roads", {}).items() if any(abs(int(t[0]) - cx) <= r and abs(int(t[1]) - cy) <= r for t in tiles)}
        snap["blocked"] = [t for t in snap.get("blocked", []) if abs(int(t[0]) - cx) <= r and abs(int(t[1]) - cy) <= r]

    def _passthrough(self, link: Link, op: str, message: dict[str, Any]) -> dict[str, Any]:
        from wizard_rts import server  # the single-player op table: the same validated world operations

        if op in ("interact", "resolve", "fire", "treat", "talk", "choose", "enter", "dungeon_move", "dungeon_interact", "duel_begin", "duel_guess", "duel_abandon"):
            duel = self.duels.get(link.duel_id)
            if duel is not None and duel.state != "finished":
                return {"status": "rejected", "reason": "in_duel", "op": op}
        with self.acting(link):
            reply = server._handle(self.world, dict(message))
        if isinstance(reply, dict):
            reply.pop("snapshot", None)  # the next state poll carries the world; a passthrough reply stays small
            if reply.get("status") in ("ok", "started", "success", "failure") and op not in ("terrain", "tile", "resources", "profile", "tech", "cards", "menu", "story_view"):
                self.command_log.append({"op": op, "player": link.id, "game_ms": self.game_ms(), "message": {k: v for k, v in message.items() if k != "op"}})
        return reply if isinstance(reply, dict) else {"status": "rejected", "reason": "bad_reply"}

    # ------------------------------------------------------------------ PvP
    def _duel_view(self, link: Link, now: float) -> dict[str, Any]:
        duel = self.duels.get(link.duel_id)
        return duel.view(link.id, now) if duel is not None else {}

    def _invite_view(self, link: Link, now: float) -> dict[str, Any]:
        inv = link.invite
        if not inv:
            return {}
        return {"duel_id": inv["duel_id"], "from": inv["from"], "from_name": inv["from_name"], "format": {k: inv["format"][k] for k in ("slots", "colours", "max_casts", "allow_repeats")},
                "expires_in_s": max(0.0, inv["expires_at"] - now)}

    def _distance(self, a: Link, b: Link) -> int:
        pa, pb = self.world.players[a.id], self.world.players[b.id]
        return abs(int(pa["tx"]) - int(pb["tx"])) + abs(int(pa["ty"]) - int(pb["ty"]))

    def _in_open_duel(self, link: Link) -> bool:
        d = self.duels.get(link.duel_id)
        return d is not None and d.state != "finished"

    def _pvp(self, link: Link, op: str, message: dict[str, Any], now: float) -> dict[str, Any]:
        if op == "pvp_view":
            return {"status": "ok", "duel": self._duel_view(link, now), "invite": self._invite_view(link, now), "outgoing": link.outgoing}
        if op == "pvp_challenge":
            return self._challenge(link, message, now)
        if op == "pvp_respond":
            return self._respond(link, message, now)
        duel = self.duels.get(link.duel_id)
        if duel is None:
            return {"status": "rejected", "reason": "no_duel"}
        if op == "pvp_ward":
            r = duel.submit_ward(link.id, list(message.get("ward", [])), now)
            if r.get("status") == "ok" and not r.get("idempotent"):
                self.command_log.append({"op": op, "player": link.id, "duel": duel.id, "game_ms": self.game_ms()})
                if duel.state == "active":
                    self._notify_duelists(duel, "duel_active", duel_id=duel.id)
            r["duel"] = duel.view(link.id, now)
            return r
        if op == "pvp_cast":
            try:
                cast_seq = int(message.get("cast_seq", 0))
            except (TypeError, ValueError):
                cast_seq = -1
            r = duel.cast(link.id, list(message.get("attack", [])), cast_seq, now)
            if r.get("status") == "ok" and not r.get("idempotent"):
                self.command_log.append({"op": op, "player": link.id, "duel": duel.id, "attack": [int(v) for v in message.get("attack", [])], "cast_seq": cast_seq, "game_ms": self.game_ms()})
                self._after_duel_change(duel, now)
            r["duel"] = duel.view(link.id, now)
            return r
        if op == "pvp_forfeit":
            r = duel.forfeit(link.id, "forfeit", now)
            if r.get("status") == "ok" and not r.get("idempotent"):
                self.command_log.append({"op": op, "player": link.id, "duel": duel.id, "game_ms": self.game_ms()})
                self._after_duel_change(duel, now)
            r["duel"] = duel.view(link.id, now)
            return r
        if op == "pvp_leave":
            if duel.state != "finished":
                duel.forfeit(link.id, "forfeit", now)
                self._after_duel_change(duel, now)
            duel.left[link.id] = True
            link.duel_id = ""
            if all(duel.left.values()):
                self.duels.pop(duel.id, None)
            return {"status": "ok", "left": duel.id, "result": duel.view(link.id, now).get("result")}
        return {"status": "rejected", "reason": "unknown_op", "op": op}

    def _challenge(self, link: Link, message: dict[str, Any], now: float) -> dict[str, Any]:
        if self.state != "playing":
            return {"status": "rejected", "reason": "not_started"}
        target = self.links.get(str(message.get("target", "")))
        if target is None or target is link:
            return {"status": "rejected", "reason": "no_such_player"}
        if not target.connected:
            return {"status": "rejected", "reason": "target_offline"}
        if self._in_open_duel(link) or self._in_open_duel(target):
            return {"status": "rejected", "reason": "already_in_duel"}
        if link.outgoing:
            return {"status": "rejected", "reason": "challenge_pending", "duel_id": link.outgoing}
        if self._distance(link, target) > pvp.CHALLENGE_RANGE:
            return {"status": "rejected", "reason": "too_far", "range": pvp.CHALLENGE_RANGE, "distance": self._distance(link, target)}
        if target.invite and target.invite["expires_at"] > now:
            return {"status": "rejected", "reason": "target_busy"}
        if self._story_busy(link) or self._story_busy(target):
            return {"status": "rejected", "reason": "busy_in_story"}
        self._duel_counter += 1
        duel_id = f"pvp{self._duel_counter}"
        fmt = pvp.make_format(message.get("format"))
        target.invite = {"duel_id": duel_id, "from": link.id, "from_name": link.name, "format": fmt, "expires_at": now + self.invite_timeout_s}
        link.outgoing = duel_id
        target.notice("challenged", duel_id=duel_id, by=link.id, by_name=link.name)
        self.events.append({"kind": "pvp_challenge", "duel": duel_id, "from": link.id, "to": target.id, "game_ms": self.game_ms()})
        return {"status": "ok", "duel_id": duel_id, "target": target.id, "expires_in_s": self.invite_timeout_s, "format": {k: fmt[k] for k in ("slots", "colours", "max_casts", "allow_repeats")}}

    def _story_busy(self, link: Link) -> bool:
        """In the middle of the story's own duel or scene: not a moment to be challenged or to challenge."""
        w = self.world
        if "narrative" not in w.__dict__ or link.ai or link.id not in party.seats(w):
            return False
        with party.as_player(w, link.id):
            return duel_lease.active(w) is not None or campaign.active_scene(w) is not None

    def _respond(self, link: Link, message: dict[str, Any], now: float) -> dict[str, Any]:
        inv = link.invite
        if not inv or inv["expires_at"] <= now:
            link.invite = None
            return {"status": "rejected", "reason": "no_invite"}
        if str(message.get("duel_id", inv["duel_id"])) != inv["duel_id"]:
            return {"status": "rejected", "reason": "wrong_duel"}
        challenger = self.links.get(inv["from"])
        link.invite = None
        if challenger is not None and challenger.outgoing == inv["duel_id"]:
            challenger.outgoing = ""
        if not bool(message.get("accept", False)):
            if challenger is not None:
                challenger.notice("declined", duel_id=inv["duel_id"], by=link.id, by_name=link.name)
            return {"status": "ok", "accepted": False, "duel_id": inv["duel_id"]}
        if challenger is None or not challenger.connected:
            return {"status": "rejected", "reason": "challenger_gone"}
        if self._in_open_duel(link) or self._in_open_duel(challenger):
            return {"status": "rejected", "reason": "already_in_duel"}
        duel = pvp.PvpDuel(inv["duel_id"], challenger.id, link.id, {challenger.id: challenger.name, link.id: link.name}, inv["format"],
                           pvp.duel_seed(int(self.world.seed), inv["duel_id"]), now)
        duel.token = ClockService(self.world.dmb.clock).acquire_pause("pvp_duel", duel.id)
        self.duels[duel.id] = duel
        challenger.duel_id = duel.id
        link.duel_id = duel.id
        self.world.events.append({"kind": "pvp_duel_begun", "duel": duel.id, "players": list(duel.players)})
        self.command_log.append({"op": "pvp_accept", "player": link.id, "duel": duel.id, "game_ms": self.game_ms()})
        challenger.notice("accepted", duel_id=duel.id, by=link.id, by_name=link.name)
        return {"status": "ok", "accepted": True, "duel_id": duel.id, "duel": duel.view(link.id, now)}

    def _notify_duelists(self, duel: pvp.PvpDuel, kind: str, **data: Any) -> None:
        for pid in duel.players:
            l = self.links.get(pid)
            if l is not None:
                l.notice(kind, **data)

    def _after_duel_change(self, duel: pvp.PvpDuel, now: float) -> None:
        if duel.state == "finished" and duel.token:
            try:
                ClockService(self.world.dmb.clock).release_pause(duel.token)
            except Exception:  # noqa: BLE001 - already released (a cycle reset)
                pass
            duel.token = ""
            self.world.events.append({"kind": "pvp_duel_ended", "duel": duel.id, "winner": duel.result["winner"] if duel.result else "", "reason": duel.reason})
            self._notify_duelists(duel, "duel_finished", duel_id=duel.id)

    # ------------------------------------------------------------------ housekeeping
    def tick(self, now: float | None = None) -> None:
        """Wall-clock admission rules: invite expiry, cast timeouts, disconnect forfeits, ghost removal. Called by the host loop."""
        now = self.clock() if now is None else now
        for ai in list(self.ais.values()):
            if ai.disabled:
                continue
            try:
                ai.tick(now)
            except Exception:  # noqa: BLE001 - a bug in a companion must never stop the world for the people playing in it
                import traceback

                traceback.print_exc()
                ai.disabled = True  # it stands where it is; the world, the clock and the humans carry on
        for link in list(self.links.values()):
            if link.invite and link.invite["expires_at"] <= now:
                challenger = self.links.get(link.invite["from"])
                if challenger is not None and challenger.outgoing == link.invite["duel_id"]:
                    challenger.outgoing = ""
                    challenger.notice("invite_expired", duel_id=link.invite["duel_id"])
                link.invite = None
        for duel in list(self.duels.values()):
            if duel.state == "finished":
                if duel.finished_at is not None and now - duel.finished_at > 600 and all(not self._in_open_duel(self.links[p]) for p in duel.players if p in self.links):
                    for p in duel.players:
                        if p in self.links and self.links[p].duel_id == duel.id:
                            self.links[p].duel_id = ""
                    self.duels.pop(duel.id, None)
                continue
            for pid in duel.players:
                l = self.links.get(pid)
                if l is not None and not l.connected and l.disconnected_at is not None and now - l.disconnected_at >= self.disconnect_grace_s:
                    duel.forfeit(pid, "disconnected", now)
                    self.command_log.append({"op": "pvp_forfeit", "player": pid, "duel": duel.id, "why": "disconnected", "game_ms": self.game_ms()})
                    self._after_duel_change(duel, now)
                    break
            if duel.state == "active":
                for pid in duel.auto_cast_overdue(now, self.cast_timeout_s):
                    duel.auto_cast(pid, now)
                    self.command_log.append({"op": "pvp_auto_cast", "player": pid, "duel": duel.id, "game_ms": self.game_ms()})
                    self._after_duel_change(duel, now)
        for link in list(self.links.values()):
            if not link.host and not link.connected and link.disconnected_at is not None and now - link.disconnected_at >= self.remove_after_s:
                self.world.players.pop(link.id, None)
                self.links.pop(link.id, None)
                if "narrative" in self.world.__dict__:
                    party.leave(self.world, link.id)
                self._notify_others(link, "player_removed", player=link.id)

    def stats(self) -> dict[str, Any]:
        return {"players": len(self.links), "online": sum(1 for l in self.links.values() if l.connected), "duels": len(self.duels),
                "commands": len(self.command_log), "game_ms": self.game_ms(), "state": self.state}
