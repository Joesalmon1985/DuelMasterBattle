#!/usr/bin/env python3
"""A scripted second human for the headed LAN tests: joins a host over the production protocol, walks next to the other wizard,
answers challenges, sets a ward and casts legal weaves until the duel ends. Prints LAN_BOT_* lines the test runner reads.

    python3 scripts/lan_bot.py --host 127.0.0.1 --port 8765 --code 1234 [--secret S (play as the host's own wizard and start the world)]
                               [--accept] [--challenge-after N] [--decline-first] [--ward 0,1,6] [--max-duels 1] [--seconds 300]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
for entry in (str(HYB), str(HYB.parent)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from wizard_rts.net.client import NetClient  # noqa: E402


def say(kind: str, **data) -> None:
    print("LAN_BOT_%s %s" % (kind.upper(), json.dumps(data)), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--code", default="")
    ap.add_argument("--secret", default="")
    ap.add_argument("--name", default="Bot")
    ap.add_argument("--accept", action="store_true", help="accept every challenge")
    ap.add_argument("--decline-first", action="store_true", help="decline the first challenge, accept the rest")
    ap.add_argument("--challenge-after", type=float, default=0.0, help="challenge the other wizard N seconds after standing next to him (0: never)")
    ap.add_argument("--ward", default="")
    ap.add_argument("--max-duels", type=int, default=1)
    ap.add_argument("--seconds", type=float, default=300.0)
    ap.add_argument("--start", action="store_true", help="start the world once another player is in (needs --secret)")
    ap.add_argument("--stay", action="store_true", help="do not walk towards the other wizard")
    args = ap.parse_args()
    rng = random.Random(7)
    c = NetClient(args.host, args.port, name=args.name).connect()
    r = c.hello(code=args.code, secret=args.secret or None)
    say("hello", **{k: r.get(k) for k in ("status", "player_id", "host", "state", "reason")})
    if r.get("status") != "ok":
        sys.exit(2)
    me = c.player_id
    t0 = time.monotonic()
    started = r.get("state") == "playing"
    duels_done = 0
    declined = False
    adjacent_since: float | None = None
    challenged = False
    duel_seen = ""
    last_poll = 0.0
    while time.monotonic() - t0 < args.seconds:
        time.sleep(max(0.0, 0.2 - (time.monotonic() - last_poll)))
        last_poll = time.monotonic()
        if not started:
            lob = c.op({"op": "lobby"})
            sess = lob.get("session", {})
            others = [p for p in sess.get("players", []) if p["id"] != me and p.get("connected")]
            if sess.get("state") == "playing":
                started = True
                c.state(full=True)
                say("started")
            elif args.start and others:
                say("start", reply=c.start().get("status"))
            continue
        st = c.state()
        if st.get("status") != "ok":
            continue
        for n in st.get("notices", []):
            say("notice", notice=n)
            if n.get("kind") == "invite_expired":
                challenged = False  # nobody answered: try again once we stand together
        duel = st.get("duel", {})
        inv = st.get("invite", {})
        if inv:
            accept = args.accept and not (args.decline_first and not declined)
            if not accept:
                declined = True
            rr = c.respond(inv["duel_id"], accept)
            say("respond", duel_id=inv["duel_id"], accept=accept, status=rr.get("status"))
            if accept and rr.get("status") == "ok":
                duel = rr.get("duel", {})
        if duel:
            if duel.get("duel_id") != duel_seen:
                duel_seen = duel["duel_id"]
                say("duel", duel_id=duel_seen, state=duel.get("state"))
            state = duel.get("state")
            fmt = duel.get("format", {})
            if state == "setup" and not duel.get("your_ward_locked"):
                ward = [int(x) for x in args.ward.split(",")] if args.ward else [rng.choice(fmt["pool"]) for _ in range(int(fmt["slots"]))]
                rr = c.ward(ward)
                say("ward", status=rr.get("status"), ward=ward)
            elif state == "active" and duel.get("your_cast_pending"):
                attack = [rng.choice(fmt["pool"]) for _ in range(int(fmt["slots"]))]
                rr = c.cast(attack)
                say("cast", status=rr.get("status"), attack=attack, fracture=rr.get("fracture"), echo=rr.get("echo"), fade=rr.get("fade"), broken=rr.get("broken"), done=rr.get("done"))
                time.sleep(0.4)  # a human takes a moment
            elif state == "finished":
                res = duel.get("result", {})
                say("result", duel_id=duel_seen, outcome=res.get("outcome"), reason=res.get("reason"), your_casts=res.get("your_casts"), rival_casts=res.get("rival_casts"), rival_ward=duel.get("rival_ward"))
                c.op({"op": "pvp_leave"})
                duels_done += 1
                challenged = False
                adjacent_since = None
                if duels_done >= args.max_duels:
                    say("done", duels=duels_done)
                    time.sleep(1.0)
                    break
            continue
        # no duel: stand next to the other wizard
        others = [p for p in st["snapshot"].get("players", []) if p["id"] != me and p.get("connected")]
        if not others:
            continue
        o = others[0]
        ox, oy = int(o["tx"]), int(o["ty"])
        mx, my = int(c.pose["tx"]), int(c.pose["ty"])
        dist = abs(ox - mx) + abs(oy - my)
        if dist <= 1:
            if adjacent_since is None:
                adjacent_since = time.monotonic()
                say("adjacent", me=[mx, my], other=[ox, oy])
            if args.challenge_after and not challenged and time.monotonic() - adjacent_since >= args.challenge_after:
                rr = c.challenge(o["id"], "three")
                challenged = rr.get("status") == "ok"
                say("challenge", target=o["id"], status=rr.get("status"), reason=rr.get("reason"))
            continue
        adjacent_since = None
        if args.stay:
            continue
        dx = (ox > mx) - (ox < mx)
        dy = (oy > my) - (oy < my)
        step = (dx, 0) if dx and abs(ox - mx) >= abs(oy - my) else (0, dy)
        rr = c.step(*step)
        if rr.get("status") != "ok":
            alt = (0, dy) if step[0] else (dx, 0)
            if alt != (0, 0):
                rr = c.step(*alt)
            if rr.get("status") != "ok":
                c.step(*rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)]))
    say("exit", duels=duels_done, pose=c.pose)
    c.close()


if __name__ == "__main__":
    main()
