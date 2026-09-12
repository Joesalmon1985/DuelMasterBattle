from __future__ import annotations

import json
import logging
import socket
import time
from dataclasses import dataclass
from typing import Any, Optional
from urllib import error, request

from .config import config

logger = logging.getLogger(__name__)


@dataclass
class OllamaResponse:
    success: bool
    data: Optional[dict] = None
    raw_response: Optional[str] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    attempts: int = 1


class OllamaClient:
    def __init__(self, cfg: Optional[Any] = None, model: Optional[str] = None):
        self.cfg = cfg or config.ollama
        self.base_url = self.cfg.host.rstrip("/")
        self.model = model or self.cfg.model
        self.timeout = self.cfg.timeout_seconds
        self.num_ctx = self.cfg.num_ctx
        self.keep_alive = self.cfg.keep_alive

    def _request(self, req: request.Request) -> OllamaResponse:
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return OllamaResponse(True, raw_response=resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = str(exc)
            return OllamaResponse(False, error=f"HTTP {exc.code}: {body}", error_type="network")
        except (error.URLError, ConnectionError) as exc:
            return OllamaResponse(False, error=f"Connection failed: {exc}", error_type="network")
        except (TimeoutError, socket.timeout) as exc:
            return OllamaResponse(False, error=f"Timeout after {self.timeout}s: {exc}", error_type="timeout")
        except Exception as exc:
            logger.exception("Unexpected Ollama error")
            return OllamaResponse(False, error=f"Unexpected error: {exc}", error_type="unknown")

    def _get(self, endpoint: str) -> OllamaResponse:
        return self._request(request.Request(f"{self.base_url}{endpoint}", method="GET"))

    def _post(self, endpoint: str, payload: dict) -> OllamaResponse:
        req = request.Request(
            f"{self.base_url}{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._request(req)

    def check_service(self) -> OllamaResponse:
        return self._get("/api/tags")

    def list_models(self) -> OllamaResponse:
        resp = self.check_service()
        if not resp.success:
            return resp
        try:
            return OllamaResponse(True, data=json.loads(resp.raw_response or ""), raw_response=resp.raw_response)
        except json.JSONDecodeError as exc:
            return OllamaResponse(False, error=f"Malformed /api/tags response: {exc}", error_type="api_parse",
                                  raw_response=resp.raw_response)

    def model_ready(self, model_name: Optional[str] = None) -> OllamaResponse:
        model = model_name or self.model
        resp = self.list_models()
        if not resp.success:
            return resp
        models = resp.data.get("models", []) if resp.data else []
        for item in models:
            name = str(item.get("name", ""))
            if name == model or name.startswith(model + ":"):
                return OllamaResponse(True, data={"model": item})
        return OllamaResponse(False, error=f"Model '{model}' not found; available: {[m.get('name') for m in models]}",
                              error_type="model")

    def build_generate_payload(self, prompt: str, *, system: Optional[str] = None,
                               temperature: Optional[float] = None, num_predict: Optional[int] = None,
                               format_schema: Optional[dict] = None, model: Optional[str] = None) -> dict:
        payload = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
            "format": format_schema if format_schema is not None else "json",
            "keep_alive": self.keep_alive,
            "options": {
                "num_ctx": self.num_ctx,
                "temperature": self.cfg.temp_writer if temperature is None else temperature,
                "num_predict": self.cfg.num_predict_writer if num_predict is None else num_predict,
            },
        }
        if system:
            payload["system"] = system
        return payload

    def generate_json(self, prompt: str, *, system: Optional[str] = None,
                      temperature: Optional[float] = None, num_predict: Optional[int] = None,
                      format_schema: Optional[dict] = None, model: Optional[str] = None) -> OllamaResponse:
        payload = self.build_generate_payload(
            prompt, system=system, temperature=temperature, num_predict=num_predict,
            format_schema=format_schema, model=model,
        )
        resp = self._post("/api/generate", payload)
        if not resp.success:
            return resp
        try:
            outer = json.loads(resp.raw_response or "")
        except json.JSONDecodeError as exc:
            return OllamaResponse(False, error=f"Malformed Ollama envelope: {exc}", error_type="api_parse",
                                  raw_response=resp.raw_response)
        model_response = outer.get("response")
        if not isinstance(model_response, str) or not model_response.strip():
            return OllamaResponse(False, error="Ollama returned an empty model response", error_type="model_json",
                                  raw_response=resp.raw_response)
        try:
            parsed = json.loads(model_response)
        except json.JSONDecodeError as exc:
            return OllamaResponse(False, error=f"Model returned malformed JSON: {exc}", error_type="model_json",
                                  raw_response=resp.raw_response)
        if not isinstance(parsed, dict):
            return OllamaResponse(False, error="Model JSON must be an object", error_type="model_json",
                                  raw_response=resp.raw_response)
        return OllamaResponse(True, data=parsed, raw_response=resp.raw_response)

    def generate_with_retry(self, prompt: str, *, system: Optional[str] = None,
                            temperature: Optional[float] = None, num_predict: Optional[int] = None,
                            format_schema: Optional[dict] = None, model: Optional[str] = None,
                            max_attempts: Optional[int] = None) -> OllamaResponse:
        attempts = max_attempts or self.cfg.max_attempts
        last: OllamaResponse | None = None
        retryable = {"network", "timeout", "api_parse", "model_json", "unknown"}
        for attempt in range(1, attempts + 1):
            resp = self.generate_json(
                prompt, system=system, temperature=temperature, num_predict=num_predict,
                format_schema=format_schema, model=model,
            )
            resp.attempts = attempt
            if resp.success:
                return resp
            last = resp
            if resp.error_type not in retryable or attempt >= attempts:
                break
            time.sleep(min(2 * attempt, 5))
        return OllamaResponse(
            False,
            error=f"Failed after {last.attempts if last else attempts} attempt(s): {last.error if last else 'unknown error'}",
            error_type="retry_exhausted" if last and last.error_type in retryable else (last.error_type if last else "unknown"),
            raw_response=last.raw_response if last else None,
            attempts=last.attempts if last else attempts,
        )
