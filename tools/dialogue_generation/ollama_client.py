"""
Ollama client for structured JSON generation.

Implements the proven pattern from Glen's Game (puca_dungeon/narrate.py):
- HTTP POST to /api/generate with stream=false, format=json
- Configurable model, context size, timeout
- Proper error handling distinguishing network failures from malformed output
"""
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional
from urllib import request, error

from .config import config

logger = logging.getLogger(__name__)


@dataclass
class OllamaResponse:
    """Structured response from Ollama."""
    success: bool
    data: Optional[dict] = None
    raw_response: Optional[str] = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # 'network', 'model', 'json_parse', 'timeout'


class OllamaClient:
    """Reusable Ollama client for JSON-mode generation."""

    def __init__(self, cfg: Optional[Any] = None):
        self.cfg = cfg or config.ollama
        self.base_url = self.cfg.host.rstrip("/")
        self.model = self.cfg.model
        self.timeout = self.cfg.timeout_seconds
        self.num_ctx = self.cfg.num_ctx
        self.keep_alive = self.cfg.keep_alive

    def _post(self, endpoint: str, payload: dict) -> OllamaResponse:
        """Send POST request to Ollama API."""
        url = f"{self.base_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        req = request.Request(url, data=data, headers=headers, method="POST")

        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return OllamaResponse(success=True, raw_response=raw)
        except error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            logger.error(f"Ollama HTTP {e.code}: {body}")
            return OllamaResponse(
                success=False,
                error=f"HTTP {e.code}: {body}",
                error_type="network"
            )
        except error.URLError as e:
            logger.error(f"Ollama connection error: {e}")
            return OllamaResponse(
                success=False,
                error=f"Connection failed: {e}",
                error_type="network"
            )
        except TimeoutError:
            logger.error(f"Ollama timeout after {self.timeout}s")
            return OllamaResponse(
                success=False,
                error=f"Timeout after {self.timeout}s",
                error_type="timeout"
            )
        except Exception as e:
            logger.exception("Unexpected Ollama error")
            return OllamaResponse(
                success=False,
                error=f"Unexpected error: {e}",
                error_type="unknown"
            )

    def _get(self, endpoint: str) -> OllamaResponse:
        """Send GET request to Ollama API."""
        url = f"{self.base_url}{endpoint}"

        req = request.Request(url, method="GET")

        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return OllamaResponse(success=True, raw_response=raw)
        except error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            logger.error(f"Ollama HTTP {e.code}: {body}")
            return OllamaResponse(
                success=False,
                error=f"HTTP {e.code}: {body}",
                error_type="network"
            )
        except error.URLError as e:
            logger.error(f"Ollama connection error: {e}")
            return OllamaResponse(
                success=False,
                error=f"Connection failed: {e}",
                error_type="network"
            )
        except TimeoutError:
            logger.error(f"Ollama timeout after {self.timeout}s")
            return OllamaResponse(
                success=False,
                error=f"Timeout after {self.timeout}s",
                error_type="timeout"
            )
        except Exception as e:
            logger.exception("Unexpected Ollama error")
            return OllamaResponse(
                success=False,
                error=f"Unexpected error: {e}",
                error_type="unknown"
            )

    def check_service(self) -> OllamaResponse:
        """Check if Ollama service is reachable."""
        return self._get("/api/tags")

    def list_models(self) -> OllamaResponse:
        """List available models."""
        resp = self.check_service()
        if not resp.success:
            return resp
        try:
            data = json.loads(resp.raw_response)
            return OllamaResponse(success=True, data=data)
        except json.JSONDecodeError as e:
            return OllamaResponse(
                success=False,
                error=f"Failed to parse model list: {e}",
                error_type="json_parse"
            )

    def model_ready(self, model_name: Optional[str] = None) -> OllamaResponse:
        """Check if a specific model is available."""
        model = model_name or self.model
        resp = self.list_models()
        if not resp.success:
            return resp
        models = resp.data.get("models", [])
        for m in models:
            if m.get("name", "").startswith(model):
                return OllamaResponse(success=True, data={"model": m})
        return OllamaResponse(
            success=False,
            error=f"Model '{model}' not found. Available: {[m.get('name') for m in models]}",
            error_type="model"
        )

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        format_schema: Optional[dict] = None,
        model: Optional[str] = None,
    ) -> OllamaResponse:
        """
        Generate structured JSON from Mistral.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            temperature: Generation temperature (default from config)
            format_schema: JSON schema for structured output (optional)
            model: Override model name (optional)

        Returns:
            OllamaResponse with parsed JSON in data field if successful
        """
        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "num_ctx": self.num_ctx,
                "keep_alive": self.keep_alive,
                "temperature": temperature if temperature is not None else self.cfg.temp_writer,
            }
        }

        if system:
            payload["system"] = system

        # For JSON schema enforcement, we rely on the model following the format instruction
        # in the prompt. Ollama's native JSON schema support is limited.

        resp = self._post("/api/generate", payload)
        if not resp.success:
            return resp

        # Parse outer Ollama response
        try:
            outer = json.loads(resp.raw_response)
        except json.JSONDecodeError as e:
            return OllamaResponse(
                success=False,
                error=f"Failed to parse Ollama response: {e}",
                error_type="json_parse",
                raw_response=resp.raw_response
            )

        # Extract model's response field
        model_response = outer.get("response", "")
        if not model_response:
            return OllamaResponse(
                success=False,
                error="Empty response from model",
                error_type="model",
                raw_response=resp.raw_response
            )

        # Parse model's JSON response
        try:
            parsed = json.loads(model_response)
            return OllamaResponse(success=True, data=parsed, raw_response=resp.raw_response)
        except json.JSONDecodeError as e:
            logger.warning(f"Model returned invalid JSON: {model_response[:200]}...")
            return OllamaResponse(
                success=False,
                error=f"Model returned invalid JSON: {e}",
                error_type="json_parse",
                raw_response=resp.raw_response
            )

    def generate_text(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> OllamaResponse:
        """Generate plain text (non-JSON) from Mistral."""
        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": self.num_ctx,
                "keep_alive": self.keep_alive,
                "temperature": temperature if temperature is not None else self.cfg.temp_writer,
            }
        }

        if system:
            payload["system"] = system

        resp = self._post("/api/generate", payload)
        if not resp.success:
            return resp

        try:
            outer = json.loads(resp.raw_response)
            text = outer.get("response", "")
            return OllamaResponse(success=True, data={"text": text}, raw_response=resp.raw_response)
        except json.JSONDecodeError as e:
            return OllamaResponse(
                success=False,
                error=f"Failed to parse Ollama response: {e}",
                error_type="json_parse",
                raw_response=resp.raw_response
            )

    def generate_with_retry(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_attempts: Optional[int] = None,
        **kwargs
    ) -> OllamaResponse:
        """Generate JSON with retry logic for transient failures."""
        attempts = max_attempts or self.cfg.max_attempts
        last_error = None

        for attempt in range(1, attempts + 1):
            resp = self.generate_json(prompt, system, temperature, **kwargs)
            if resp.success:
                if attempt > 1:
                    logger.info(f"Succeeded on attempt {attempt}/{attempts}")
                return resp

            last_error = resp.error
            logger.warning(f"Attempt {attempt}/{attempts} failed: {resp.error} (type: {resp.error_type})")

            # Don't retry on model errors (model not found, etc.) or JSON parse errors from model
            if resp.error_type in ("model", "json_parse"):
                break

            if attempt < attempts:
                time.sleep(2 * attempt)  # Exponential backoff

        return OllamaResponse(
            success=False,
            error=f"Failed after {attempts} attempts. Last error: {last_error}",
            error_type="retry_exhausted"
        )