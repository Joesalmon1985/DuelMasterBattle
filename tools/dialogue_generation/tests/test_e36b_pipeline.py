import json
from pathlib import Path
from unittest.mock import patch

import openpyxl
import pytest

from dialogue_generation.config import config
from dialogue_generation.database import DialogueDatabase
from dialogue_generation.exporter import export_cast
from dialogue_generation.ollama_client import OllamaClient, OllamaResponse
from dialogue_generation.pipeline import ingest_cast
from dialogue_generation.validator import enrich_exchange, validate_exchange
from dialogue_generation.workbook_reader import EXPECTED_HEADERS, extract_beats, read_cast_rows
from dialogue_generation.worldviews import load_worldviews


def make_workbook(path: Path, rows: int = 12):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Dialogue Matrix"
    ws.append(EXPECTED_HEADERS)
    for i in range(rows):
        choice = i < 3
        tragic = "(Dead in this tragic branch — no post-tragedy dialogue.)" if i == rows - 1 else f"Tragic ending {i}"
        ws.append([
            "E36B", f"Soap {i}", "broken promise", f"NPC {i}", f"Role {i}", f"Story {i}",
            f"Personality {i}", "available", f"Trigger {i}", f"Opening {i}",
            "Yes" if choice else "No", i + 1 if choice else None,
            f"Choice prompt {i}" if choice else "", f"Option A {i}" if choice else "",
            f"Response A {i}" if choice else "", f"Option B {i}" if choice else "",
            f"Response B {i}" if choice else "", f"State A {i}" if choice else "",
            f"State B {i}" if choice else "", f"Normal ending {i}", tragic,
        ])
    wb.save(path)


def test_real_schema_creates_from_empty_database(tmp_path):
    db_path = tmp_path / "new.db"
    with DialogueDatabase(db_path) as db:
        tables = {r[0] for r in db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"source_rows", "beats", "beat_instances", "dialogue_banks", "bank_memberships", "generations"} <= tables
    assert db_path.exists()


def test_e36b_extracts_41_beats_and_stable_ids(tmp_path):
    workbook = tmp_path / "fixture.xlsx"
    make_workbook(workbook)
    rows1 = read_cast_rows(workbook, "E36B")
    beats1 = extract_beats(rows1)
    rows2 = read_cast_rows(workbook, "E36B")
    beats2 = extract_beats(rows2)
    assert len(rows1) == 12
    assert len(beats1) == 41
    assert [b.instance_id for b in beats1] == [b.instance_id for b in beats2]
    assert [b.beat_id for b in beats1] == [b.beat_id for b in beats2]
    assert sum(1 for b in beats1 if b.consequential) == 3


def test_header_mismatch_fails_loudly(tmp_path):
    path = tmp_path / "bad.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Dialogue Matrix"
    ws.append(["Wrong"] + EXPECTED_HEADERS[1:])
    wb.save(path)
    with pytest.raises(ValueError, match="schema mismatch"):
        read_cast_rows(path, "E36B")


def test_ingest_is_idempotent(tmp_path):
    workbook = tmp_path / "fixture.xlsx"
    make_workbook(workbook)
    db_path = tmp_path / "dialogue.db"
    with DialogueDatabase(db_path) as db:
        first = ingest_cast(db, workbook, "E36B")
        second = ingest_cast(db, workbook, "E36B")
        assert first["source_rows"] == second["source_rows"] == 12
        assert first["beat_instances"] == second["beat_instances"] == 41
        assert first["unique_beats"] == second["unique_beats"]
        assert db.conn.execute("SELECT COUNT(*) FROM source_rows").fetchone()[0] == 12
        assert db.conn.execute("SELECT COUNT(*) FROM beat_instances").fetchone()[0] == 41


def test_ollama_payload_places_keep_alive_and_schema_correctly():
    client = OllamaClient(model="custom-model")
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    payload = client.build_generate_payload("x", system="s", temperature=0.2, num_predict=123, format_schema=schema)
    assert payload["model"] == "custom-model"
    assert payload["stream"] is False
    assert payload["keep_alive"] == client.keep_alive
    assert "keep_alive" not in payload["options"]
    assert payload["options"]["num_ctx"] == client.num_ctx
    assert payload["options"]["num_predict"] == 123
    assert payload["format"] == schema


def test_malformed_model_json_is_retryable(monkeypatch):
    client = OllamaClient()
    responses = [
        OllamaResponse(False, error="bad json", error_type="model_json"),
        OllamaResponse(True, data={"ok": True}),
    ]
    monkeypatch.setattr(client, "generate_json", lambda *a, **kw: responses.pop(0))
    monkeypatch.setattr("dialogue_generation.ollama_client.time.sleep", lambda *_: None)
    result = client.generate_with_retry("x", max_attempts=3)
    assert result.success
    assert result.data == {"ok": True}
    assert result.attempts == 2


def _valid_exchange(consequential=True):
    keys = ["monarchist", "anarchist", "religious", "guildist", "arcane", "druidic", "cracked"]
    responses = []
    john_lines = [
        "The reeve has authority here, but that authority obliges him to protect those under his roof.",
        "No one gets to own another person's choice; ask what help they want and act beside them.",
        "A sworn promise has moral weight, but mercy for the vulnerable must guide how we keep it.",
        "Put the terms plainly before everyone and settle what each side actually owes before trading another favour.",
        "Let the person who understands the danger best take charge, and judge the rest by what they can actually do.",
        "Stop forcing the matter; find the course that restores balance without making tomorrow's wound worse.",
        "This feels like a choice laid out for us before we arrived; perhaps the pattern matters as much as the promise.",
    ]
    npc_lines = [
        "You speak as though rank should bind the powerful too; I had not expected that.",
        "That would leave the choice with them, which is more freedom than anyone else has offered.",
        "If mercy can live beside an oath, perhaps I can still face the shrine tomorrow.",
        "Written terms would make it harder for either side to pretend the bargain meant something else.",
        "You make competence sound colder than kindness, but I cannot deny the danger is real.",
        "Perhaps mending what was disturbed matters more than proving which of us was right.",
        "I do not know what pattern you see, but you have made me notice how neatly this trap has closed.",
    ]
    for i, key in enumerate(keys):
        responses.append({
            "worldview": key,
            "context_fit": 5 - (i % 4),
            "conviction_tier": 2,
            "branch": ("A" if i < 4 else "B") if consequential else None,
            "john": john_lines[i],
            "npc_reaction": npc_lines[i],
        })
    return {"bank_id": "BANK_X", "responses": responses}


