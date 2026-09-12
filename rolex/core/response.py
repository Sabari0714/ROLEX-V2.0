"""Rolex response pipeline — every reply Rolex gives goes through here."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..logging_setup import get_logger

log = get_logger("core.response")


@dataclass
class RolexResponse:
    """The single, final, Rolex-owned answer object."""

    text: str = ""
    intent: str = "unknown"
    route: str = "local"            # local | knowledge | ai | tool | automation...
    confidence: float = 1.0
    sources: list = field(default_factory=list)      # provider names used
    language: str = "en"            # ta | en | tanglish
    uncertainty: bool = False
    latency_ms: float = 0.0
    meta: dict = field(default_factory=dict)

    _t0: float = field(default_factory=time.time, repr=False)

    def done(self) -> "RolexResponse":
        self.latency_ms = round((time.time() - self._t0) * 1000, 1)
        return self

    def stamp(self) -> dict:
        return {
            "intent": self.intent, "route": self.route,
            "confidence": self.confidence, "sources": self.sources,
            "latency_ms": self.latency_ms, "uncertainty": self.uncertainty,
        }

    def __str__(self) -> str:  # noqa: D105
        return self.text


class ResponsePipeline:
    """Post-processing every Rolex answer passes through:
    formatting, fallback text, and quality stamps."""

    def __init__(self):
        self.before_hooks: list = []   # call(response) -> response
        self.after_hooks: list = []

    def register_before(self, fn): self.before_hooks.append(fn)
    def register_after(self, fn): self.after_hooks.append(fn)

    def emit(self, response: RolexResponse) -> RolexResponse:
        for fn in self.before_hooks:
            response = fn(response) or response
        response = response.done()
        for fn in self.after_hooks:
            response = fn(response) or response
        log.info("response intent=%s route=%s conf=%.2f %dms",
                 response.intent, response.route, response.confidence,
                 response.latency_ms)
        return response

    def error(self, message: str, route: str = "local") -> RolexResponse:
        return self.emit(RolexResponse(
            text=message, intent="error", route=route, confidence=0.0,
        ))
