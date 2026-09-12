"""OpenAI provider — Chat Completions via REST (no SDK dependency)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..config import CONFIG
from ..errors import ProviderError, ProviderTimeout
from .base_provider import AIProvider


class OpenAIProvider(AIProvider):
    name = "openai"
    priority = 10

    def _available(self) -> bool:
        return bool(CONFIG.OPENAI_API_KEY)

    def _ask_once(self, prompt: str) -> str:
        payload = {
            "model": CONFIG.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content":
                    "You are a factual intelligence source for ROLEX AI. "
                    "Give accurate, concise, well-structured answers. "
                    "If unsure, say so plainly."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{CONFIG.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {CONFIG.OPENAI_API_KEY}",
            },
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ProviderError(f"openai HTTP {e.code}") from e
        except urllib.error.URLError as e:
            if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                raise ProviderTimeout(f"openai {self.timeout}s") from e
            raise ProviderError(f"openai unreachable: {e.reason}") from e
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"openai bad response shape: {e}") from e
