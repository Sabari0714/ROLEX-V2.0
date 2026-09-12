"""Gemini provider — generateContent REST API."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..config import CONFIG
from ..errors import ProviderError, ProviderTimeout
from .base_provider import AIProvider


class GeminiProvider(AIProvider):
    name = "gemini"
    priority = 20

    def _available(self) -> bool:
        return bool(CONFIG.GEMINI_API_KEY)

    def _ask_once(self, prompt: str) -> str:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3},
            "systemInstruction": {"parts": [{"text":
                "You are a factual intelligence source for ROLEX AI. "
                "Give accurate, concise answers. If unsure, say so."}]},
        }
        data = json.dumps(payload).encode("utf-8")
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{CONFIG.GEMINI_MODEL}:generateContent"
               f"?key={CONFIG.GEMINI_API_KEY}")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ProviderError(f"gemini HTTP {e.code}") from e
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                raise ProviderTimeout(f"gemini {self.timeout}s") from e
            raise ProviderError(f"gemini unreachable: {e.reason}") from e
        try:
            return body["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"gemini bad response shape: {e}") from e
