"""Entry points the Android plugin (Chaquopy) calls: start the host loop in a thread inside the app process, stop it, read status.

No numpy, no C kernel, no file writes outside `HOME` (Chaquopy sets HOME to the app's files directory). Everything the
world needs is stdlib plus the packaged `wizard_rts` and `sim` sources."""

from __future__ import annotations

import collections
import json
import os
import sys
import threading
import traceback
from typing import Any

os.environ.setdefault("DMB_NO_NATIVE", "1")  # no compiler on a phone: the pure-Python A* twin (byte-identical results)

_lock = threading.Lock()
_thread: threading.Thread | None = None
_host: Any = None
_status: dict[str, Any] = {"state": "idle"}
_log: collections.deque[str] = collections.deque(maxlen=200)


def log(line: str) -> None:
    _log.append(str(line))


def _run(args: dict[str, Any]) -> None:
    global _host
    try:
        from wizard_rts.net import protocol
        from wizard_rts.net.host import HostServer, lan_addresses, new_world, prepare_world
        from wizard_rts.net.session import MultiplayerSession

        _status.update(state="building_world")
        if args.get("runs_dir"):
            os.environ["DMB_RUNS"] = str(args["runs_dir"])  # where Wizard World saves live: the app's own storage, which the menu can also look at
        seed, map_size, profile = int(args.get("seed", 507)), str(args.get("map", "small")), str(args.get("profile", "campaign"))
        if profile == "god_catan_v1":  # God World (docs/GOD_WORLD_PRD.md): the on-device authority is GodWorld, nothing of the wizard's world is built
            from wizard_rts.net.host import build_god_host

            host = build_god_host({**args, "seed": seed, "max_players": 1})
            session = host.session
            prepared = host.prepared
        else:
            permanent = bool(args.get("runs_dir")) or bool(args.get("continue"))
            world, prepared = prepare_world(profile, seed, map_size, new_world_flag=bool(args.get("new_world")), new_wizard=bool(args.get("new_wizard")), permanent=permanent)
            if bool(args.get("games_village")):
                from wizard_rts.narrative import games_village

                games_village.ensure(world)
            session = MultiplayerSession(world, name=str(args.get("name", "Phone")), join_code=args.get("code"), host_secret=args.get("secret"),
                                         max_players=int(args.get("max_players", 2)), view_radius=int(args.get("view_radius", protocol.DEFAULT_VIEW_RADIUS)),
                                         world_factory=lambda: new_world(seed, map_size, profile), ai_companions=1 if int(args.get("max_players", 2)) == 1 else 0)
            host = HostServer(world, session, bind=str(args.get("bind", "0.0.0.0")), port=int(args.get("port", protocol.DEFAULT_PORT)),
                              discovery_port=(int(args["discovery_port"]) if args.get("discovery_port") else None))
            host.permanent = permanent
            host.prepared = prepared
            if prepared.get("loaded"):
                host.begin_catch_up(int(prepared.get("owed_ms", 0)))
        host.start()
        _host = host
        _status.update(state="ready", port=host.port, code=session.join_code, secret=session.host_secret, lan=lan_addresses(), name=session.name,
                       protocol=protocol.PROTOCOL_VERSION, game=protocol.GAME_VERSION)
        log(host.ready_line())
        while not host.stop_flag:
            host.step(0.02)
    except Exception:  # noqa: BLE001
        _status.update(state="failed", error=traceback.format_exc()[-2000:])
        log(traceback.format_exc())
    finally:
        if _host is not None:
            try:
                _status["stats"] = _host.summary()
                _host.stop()
            except Exception:  # noqa: BLE001
                pass
        if _status.get("state") != "failed":
            _status.update(state="stopped")


