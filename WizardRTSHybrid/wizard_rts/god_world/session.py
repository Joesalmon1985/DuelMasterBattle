"""The host-facing session of a God World: the same wire shape as the Wizard World's `MultiplayerSession` (hello, start, state, leave) so the
existing `HostServer`, the Android plugin and the Godot `LanSession` carry it unchanged, plus the god's own ops: board, inspect, pause,
speed, save, new_world. Nothing here moves a faction: the spectator only views, inspects and sets playback."""

from __future__ import annotations

import os
import secrets
import time
from typing import Any

from wizard_rts.net import protocol

from . import inspect as inspect_mod
from . import rules, snapshot
from .world import GodWorld

GOD_OPS = frozenset({"ping", "lobby", "start", "state", "leave", "board", "inspect", "label", "pause", "speed", "save", "new_world", "stats", "events"})
HOST_ONLY = frozenset({"start", "pause", "speed", "save", "new_world"})


class Link:
    def __init__(self, pid: str, name: str, token: str, host: bool) -> None:
        self.id, self.name, self.token, self.host = pid, name, token, host
        self.connected = True
        self.ai = False
        self.spawned = True
        self.conn: Any = None
        self.last_seen = 0.0
        self.disconnected_at: float | None = None
        self.notices: list[dict[str, Any]] = []
        self.board_sent = False


