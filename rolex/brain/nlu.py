"""NLU pipeline — language + intent + entities + follow-up in one call."""
from __future__ import annotations

from dataclasses import dataclass, field

from .language import LANG, LanguageDetector
from .intents import IntentDetector
from .entities import EntityExtractor
from .flow import ConversationFlow
from .context import ContextTracker
from .reasoning import Reasoner


@dataclass
class NLUResult:
    text: str
    lang: str                        # ta | en | tanglish | mixed | unknown
    lang_confidence: float
    intent: str
    intent_confidence: float
    entities: dict = field(default_factory=dict)
    is_followup: bool = False
    merged_text: str = ""
    reply_style: str = "en"          # ta | tanglish | en


class NLU:
    """The complete local brain front-end. Zero network calls."""

    def __init__(self):
        self.lang_detector = LanguageDetector()
        self.intent_detector = IntentDetector()
        self.entities = EntityExtractor()
        self.reasoner = Reasoner()
        self.ctx = ContextTracker()
        self.flow = ConversationFlow(self.ctx)

    # -----------------------------------------------------------
    def analyze(self, text: str) -> NLUResult:
        text = (text or "").strip()
        lr = self.lang_detector.detect(text)
        ir = self.intent_detector.detect(text, lr.lang)

        ent = self.entities.extract(text)
        resolved = self.flow.resolve(text, ir.intent)

        self.flow.track(text, ir.intent, lr.lang.value, ent)

        return NLUResult(
            text=text,
            lang=lr.lang.value,
            lang_confidence=lr.confidence,
            intent=resolved["intent"],
            intent_confidence=ir.confidence,
            entities=ent,
            is_followup=resolved["is_followup"],
            merged_text=resolved["merged_text"],
            reply_style=LanguageDetector.reply_style(lr.lang),
        )

    # Convenience passthroughs -----------------------------------
    def is_local(self, intent: str) -> bool:
        return intent in IntentDetector.LOCAL_INTENTS

    def context_summary(self) -> dict:
        return self.ctx.summary()
