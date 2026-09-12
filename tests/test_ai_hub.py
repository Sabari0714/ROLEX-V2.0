"""Tests for Phase 6 - AI Intelligence Hub (offline, mock providers)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rolex.ai_hub.base_provider import AIProvider, ProviderResponse
from rolex.ai_hub.hub import IntelligenceHub
from rolex.errors import ProviderError, ProviderTimeout


# ------------------------------------------------------------ mock providers
class MockProvider(AIProvider):
    """Fake source for testing - no network, instant answers."""

    def __init__(self, name="mock", priority=50, reply="Rolex test reply",
                 fail=False, timeout=False):
        super().__init__()
        self.name = name
        self.priority = priority
        self.reply_text = reply
        self.fail = fail
        self.timeout = timeout
        self.calls = 0

    def _available(self) -> bool:
        return True

    def _ask_once(self, prompt: str) -> str:
        self.calls += 1
        if self.timeout:
            raise ProviderTimeout(f"{self.name} mock timeout")
        if self.fail:
            raise ProviderError(f"{self.name} mock error")
        return self.reply_text


# ----------------------------------------------------------------- tests
def test_provider_retry_and_health():
    p = MockProvider(name="flaky", fail=True)
    assert p.available() is True
    resp = p.ask("hello")
    # failed all retries -> ok=False, health degraded
    assert resp.ok is False
    assert p.health.consecutive_failures >= 1
    print("PASS test_provider_retry_and_health")


def test_circuit_breaker():
    p = MockProvider(name="cb", fail=True)
    p.ask("1"); p.ask("2"); p.ask("3")
    # 3 consecutive failures -> health.ok False (circuit open)
    assert p.health.ok is False
    assert p.available() is False
    print("PASS test_circuit_breaker")


def test_provider_success_path():
    p = MockProvider(name="good", reply="exact answer 42")
    resp = p.ask("meaning of life")
    assert resp.ok is True
    assert resp.text == "exact answer 42"
    assert resp.provider == "good"
    assert p.health.total_calls == 1
    assert p.health.consecutive_failures == 0
    print("PASS test_provider_success_path")


def test_hub_pick_priority_order():
    a = MockProvider(name="pa", priority=10, reply="A")
    b = MockProvider(name="pb", priority=20, reply="B")
    hub = IntelligenceHub(providers=[b, a])
    assert hub.pick().name == "pa"          # lower priority number wins
    print("PASS test_hub_pick_priority_order")


def test_hub_pick_skips_unhealthy():
    a = MockProvider(name="sick", priority=10, fail=True)
    a.ask("x"); a.ask("y"); a.ask("z")      # circuit-broken
    b = MockProvider(name="ok", priority=20)
    hub = IntelligenceHub(providers=[a, b])
    assert hub.pick().name == "ok"
    print("PASS test_hub_pick_skips_unhealthy")


def test_hub_ask_all_parallel():
    a = MockProvider(name="pa", priority=10, reply="alpha")
    b = MockProvider(name="pb", priority=20, reply="beta")
    hub = IntelligenceHub(providers=[a, b])
    resps = hub.ask_all("question")
    assert len(resps) == 2
    assert all(r.ok for r in resps)
    names = {r.provider for r in resps}
    assert names == {"pa", "pb"}
    print("PASS test_hub_ask_all_parallel")


def test_hub_ask_multi_serial_when_single():
    a = MockProvider(name="only", priority=10, reply="solo")
    hub = IntelligenceHub(providers=[a])
    resps = hub.ask_multi("q")
    assert len(resps) == 1 and resps[0].ok and resps[0].text == "solo"
    print("PASS test_hub_ask_multi_serial_when_single")


def test_hub_ask_multi_parallel():
    import os
    os.environ["ROLEX_AI_PARALLEL"] = "1"
    a = MockProvider(name="pa", priority=10, reply="alpha")
    b = MockProvider(name="pb", priority=20, reply="beta")
    hub = IntelligenceHub(providers=[a, b])
    resps = hub.ask_multi("q")
    assert len(resps) == 2 and all(r.ok for r in resps)
    print("PASS test_hub_ask_multi_parallel")


def test_hub_no_providers():
    hub = IntelligenceHub(providers=[])
    assert hub.pick() is None
    resps = hub.ask_all("q")
    assert resps[0].ok is False
    print("PASS test_hub_no_providers")


def test_hub_health_report():
    a = MockProvider(name="hr", reply="ok")
    a.ask("ping")
    hub = IntelligenceHub(providers=[a])
    rep = hub.health_report()
    assert "hr" in rep and rep["hr"]["available"] is True
    assert rep["hr"]["calls"] == 1
    print("PASS test_hub_health_report")


def test_real_hub_offline_safe():
    """Real HUB with no keys -> providers not configured, graceful."""
    from rolex.ai_hub.hub import HUB
    rep = HUB.health_report()
    assert set(rep.keys()) == {"openai", "gemini", "ollama"}
    # In sandbox: no keys set -> openai/gemini not configured
    assert rep["openai"]["configured"] is False
    assert rep["gemini"]["configured"] is False
    print("PASS test_real_hub_offline_safe")


if __name__ == "__main__":
    test_provider_retry_and_health()
    test_circuit_breaker()
    test_provider_success_path()
    test_hub_pick_priority_order()
    test_hub_pick_skips_unhealthy()
    test_hub_ask_all_parallel()
    test_hub_ask_multi_serial_when_single()
    test_hub_ask_multi_parallel()
    test_hub_no_providers()
    test_hub_health_report()
    test_real_hub_offline_safe()
    print("ALL AI-HUB TESTS PASSED")
