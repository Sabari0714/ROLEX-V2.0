"""Phase 2 test — Rolex core (identity, state, events, commands, lifecycle)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rolex.core.identity import IDENTITY                      # noqa: E402
from rolex.core.state import SystemState, StateMachine        # noqa: E402
from rolex.core.events import EventBus                        # noqa: E402
from rolex.core.response import RolexResponse, ResponsePipeline  # noqa: E402
from rolex.core.commands import CommandProcessor              # noqa: E402
from rolex.core.lifecycle import RolexLifecycle               # noqa: E402


def test_identity():
    assert IDENTITY.name == "Rolex"
    assert IDENTITY.matches_name("rolex help me")
    assert "ROLEX" in IDENTITY.introduction.upper()


def test_state_machine():
    sm = StateMachine()
    assert sm.state == SystemState.OFFLINE
    assert sm.transition(SystemState.BOOTING)
    assert sm.transition(SystemState.LISTENING)
    assert sm.transition(SystemState.THINKING)
    assert sm.transition(SystemState.LISTENING)
    assert sm.uptime >= 0
    assert "state" in sm.snapshot()


def test_events():
    bus = EventBus()
    seen = []
    bus.subscribe("ping", lambda e: seen.append(e.data["n"]))
    bad = lambda e: 1 / 0                      # noqa: E731  (must not kill bus)
    bus.subscribe("ping", bad)
    bus.publish("ping", {"n": 7})
    assert seen == [7], "safe handlers required"


def test_response():
    pipe = ResponsePipeline()
    r = pipe.emit(RolexResponse(text="hello", intent="greet", route="local"))
    assert r.latency_ms >= 0
    assert r.stamp()["intent"] == "greet"


def test_commands():
    cp = CommandProcessor()
    assert cp.parse("/status") == "status"
    assert cp.parse("status") == "status"
    assert cp.parse("what is ohms law") is None
    assert "ROLEX" in cp.execute("/version")
    assert "commands" in cp.execute("/help")


def test_lifecycle():
    class Mod:
        def __init__(self): self.up = False
        def startup(self): self.up = True
        def shutdown(self): self.up = False
    lc = RolexLifecycle({"demo": Mod()})
    rep = lc.startup()
    assert rep["demo"] == "ok"
    assert lc.sm.state in (SystemState.LISTENING, SystemState.DEGRADED)
    rep2 = lc.shutdown()
    assert rep2["demo"] == "ok"
    assert lc.sm.state == SystemState.STOPPED


if __name__ == "__main__":
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            print(f"PASS {k}")
    print("PHASE 2 CORE: ALL OK")
