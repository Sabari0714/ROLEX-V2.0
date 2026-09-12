"""Intelligence Hub — parallel calls, health, smart provider selection."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config import CONFIG
from ..logging_setup import get_logger
from .base_provider import AIProvider, ProviderResponse
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider

log = get_logger("ai.hub")


class IntelligenceHub:
    """Routes questions to intelligence SOURCES.
    Rolex — and only Rolex — owns the final answer (see answer_engine)."""

    def __init__(self, providers: list[AIProvider] | None = None,
                 max_workers: int = 4):
        if providers is None:
            providers = [OpenAIProvider(), GeminiProvider(),
                         OllamaProvider()]
        self.providers: list[AIProvider] = providers
        self.max_workers = max_workers

    # ------------------------------------------------------- single
    def pick(self) -> AIProvider | None:
        """Smart selection: available → priority → health → latency."""
        alive = [p for p in self.providers if p.available()]
        if not alive:
            return None
        alive.sort(key=lambda p: (p.priority, p.health.avg_latency_ms
                                  or 1e9, p.health.consecutive_failures))
        return alive[0]

    def ask_one(self, prompt: str) -> ProviderResponse:
        p = self.pick()
        if p is None:
            return ProviderResponse(ok=False, error="no provider available")
        return p.ask(prompt)

    # ------------------------------------------------------- parallel
    def ask_all(self, prompt: str) -> list[ProviderResponse]:
        """Parallel calls to every AVAILABLE provider (ThreadPool)."""
        alive = [p for p in self.providers if p.available()]
        if not alive:
            return [ProviderResponse(ok=False, error="no providers available")]

        results: list[ProviderResponse] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(p.ask, prompt): p for p in alive}
            for fut in as_completed(futures):
                p = futures[fut]
                try:
                    results.append(fut.result(timeout=self._timeout() + 5))
                except Exception as e:  # noqa: BLE001
                    results.append(ProviderResponse(
                        provider=p.name, ok=False, error=str(e)))
        # stable order by priority
        order = {p.name: i for i, p in enumerate(
            sorted(self.providers, key=lambda x: x.priority))}
        results.sort(key=lambda r: order.get(r.provider, 99))
        return results

    def ask_all_serial(self, prompt: str) -> list[ProviderResponse]:
        out = []
        for p in sorted(self.providers, key=lambda x: x.priority):
            if p.available():
                out.append(p.ask(prompt))
        return out

    def ask_multi(self, prompt: str) -> list[ProviderResponse]:
        """Parallel if enabled, else serial."""
        if CONFIG.AI_PARALLEL and sum(p.available() for p in self.providers) > 1:
            return self.ask_all(prompt)
        return self.ask_all_serial(prompt)

    # ------------------------------------------------------- health
    def health_report(self) -> dict:
        return {p.name: {
            "available": p.available(),
            "configured": p._available(),
            "calls": p.health.total_calls,
            "failures": p.health.total_failures,
            "avg_latency_ms": round(p.health.avg_latency_ms, 1),
            "healthy": p.health.ok,
        } for p in self.providers}

    def heartbeat_all(self) -> dict:
        """Quick health check ping (1-token style ask, cheap)."""
        out = {}
        for p in self.providers:
            if not p._available():
                out[p.name] = "not-configured"
                continue
            t0 = time.time()
            resp = p.ask("Reply with the single word: OK")
            took = (time.time() - t0) * 1000
            out[p.name] = ("up" if resp.ok else f"down ({resp.error})") + \
                f" [{took:.0f}ms]"
        return out

    def _timeout(self) -> float:
        return CONFIG.AI_TIMEOUT


HUB = IntelligenceHub()