class GodSession:
    def __init__(self, world: GodWorld, name: str = "God World", join_code: str | None = None, host_secret: str | None = None, max_players: int = 1,
                 clock=time.monotonic, permanent: bool = False, autosave_s: float = 120.0, **_ignored: Any) -> None:
        self.world = world
        self.name = name
        self.join_code = join_code or f"{secrets.randbelow(10000):04d}"
        self.host_secret = host_secret or secrets.token_hex(12)
        self.max_players = max(1, int(max_players))
        self.clock = clock
        self.links: dict[str, Link] = {}
        self.by_conn: dict[Any, Link] = {}
        self.orphaned_conns: list[Any] = []
        self.state = "lobby"
        self.events: list[dict[str, Any]] = []
        self.command_log: list[dict[str, Any]] = []
        self.on_world_swap = None
        self.on_ending = None
        self.catch_up: dict[str, Any] = {"owed_ms": 0, "active": False}
        self.permanent = permanent
        self.autosave_s = float(autosave_s)
        self._last_autosave = self.clock()
        self.ais: dict[str, Any] = {}
        self.view_radius = 0
        self.ending = None

    # ------------------------------------------------------------------ host surface
    def game_ms(self) -> int:
        return int(self.world.game_ms)

    def info(self) -> dict[str, Any]:
        return {"name": self.name, "state": self.state, "players": sum(1 for l in self.links.values() if l.connected), "max_players": self.max_players,
                "protocol": protocol.PROTOCOL_VERSION, "game": protocol.GAME_VERSION, "profile": self.world.profile, "age": int(self.world.age), "game_ms": self.game_ms(),
                "code_required": True}

    def lobby_view(self) -> dict[str, Any]:
        return {"name": self.name, "state": self.state, "max_players": self.max_players, "profile": self.world.profile, "seed": int(self.world.seed),
                "players": [{"id": l.id, "name": l.name, "host": l.host, "connected": l.connected, "ai": False} for l in self.links.values()], "catch_up": dict(self.catch_up)}

    def stats(self) -> dict[str, Any]:
        return {"players": len(self.links), "online": sum(1 for l in self.links.values() if l.connected), "commands": len(self.command_log), "game_ms": self.game_ms(),
                "state": self.state, "age": int(self.world.age), "counters": dict(self.world.counters)}

    def disconnect(self, conn: Any, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        link = self.by_conn.pop(conn, None)
        if link is not None:
            link.connected = False
            link.conn = None
            link.disconnected_at = now

    def rebind(self, world: GodWorld) -> None:
        self.world = world

    def tick(self, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        w = self.world
        if w.save_requested and self.permanent:
            slot = str(w.save_requested)
            w.save_requested = None
            self._save(slot)
        elif w.save_requested:
            w.save_requested = None
        if self.permanent and self.autosave_s > 0 and now - self._last_autosave >= self.autosave_s and self.state == "playing":
            self._last_autosave = now
            self._save("auto")

    def _save(self, slot: str) -> dict[str, Any]:
        from . import persist

        try:
            return persist.save_world(self.world, slot)
        except (OSError, persist.SaveError) as exc:
            return {"status": "error", "detail": str(exc)}

    # ------------------------------------------------------------------ messages
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
        if op not in GOD_OPS:
            return {"status": "rejected", "reason": "not_allowed_in_god_world", "op": op}
        if op in HOST_ONLY and not link.host:
            return {"status": "rejected", "reason": "host_only", "op": op}
        if op == "leave":
            self.disconnect(conn, now)
            return {"status": "ok", "left": link.id}
        if op == "ping":
            return {"status": "ok", "pong": message.get("t"), "game_ms": self.game_ms()}
        if op == "lobby":
            return {"status": "ok", "session": self.lobby_view(), "you": link.id}
        if op == "start":
            if self.state != "playing":
                self.state = "playing"
                self.events.append({"kind": "start", "game_ms": self.game_ms()})
            return {"status": "ok", "state": self.state, "session": self.lobby_view()}
        if op == "state":
            return self.state_view(link, message)
        if op == "board":
            link.board_sent = True
            return {"status": "ok", "board": snapshot.board_view(self.world)}
        if op == "inspect":
            return {"status": "ok", "details": inspect_mod.details(self.world, str(message.get("id", "")))}
        if op == "label":
            return {"status": "ok", "label": inspect_mod.label(self.world, str(message.get("id", "")))}
        if op == "events":
            n = max(1, min(200, int(message.get("n", 50))))
            return {"status": "ok", "events": self.world.events[-n:]}
        if op == "pause":
            r = self.world.set_paused(bool(message.get("on", True)))
            self.command_log.append({"op": op, "player": link.id, "on": self.world.paused, "game_ms": self.game_ms()})
            return r
        if op == "speed":
            r = self.world.set_speed(int(message.get("scale", 1)))
            self.command_log.append({"op": op, "player": link.id, "scale": self.world.speed, "game_ms": self.game_ms()})
            return r
        if op == "save":
            return self._save(str(message.get("slot", "manual")))
        if op == "new_world":
            return self._new_world(link, message)
        if op == "stats":
            return {"status": "ok", **self.stats()}
        return {"status": "rejected", "reason": "unknown_op", "op": op}

    def _hello(self, conn: Any, message: dict[str, Any], now: float) -> dict[str, Any]:
        if int(message.get("protocol", -1)) != protocol.PROTOCOL_VERSION:
            return {"status": "rejected", "reason": "protocol_mismatch", "expected": protocol.PROTOCOL_VERSION, "got": message.get("protocol")}
        if not protocol.game_compatible(str(message.get("game", ""))):
            return {"status": "rejected", "reason": "version_mismatch", "expected": protocol.GAME_VERSION, "got": str(message.get("game", ""))}
        name = str(message.get("name", "")).strip()[:24] or "Watcher"
        is_host = bool(message.get("secret")) and secrets.compare_digest(str(message.get("secret")), self.host_secret)
        token = str(message.get("token", "") or "")
        link = next((l for l in self.links.values() if token and secrets.compare_digest(l.token, token)), None)
        if link is None and not is_host and str(message.get("code", "")) != self.join_code:
            return {"status": "rejected", "reason": "bad_code"}
        if link is None and is_host:
            link = next((l for l in self.links.values() if l.host), None)
        reconnect = link is not None
        if link is None:
            if len(self.links) >= self.max_players:
                return {"status": "rejected", "reason": "full", "max_players": self.max_players}
            pid = f"god{len(self.links) + 1}"
            link = Link(pid, name, secrets.token_hex(16), is_host)
            self.links[pid] = link
        if link.conn is not None and link.conn is not conn:
            self.by_conn.pop(link.conn, None)
            self.orphaned_conns.append(link.conn)
        link.conn = conn
        link.connected = True
        link.disconnected_at = None
        self.by_conn[conn] = link
        self.events.append({"kind": "reconnect" if reconnect else "join", "player": link.id, "game_ms": self.game_ms()})
        return {"status": "ok", "player_id": link.id, "token": link.token, "host": link.host, "reconnect": reconnect, "name": link.name, "protocol": protocol.PROTOCOL_VERSION,
                "game": protocol.GAME_VERSION, "session": self.lobby_view(), "seed": int(self.world.seed), "map": self.world.map_size, "spawned": True, "state": self.state,
                "profile": self.world.profile, "join_code_required": True, "pose": {"tx": 0, "ty": 0, "facing": "down", "hex": [0, 0], "seq": 0}, "duel": {}}

    def state_view(self, link: Link, message: dict[str, Any]) -> dict[str, Any]:
        view = message.get("view")
        try:
            view = [float(c) for c in view] if isinstance(view, (list, tuple)) and len(view) == 4 else None
        except (TypeError, ValueError):
            view = None
        snap = snapshot.snapshot(self.world, view)
        out = {"status": "ok", "seq": message.get("seq"), "you": link.id, "session_state": self.state, "snapshot": snap, "notices": list(link.notices),
               "players_online": sum(1 for l in self.links.values() if l.connected)}
        if bool(message.get("full", False)) or not link.board_sent:
            out["board"] = snapshot.board_view(self.world)
            link.board_sent = True
        link.notices.clear()
        return out

    def _new_world(self, link: Link, message: dict[str, Any]) -> dict[str, Any]:
        from . import persist

        archived = persist.archive_all() if self.permanent else []
        seed = int(message.get("seed", int(time.time()) % 100000))
        world = GodWorld(seed=seed)
        self.world = world
        for l in self.links.values():
            l.board_sent = False
        if self.on_world_swap is not None:
            self.on_world_swap(world)
        self.command_log.append({"op": "new_world", "player": link.id, "seed": seed})
        return {"status": "ok", "new_world": True, "seed": seed, "archived": archived}


def build_world(args: dict[str, Any]) -> tuple[GodWorld, dict[str, Any]]:
    """The God World this device hosts: the newest save when the host is permanent (`runs_dir` or `continue`), else a fresh world on `seed`.
    `new_world` archives the saves first; `fresh` deletes nothing (archives too). A save it cannot read is an error the caller shows."""
    from . import persist

    if args.get("runs_dir"):
        os.environ["DMB_RUNS"] = str(args["runs_dir"])
    permanent = bool(args.get("runs_dir")) or bool(args.get("continue"))
    info: dict[str, Any] = {"loaded": False, "path": "", "archived": [], "permanent": permanent}
    if bool(args.get("new_world")) or bool(args.get("fresh")):
        info["archived"] = persist.archive_all()
    path = persist.latest() if (permanent and not args.get("new_world") and not args.get("fresh")) else None
    start_age = int(args.get("start_age") or os.environ.get("DMB_GOD_START_AGE", "0") or 0)
    if path is None or start_age:
        world = GodWorld(seed=int(args.get("seed", 507)))
        if start_age in (2, 3, 4):  # developer evidence only: the island opens in a later age with the same two villages per faction
            seq = 0
            while world.phase == "SETUP":
                seq += 1
                world.advance(1000, seq, snapshot=False)
            world.age = start_age
            for v in world.villages.values():
                v["age"] = start_age
            info["start_age"] = start_age
            info["permanent"] = False
        return world, info
    world, li = persist.load_world(path)
    info.update(loaded=True, path=li["path"], game_ms=int(world.game_ms), age=int(world.age))
    return world, info
