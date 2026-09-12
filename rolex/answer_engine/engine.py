"""Rolex Answer Engine (Phase 7) \u2014 Rolex owns the ONE final answer.

Flow: sources \u2192 validate (cross-check) \u2192 confidence \u2192 hallucination
check \u2192 compose ONE RolexFinalAnswer \u2192 uncertainty handling.

AI providers are intelligence SOURCES only. The user-facing final answer
is composed and owned by Rolex itself.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..ai_hub.base_provider import AIProvider, ProviderResponse
from ..ai_hub.hub import IntelligenceHub
from ..config import CONFIG
from ..knowledge import KnowledgeBase
from ..logging_setup import get_logger
from .confidence import ConfidenceScorer
from .hallucination import HallucinationDetector, HallucinationReport
from .validator import AnswerValidator, ValidationReport

log = get_logger("answer")


# --------------------------------------------------------------------- model
@dataclass
class RolexFinalAnswer:
    """The single answer Rolex hands back to the user."""
    text: str = ""
    question: str = ""
    route: str = "ai"               # ai | knowledge | offline
    confidence: float = 0.0
    confidence_label: str = "low"
    sources: list[str] = field(default_factory=list)
    validation: ValidationReport | None = None
    hallucination: HallucinationReport | None = None
    uncertain: bool = False
    used_kb_fallback: bool = False

    def __str__(self) -> str:  # noqa: D105
        flag = " \u26a0\ufe0f" if self.uncertain else ""
        return f"[{self.route}]{flag} {self.text[:120]}"


_HEDGE_SENT = re.compile(
    r"^[^\n.!?]*(?:as an ai|my knowledge cutoff|i do not have access|"
    r"i cannot access|i apologize)[^\n.!?]*[.!?]?\s*",
    re.I | re.M)


class AnswerEngine:
    """Composes the ONE final Rolex answer from intelligence sources."""

    def __init__(self, hub: IntelligenceHub | None = None,
                 knowledge: KnowledgeBase | None = None,
                 validator: AnswerValidator | None = None,
                 scorer: ConfidenceScorer | None = None,
                 detector: HallucinationDetector | None = None):
        self.hub = hub or IntelligenceHub()
        self.kb = knowledge or KnowledgeBase()
        self.validator = validator or AnswerValidator()
        self.scorer = scorer or ConfidenceScorer()
        self.detector = detector or HallucinationDetector()

    # ------------------------------------------------------------ main
    def answer(self, question: str,
               responses: list[ProviderResponse] | None = None
               ) -> RolexFinalAnswer:
        """Ask sources (if needed), validate, and compose the final answer."""
        question = (question or "").strip()
        if responses is None:
            responses = self.hub.ask_multi(question)

        report = self.validator.validate(responses)
        ok = [r for r in responses if r.ok and r.text]

        # -------------------------------------------------- no live source
        if not ok:
            return self._fallback_local(question)

        # -------------------------------------------------- choose source
        chosen = self._choose(responses, ok)
        text = self._clean(chosen.text)
        conf = self.scorer.score(report)
        hall = self.detector.check(text, question=question, validation=report)

        if hall.suspicious:
            conf = round(max(0.1, conf - 0.25), 3)
            log.warning("hallucination risk on %r: %s",
                        question[:60], hall.reasons)

        label = self.scorer.label(conf)
        uncertain = self.scorer.should_flag_uncertain(conf) or hall.suspicious

        final_text = self._compose(
            text, report=report, confidence=conf, uncertain=uncertain,
            sources=[r.provider for r in ok])

        return RolexFinalAnswer(
            text=final_text, question=question, route="ai",
            confidence=conf, confidence_label=label,
            sources=[r.provider for r in ok],
            validation=report, hallucination=hall, uncertain=uncertain)

    # ------------------------------------------------------------ helpers
    def _choose(self, responses: list[ProviderResponse],
                ok: list[ProviderResponse]) -> ProviderResponse:
        """Pick the most-trusted ok source: priority order, then latency."""
        order = {p.name: p.priority for p in self.hub.providers}
        ranked = sorted(ok, key=lambda r: (order.get(r.provider, 99),
                                           r.latency_ms))
        return ranked[0]

    def _clean(self, text: str) -> str:
        """Strip provider self-disclaimers \u2014 the final answer is Rolex's."""
        cleaned = _HEDGE_SENT.sub("", text or "").strip()
        return cleaned or (text or "").strip()

    def _compose(self, text: str, *, report: ValidationReport,
                 confidence: float, uncertain: bool,
                 sources: list[str]) -> str:
        """Rolex frames the answer \u2014 one voice, honest about confidence."""
        parts: list[str] = []

        if uncertain:
            parts.append("\u26a0\ufe0f Rolex-ku ithu la full confidence illa. "
                         "\u0bae\u0bc1\u0b95\u0bcd\u0b95\u0bbf\u0baf\u0bae\u0bbe\u0b95 "
                         "verify pannunga.\n")
        parts.append(text.strip())

        if report.n_ok > 1:
            verdict = ("\u2705 verified" if report.verdict == "agree"
                       else "\u26a0\ufe0f sources disagree")
            parts.append(f"\n\u2014 Rolex {verdict} \u00b7 confidence "
                         f"{confidence:.0%} \u00b7 sources: "
                         f"{', '.join(sources)}")
        elif report.n_ok == 1:
            parts.append(f"\n\u2014 Rolex \u00b7 confidence {confidence:.0%} "
                         f"\u00b7 source: {sources[0] if sources else '?'}")
        return "\n".join(parts)

    # -------------------------------------------------- fallback paths
    def _fallback_local(self, question: str) -> RolexFinalAnswer:
        """No provider answered \u2192 try the local knowledge base."""
        match = self.kb.best(question, min_score=2.0)
        if match is not None:
            entry = match.entry
            body = entry.content.strip()
            if entry.formula:
                body += f"\n\U0001d493\U0001d582\U0001d5b8\U0001d5b6\U0001d58a\U0001d5ae\U0001d5b2\U0001d49f: {entry.formula}"
            text = (f"\U0001f4d8 {entry.title}\n{body}\n"
                    f"\u2014 Rolex \u00b7 local knowledge ({entry.topic})")
            return RolexFinalAnswer(
                text=text, question=question, route="knowledge",
                confidence=0.6, confidence_label="medium",
                sources=["local-kb"], used_kb_fallback=True)

        text = ("\u26a0\ufe0f Rolex offline mode: AI intelligence sources "
                "connect aagala, ithu local knowledge base-layum "
                "illa.\nInternet/config check pannunga \u2014 "
                "ROLEX ready to try again.")
        return RolexFinalAnswer(
            text=text, question=question, route="offline",
            confidence=0.0, confidence_label="very-low",
            sources=[])

    # ------------------------------------------------------------ report
    def status(self) -> dict:
        return {
            "providers": self.hub.health_report(),
            "knowledge_entries": len(self.kb.entries),
            "confidence_threshold": CONFIG.CONFIDENCE_THRESHOLD,
        }


ANSWER_ENGINE = AnswerEngine()
