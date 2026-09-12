"""Phase 5 test — Knowledge Engine (local, searchable)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rolex.knowledge import KnowledgeBase            # noqa: E402


def get_kb():
    return KnowledgeBase(os.path.join("rolex", "knowledge", "topics"))


def test_load():
    kb = get_kb()
    assert kb.count() >= 40, f"need ≥40 entries, got {kb.count()}"
    topics = kb.topics()
    for expected in ("electrical", "electronics", "mechanical",
                     "civil", "computer", "science", "general"):
        assert expected in topics, f"missing topic {expected}"


def test_search_ohms_law():
    kb = get_kb()
    m = kb.best("ohms law")
    assert m is not None, "ohms law must be found"
    assert "ohm" in m.entry.title.lower()


def test_search_transformer():
    kb = get_kb()
    m = kb.best("what is a transformer")
    assert m and "transformer" in m.entry.title.lower()


def test_search_electronics():
    kb = get_kb()
    m = kb.best("led forward voltage")
    assert m and m.entry.topic == "electronics"
    m2 = kb.best("resistor color code")
    assert m2 and "resistor" in m2.entry.title.lower()


def test_search_mechanical():
    kb = get_kb()
    m = kb.best("gear ratio")
    assert m and m.entry.topic == "mechanical"


def test_search_civil():
    kb = get_kb()
    m = kb.best("m20 concrete grade")
    assert m and m.entry.topic == "civil"


def test_search_computer():
    kb = get_kb()
    m = kb.best("osi model layers")
    assert m and m.entry.topic == "computer"


def test_search_science():
    kb = get_kb()
    m = kb.best("newtons laws of motion")
    assert m and "newton" in m.entry.title.lower()


def test_search_general():
    kb = get_kb()
    m = kb.best("solar system planets")
    assert m and m.entry.topic == "general"


def test_add_entry_and_persist(tmp=None):
    import tempfile
    from rolex.knowledge.base import KnowledgeBase as KB
    with tempfile.TemporaryDirectory() as td:
        kb = KB(td)
        eid = kb.add_entry("learned", {
            "title": "Learned Fact",
            "content": "Rolex learned this fact.",
            "keywords": ["learned", "fact"],
        })
        assert eid in kb.entries
        kb2 = KB(td)
        assert kb2.get(eid) is not None, "entry must persist to JSON"


if __name__ == "__main__":
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            print(f"PASS {k}")
    print("PHASE 5 KNOWLEDGE ENGINE: ALL OK")
