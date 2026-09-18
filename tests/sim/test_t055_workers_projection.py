from copy import deepcopy

from sim.dmb.industry import fraction
from sim.dmb.industry.projection import (
    MAX_CARRIERS_PER_CONNECTION,
    VISUAL_CARRY_CAPACITY_PER_SEC,
    IndustryProjection,
)
from sim.dmb.people.jobs import JobService
from sim.dmb.people.registry import PeopleService
from sim.dmb.testing.fixtures import load_fixture


def _advance(sim, milliseconds=100):
    sequence = int(sim.state.clock["clock_sequence"]) + 1
    assert sim.advance(milliseconds, sequence).status == "ACCEPTED"


def _meters(sim):
    return {
        key: fraction(value["meter"])
        for key, value in sim.state.industry["factories"].items()
    }


def test_accounting_backfills_persistent_people_and_replacement_identity() -> None:
    sim = load_fixture("FX-INDUSTRY")
    fx = sim.state.board["fx_industry"]
    jobs = JobService(sim.state)
    jobs.register_job(
        "industry:operator",
        workplace_id=fx["processor_id"],
        job_id="job:processor",
        node_id=fx["node_id"],
    )
    _advance(sim)
    first_id = sim.state.definitions["jobs"]["industry:operator"]["person_id"]
    assert first_id in sim.state.people

    PeopleService(sim.state).relocate(first_id, "node:1")
    saved = deepcopy(sim.state.to_dict())
    assert saved["people"][first_id]["node_id"] == "node:1"
    jobs.vacate("industry:operator")
    _advance(sim)
    replacement_id = sim.state.definitions["jobs"]["industry:operator"]["person_id"]
    assert replacement_id != first_id
    assert first_id in sim.state.people
    assert replacement_id in sim.state.people


def test_per_connection_carriers_from_real_routes_only() -> None:
    sim = load_fixture("FX-INDUSTRY")
    _advance(sim)
    projection = IndustryProjection(sim.state)
    connections = projection.connections()
    raw = [row for row in connections if row["kind"] == "raw_input"]
    outbound = [row for row in connections if row["kind"] == "processed_output"]
    assert len(raw) == 2
    assert {row["resource_label"] for row in raw} == {"Foraged berries and nuts", "Flint"}
    assert {row["from_id"] for row in raw} == {"source:woodland", "source:ore"}
    assert all(row["to_id"] == "processor:fx-industry" for row in raw)
    assert len(outbound) == 3
    assert {row["to_id"] for row in outbound} == {
        "factory:fx-skirmisher",
        "factory:fx-line",
        "factory:fx-heavy",
    }
    # No invented same-building or factory-to-factory tours.
    assert all(row["from_id"] != row["to_id"] for row in connections)
    assert VISUAL_CARRY_CAPACITY_PER_SEC > 0
    assert MAX_CARRIERS_PER_CONNECTION >= 1

    rows = projection.workers(node_id="node:industry")
    carriers = [row for row in rows if row.get("role") == "carrier"]
    assert carriers, "active connections must assign carriers"
    ids_before = sorted(row["person_id"] for row in carriers)
    # Projection refresh must not recreate identities.
    again = IndustryProjection(sim.state).workers(node_id="node:industry")
    ids_after = sorted(row["person_id"] for row in again if row.get("role") == "carrier")
    assert ids_before == ids_after
    for carrier in carriers:
        waypoints = carrier["waypoints"]
        assert len(waypoints) == 2
        assert waypoints[0]["id"] == carrier["from_id"]
        assert waypoints[1]["id"] == carrier["to_id"]
        # Must not include unrelated factories on a raw leg.
        if carrier["connection_kind"] == "raw_input":
            assert "factory:" not in waypoints[0]["id"]
            assert "factory:" not in waypoints[1]["id"]


def test_projection_and_visual_obstruction_cannot_change_accounting() -> None:
    sim = load_fixture("FX-INDUSTRY")
    fx = sim.state.board["fx_industry"]
    _advance(sim)
    before = deepcopy(sim.state.to_dict())
    rows = IndustryProjection(sim.state).workers(node_id=fx["node_id"])
    assert rows and rows[0]["person_id"] in sim.state.people
    assert sim.state.to_dict() == before

    # Client path block sends no command; meters match an uninterrupted twin.
    control = load_fixture("FX-INDUSTRY")
    _advance(sim, 900)
    _advance(control, 1000)
    assert _meters(sim) == _meters(control)


def test_explicit_job_strike_changes_output_while_unloaded_people_remain() -> None:
    sim = load_fixture("FX-INDUSTRY")
    fx = sim.state.board["fx_industry"]
    jobs = JobService(sim.state)
    _advance(sim)
    person_id = sim.state.definitions["jobs"]["industry:operator:fx"]["person_id"]
    baseline = _meters(sim)
    jobs.set_modifier("industry:operator:fx", 0)
    sim.state.player["node_id"] = "node:1"
    _advance(sim, 1000)
    assert _meters(sim) == baseline
    assert person_id in sim.state.people
    attendants = [
        row
        for row in IndustryProjection(sim.state).workers(node_id=fx["node_id"])
        if row.get("job_key") == "industry:operator:fx"
    ]
    assert attendants and attendants[0]["cue"] == "on_strike"
    # Carriers wait when throughput is zero.
    carriers = [
        row
        for row in IndustryProjection(sim.state).workers(node_id=fx["node_id"])
        if row.get("role") == "carrier"
    ]
    assert carriers
    assert all(row["cue"] in {"waiting", "on_strike"} for row in carriers)
