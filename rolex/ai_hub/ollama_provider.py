"""Ollama provider — local models, zero cloud dependency."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..config import CONFIG
from ..errors import ProviderError, ProviderTimeout
from .base_provider import AIProvider


class OllamaProvider(AIProvider):
    name = "ollama"
    priority = 30

    def _available(self) -> bool:
        return bool(CONFIG.OLLAMA_BASE_URL)

    def check_server(self) -> bool:
        """Is the local Ollama server up? (health check)"""
        try:
            with urllib.request.urlopen(
                    f"{CONFIG.OLLAMA_BASE_URL.rstrip('/')}/api/tags",
                    timeout=5) as resp:
                return resp.status == 200
        except Exception:  # noqa: BLE001
            return False

    def _ask_once(self, prompt: str) -> str:
        payload = {
            "model": CONFIG.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{CONFIG.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
            data=data, headers={"Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ProviderError(f"ollama HTTP {e.code}") from e
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                raise ProviderTimeout(f"ollama {self.timeout}s") from e
            raise ProviderError(f"ollama unreachable: {e.reason}") from e
        try:
            return body["response"]
        except (KeyError, TypeError) as e:
            raise ProviderError(f"ollama bad response shape: {e}") from e
