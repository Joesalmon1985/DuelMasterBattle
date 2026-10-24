"""The industrial ages of the living village (docs/PLAN_GOD_WORLD_LIVING.md stage C; the brief's V08 to V11): belts move spaced packets and back up
when the destination is full, a broken segment delivers nothing, processors consume their recipes exactly, water is pumped through a pipe and a
tank into the cultivator, the generator powers the machines only while it burns coal, and the ground factory musters a unit from silicon and
lead within the garrison quota."""

from __future__ import annotations

from wizard_rts.god_world import local_ops, planner, rules
from wizard_rts.god_world.world import GodWorld


def _age4_village(seed=0, role_needed="BRICK"):
    w = GodWorld(seed=seed)
    w.pandemic_enabled = False  # the economy-only regression (the campaign has its own tests)
    w.ai_enabled = False
    seq = [0]

    def step(ms=100):
        seq[0] += 1
        w.advance(ms, seq[0], snapshot=False)

    while w.phase == "SETUP":
        step(1000)
    w.age = 4
    for v in w.villages.values():
        v["age"] = 4
    v = next((v for v in w.villages.values() if v["status"] == "operational" and any(w.board.role(h) == role_needed for h in w.board.node_hexes[v["node"]])), None)
    assert v is not None
    ops = local_ops.complete_all(w, v)
    for s in ops["sites"].values():
        s["state"] = "idle"
        s["ready_ms"] = 0
    return w, v, ops, step


def _sites(ops, kind):
    return [s for s in ops["sites"].values() if s["kind"] == kind]


def test_v11_belts_carry_spaced_packets_and_back_up_when_the_end_is_full():
    w, v, ops, step = _age4_village(0, "BRICK")
    belts = [g for g in ops["segments"].values() if g["kind"] == "belt"]
    assert belts, "an age-four village runs on belts"
    seen_items = 0
    min_gap = 9.0
    for _ in range(1500):
        step()
        for g in belts:
            items = g["items"]
            seen_items += len(items)
            for i in range(1, len(items)):
                min_gap = min(min_gap, (float(items[i - 1]["t"]) - float(items[i]["t"])) * float(g["length"]))
    assert seen_items > 0
    assert min_gap >= local_ops.BELT_SPACING - 1e-6, min_gap
    # a belt into the core: fill the core's stock of that good to its cap and keep going: packets are still accepted (shipped), a processor belt backs up
    proc = next((s for s in _sites(ops, "processor") if s.get("hex")), None)
    if proc is not None:
        feed = next(g for g in ops["segments"].values() if g["to"] == proc["id"])
        proc["state"] = "working"
        proc["progress_ms"] = -10 ** 9  # the processor never finishes: its inlet fills, then the belt queues
        cap = planner.chains()["caps"]["site_in"]
        for _ in range(3000):
            step()
        assert int(proc["in"].get(feed["good"], 0)) <= cap
        if feed["items"]:
            assert float(feed["items"][0]["t"]) >= 1.0 - 1e-9  # the first packet waits at the end
    w.check()


def test_v11_a_broken_belt_delivers_nothing_and_recovers():
    w, v, ops, step = _age4_village(1, "BRICK")
    smelter = next((s for s in _sites(ops, "processor") if s["good"] == "silicon"), None)
    if smelter is None:
        smelter = next(s for s in _sites(ops, "processor"))
    feeds = [g for g in ops["segments"].values() if g["to"] == smelter["id"]]
    assert feeds
    for _ in range(2500):
        step()
    made = int(smelter.get("produced", 0))
    assert made > 0, "the chain should have produced before the cut"
    for g in feeds:
        g["broken"] = True
    for _ in range(1200):
        step()
    stuck = int(smelter.get("produced", 0))
    for _ in range(2500):
        step()
    assert int(smelter.get("produced", 0)) <= stuck + 1  # at most the batch already inside finished
    assert smelter["state"] in ("short", "working", "full")
    for g in feeds:
        g["broken"] = False
    before = int(smelter.get("produced", 0))
    for _ in range(4000):
        step()
    assert int(smelter.get("produced", 0)) > before  # reconnected: it resumes


