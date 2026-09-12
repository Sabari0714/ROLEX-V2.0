"""Rolex core event system — publish/subscribe, safe handlers."""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from ..errors import safe_call
from ..logging_setup import get_logger

log = get_logger("core.events")


@dataclass
class Event:
    name: str
    data: dict = field(default_factory=dict)
    source: str = "core"
    ts: float = field(default_factory=time.time)

    def __str__(self) -> str:  # noqa: D105
        return f"Event({self.name})"


class EventBus:
    """Synchronous, exception-isolated event bus."""

    def __init__(self, history_size: int = 100):
        self._subs: dict[str, list[Callable[[Event], None]]] = defaultdict(list)
        self._any: list[Callable[[Event], None]] = []
        self.history: list[Event] = []

    def subscribe(self, name: str, handler: Callable[[Event], None]) -> None:
        if handler not in self._subs[name]:
            self._subs[name].append(handler)

    def subscribe_all(self, handler: Callable[[Event], None]) -> None:
        if handler not in self._any:
            self._any.append(handler)

    def unsubscribe(self, name: str, handler) -> None:
        try:
            self._subs[name].remove(handler)
        except (KeyError, ValueError):
            pass

    # -----------------------------------------------------------
    def publish(self, name: str, data: dict | None = None,
                source: str = "core") -> Event:
        ev = Event(name=name, data=data or {}, source=source)
        self.history.append(ev)
        if len(self.history) > 2000:
            self.history = self.history[-1000:]

        for h in list(self._subs.get(name, [])):
            safe_call(h, ev, log=log)          # one bad handler can't kill Rolex
        for h in list(self._any):
            safe_call(h, ev, log=log)
        return ev

    def count(self, name: str | None = None) -> int:
        if name:
            return len(self.history) and sum(1 for e in self.history if e.name == name)
        return len(self.history)


EVENT_BUS = EventBus()
