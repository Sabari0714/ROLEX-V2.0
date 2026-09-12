"""Conversation flow — multi-turn state handling (Phase 3)."""
from __future__ import annotations

from .context import ContextTracker


class ConversationFlow:
    """Glues NLU + context into a coherent multi-turn conversation:
    resolves follow-ups, keeps topics, and prepares the next reply context."""

    def __init__(self, context: ContextTracker | None = None):
        self.ctx = context or ContextTracker()

    # -----------------------------------------------------------
    def track(self, text: str, intent: str, lang: str, entities: dict) -> None:
        self.ctx.add(text, intent, lang, entities)

    def resolve(self, text: str, intent: str) -> dict:
        """Resolve a possibly-vague utterance into a full request."""
        result = {"text": text, "intent": intent, "is_followup": False,
                  "merged_text": text}

        if intent in ("confirmation", "denial"):
            result["is_followup"] = True
            result["intent"] = f"{intent}:continue"
            return result

        if self.ctx.is_followup(text):
            result["is_followup"] = True
            prev = self.ctx.last()
            if prev:
                # Merge previous subject with the new tail question.
                result["merged_text"] = f"{prev.text} {text}"
                if intent in ("unknown", "smalltalk"):
                    result["intent"] = prev.intent
        return result

    # -----------------------------------------------------------
    def topic(self) -> str | None:
        return self.ctx.topic

    def summary(self) -> dict:
        return self.ctx.summary()

    def reset(self) -> None:
        self.ctx.clear()