def test_v10_water_is_pumped_through_the_pipe_and_tank_into_the_cultivator():
    w, v, ops, step = _age4_village(2, "WHEAT")
    cult = next(s for s in _sites(ops, "producer") if s.get("needs_water"))
    pumps = _sites(ops, "pump")
    assert pumps, "a cultivator needs a water source"
    pipes = [g for g in ops["segments"].values() if g["kind"] == "pipe"]
    assert pipes
    assert cult["state"] in ("idle", "short")
    pods_before = int(cult.get("produced", 0))
    water_seen = False
    for _ in range(3000):
        step()
        if int(cult.get("water", 0)) > 0 or any(float(g["fill"]) > 0 for g in pipes):
            water_seen = True
    assert water_seen
    assert int(cult.get("produced", 0)) > pods_before
    # cut the water: the cultivator runs its buffer down and stops
    for g in pipes:
        g["broken"] = True
    for _ in range(6000):
        step()
    assert cult["state"] == "short" and int(cult.get("water", 0)) == 0


def test_power_comes_from_coal_and_its_lack_stops_the_machines():
    w, v, ops, step = _age4_village(3, "BRICK")
    gen = next(s for s in _sites(ops, "generator"))
    procs = [s for s in _sites(ops, "processor")]
    feed = [g for g in ops["segments"].values() if g["to"] == gen["id"]]
    assert feed, "the generator is fed by belt"
    for _ in range(2000):
        step()
    assert ops["power"] is True and gen["state"] == "working"
    for g in feed:
        g["broken"] = True
    gen["in"]["coal"] = 0
    gen["fuel_ms"] = 0
    step()
    step()
    assert ops["power"] is False
    for _ in range(50):
        step()
    assert all(p["state"] in ("unpowered", "working") for p in procs)  # a batch already running finishes, nothing new starts
    for g in feed:
        g["broken"] = False
    for _ in range(3000):
        step()
    assert ops["power"] is True


def test_v09_silicon_and_lead_build_a_unit_within_the_quota():
    w, v, ops, step = _age4_village(4, "BRICK")
    fac = next(s for s in _sites(ops, "factory"))
    feeds = [g for g in ops["segments"].values() if g["to"] == fac["id"]]
    assert {g["good"] for g in feeds} >= {"silicon", "lead"}, feeds
    units_before = sum(1 for u in w.units.values() if u["village"] == v["id"] and u["status"] == "active")
    for _ in range(12000):
        step()
        if int(ops.get("units_made", 0)) >= 1:
            break
    assert int(ops.get("units_made", 0)) >= 1, (fac["state"], fac["in"])
    units_after = sum(1 for u in w.units.values() if u["village"] == v["id"] and u["status"] == "active")
    assert units_after == units_before + int(ops["units_made"])
    quota = rules.limit("garrison_settlement") if int(v["level"]) == 1 else rules.limit("garrison_city")
    assert units_after <= quota
    # the timer never adds a unit to a village with a factory
    assert all(u["art"] == fac["unit"] for u in w.units.values() if u["village"] == v["id"] and u["age"] == 4)
    w.check()


def test_the_industrial_layer_does_not_move_the_strategic_game_either():
    a = GodWorld(seed=5)
    a.pandemic_enabled = False  # the economy-only regression (the campaign has its own tests)
    b = GodWorld(seed=5)
    b.pandemic_enabled = False  # the economy-only regression (the campaign has its own tests)
    b.local_ops_enabled = False
    for i in range(600):
        a.advance(1000, i + 1, snapshot=False)
        b.advance(1000, i + 1, snapshot=False)
    a.age = b.age = 4
    for v in list(a.villages.values()) + list(b.villages.values()):
        v["age"] = 4
    for i in range(600, 1500):
        a.advance(1000, i + 1, snapshot=False)
        b.advance(1000, i + 1, snapshot=False)
    assert a.last_roll == b.last_roll and a.ledger.hands == b.ledger.hands
