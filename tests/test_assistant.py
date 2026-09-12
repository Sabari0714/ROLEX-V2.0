"""Tests for Phase 15 - RolexAssistant facade (routing, lifecycle, memory).

Isolation discipline: every test injects TEMP tasks/memory/docs engines so
the REAL data/ directory is never polluted. AskResult routing verified:
wake, math (local), command, reminder, document, knowledge, ai/offline.
"""
import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rolex.assistant import RolexAssistant, AskResult, get_assistant
from rolex.automation.engine import TaskEngine
from rolex.memory.store import MemoryStore
from rolex.documents.engine import DocumentEngine
from rolex.knowledge.base import KnowledgeBase


def _temp_kb() -> KnowledgeBase:
    """Empty KB in a temp dir - no real knowledge/ reads/writes."""
    return KnowledgeBase(kb_dir=tempfile.mkdtemp())


def _assistant() -> RolexAssistant:
    tmp = tempfile.mkdtemp()
    return RolexAssistant(
        tasks=TaskEngine(db_path=os.path.join(tmp, "tasks.db")),
        memory=MemoryStore(db_path=os.path.join(tmp, "memory.db")),
        docs=DocumentEngine(db_path=os.path.join(tmp, "docs.db")),
        kb=_temp_kb(),
    )


# ------------------------------------------------------------ AskResult
def test_askresult_shape():
    r = AskResult(text="hello", route="wake", confidence=0.9,
                  local=False, seconds=1.25)
    assert isinstance(r, AskResult)
    assert r.text == "hello" and r.route == "wake"
    assert r.local is False and abs(r.confidence - 0.9) < 1e-9
    s = str(r)
    assert "AI" in s and "wake" in s and "0.90" in s
    local_r = AskResult(text="42", route="math", local=True)
    assert "LOCAL" in str(local_r)


# ------------------------------------------------------------- routing
def test_empty_input_is_wake():
    a = _assistant()
    r = a.ask("")
    assert r.route == "wake" and "Listening" in r.text


def test_math_is_local_lightning():
    a = _assistant()
    r = a.ask("what is 12 * 8 + 4")
    assert r.route == "math" and r.local is True
    assert "100" in r.text and "⚡" in r.text
    assert r.confidence == 1.0


def test_engineering_math_local():
    a = _assistant()
    r = a.ask("ohm's law: 5V and 2.5A, resistance?")
    assert r.route == "math" and r.local is True


def test_wake_word_handled():
    a = _assistant()
    r = a.ask("hey guru what is 9 squared")
    assert r.route == "math" and r.local is True and "81" in r.text
    r2 = a.ask("hey guru")
    assert r2.route == "wake" and "yes" in r2.text.lower()


def test_command_route():
    a = _assistant()
    r = a.ask("version")
    assert r.route == "command" and r.local is True
    assert "2.2.0" in r.text   # v2.2 multi-provider keys


def test_reminder_route():
    a = _assistant()
    # unique title so a re-run never collides with real DB
    r = a.ask("remind me in 5 minutes to check ph15-test marker")
    assert r.route == "reminder" and r.local is True
    assert "🔔" in r.text and "ph15-test" in r.text
    # clean up the temp task registration
    for t in list(a.tasks.upcoming(50)):
        if "ph15-test" in t.title:
            a.tasks.cancel(t.id)


def test_document_route():
    tmp = tempfile.mkdtemp()
    p = Path(tmp) / "spec.md"
    p.write_text("# Rolex spec\nThe assistant is local-first. "
                 "Math engine answers locally. Local-first design saves battery.",
                 encoding="utf-8")
    a = _assistant()
    r = a.ask(f"summarize {p}")
    assert r.route == "document" and r.local is True
    assert "PDF".upper() in (r.text.upper()) or "spec.md" in r.text
    assert "words" in r.text


def test_document_route_missing_file_is_graceful():
    a = _assistant()
    r = a.ask("summarize /no/such/file999.txt")
    assert r.route == "document"
    assert "error" in r.text.lower()


def test_knowledge_route_local():
    a = _assistant()
    a.kb.add_entry("test", {
        "title": "Ohms Law Test Entry",
        "content": "Ohm's law states voltage equals current times resistance.",
        "keywords": ["ohm", "voltage", "resistance"],
    }, persist=False)
    r = a.ask("tell me about ohms law voltage resistance")
    assert r.route == "knowledge" and r.local is True
    assert "📘" in r.text and "Ohms Law Test Entry" in r.text


def test_unknown_question_offline_honest():
    a = _assistant()
    r = a.ask("who won the 2035 world cup final score")
    # no providers configured in test env - must fall back honestly
    assert r.route in ("ai", "offline")
    assert r.text                       # never empty
    assert 0.0 <= r.confidence <= 1.0


# ------------------------------------------------------------ lifecycle
def test_startup_shutdown_status():
    a = _assistant()
    rep = a.startup()
    assert isinstance(rep.get("recovery"), dict)
    assert any(v == "ok" for k, v in rep.items() if k != "recovery")
    st = a.status()
    assert st["state"] == "listening"
    assert st["identity"] == "Rolex"
    assert "version" in st and "turns" in st and "kb_entries" in st
    a.shutdown()
    st2 = a.status()
    assert st2["state"] == "stopped"


def test_turns_counted():
    a = _assistant()
    assert a.status()["turns"] == 0
    a.ask("1+1")
    a.ask("2+2")
    assert a.status()["turns"] == 2


def test_memory_records_exchange():
    a = _assistant()
    before = a.memory.stats()["turns"]
    a.ask("3*3")
    after = a.memory.stats()["turns"]
    assert after == before + 2            # user turn + rolex reply turn
    turns = a.memory.recent_turns(n=4)
    assert any(t.text == "3*3" for t in turns)
    assert any("9" in t.text for t in turns)


# ----------------------------------------------------------- singleton
def test_get_assistant_singleton():
    a1 = get_assistant()
    a2 = get_assistant()
    assert a1 is a2 and isinstance(a1, RolexAssistant)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {t.__name__}: {e}")
    print(f"\nPHASE 15 ASSISTANT: {passed}/{len(tests)} PASSED")
    sys.exit(0 if passed == len(tests) else 1)
