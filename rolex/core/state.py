"""Rolex system state — lifecycle states + observable snapshots."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class SystemState(Enum):
    OFFLINE = "offline"        # not started
    BOOTING = "booting"        # startup sequence running
    LISTENING = "listening"    # idle, waiting for input
    THINKING = "thinking"      # processing a request (brain/router active)
    ACTING = "acting"          # executing tools / actions
    LEARNING = "learning"      # self-improvement pipeline running
    DEGRADED = "degraded"      # partially failed but alive
    STOPPED = "stopped"        # emergency stop / shutdown finished


# Allowed transitions keep the lifecycle strict.
_ALLOWED = {
    SystemState.OFFLINE: {SystemState.BOOTING},
    SystemState.BOOTING: {SystemState.LISTENING, SystemState.DEGRADED},
    SystemState.LISTENING: {SystemState.THINKING, SystemState.ACTING,
                            SystemState.LEARNING, SystemState.STOPPED},
    SystemState.THINKING: {SystemState.LISTENING, SystemState.ACTING,
                           SystemState.DEGRADED, SystemState.STOPPED},
    SystemState.ACTING: {SystemState.LISTENING, SystemState.DEGRADED,
                         SystemState.STOPPED},
    SystemState.LEARNING: {SystemState.LISTENING, SystemState.DEGRADED,
                           SystemState.STOPPED},
    SystemState.DEGRADED: {SystemState.LISTENING, SystemState.STOPPED},
    SystemState.STOPPED: {SystemState.OFFLINE},
}


@dataclass
class _Snap:
    state: SystemState
    note: str
    at: float


class StateMachine:
    """Tracks Rolex state with transition history + uptime."""

    def __init__(self):
        self.state = SystemState.OFFLINE
        self.boot_time: float | None = None
        self.history: list[_Snap] = [_Snap(self.state, "created", time.time())]

    # -----------------------------------------------------------
    def transition(self, new: SystemState, note: str = "") -> bool:
        if new == self.state:
            return True
        if new not in _ALLOWED.get(self.state, set()):
            return False
        if new == SystemState.BOOTING:
            self.boot_time = time.time()
        self.state = new
        self.history.append(_Snap(new, note, time.time()))
        if len(self.history) > 200:
            self.history = self.history[-100:]
        return True

    def force(self, new: SystemState, note: str = "forced") -> None:
        """Emergency-only direct set (used by emergency stop)."""
        self.state = new
        self.history.append(_Snap(new, note, time.time()))

    # -----------------------------------------------------------
    @property
    def uptime(self) -> float:
        return (time.time() - self.boot_time) if self.boot_time else 0.0

    def is_busy(self) -> bool:
        return self.state in (SystemState.THINKING, SystemState.ACTING,
                              SystemState.LEARNING)

    def snapshot(self) -> dict:
        return {
            "state": self.state.value,
            "uptime_sec": round(self.uptime, 1),
            "busy": self.is_busy(),
            "last_change": self.history[-1].note or self.history[-1].state.value,
        }

    def recent(self, n: int = 10) -> list[dict]:
        return [
            {"state": s.state.value, "note": s.note, "t": round(s.at, 1)}
            for s in self.history[-n:]
        ]
