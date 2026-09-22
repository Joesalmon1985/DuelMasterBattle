"""G05 starting-village dialogue sanity — no retired quest / Aspect contamination."""

from __future__ import annotations

from pathlib import Path

from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.narrative.knowledge import KnowledgeFact, reveal
from sim.dmb.narrative.line_catalog import LineCatalog
from sim.dmb.narrative.person_dialogue import occupation_answer_line, person_talk_context
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.boulder_quest import (
    QUEST_INSTANCE_ID,
    ROCKFALL_ID,
    accept_move,
    complete_move,
    eligible_boulder_helpers,
    get_rockfall,
)

ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = (
    ROOT
    / "Pack"
    / "DuelMasterBattle_Build_Pack"
    / "tracking"
    / "gates"
    / "G05"
    / "dialogue_matrix.md"
)
AUDIT_PATH = ROOT / "docs" / "review" / "G05_STARTING_VILLAGE_DIALOGUE_AUDIT.md"

RETIRED_PHRASES = (
    "route a",
    "route b",
    "sluice",
    "channel is open",
    "demon",
    "manifestation",
    "yard has gone quiet",
    "patrol cleared",
    "factory shortage",
    "lost handle",
    "reason marks",
    "empathy",
    "as worker, reason",
)


def _sim():
    return load_fixture("FX-VILLAGE", seed=507)


def _cmd(sim, kind: str, payload: dict, *, cid: str) -> dict:
    env = CommandEnvelope(
        protocol_version=1,
        session_id="dlg",
        world_id=sim.state.world_id,
        command_id=cid,
        expected_world_version=sim.state.world_version,
        kind=kind,
        payload=payload,
    )
    return sim.dispatch(env).to_dict()


def _talk(sim, person_id: str, *, cid: str) -> dict:
    reply = _cmd(sim, "Interact", {"action": "talk", "entity_id": person_id}, cid=cid)
    assert reply["status"] == "ACCEPTED", reply
    payload = reply.get("payload") or {}
    session = payload.get("session") or {}
    sid = str(session.get("id") or "")
    if sid:
        _cmd(sim, "Interact", {"action": "close_dialogue", "session_id": sid}, cid=f"{cid}-close")
    return {
        "person_id": person_id,
        "line_id": session.get("line_id"),
        "text": str(payload.get("text") or session.get("text") or ""),
        "choices": list(payload.get("choices") or []),
        "quest_id": session.get("quest_id"),
    }


def _people_at(sim, node_id: str = "node:35") -> list[str]:
    out = []
    for pid, person in sorted((sim.state.people or {}).items()):
        if not person.get("alive", True):
            continue
        if str(person.get("node_id") or "") != node_id:
            continue
        out.append(pid)
    return out


def _assert_clean_text(text: str, *, allow_ridge: bool = False) -> None:
    low = text.lower()
    for phrase in RETIRED_PHRASES:
        if phrase == "ridge" and allow_ridge:
            continue
        assert phrase not in low, f"retired phrase {phrase!r} in {text!r}"


def test_production_catalog_scopes() -> None:
    catalog = LineCatalog.load()
    assert catalog.get("dialogue.boulder.offer") is not None
    assert catalog.get("dialogue.mara.offer") is None
    for line in catalog.lines.values():
        assert not line.get("aspect_id"), line.get("id")
        assert line.get("quest_id") != "quest.factory_shortage"
        scope = str(line.get("scope") or "normal")
        assert scope in {"normal", "rockfall", "soldier", ""}


