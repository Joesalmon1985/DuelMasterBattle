"""The LAN host: one HybridWorld, one clock loop, many connections, UDP discovery. Runs on a phone (Chaquopy), a laptop, or
inside a test thread; `step()` is the whole loop body so tests can drive it without threads.

    python3 -m wizard_rts.net.host --name "Joe's world" --code 1234 [--bind 0.0.0.0] [--port 8765] [--seed 507] [--map small]

Prints `HYBRID_HOST_READY {json}` once listening. The clock: every `tick_s` of wall time the host calls `world.advance(ms)`
with the elapsed wall time (capped by `max_catchup_s`, so a stalled host does not fast-forward the world); the clock
service turns that into whole 100 ms quanta and honours pause tokens. Nothing else advances the world.
"""

from __future__ import annotations

import argparse
import json
import os
import selectors
import socket
import sys
import time
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parents[2]
_ROOT = _HERE.parent
for entry in (str(_HERE), str(_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from wizard_rts import history, narrative, tech  # noqa: E402
from wizard_rts.narrative import clockdebt, tutorial  # noqa: E402
from wizard_rts.net import protocol  # noqa: E402
from wizard_rts.net.session import MultiplayerSession  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def new_world(seed: int = 507, map_size: str = "small", profile: str = "campaign", wizard: bool = True) -> HybridWorld:
    """A fresh Wizard World: the same world `server.new_world` builds for the classic single-player game (the autonomous civilisation plus
    the narrative layer and the apprentice's mentor). `wizard=False` is the bare simulation, for the harness tests that never talk to anyone."""
    world = HybridWorld(seed=int(seed), map_size=map_size, profile=profile)
    world.visual_state = True  # presentation fields for the clients (as server.serve does)
    if wizard:
        narrative.enable(world)  # Wizard Mode state lives only in worlds a server creates (never in HybridEnv or training worlds)
        tutorial.start(world)  # campaign only: the mentor stands beside the wizard (a loaded world keeps its own)
    return world


def latest_save(profile: str = "campaign") -> Path | None:
    """The newest valid Wizard World save of this device, any slot (quit, auto, manual), or None."""
    from wizard_rts.narrative import persist

    best: tuple[float, Path] | None = None
    for slot in ("quit", "auto", "manual"):
        try:
            path = persist.slot_path(profile, slot)
        except persist.SaveError:
            continue
        if path.exists() and persist._valid(path):
            mtime = path.stat().st_mtime
            if best is None or mtime > best[0]:
                best = (mtime, path)
    return best[1] if best else None


def archive_saves(profile: str, stamp: str | None = None) -> list[str]:
    """"Start a new world": the existing saves are renamed, never deleted (the owner can put them back by hand)."""
    from wizard_rts.narrative import persist

    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    out = []
    folder = persist.saves_dir(profile)
    if not folder.exists():
        return out
    for p in sorted(folder.glob("*.pkl")) + sorted(folder.glob("*.json")):
        if ".retired-" in p.name:
            continue
        target = p.with_name(f"{p.stem}.retired-{stamp}{p.suffix}")
        try:
            os.replace(p, target)
            out.append(str(target))
        except OSError:
            pass
    return out


def prepare_world(profile: str, seed: int, map_size: str, *, new_world_flag: bool = False, new_wizard: bool = False, now: float | None = None,
                  permanent: bool = True) -> tuple[HybridWorld, dict[str, Any]]:
    """The world this installation hosts (plan section 3.3). With `permanent`, the newest save is the world: it is loaded, never regenerated, and a
    save the code cannot read is an error the caller shows (nothing silently starts over). `new_world_flag` archives the saves first (the explicit
    "Start a new world"). On a loaded world the human seats of the last session are retired (a new session seats whoever comes); the host seat is
    retired when its wizard is dead or when `new_wizard` was asked for, so the next apprentice is a new person in the same world. `owed_ms` is the
    offline catch-up the host pays before the world opens (`clockdebt`)."""
    from wizard_rts.narrative import mortality, party, persist

    info: dict[str, Any] = {"loaded": False, "path": "", "owed_ms": 0, "retired": [], "archived": [], "host_was_dead": False}
    if new_world_flag:
        info["archived"] = archive_saves(profile)
    path = latest_save(profile) if (permanent and not new_world_flag) else None
    if path is None:
        return new_world(seed, map_size, profile), info
    try:
        world, li = persist.load_world(path)
    except persist.SaveError as exc:
        if exc.prev:
            world, li = persist.load_world(exc.prev)
            info["recovered_from_prev"] = True
        else:
            raise
    world.visual_state = True
    world.players = {}
    tutorial.start(world)
    info.update(loaded=True, path=li["path"], game_ms=li["game_ms"], closed_at=li.get("closed_at"), game_version=li.get("game_version", ""), last_catch_up=li.get("catch_up", {}),
                hash_mismatch=li.get("hash_mismatch", False))
    if narrative.enabled(world):
        host_seat = party.party(world).get("host", "")
        for seat in list(party.order(world)):
            rec = party.seats(world).get(seat)
            if rec is not None and rec.get("human") and seat != host_seat:
                info["retired"].append(party.retire(world, seat, "session_over"))
        if host_seat and host_seat in party.seats(world):
            dead = mortality.is_dead(world, host_seat)
            info["host_was_dead"] = dead
            if dead or new_wizard:
                info["retired"].append(party.retire(world, host_seat, "died" if dead else "new_wizard"))
        if now is None:
            now = time.time()
            if os.environ.get("HYBRID_FAKE_ABSENCE_S") and li.get("closed_at"):  # developer: pretend the installation was closed this long
                now = float(li["closed_at"]) + float(os.environ["HYBRID_FAKE_ABSENCE_S"])
        info["owed_ms"] = clockdebt.owed_ms(li.get("closed_at"), now)
    return world, info


def load_saved_world(profile: str = "campaign") -> HybridWorld | None:
    """Continue: the newest Wizard World save, ready to be hosted. The single wizard of a save becomes the host's wizard again
    (`world.players` is rebuilt by the session), and a damaged save falls back to its `.prev` twin."""
    from wizard_rts.narrative import persist

    path = latest_save(profile)
    if path is None:
        return None
    try:
        world, _info = persist.load_world(path)
    except persist.SaveError as exc:
        if exc.prev:
            world, _info = persist.load_world(exc.prev)
        else:
            return None
    world.visual_state = True
    world.players = {}
    tutorial.start(world)
    return world


def lan_addresses() -> list[str]:
    """The non-loopback IPv4 addresses this machine has (what a joining phone would type)."""
    out: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in out:
                out.append(ip)
    except socket.gaierror:
        pass
    try:  # the interface a default route would use (works without DNS)
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("10.255.255.255", 1))
        ip = probe.getsockname()[0]
        probe.close()
        if not ip.startswith("127.") and ip not in out:
            out.append(ip)
    except OSError:
        pass
    return out


class HostServer:
    def __init__(self, world: HybridWorld, session: MultiplayerSession, bind: str = "0.0.0.0", port: int = protocol.DEFAULT_PORT,
                 discovery_port: int | None = protocol.DISCOVERY_PORT, tick_s: float = 0.1, max_catchup_s: float = 0.5, clock=time.monotonic) -> None:
        self.world = world
        self.session = session
        self.bind = bind
        self.port = int(port)
        self.discovery_port = discovery_port
        self.tick_s = float(tick_s)
        self.max_catchup_s = float(max_catchup_s)
        self.clock = clock
        self.sel = selectors.DefaultSelector()
        self.listener: socket.socket | None = None
        self.udp: socket.socket | None = None
        self.buffers: dict[socket.socket, bytes] = {}
        self.seq = int(world.dmb.clock.get("clock_sequence", 0))
        self.last_tick: float | None = None
        self.stop_flag = False
        self.stats = {"bytes_in": 0, "bytes_out": 0, "messages": 0, "replies": 0, "advances": 0, "quanta": 0, "probes": 0, "connections": 0, "tick_ms_max": 0.0, "tick_ms_total": 0.0, "ticks": 0}
        self.per_conn: dict[socket.socket, dict[str, int]] = {}
        session.on_world_swap = self._adopt_world  # a single-player New game replaces the world object
        session.on_ending = self._on_ending  # every human is dead: the world is saved with the bodies in it and the session winds down
        self.stop_at: float | None = None
        self.ending_save: dict[str, Any] | None = None
        self.permanent = False  # the installation's world: saved on endings and after the catch-up
        self.catch_up: dict[str, Any] = {"owed_ms": 0, "paid_ms": 0, "forfeited_ms": 0, "active": False, "spent_s": 0.0, "budget_s": clockdebt.settings()["budget_s"], "written_off": True}
        session.catch_up = self.catch_up  # the lobby shows it; `start` forfeits what is left

    def begin_catch_up(self, owed_ms: int) -> None:
        """The world is owed `owed_ms` of simulated time for the installation's absence: paid in slices by `step()` while the lobby is open."""
        owed = max(0, int(owed_ms))
        self.catch_up.update(owed_ms=owed, paid_ms=0, forfeited_ms=0, active=owed > 0, spent_s=0.0, written_off=owed <= 0)

    def _catch_up_slice(self, max_quanta: int = 5) -> None:
        cu = self.catch_up
        if cu["active"]:
            for _ in range(max_quanta):
                if cu["paid_ms"] >= cu["owed_ms"] or cu["spent_s"] >= cu["budget_s"]:
                    cu["active"] = False
                    break
                t0 = self.clock()
                self.seq += 1
                self.world.advance(100, self.seq, snapshot=False)
                cu["paid_ms"] += 100
                cu["spent_s"] += self.clock() - t0
            if cu["active"]:
                return
            cu["forfeited_ms"] = max(0, cu["owed_ms"] - cu["paid_ms"])
            self.last_tick = self.clock()  # the real-time clock resumes from now, not from before the catch-up
        if not cu["written_off"]:
            self._write_off()

    def _write_off(self) -> None:
        """The debt is consumed: the save is rewritten at once with the new `closed_at`, so a crash (or a reconnect) can never apply it twice."""
        cu = self.catch_up
        cu["written_off"] = True
        self.world.catch_up_record = {"owed_ms": cu["owed_ms"], "paid_ms": cu["paid_ms"], "forfeited_ms": cu["forfeited_ms"], "spent_s": round(cu["spent_s"], 2),
                                      "game_ms": int(self.world.dmb.clock.get("game_ms", 0))}
        if self.permanent and narrative.enabled(self.world):
            self.save_world("quit")

    def save_world(self, slot: str = "quit") -> dict[str, Any]:
        from wizard_rts import server

        try:
            out = server._handle(self.world, {"op": "save", "slot": slot})
        except Exception as exc:  # noqa: BLE001
            out = {"status": "error", "detail": str(exc)}
        return out if isinstance(out, dict) else {"status": "error"}

    def _on_ending(self, session: MultiplayerSession) -> None:
        """The session's game has ended. The host's own world (a private session, or the hosting installation's world) is saved as it is, dead
        apprentices and all; the clients read `ending` from their state polls, show it and leave; the host stops once they have, or after a while."""
        if narrative.enabled(self.world) and (self.permanent or session.max_players == 1):
            self.ending_save = self.save_world("quit")
        self.stop_at = self.clock() + 30.0

    def _adopt_world(self, world: HybridWorld) -> None:
        self.world = world
        self.seq = int(world.dmb.clock.get("clock_sequence", 0))

    # ---------------------------------------------------------------- lifecycle
    def start(self) -> None:
        ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ls.bind((self.bind, self.port))
        ls.listen(8)
        ls.setblocking(False)
        self.port = ls.getsockname()[1]
        self.listener = ls
        self.sel.register(ls, selectors.EVENT_READ, "listen")
        if self.discovery_port:
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except OSError:
                    pass
            udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp.bind(("0.0.0.0" if self.bind in ("", "0.0.0.0") else self.bind, int(self.discovery_port)))
            udp.setblocking(False)
            self.udp = udp
            self.sel.register(udp, selectors.EVENT_READ, "udp")
        self.last_tick = self.clock()

    def ready_line(self) -> str:
        info = {"port": self.port, "bind": self.bind, "discovery_port": self.discovery_port, "code": self.session.join_code, "secret": self.session.host_secret,
                "name": self.session.name, "lan": lan_addresses(), "protocol": protocol.PROTOCOL_VERSION, "game": protocol.GAME_VERSION,
                "catch_up": {k: self.catch_up[k] for k in ("owed_ms", "active")}, "prepared": {k: v for k, v in getattr(self, "prepared", {}).items() if k in ("loaded", "retired", "host_was_dead", "archived", "game_ms")}}
        return "HYBRID_HOST_READY " + json.dumps(info)

    def stop(self) -> None:
        self.stop_flag = True
        for conn in list(self.buffers):
            self._close(conn)
        for s in (self.listener, self.udp):
            if s is not None:
                try:
                    self.sel.unregister(s)
                except Exception:  # noqa: BLE001
                    pass
                s.close()
        self.listener = self.udp = None

    def run_forever(self, idle_s: float = 0.02) -> None:
        while not self.stop_flag:
            self.step(idle_s)

    # ---------------------------------------------------------------- one loop body
    def step(self, timeout: float = 0.0) -> None:
        t0 = self.clock()
        for key, _mask in self.sel.select(timeout):
            if key.data == "listen":
                self._accept()
            elif key.data == "udp":
                self._probe()
            else:
                self._read(key.fileobj)  # type: ignore[arg-type]
        now = self.clock()
        self._catch_up_slice()
        if not self.catch_up["active"]:
            self._advance(now)
        self.session.tick(now)
        for conn in self.session.orphaned_conns:
            self._close(conn, notify=False)
        self.session.orphaned_conns.clear()
        if self.stop_at is not None and (now >= self.stop_at or not any(l.connected for l in self.session.links.values() if not l.ai)):
            self.stop_flag = True
        spent = (self.clock() - t0) * 1000.0
        self.stats["ticks"] += 1
        self.stats["tick_ms_total"] += spent
        self.stats["tick_ms_max"] = max(self.stats["tick_ms_max"], spent)

    def _advance(self, now: float) -> None:
        if self.last_tick is None:
            self.last_tick = now
            return
        elapsed = now - self.last_tick
        if elapsed < self.tick_s:
            return
        self.last_tick = now
        ms = int(min(elapsed, self.max_catchup_s) * 1000.0)
        self.seq += 1
        t0 = self.clock()
        reply = self.world.advance(ms, self.seq, snapshot=False)
        spent = (self.clock() - t0) * 1000.0
        self.stats["advances"] += 1
        self.stats["quanta"] += int(reply.get("quanta", 0))
        self.stats["advance_ms_total"] = self.stats.get("advance_ms_total", 0.0) + spent
        if spent > self.stats.get("advance_ms_max", 0.0):
            self.stats["advance_ms_max"] = spent
            self.stats["advance_ms_max_quanta"] = int(reply.get("quanta", 0))
        if getattr(self.world, "cycle_pending", False) and tech.god_allowed(self.world) is not None:
            old = self.world
            self.world = history.cycle_reset(old)  # a new cycle: every wizard carries over (session.rebind)
            self.world.visual_state = True
            if narrative.enabled(old):
                narrative.carry_over(old, self.world)  # the wizard's spells, lessons and duels cross the reset too
                tutorial.start(self.world)
            self.session.rebind(self.world)
            self.seq = int(self.world.dmb.clock.get("clock_sequence", 0))

    # ---------------------------------------------------------------- connections
    def _accept(self) -> None:
        assert self.listener is not None
        try:
            conn, _addr = self.listener.accept()
        except OSError:
            return
        conn.setblocking(True)
        conn.settimeout(5.0)
        try:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        self.buffers[conn] = b""
        self.per_conn[conn] = {"in": 0, "out": 0}
        self.sel.register(conn, selectors.EVENT_READ, "conn")
        self.stats["connections"] += 1

    def _close(self, conn: socket.socket, notify: bool = True) -> None:
        if notify:
            self.session.disconnect(conn, self.clock())
        try:
            self.sel.unregister(conn)
        except Exception:  # noqa: BLE001
            pass
        self.buffers.pop(conn, None)
        self.per_conn.pop(conn, None)
        try:
            conn.close()
        except OSError:
            pass

    def _read(self, conn: socket.socket) -> None:
        try:
            chunk = conn.recv(65536)
        except (ConnectionError, OSError):
            chunk = b""
        if not chunk:
            self._close(conn)
            return
        self.stats["bytes_in"] += len(chunk)
        self.per_conn[conn]["in"] += len(chunk)
        buf = self.buffers.get(conn, b"") + chunk
        if len(buf) > protocol.MAX_LINE_BYTES and b"\n" not in buf:
            self._close(conn)
            return
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if not line.strip():
                continue
            self.stats["messages"] += 1
            t_op = self.clock()
            message: Any = None
            try:
                message = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                reply: dict[str, Any] = {"status": "rejected", "reason": "bad_json"}  # timed and counted under op "?" like any other line
            else:
                try:
                    reply = self.session.handle(conn, message, self.clock())
                except Exception as exc:  # noqa: BLE001 - one bad op must not take the world down for everyone
                    import traceback

                    traceback.print_exc()
                    sys.stdout.flush()
                    reply = {"status": "error", "reason": "server_error", "detail": f"{type(exc).__name__}: {exc}", "op": str(message.get("op", "")) if isinstance(message, dict) else ""}
            if not self._send(conn, reply):
                return
            spent_ms = (self.clock() - t_op) * 1000.0
            op_name = str(message.get("op", "")) if isinstance(message, dict) else "?"
            agg = self.stats.setdefault("op_ms", {}).setdefault(op_name, [0, 0.0, 0.0])  # count, total ms, max ms
            agg[0] += 1
            agg[1] += spent_ms
            agg[2] = max(agg[2], spent_ms)
        if conn in self.buffers:
            self.buffers[conn] = buf

    def _send(self, conn: socket.socket, reply: dict[str, Any]) -> bool:
        data = json.dumps(reply, separators=(",", ":"), default=str).encode("utf-8") + b"\n"
        try:
            conn.sendall(data)
        except (ConnectionError, OSError, socket.timeout):
            self._close(conn)
            return False
        self.stats["bytes_out"] += len(data)
        self.stats["replies"] += 1
        if conn in self.per_conn:
            self.per_conn[conn]["out"] += len(data)
        return True

    def _probe(self) -> None:
        assert self.udp is not None
        try:
            data, addr = self.udp.recvfrom(2048)
        except OSError:
            return
        if not data.startswith(protocol.DISCOVERY_MAGIC.encode("utf-8")):
            return
        self.stats["probes"] += 1
        info = self.session.info()
        info.update(port=self.port, lan=lan_addresses())
        try:
            self.udp.sendto(json.dumps(info, separators=(",", ":")).encode("utf-8"), addr)
        except OSError:
            pass

    def summary(self) -> dict[str, Any]:
        out = dict(self.stats)
        out["op_ms"] = {k: {"n": v[0], "avg": round(v[1] / max(1, v[0]), 1), "max": round(v[2], 1)} for k, v in self.stats.get("op_ms", {}).items()}
        out["tick_ms_avg"] = (self.stats["tick_ms_total"] / self.stats["ticks"]) if self.stats["ticks"] else 0.0
        out["session"] = self.session.stats()
        return out


def build(args: argparse.Namespace) -> HostServer:
    """The app always passes `--runs-dir`, which makes the world permanent (the newest save is the world). A developer host without it builds a fresh
    world unless `--continue` asks for the save (the old behaviour, kept for the launchers and the headed tests)."""
    if getattr(args, "runs_dir", ""):
        os.environ["DMB_RUNS"] = str(args.runs_dir)
    permanent = bool(getattr(args, "runs_dir", "")) or bool(getattr(args, "continue_game", False))
    world, info = prepare_world(args.profile, args.seed, args.map, new_world_flag=bool(getattr(args, "new_world", False)),
                                new_wizard=bool(getattr(args, "new_wizard", False)), permanent=permanent)
    session = MultiplayerSession(world, name=args.name, join_code=args.code, host_secret=args.secret, max_players=args.max_players, view_radius=args.view_radius,
                                 first_joiner_hosts=bool(getattr(args, "first_joiner_hosts", False)),
                                 world_factory=lambda: new_world(args.seed, args.map, args.profile), ai_companions=1 if int(args.max_players) == 1 else 0)
    host = HostServer(world, session, bind=args.bind, port=args.port, discovery_port=None if args.no_discovery else args.discovery_port)
    host.permanent = permanent
    host.prepared = info
    if info.get("loaded"):
        host.begin_catch_up(int(info.get("owed_ms", 0)))
    return host


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="DuelMasterBattle LAN host")
    ap.add_argument("--bind", default=os.environ.get("HYBRID_HOST_BIND", "0.0.0.0"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("HYBRID_SIM_PORT", protocol.DEFAULT_PORT)))
    ap.add_argument("--discovery-port", type=int, default=protocol.DISCOVERY_PORT)
    ap.add_argument("--no-discovery", action="store_true")
    ap.add_argument("--name", default=os.environ.get("HYBRID_HOST_NAME", "DuelMasterBattle"))
    ap.add_argument("--code", default=os.environ.get("HYBRID_JOIN_CODE"))
    ap.add_argument("--secret", default=os.environ.get("HYBRID_HOST_SECRET"))
    ap.add_argument("--seed", type=int, default=int(os.environ.get("HYBRID_SEED", "507")))
    ap.add_argument("--map", default=os.environ.get("HYBRID_MAP", "small"))
    ap.add_argument("--profile", default=os.environ.get("HYBRID_PROFILE", "campaign"))
    ap.add_argument("--max-players", type=int, default=2)
    ap.add_argument("--view-radius", type=int, default=protocol.DEFAULT_VIEW_RADIUS)
    ap.add_argument("--first-joiner-hosts", action="store_true",
                    help="this machine has no wizard of its own (a PC hosting for phones): the first player to join with the code gets the host role and the START button")
    ap.add_argument("--runs-dir", default="", help="where Wizard World saves live (DMB_RUNS); the menu looks in the same folder")
    ap.add_argument("--continue", dest="continue_game", action="store_true", help="host the newest Wizard World save of this device (always the case with --runs-dir)")
    ap.add_argument("--new-wizard", action="store_true", help="retire the host's wizard (alive or dead) and seat a new apprentice in the same world")
    ap.add_argument("--new-world", action="store_true", help="archive the saves and build a fresh world (the explicit 'Start a new world')")
    ap.add_argument("--stats-every", type=float, default=0.0, help="print HYBRID_HOST_STATS every N seconds")
    ap.add_argument("--ready-file", default="", help="also write the ready line's JSON to this file (the Godot launcher polls it)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    host = build(args)
    host.start()
    print(host.ready_line(), flush=True)
    if args.ready_file:
        tmp = Path(args.ready_file + ".tmp")
        tmp.write_text(host.ready_line().split(" ", 1)[1], encoding="utf-8")
        os.replace(tmp, args.ready_file)
    last = time.monotonic()
    try:
        while not host.stop_flag:
            host.step(0.02)
            if args.stats_every and time.monotonic() - last >= args.stats_every:
                last = time.monotonic()
                print("HYBRID_HOST_STATS " + json.dumps(host.summary()), flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        print("HYBRID_HOST_STATS " + json.dumps(host.summary()), flush=True)
        host.stop()


if __name__ == "__main__":
    main()
