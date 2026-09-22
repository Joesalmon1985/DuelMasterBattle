"""T084 offline dialogue catalogue and runtime selection."""

from __future__ import annotations

from pathlib import Path

from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.narrative.dialogue import DialogueResolver
from sim.dmb.narrative.knowledge import KnowledgeFact, reveal
from sim.dmb.narrative.line_catalog import LineCatalog
from sim.dmb.people.registry import PeopleService

_ARCHIVE = (
    Path(__file__).resolve().parents[2]
    / "godot_project"
    / "content"
    / "source"
    / "dialogue"
)


def _world(*, include_archive: bool = False) -> tuple[WorldState, str, DialogueResolver]:
    state = WorldState(world_id=WorldId("world:t084"), ids=IdAllocator(WorldId("world:t084")))
    people = PeopleService(state)
    person = people.create_person(name="MaraSecret", role="worker", node_id="node:v")
    catalog = LineCatalog.load(_ARCHIVE, include_archive=include_archive)
    resolver = DialogueResolver(state, catalog)
    return state, person["id"], resolver


def test_missing_variable_uses_truthful_fallback() -> None:
    state, pid, resolver = _world(include_archive=True)
    named = resolver.catalog.get("dialogue.mara.named")
    assert named is not None
    text = resolver._render(named, speaker_id=pid)
    assert text == "They introduce themselves carefully."
    assert "MaraSecret" not in text


def test_unknown_name_cannot_leak() -> None:
    state, pid, resolver = _world(include_archive=True)
    session = resolver.start(
        speaker_id=pid,
        quest_id="quest.factory_shortage",
        stage=0,
        cause_id="cause.factory_shortage",
    )
    assert "MaraSecret" not in session["text"]
    reveal(state, pid, KnowledgeFact(pid, "met", role="worker"), role="worker")
    state.knowledge[pid]["name"] = "Mara"
    text = resolver._render(resolver.catalog.get("dialogue.mara.named"), speaker_id=pid)
    assert text == "I am Mara."
    assert "MaraSecret" not in text


def test_wrong_era_and_cause_rejected() -> None:
    _state, pid, resolver = _world(include_archive=True)
    line = resolver._select_line(
        speaker_id=pid,
        speaker_role="worker",
        quest_id="quest.factory_shortage",
        stage=1,
        cause_id="cause.factory_shortage",
        era_id="ancient",
    )
    assert line["id"] == "dialogue.mara.demon_hint"
    ids = {c["id"] for c in resolver.catalog.candidates(era_id="ancient", speaker_role="worker", allow_archived=True)}
    assert "dialogue.wrong_era" not in ids


def test_production_catalog_excludes_aspect_and_shortage() -> None:
    catalog = LineCatalog.load()
    assert "dialogue.mara.offer" not in catalog.lines
    assert not any(line.get("aspect_id") for line in catalog.lines.values())
    assert "dialogue.boulder.offer" in catalog.lines


def test_aspect_lines_rejected_without_aspect_context() -> None:
    state, pid, resolver = _world(include_archive=True)
    # Force only aspect candidates by stripping ordinary procedural win:
    line = resolver._select_line(
        speaker_id=pid,
        speaker_role="worker",
        quest_id=None,
        stage=None,
        cause_id=None,
        era_id="ancient",
        aspect_id=None,
    )
    assert not line.get("aspect_id")
    assert "reason" not in str(line.get("text") or "").lower() or line["id"] == "dialogue.person.ordinary"


def test_runtime_has_zero_llm_network_imports() -> None:
    import sim.dmb.narrative.dialogue as dialogue_mod
    import sim.dmb.narrative.line_catalog as catalog_mod

    forbidden = {"openai", "httpx", "requests", "urllib", "aiohttp", "anthropic"}
    for mod in (dialogue_mod, catalog_mod):
        imported = set(mod.__dict__.keys())
        assert forbidden.isdisjoint(imported)
        src = open(mod.__file__, encoding="utf-8").read()
        for name in forbidden:
            assert f"import {name}" not in src