def test_ordinary_talk_before_inspect_is_occupational() -> None:
    sim = _sim()
    helpers = set(eligible_boulder_helpers(sim.state, "node:35"))
    for pid in _people_at(sim):
        row = _talk(sim, pid, cid=f"pre-{pid}")
        _assert_clean_text(row["text"], allow_ridge=("Miner" in str((sim.state.people[pid] or {}).get("occupation"))))
        assert row["line_id"] in {
            "dialogue.person.ordinary",
            "dialogue.villager.baseline",
            "dialogue.leader.baseline",
            "dialogue.soldier.baseline",
            "dialogue.worker.baseline",
            "dialogue.neutral_fallback",
        } or row["quest_id"] in {None, ""}
        assert not any(c.get("id") == "ask_clear_rockfall" for c in row["choices"])
        if pid in helpers:
            ctx = person_talk_context(sim.state, pid)
            # Opening should mention work/settlement context, not Aspect prose.
            assert "aspect" not in row["text"].lower()
            assert ctx["occupation"]


def test_ask_occupation_is_truthful_and_does_not_clear() -> None:
    sim = _sim()
    reveal(sim.state, ROCKFALL_ID, KnowledgeFact(ROCKFALL_ID, "observed", role="rockfall"), role="rockfall")
    helper = eligible_boulder_helpers(sim.state, "node:35")[3]  # clay / non-factory
    talk = _cmd(sim, "Interact", {"action": "talk", "entity_id": helper}, cid="occ-talk")
    session = (talk.get("payload") or {}).get("session") or {}
    choices = (talk.get("payload") or {}).get("choices") or []
    assert any(c.get("id") == "ask_occupation" for c in choices)
    chosen = _cmd(
        sim,
        "Interact",
        {
            "action": "choose_dialogue",
            "session_id": session["id"],
            "choice_id": "ask_occupation",
        },
        cid="occ-choose",
    )
    text = str((chosen.get("payload") or {}).get("session", {}).get("text") or "")
    expected = occupation_answer_line(person_talk_context(sim.state, helper))
    assert text == expected
    assert get_rockfall(sim.state)["status"] == "blocking"
    assert sim.state.quests[QUEST_INSTANCE_ID].get("helper_person_id") in {None, ""}


def test_rockfall_option_only_after_inspect() -> None:
    sim = _sim()
    helper = eligible_boulder_helpers(sim.state, "node:35")[0]
    before = _talk(sim, helper, cid="before")
    assert not any(c.get("id") == "ask_clear_rockfall" for c in before["choices"])
    reveal(sim.state, ROCKFALL_ID, KnowledgeFact(ROCKFALL_ID, "observed", role="rockfall"), role="rockfall")
    after = _talk(sim, helper, cid="after")
    assert any(c.get("id") == "ask_clear_rockfall" for c in after["choices"])
    assert after["line_id"] == "dialogue.boulder.offer"


