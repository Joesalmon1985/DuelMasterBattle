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

from wizard_rts import history, tech  # noqa: E402
from wizard_rts.net import protocol  # noqa: E402
from wizard_rts.net.session import MultiplayerSession  # noqa: E402
from wizard_rts.world import HybridWorld  # noqa: E402


def new_world(seed: int = 507, map_size: str = "small", profile: str = "campaign") -> HybridWorld:
    world = HybridWorld(seed=int(seed), map_size=map_size, profile=profile)
    world.visual_state = True  # presentation fields for the clients (as server.serve does)
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
                "name": self.session.name, "lan": lan_addresses(), "protocol": protocol.PROTOCOL_VERSION, "game": protocol.GAME_VERSION}
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
        self._advance(now)
        self.session.tick(now)
        for conn in self.session.orphaned_conns:
            self._close(conn, notify=False)
        self.session.orphaned_conns.clear()
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
            self.world = history.cycle_reset(self.world)  # a new cycle: every wizard carries over (session.rebind)
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
    world = new_world(args.seed, args.map, args.profile)
    session = MultiplayerSession(world, name=args.name, join_code=args.code, host_secret=args.secret, max_players=args.max_players, view_radius=args.view_radius,
                                 first_joiner_hosts=bool(getattr(args, "first_joiner_hosts", False)))
    return HostServer(world, session, bind=args.bind, port=args.port, discovery_port=None if args.no_discovery else args.discovery_port)


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
