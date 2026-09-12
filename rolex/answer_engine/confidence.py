"""Confidence scoring — how much Rolex trusts the sourced answer."""
from __future__ import annotations

from ..config import CONFIG
from .validator import ValidationReport


class ConfidenceScorer:
    """0.0 → 1.0 confidence from validation + source quality."""

    def score(self, report: ValidationReport,
              source_latencies: dict[str, float] | None = None) -> float:
        base = 0.0

        if report.verdict == "empty":
            return 0.0
        if report.verdict == "single":
            base = 0.55            # one source, unverified
        if report.verdict == "agree":
            # agreement boosts confidence strongly
            base = 0.75 + 0.2 * min(report.avg_similarity, 1.0)
            if report.n_ok >= 3:
                base += 0.05
        if report.verdict == "disagree":
            base = 0.30            # sources conflict — low trust

        # numeric agreement bonus
        if report.n_ok > 1 and report.numeric_agreement and report.numbers_found:
            base += 0.05

        return max(0.0, min(1.0, round(base, 3)))

    def label(self, conf: float) -> str:
        if conf >= 0.85: return "high"
        if conf >= CONFIG.CONFIDENCE_THRESHOLD: return "medium"
        if conf > 0.3: return "low"
        return "very-low"

    def should_flag_uncertain(self, conf: float) -> bool:
        return conf < CONFIG.CONFIDENCE_THRESHOLD