def test_dialogue_matrix_all_states(tmp_path=None) -> None:
    """Walk every Person through G05 dialogue states; write human matrix."""
    sim = _sim()
    people = _people_at(sim)
    helpers = set(eligible_boulder_helpers(sim.state, "node:35"))
    rows: list[dict] = []

    def snap(state_name: str) -> None:
        for pid in people:
            person = sim.state.people[pid]
            ctx = person_talk_context(sim.state, pid)
            talk = _talk(sim, pid, cid=f"{state_name}-{pid}")
            _assert_clean_text(
                talk["text"],
                allow_ridge=("Miner" in str(ctx.get("occupation")) or "ridge" in talk["text"].lower() and "Miner" in str(ctx.get("occupation"))),
            )
            assert "quest.factory_shortage" not in str(talk.get("quest_id") or "")
            assert not str(talk.get("line_id") or "").startswith("dialogue.aspect.")
            assert not str(talk.get("line_id") or "").startswith("dialogue.mara.")
            rows.append(
                {
                    "state": state_name,
                    "person_id": pid,
                    "occupation": ctx.get("occupation"),
                    "workplace": ctx.get("workplace_label"),
                    "activity": ctx.get("activity"),
                    "helper": pid in helpers,
                    "line_id": talk["line_id"],
                    "text": talk["text"],
                    "choices": [c.get("id") for c in talk["choices"]],
                }
            )

    snap("A_unseen")
    reveal(sim.state, ROCKFALL_ID, KnowledgeFact(ROCKFALL_ID, "observed", role="rockfall"), role="rockfall")
    snap("B_inspected")

    helper = sorted(helpers)[0]
    accept_move(sim.state, helper_person_id=helper)
    snap("C_clearing")

    complete_move(sim.state)
    # Mark completion ack so helper returns to ordinary after done once.
    quest = sim.state.quests[QUEST_INSTANCE_ID]
    # First talk after clear should be done for helper.
    done = _talk(sim, helper, cid="done-helper")
    assert "cleared" in done["text"].lower()
    quest["completion_ack"] = True
    snap("D_cleared")

    # Write matrix + audit for humans.
    lines = [
        "# G05 dialogue matrix — seed 507 / node:35",
        "",
        "Generated by `tests/sim/test_g05_dialogue_matrix.py`.",
        "",
    ]
    for state in ("A_unseen", "B_inspected", "C_clearing", "D_cleared"):
        lines.append(f"## {state}")
        lines.append("")
        for row in rows:
            if row["state"] != state:
                continue
            choices = ", ".join(str(c) for c in row["choices"]) or "(none)"
            lines.append(
                f"- **{row['person_id']}** — {row['occupation']} @ {row['workplace'] or '?'} "
                f"(activity={row['activity']}, helper={row['helper']})"
            )
            lines.append(f"  - `{row['line_id']}`: {row['text']}")
            lines.append(f"  - choices: {choices}")
        lines.append("")
    MATRIX_PATH.parent.mkdir(parents=True, exist_ok=True)
    MATRIX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    audit = [
        "# G05 starting village dialogue audit — node:35 / seed 507",
        "",
        "Authoritative Person roster with ordinary and Rockfall talk behaviour.",
        "",
    ]
    sim2 = _sim()
    reveal(sim2.state, ROCKFALL_ID, KnowledgeFact(ROCKFALL_ID, "observed", role="rockfall"), role="rockfall")
    helpers2 = set(eligible_boulder_helpers(sim2.state, "node:35"))
    for pid in _people_at(sim2):
        person = sim2.state.people[pid]
        ctx = person_talk_context(sim2.state, pid)
        # Reset-ish: talk before inspect on fresh? Use sim2 unseen by clearing knowledge mid-loop is hard;
        # record contexts from person_talk_context + scripted talks on dedicated sims.
        audit.append(f"## {pid}")
        audit.append("")
        audit.append(f"- display_name: {person.get('display_name') or person.get('name')}")
        audit.append(f"- role: {person.get('role')}")
        audit.append(f"- occupation: {ctx.get('occupation')}")
        audit.append(f"- workplace_id: {ctx.get('workplace_id')}")
        audit.append(f"- workplace: {ctx.get('workplace_label')} ({ctx.get('workplace_kind')})")
        audit.append(f"- activity: {ctx.get('activity')} / {ctx.get('activity_label')}")
        audit.append(f"- resource: {ctx.get('resource_label')}")
        audit.append(f"- eligible Rockfall helper: {pid in helpers2}")
        audit.append(f"- occupation answer: {occupation_answer_line(ctx)}")
        audit.append("")
    # Attach matrix summaries for normal / inspected from rows
    by_person = {}
    for row in rows:
        by_person.setdefault(row["person_id"], {})[row["state"]] = row
    for pid, states in by_person.items():
        audit.append(f"### Talk samples — {pid}")
        for key, label in (
            ("A_unseen", "normal Talk"),
            ("B_inspected", "post-inspect Talk"),
            ("C_clearing", "Rockfall-active Talk"),
            ("D_cleared", "Rockfall-completed Talk"),
        ):
            row = states.get(key)
            if not row:
                continue
            audit.append(f"- {label}: `{row['line_id']}` — {row['text']}")
            if row["choices"]:
                audit.append(f"  - choices: {', '.join(map(str, row['choices']))}")
        audit.append("")
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text("\n".join(audit) + "\n", encoding="utf-8")
    assert MATRIX_PATH.is_file()
    assert AUDIT_PATH.is_file()
