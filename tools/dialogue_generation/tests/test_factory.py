import json
from pathlib import Path
from unittest.mock import Mock, patch

from dialogue_generation.ollama_client import OllamaClient
from dialogue_generation.prompts import CLASSIFIER_SCHEMA, REVIEW_SCHEMA, WRITER_SCHEMA
from dialogue_generation.worldviews import load_worldviews


def test_worldview_source_is_complete():
    worldviews = load_worldviews(Path(__file__).parent.parent / "worldviews.json")
    assert set(worldviews.by_code) == {"M", "A", "R", "G", "S", "D", "C"}
    assert len(worldviews.worldviews) == 7
    assert "Rule by a gifted caste" in worldviews.by_code["S"].shadow
    assert worldviews.by_code["M"].delta["M"] == 3


def test_structured_schemas_present():
    assert "best_match" in CLASSIFIER_SCHEMA["properties"]
    assert WRITER_SCHEMA["properties"]["responses"]["minItems"] == 7
    assert "approved" in REVIEW_SCHEMA["properties"]


def test_model_ready_recognises_tagged_model():
    client = OllamaClient()
    with patch("urllib.request.urlopen") as mock:
        payload = {"models": [{"name": "mistral:latest"}]}
        mock.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        assert client.model_ready("mistral").success


def test_generate_json_parses_outer_and_model_json():
    client = OllamaClient()
    with patch("urllib.request.urlopen") as mock:
        outer = {"response": json.dumps({"ok": True})}
        mock.return_value.__enter__.return_value.read.return_value = json.dumps(outer).encode()
        result = client.generate_json("test")
        assert result.success
        assert result.data == {"ok": True}