def start(args_json: str) -> str:
    """Start hosting; `args_json` keys: port, bind, name, code, secret, seed, map, profile, max_players, discovery_port, view_radius,
    continue (host the newest Wizard World save), runs_dir (where saves live)."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return json.dumps({"status": "rejected", "reason": "already_running", **_status})
        try:
            args = json.loads(args_json) if args_json else {}
        except json.JSONDecodeError:
            return json.dumps({"status": "rejected", "reason": "bad_args"})
        _status.clear()
        _status.update(state="starting")
        _thread = threading.Thread(target=_run, args=(args,), name="dmb-host", daemon=True)
        _thread.start()
        return json.dumps({"status": "ok", "state": "starting"})


def stop() -> str:
    with _lock:
        if _host is not None:
            _host.stop_flag = True
        return json.dumps({"status": "ok"})


def status() -> str:
    extra = {}
    if _host is not None:
        extra["catch_up"] = {k: _host.catch_up.get(k) for k in ("owed_ms", "paid_ms", "forfeited_ms", "active")}
        extra["prepared"] = {k: v for k, v in getattr(_host, "prepared", {}).items() if k in ("loaded", "retired", "host_was_dead", "archived", "game_ms")}
    return json.dumps({"status": "ok", "python": sys.version.split()[0], "thread_alive": bool(_thread is not None and _thread.is_alive()), **_status, **extra})


def log_tail(n: int = 40) -> str:
    return "\n".join(list(_log)[-int(n):])


def self_test() -> str:
    """Build a world and advance it (no sockets): proves the real simulation runs inside this process."""
    import time

    from wizard_rts.net.host import new_world

    t = time.time()
    w = new_world(507, "small", "campaign")
    built = time.time() - t
    t = time.time()
    seq = 0
    for _ in range(50):
        seq += 1
        w.advance(100, seq, snapshot=False)
    stepped = time.time() - t
    # the Wizard World layer and the AI companion must import and run from the staged tree too (no numpy, no compiler, no repository)
    from wizard_rts.narrative import tutorial
    from wizard_rts.net import ai_wizard, protocol
    from wizard_rts.net.session import MultiplayerSession

    session = MultiplayerSession(w, name="selftest", join_code="0000", host_secret="s", max_players=1, ai_companions=1)
    conn = object()
    session.handle(conn, {"op": "hello", "protocol": protocol.PROTOCOL_VERSION, "game": protocol.GAME_VERSION, "secret": "s", "name": "Self"}, 0.0)
    session.handle(conn, {"op": "start"}, 0.0)
    companion = sorted(l.name for l in session.links.values() if l.ai)
    # single-player save and continue work in this process too (a pickle of the narrative world, in a scratch folder)
    import shutil
    import tempfile

    from wizard_rts.net.host import load_saved_world

    scratch = tempfile.mkdtemp(prefix="dmb_selftest_")
    previous = os.environ.get("DMB_RUNS")
    os.environ["DMB_RUNS"] = scratch
    try:
        saved = session.handle(conn, {"op": "save", "slot": "manual"}, 0.0)
        reloaded = load_saved_world("campaign") if saved.get("status") == "ok" else None
        save_ok = bool(reloaded is not None and "narrative" in reloaded.__dict__ and tutorial.state(reloaded)["teacher"])
    finally:
        if previous is None:
            os.environ.pop("DMB_RUNS", None)
        else:
            os.environ["DMB_RUNS"] = previous
        shutil.rmtree(scratch, ignore_errors=True)
    return json.dumps({"status": "ok", "python": sys.version.split()[0], "platform": sys.platform, "build_s": round(built, 2), "advance_5s_game_s": round(stepped, 2),
                       "game_ms": int(w.dmb.clock.get("game_ms", 0)), "buildings": len(w.buildings), "units": len(w.units), "hash": w.state_hash()[:12],
                       "narrative": "narrative" in w.__dict__, "mentor": bool(tutorial.state(w)["teacher"]), "companion": companion, "save_continue": save_ok, "protocol": protocol.PROTOCOL_VERSION,
                       "game": protocol.GAME_VERSION, "ai_characters": sorted(ai_wizard.characters()["wizards"])})
