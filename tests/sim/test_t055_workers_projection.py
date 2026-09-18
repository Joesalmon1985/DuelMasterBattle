from copy import deepcopy
from fractions import Fraction

from sim.dmb.industry import fraction
from sim.dmb.industry.projection import IndustryProjection
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


def test_projection_and_visual_obstruction_cannot_change_accounting() -> None:
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
    before = deepcopy(sim.state.to_dict())
    rows = IndustryProjection(sim.state).workers(node_id=fx["node_id"])
    assert rows and rows[0]["person_id"] in sim.state.people
    assert rows[0]["cue"] in {"working", "carrying"}
    assert rows[0]["waypoints"], "route workplaces must be projected for presentation"
    assert sim.state.to_dict() == before

    # Blocking a decorative route is represented only in the client and sends
    # no command; the authoritative outcome remains identical.
    control = load_fixture("FX-INDUSTRY")
    _advance(sim, 900)
    _advance(control, 1000)
    assert _meters(sim) == _meters(control)


def test_explicit_job_strike_changes_output_while_unloaded_people_remain() -> None:
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
    person_id = sim.state.definitions["jobs"]["industry:operator"]["person_id"]
    baseline = _meters(sim)
    jobs.set_modifier("industry:operator", 0)
    sim.state.player["node_id"] = "node:1"
    _advance(sim, 1000)
    assert _meters(sim) == baseline
    assert person_id in sim.state.people
    assert IndustryProjection(sim.state).workers(node_id=fx["node_id"])[0]["cue"] == "on_strike"