def test_validator_enforces_seven_and_branch_coverage():
    w = load_worldviews(Path(__file__).parent.parent / "worldviews.json")
    context = {"bank": {"consequential": 1}, "instances": []}
    good = enrich_exchange(_valid_exchange(True), w, "BANK_X")
    assert validate_exchange(good, context, w) == []
    bad = json.loads(json.dumps(good))
    for r in bad["responses"]:
        r["branch"] = "A"
    issues = validate_exchange(bad, context, w)
    assert any(i["category"] == "branch" for i in issues)


def test_export_requires_every_bank_approved(tmp_path):
    workbook = tmp_path / "fixture.xlsx"
    make_workbook(workbook, rows=1)
    db_path = tmp_path / "dialogue.db"
    with DialogueDatabase(db_path) as db:
        ingest_cast(db, workbook, "E36B")
        beat = db.unbanked_beats("E36B")[0]
        db.create_bank("BANK_TEST", beat["beat_id"])
        with pytest.raises(RuntimeError, match="not approved"):
            export_cast(db, "E36B", tmp_path / "out")

class FakeClient:
    model = "mistral"

    def generate_with_retry(self, prompt, **kwargs):
        schema = kwargs.get("format_schema") or {}
        props = schema.get("properties", {})
        if "responses" in props:
            low = prompt.lower()
            consequential = ('"consequential": true' in low) or ('"consequential": 1' in low)
            keys = ["monarchist", "anarchist", "religious", "guildist", "arcane", "druidic", "cracked"]
            lines = [
                "Authority must answer for the promise as surely as the subject does.",
                "No one should be forced to carry a promise they never freely chose.",
                "Keep faith where you can, but not by abandoning mercy for the vulnerable.",
                "Set the obligation down plainly and settle what each side actually owes.",
                "Put the decision in the hands of whoever can best control the danger.",
                "Choose the course that restores balance instead of feeding the quarrel.",
                "Funny how every path seems to fork exactly when someone asks us to choose.",
            ]
            reactions = [
                "Then perhaps rank is a burden as well as a privilege.",
                "That is the first answer that leaves the choice in our hands.",
                "I can accept an oath that still leaves room for mercy.",
                "A clear account would end half the lies around this bargain.",
                "Cold words, but I cannot deny that skill matters here.",
                "Mending the harm may matter more than winning the argument.",
                "I wish I knew what pattern you keep seeing in all this.",
            ]
            responses = []
            for i, key in enumerate(keys):
                responses.append({
                    "worldview": key,
                    "context_fit": 4,
                    "conviction_tier": 2,
                    "branch": ("A" if i < 4 else "B") if consequential else None,
                    "john": lines[i],
                    "npc_reaction": reactions[i],
                })
            return OllamaResponse(True, data={"bank_id": "ignored", "responses": responses})
        if "approved" in props:
            return OllamaResponse(True, data={"approved": True, "issues": [], "summary": "Approved"})
        if "best_match" in props:
            return OllamaResponse(True, data={"best_match": None, "confidence": 0.99, "can_share_dialogue": False, "reason": "Keep separate"})
        return OllamaResponse(False, error="Unexpected fake schema", error_type="model")


def test_fake_end_to_end_generation_and_export(tmp_path):
    from dialogue_generation.pipeline import generate_cast

    workbook = tmp_path / "fixture.xlsx"
    make_workbook(workbook, rows=1)
    db_path = tmp_path / "dialogue.db"
    out = tmp_path / "out"
    with DialogueDatabase(db_path) as db:
        ingest_cast(db, workbook, "E36B")
        result = generate_cast(db, "E36B", FakeClient(), load_worldviews(Path(__file__).parent.parent / "worldviews.json"))
        assert result["needs_review"] == 0
        assert result["approved"] == result["banks"]
        exported = export_cast(db, "E36B", out)
        payload = json.loads(Path(exported["json"]).read_text(encoding="utf-8"))
        assert payload["cast_id"] == "E36B"
        assert payload["bank_count"] == result["banks"]
        assert all(len(bank["responses"]) == 7 for bank in payload["banks"])
        decision_banks = [b for b in payload["banks"] if b["consequential"]]
        assert decision_banks
        for bank in decision_banks:
            assert {r["branch"] for r in bank["responses"]} == {"A", "B"}


def test_canonical_workbook_e36b_shape_if_present():
    repo_root = Path(__file__).resolve().parents[3]
    workbook = repo_root / "docs" / "Duel_Master_Battle_Village_Cast_Matrix_Dialogue_COMPLETE_112_FANTASY_STORY_AUDITED.xlsx"
    if not workbook.exists():
        pytest.skip("Canonical workbook not present in this test checkout")
    rows = read_cast_rows(workbook, "E36B")
    beats = extract_beats(rows)
    assert len(rows) == 12
    assert len(beats) == 41
    assert sum(1 for b in beats if b.consequential) == 3
