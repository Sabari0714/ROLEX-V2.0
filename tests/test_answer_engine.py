"""Tests for Phase 7 - Rolex Answer Engine (offline, mock sources)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rolex.ai_hub.base_provider import AIProvider, ProviderResponse
from rolex.ai_hub.hub import IntelligenceHub
from rolex.answer_engine import (AnswerEngine, RolexFinalAnswer, ANSWER_ENGINE)
from rolex.knowledge import KnowledgeBase
from rolex.errors import ProviderError


# ------------------------------------------------------------ mock provider
class MockProvider(AIProvider):
    def __init__(self, name="mock", priority=50, reply="Rolex test reply",
                 fail=False):
        super().__init__()
        self.name = name
        self.priority = priority
        self.reply_text = reply
        self.fail = fail
        self.calls = 0

    def _available(self) -> bool:
        return True

    def _ask_once(self, prompt: str) -> str:
        self.calls += 1
        if self.fail:
            raise ProviderError(f"{self.name} mock error")
        return self.reply_text


def _engine(providers):
    hub = IntelligenceHub(providers=providers)
    return AnswerEngine(hub=hub, knowledge=KnowledgeBase())


def _resp(text, provider="p", ok=True, latency=10.0):
    return ProviderResponse(text=text, provider=provider, ok=ok,
                            latency_ms=latency)


# ----------------------------------------------------------------- tests
def test_single_source_answer():
    e = _engine([MockProvider(name="src", reply="Ohm's law is V = I * R.")])
    fa = e.answer("ohm law enna")
    assert fa.route == "ai"
    assert "V = I * R" in fa.text
    assert fa.confidence == 0.55
    assert fa.confidence_label == "low"      # single unverified source
    assert fa.sources == ["src"]
    # below threshold -> Rolex flags it honestly
    assert fa.uncertain is True
    assert "full confidence illa" in fa.text
    print("PASS test_single_source_answer")


def test_single_source_uncertain_below_threshold():
    # confidence 0.55 < threshold 0.65 -> uncertain flagged
    e = _engine([MockProvider(name="src", reply="The capital is Chennai.")])
    fa = e.answer("capital of tamilnadu")
    assert fa.uncertain is True
    assert "Rolex-ku ithu la full confidence illa" in fa.text
    print("PASS test_single_source_uncertain_below_threshold")


def test_two_sources_agree():
    a = MockProvider(name="pa", priority=10, reply="V equals I times R.")
    b = MockProvider(name="pb", priority=20, reply="V equals I times R.")
    e = _engine([a, b])
    fa = e.answer("ohm law")
    assert fa.route == "ai"
    assert fa.validation.n_ok == 2
    assert fa.validation.verdict == "agree"
    assert fa.confidence >= 0.75
    assert "verified" in fa.text
    assert set(fa.sources) == {"pa", "pb"}
    print("PASS test_two_sources_agree")


def test_two_sources_disagree():
    a = MockProvider(name="pa", priority=10, reply="Python released 1991.")
    b = MockProvider(name="pb", priority=20,
                     reply="Java released 1995 with Sun Microsystems.")
    e = _engine([a, b])
    fa = e.answer("python release year")
    assert fa.validation.verdict == "disagree"
    assert fa.confidence <= 0.35
    assert fa.uncertain is True
    assert "sources disagree" in fa.text
    print("PASS test_two_sources_disagree")


def test_hallucination_penalty():
    a = MockProvider(name="pa", priority=10,
                     reply="Check https://www.example.com/fake for info.")
    e = _engine([a])
    fa = e.answer("tell me about resistors")
    assert fa.hallucination is not None
    assert fa.hallucination.suspicious is True
    assert fa.confidence <= 0.30          # penalized
    assert fa.uncertain is True
    print("PASS test_hallucination_penalty")


def test_hallucination_clean_answer_not_penalized():
    a = MockProvider(name="pa", priority=10,
                     reply="A resistor limits current. Resistors use ohms.")
    e = _engine([a])
    fa = e.answer("tell me about resistors")
    assert fa.hallucination is not None
    assert fa.hallucination.suspicious is False
    assert fa.confidence == 0.55
    print("PASS test_hallucination_clean_answer_not_penalized")


def test_kb_fallback_on_provider_failure():
    e = _engine([MockProvider(name="dead", fail=True)])
    fa = e.answer("what is ohms law")
    assert fa.route == "knowledge"
    assert fa.used_kb_fallback is True
    assert "V = I" in fa.text
    assert fa.sources == ["local-kb"]
    print("PASS test_kb_fallback_on_provider_failure")


def test_kb_fallback_picks_formula_entry():
    e = _engine([MockProvider(name="dead", fail=True)])
    fa = e.answer("tell me about gst tax calculation")
    fa2 = e.answer("power consumption electricity unit energy")
    assert fa.route == "knowledge" or fa2.route == "knowledge"
    assert (fa.used_kb_fallback is True
            or fa2.used_kb_fallback is True)
    print("PASS test_kb_fallback_picks_formula_entry")


def test_offline_no_kb_match():
    e = _engine([MockProvider(name="dead", fail=True)])
    fa = e.answer("zzz qqq xyzzyx")
    assert fa.route == "offline"
    assert fa.confidence == 0.0
    assert "offline mode" in fa.text
    print("PASS test_offline_no_kb_match")


def test_precomputed_responses():
    """answer() accepts responses= to skip hub call (local math route)."""
    e = _engine([])
    fa = e.answer("2+2", responses=[_resp("4", provider="rolex-local")])
    assert fa.route == "ai"
    assert fa.confidence == 0.55
    assert fa.sources == ["rolex-local"]
    print("PASS test_precomputed_responses")


def test_hedge_cleanup():
    """Provider self-disclaimers stripped - Rolex owns the final answer."""
    a = MockProvider(name="pa", priority=10,
                     reply="As an AI, I do not have access to real-time data. "
                           "The boiling point of water is 100 C.")
    e = _engine([a])
    fa = e.answer("boiling point of water")
    body = fa.text
    assert "As an AI" not in body
    assert "100 C" in body
    print("PASS test_hedge_cleanup")


def test_answer_engine_singleton_importable():
    assert ANSWER_ENGINE is not None
    assert isinstance(ANSWER_ENGINE, AnswerEngine)
    assert isinstance(ANSWER_ENGINE, AnswerEngine)
    st = ANSWER_ENGINE.status()
    assert "providers" in st and "knowledge_entries" in st
    print("PASS test_answer_engine_singleton_importable")


if __name__ == "__main__":
    test_single_source_answer()
    test_single_source_uncertain_below_threshold()
    test_two_sources_agree()
    test_two_sources_disagree()
    test_hallucination_penalty()
    test_hallucination_clean_answer_not_penalized()
    test_kb_fallback_on_provider_failure()
    test_kb_fallback_picks_formula_entry()
    test_offline_no_kb_match()
    test_precomputed_responses()
    test_hedge_cleanup()
    test_answer_engine_singleton_importable()
    print("ALL ANSWER-ENGINE TESTS PASSED")
