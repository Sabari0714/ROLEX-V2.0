"""Base AI provider — abstract interface + health tracking."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..config import CONFIG
from ..errors import ProviderError, ProviderTimeout
from ..logging_setup import get_logger


@dataclass
class ProviderResponse:
    """Raw response from one intelligence source."""
    text: str = ""
    provider: str = ""
    latency_ms: float = 0.0
    ok: bool = False
    error: str = ""


@dataclass
class ProviderHealth:
    name: str
    ok: bool = True
    consecutive_failures: int = 0
    last_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    total_calls: int = 0
    total_failures: int = 0
    last_check: float = 0.0
    _latencies: list = field(default_factory=list, repr=False)

    def record(self, ok: bool, latency_ms: float) -> None:
        self.total_calls += 1
        self.last_latency_ms = latency_ms
        self.last_check = time.time()
        if ok:
            self.consecutive_failures = 0
            self.ok = True
            self._latencies.append(latency_ms)
            self._latencies = self._latencies[-20:]
            self.avg_latency_ms = sum(self._latencies) / len(self._latencies)
        else:
            self.total_failures += 1
            self.consecutive_failures += 1
            if self.consecutive_failures >= 3:
                self.ok = False


class AIProvider(ABC):
    """Every intelligence source implements this. Never raises on ask()."""

    name: str = "base"
    priority: int = 100          # lower = preferred

    def __init__(self):
        self.log = get_logger(f"ai.{self.name}")
        self.health = ProviderHealth(self.name)
        self.timeout = CONFIG.AI_TIMEOUT
        self.retries = CONFIG.AI_RETRIES

    # ------------------------------------------------------- interface
    @abstractmethod
    def _ask_once(self, prompt: str) -> str:
        """Single attempt. Raise ProviderError/ProviderTimeout on failure."""

    def _available(self) -> bool:
        """Config check (key present, base URL set...)."""
        return True

    # ------------------------------------------------------- public API
    def available(self) -> bool:
        return self._available() and self.health.ok

    def ask(self, prompt: str) -> ProviderResponse:
        """Ask with retries + timeout + health tracking. Never raises."""
        t0 = time.time()
        if not self._available():
            self.health.record(False, 0)
            return ProviderResponse(
                provider=self.name, ok=False,
                error=f"{self.name} not configured")

        last_err = ""
        for attempt in range(max(1, self.retries + 1)):
            try:
                text = self._ask_once(prompt)
                if not text or not text.strip():
                    raise ProviderError(f"{self.name} returned empty text")
                latency = (time.time() - t0) * 1000
                self.health.record(True, latency)
                return ProviderResponse(text=text.strip(), provider=self.name,
                                        latency_ms=latency, ok=True)
            except ProviderTimeout as e:
                last_err = f"timeout: {e}"
                self.log.warning("attempt %d timeout (%.0fs)",
                                 attempt + 1, self.timeout)
            except ProviderError as e:
                last_err = str(e)
                self.log.warning("attempt %d failed: %s", attempt + 1, e)
            except Exception as e:  # noqa: BLE001
                last_err = f"unexpected: {e}"
                self.log.warning("attempt %d error: %s", attempt + 1, e)

        latency = (time.time() - t0) * 1000
        self.health.record(False, latency)
        return ProviderResponse(provider=self.name, ok=False, error=last_err)
