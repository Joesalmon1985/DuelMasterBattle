"""
Unit tests for the Dialogue Generation Factory.

Tests are designed to run WITHOUT a live Ollama service by mocking the network layer.
"""
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add the package to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dialogue_generation.ollama_client import OllamaClient, OllamaResponse


class TestOllamaClient:
    """Tests for OllamaClient with mocked HTTP."""

    @pytest.fixture
    def client(self):
        return OllamaClient()

    @pytest.fixture
    def mock_success_response(self):
        """Mock a successful Ollama response."""
        with patch("urllib.request.urlopen") as mock:
            outer = {"response": json.dumps({"test": "ok", "number": 42})}
            mock.return_value.__enter__.return_value.read.return_value = json.dumps(outer).encode()
            yield mock

    @pytest.fixture
    def mock_http_error(self):
        """Mock an HTTP error from Ollama."""
        from urllib import error
        with patch("urllib.request.urlopen") as mock:
            err = error.HTTPError("http://test", 500, "Internal Server Error", {}, None)
            mock.side_effect = err
            yield mock

    @pytest.fixture
    def mock_connection_error(self):
        """Mock a connection error."""
        from urllib import error
        with patch("urllib.request.urlopen") as mock:
            mock.side_effect = error.URLError("Connection refused")
            yield mock

    def test_check_service_success(self, client, mock_success_response):
        """check_service returns success when Ollama responds."""
        resp = client.check_service()
        assert resp.success is True

    def test_check_service_network_failure(self, client, mock_connection_error):
        """check_service returns network error on connection failure."""
        resp = client.check_service()
        assert resp.success is False
        assert resp.error_type == "network"

    def test_model_ready_found(self, client):
        """model_ready succeeds when model is in list."""
        with patch("urllib.request.urlopen") as mock:
            data = {"models": [{"name": "mistral:latest", "size": 12345}]}
            mock.return_value.__enter__.return_value.read.return_value = json.dumps(data).encode()
            resp = client.model_ready("mistral")
            assert resp.success is True
            assert resp.data["model"]["name"] == "mistral:latest"

    def test_model_ready_not_found(self, client):
        """model_ready fails when model not in list."""
        with patch("urllib.request.urlopen") as mock:
            data = {"models": [{"name": "llama2:latest", "size": 12345}]}
            mock.return_value.__enter__.return_value.read.return_value = json.dumps(data).encode()
            resp = client.model_ready("mistral")
            assert resp.success is False
            assert resp.error_type == "model"

    def test_generate_json_success(self, client, mock_success_response):
        """generate_json parses valid JSON response."""
        resp = client.generate_json("test prompt", temperature=0.1)
        assert resp.success is True
        assert resp.data == {"test": "ok", "number": 42}

    def test_generate_json_model_returns_invalid_json(self, client):
        """generate_json fails when model returns invalid JSON."""
        with patch("urllib.request.urlopen") as mock:
            outer = {"response": "this is not valid json"}
            mock.return_value.__enter__.return_value.read.return_value = json.dumps(outer).encode()
            resp = client.generate_json("test prompt", temperature=0.1)
            assert resp.success is False
            assert resp.error_type == "json_parse"

    def test_generate_json_ollama_returns_http_error(self, client, mock_http_error):
        """generate_json fails gracefully on HTTP error."""
        resp = client.generate_json("test prompt", temperature=0.1)
        assert resp.success is False
        assert resp.error_type == "network"

    def test_generate_text_success(self, client):
        """generate_text extracts plain text response."""
        with patch("urllib.request.urlopen") as mock:
            outer = {"response": "Hello, world!"}
            mock.return_value.__enter__.return_value.read.return_value = json.dumps(outer).encode()
            resp = client.generate_text("test prompt", temperature=0.1)
            assert resp.success is True
            assert resp.data["text"] == "Hello, world!"

    def test_retry_exhausted(self, client):
        """generate_with_retry fails after max attempts."""
        with patch("urllib.request.urlopen") as mock:
            from urllib import error
            mock.side_effect = error.URLError("Connection refused")
            resp = client.generate_with_retry("test", max_attempts=2)
            assert resp.success is False
            assert resp.error_type == "retry_exhausted"

    def test_retry_succeeds_on_second_attempt(self, client):
        """generate_with_retry succeeds after transient failure."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                from urllib import error
                raise error.URLError("Transient")
            outer = {"response": json.dumps({"result": "ok"})}
            mock_resp = Mock()
            mock_resp.__enter__ = Mock(return_value=Mock(read=lambda: json.dumps(outer).encode()))
            mock_resp.__exit__ = Mock(return_value=False)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=side_effect) as mock:
            resp = client.generate_with_retry("test", max_attempts=3)
            assert resp.success is True
            assert resp.data == {"result": "ok"}
            assert call_count[0] == 2


class TestConfig:
    """Tests for configuration."""

    def test_default_config(self):
        """Default config has expected values."""
        from dialogue_generation.config import config
        assert config.ollama.host == "http://127.0.0.1:11434"
        assert config.ollama.model == "mistral"
        assert config.ollama.temp_classifier == 0.1
        assert config.ollama.temp_writer == 0.45
        assert len(config.worldview.codes) == 7
        assert "M" in config.worldview.codes
        assert "C" in config.worldview.codes

    def test_worldview_mappings(self):
        """Worldview code/key mappings are consistent."""
        from dialogue_generation.config import config
        wv = config.worldview
        assert wv.code_to_key["M"] == "monarchist"
        assert wv.key_to_code["anarchist"] == "A"
        assert set(wv.codes) == set(wv.code_to_name.keys())


class TestPrompts:
    """Tests for prompt templates."""

    def test_classify_bank_prompts_exist(self):
        """CLASSIFY_BANK prompts are defined."""
        from dialogue_generation.prompts import CLASSIFY_BANK_SYSTEM, CLASSIFY_BANK_USER
        assert "JSON" in CLASSIFY_BANK_SYSTEM
        assert "best_match" in CLASSIFY_BANK_SYSTEM
        assert "{source_text}" in CLASSIFY_BANK_USER

    def test_write_exchange_prompts_exist(self):
        """WRITE_EXCHANGE prompts are defined."""
        from dialogue_generation.prompts import WRITE_EXCHANGE_SYSTEM, WRITE_EXCHANGE_USER
        assert "seven worldview" in WRITE_EXCHANGE_SYSTEM.lower()
        assert "bank_id" in WRITE_EXCHANGE_SYSTEM
        assert "{bank_id}" in WRITE_EXCHANGE_USER

    def test_review_exchange_prompts_exist(self):
        """REVIEW_EXCHANGE prompts are defined."""
        from dialogue_generation.prompts import REVIEW_EXCHANGE_SYSTEM, REVIEW_EXCHANGE_USER
        assert "approved" in REVIEW_EXCHANGE_SYSTEM
        assert "issues" in REVIEW_EXCHANGE_SYSTEM
        assert "{exchange_json}" in REVIEW_EXCHANGE_USER


if __name__ == "__main__":
    pytest.main([__file__, "-v"])