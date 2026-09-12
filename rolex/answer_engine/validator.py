"""Validator — compares provider outputs for factual consistency."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from ..ai_hub.base_provider import ProviderResponse


@dataclass
class ValidationReport:
    n_sources: int = 0
    n_ok: int = 0
    pairwise_similarity: list = field(default_factory=list)
    avg_similarity: float = 1.0
    numeric_agreement: bool = True
    numbers_found: list = field(default_factory=list)
    verdict: str = "single"     # agree | disagree | single | empty


def _numbers(text: str) -> list[str]:
    return re.findall(r"-?\d+(?:\.\d+)?", text or "")


def _similarity(a: str, b: str) -> float:
    """Fuzzy text similarity 0..1 on token sequences."""
    ta = a.lower().split()
    tb = b.lower().split()
    if not ta or not tb:
        return 0.0
    sm = difflib.SequenceMatcher(None, ta, tb)
    return sm.quick_ratio() * 0.5 + sm.ratio() * 0.5


class AnswerValidator:
    """Cross-checks what the intelligence sources said."""

    def validate(self, responses: list[ProviderResponse]) -> ValidationReport:
        ok = [r for r in responses if r.ok and r.text]
        rep = ValidationReport(n_sources=len(responses), n_ok=len(ok))

        if not ok:
            rep.verdict = "empty"
            return rep
        if len(ok) == 1:
            rep.verdict = "single"
            rep.numbers_found = _numbers(ok[0].text)
            return rep

        # pairwise similarity
        sims = []
        for i in range(len(ok)):
            for j in range(i + 1, len(ok)):
                s = _similarity(ok[i].text, ok[j].text)
                sims.append(round(s, 3))
        rep.pairwise_similarity = sims
        rep.avg_similarity = sum(sims) / len(sims) if sims else 1.0

        # numeric agreement: every source must agree on the KEY number
        num_sets = [set(_numbers(r.text)) for r in ok]
        common = set.intersection(*num_sets) if num_sets else set()
        all_nums = set().union(*num_sets) if num_sets else set()
        rep.numbers_found = sorted(all_nums)
        if all_nums and not common:
            # no shared number at all while numbers exist
            rep.numeric_agreement = not all_nums or len(num_sets) == 1

        rep.verdict = "agree" if rep.avg_similarity >= 0.35 or common else \
            "disagree"
        return rep
