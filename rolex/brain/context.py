"""Conversation context tracker — multi-turn memory for the brain."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Turn:
    text: str
    intent: str = "unknown"
    lang: str = "en"
    entities: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class ContextTracker:
    """Holds the recent conversation so Rolex can understand follow-ups
    like 'athu eppadi?', 'continue', 'and 5 more?', 'seriya sollu'."""

    def __init__(self, max_turns: int = 20):
        self.turns: list[Turn] = []
        self.max_turns = max_turns
        self.topic: str | None = None          # running topic label
        self.pending: dict = field(default_factory=dict)  # unfinished flows

    # -----------------------------------------------------------
    def add(self, text: str, intent: str, lang: str, entities: dict) -> Turn:
        turn = Turn(text=text, intent=intent, lang=lang, entities=entities)
        self.turns.append(turn)
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]
        if intent not in ("confirmation", "denial", "smalltalk"):
            self.topic = intent
        return turn

    # -----------------------------------------------------------
    def last(self, n: int = 1) -> Turn | None:
        if not self.turns:
            return None
        return self.turns[-n] if n <= len(self.turns) else None

    def last_intent(self) -> str | None:
        t = self.last()
        return t.intent if t else None

    def find_last_intent(self, intent: str, skip_last: bool = False) -> Turn | None:
        rng = self.turns[:-1] if skip_last else self.turns
        for t in reversed(rng):
            if t.intent == intent:
                return t
        return None

    def is_followup(self, text: str) -> bool:
        """Short/vague utterances that refer to the previous topic."""
        t = " ".join((text or "").split()).lower().strip("!?., ")
        followups = {
            "athu eppadi", "adhu epdi", "how", "why", "explain more",
            "continue", "innum sollu", "sollu more", "tell me more", "more",
            "and", "appo", "seriya", "correct a", "and also", "example kudu",
            "example", "அது எப்படி", "மேலும் சொல்லு", "உதாரணம்",
        }
        if t in followups:
            return True
        return len(t) <= 3 and self.turns != []

    def numbers_from_history(self, n: int = 5) -> list[float]:
        out: list[float] = []
        for t in reversed(self.turns[-n:]):
            out.extend(t.entities.get("numbers", []))
        return out

    # -----------------------------------------------------------
    def set_pending(self, key: str, data: dict) -> None:
        self.pending[key] = data

    def pop_pending(self, key: str) -> dict | None:
        return self.pending.pop(key, None)

    def clear(self) -> None:
        self.turns.clear()
        self.topic = None
        self.pending.clear()

    def summary(self) -> dict:
        return {
            "turns": len(self.turns),
            "topic": self.topic,
            "last_intent": self.last_intent(),
            "pending": list(self.pending.keys()),
        }
