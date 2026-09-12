"""Hallucination detector — pattern-level safety checks (Phase 7)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class HallucinationReport:
    suspicious: bool = False
    reasons: list = field(default_factory=list)
    risk_score: float = 0.0          # 0 = clean, 1 = very suspicious

    def __str__(self) -> str:  # noqa: D105
        return f"risk={self.risk_score:.2f} reasons={self.reasons}"


_HEDGES = re.compile(
    r"\b(as an ai|i'?m not sure|i cannot|i don'?t have access|"
    r"my knowledge cutoff|i do not have (?:real-time|current)|"
    r"cannot verify|i apologize)\b", re.I)
_MIXED_SCRIPT = re.compile(r"[A-Za-z]{8,}[அ-ஹ][a-z]+")
_FABRICATED_URL = re.compile(
    r"https?://(?:[a-z0-9-]+\.)?(?:example|fake|placeholder|nonexistent)\b",
    re.I)
_OVERCONFIDENT = re.compile(
    r"\b(always|never|guaranteed|100% certain|definitely impossible)\b", re.I)


class HallucinationDetector:
    """Heuristic checks Rolex runs on every sourced answer."""

    def check(self, text: str, question: str = "",
              validation=None) -> HallucinationReport:
        rep = HallucinationReport()
        if not text:
            rep.suspicious = True
            rep.reasons.append("empty answer")
            rep.risk_score = 1.0
            return rep

        reasons: list[str] = []
        risk = 0.0

        if _HEDGES.search(text):
            reasons.append("hedge/self-disclaimer")
            risk += 0.15
        if _FABRICATED_URL.search(text):
            reasons.append("fabricated-looking URL")
            risk += 0.55          # strong red flag on its own
        if _MIXED_SCRIPT.search(text):
            reasons.append("script-mangling artifact")
            risk += 0.25

        # question keywords completely absent from answer
        if question:
            stops = {"what", "when", "where", "which", "about", "does",
                     "explain", "tell", "give", "some", "that", "this", "have"}
            qk = {w for w in re.findall(r"[a-z]{4,}", question.lower())
                  if w not in stops}
            if qk and len(qk) > 1:
                body = text.lower()
                hit = sum(1 for w in qk if w in body)
                if hit == 0:
                    reasons.append("answer ignores the question")
                    risk += 0.30
                elif hit / len(qk) < 0.25:
                    reasons.append("question mostly unanswered")
                    risk += 0.10

        # sources disagree hard
        if validation is not None and getattr(validation, "verdict", "") == "disagree":
            reasons.append("sources disagree")
            risk += 0.30

        rep.reasons = reasons
        rep.risk_score = round(min(1.0, risk), 2)
        rep.suspicious = rep.risk_score >= 0.5
        return rep
