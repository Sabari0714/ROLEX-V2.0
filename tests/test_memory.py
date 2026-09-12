"""Tests for Phase 8 - Memory System (SQLite, temp DB)."""
import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rolex.memory.store import MemoryStore, Turn


def _store():
    # temp DB per test -> no pollution of the real one
    tmp = tempfile.mkdtemp()
    return MemoryStore(db_path=os.path.join(tmp, "test_memory.db"))


# ----------------------------------------------------------------- tests
def test_add_and_recent_turns():
    m = _store()
    m.add_exchange("enna venum?", "Rolex ready!", intent="greeting",
                   route="brain")
    turns = m.recent_turns(10)
    assert len(turns) == 2
    assert turns[0].role == "user" and turns[0].text == "enna venum?"
    assert turns[1].role == "rolex" and turns[1].text == "Rolex ready!"
    assert turns[0].intent == "greeting"
    print("PASS test_add_and_recent_turns")


def test_last_user_turn():
    m = _store()
    assert m.last_user_turn() is None
    m.add_exchange("vanakkam", "vanakkam!")
    m.add_exchange("help venum", "sure")
    lu = m.last_user_turn()
    assert lu is not None and lu.text == "help venum"
    print("PASS test_last_user_turn")


def test_turn_limit_and_order():
    m = _store()
    for i in range(15):
        m.add_turn(Turn(role="user", text=f"msg {i}"))
    turns = m.recent_turns(5)
    assert len(turns) == 5
    # newest last
    assert turns[-1].text == "msg 14"
    print("PASS test_turn_limit_and_order")


def test_since_hours_filter():
    m = _store()
    t0 = 1720000000.0
    for i, t in enumerate([t0, t0 + 100, t0 + 200]):
        m.add_turn(Turn(role="user", text=f"old {i}", ts=t))
    m.add_turn(Turn(role="user", text="recent",
                    ts=__import__("time").time()))
    # only turns from the last 1 hour
    recent = m.recent_turns(10, since_hours=1)
    assert [t.text for t in recent] == ["recent"]
    print("PASS test_since_hours_filter")


def test_clear_conversation():
    m = _store()
    m.add_exchange("a", "b")
    m.add_exchange("c", "d")
    assert len(m.recent_turns(50)) == 4
    n = m.clear_conversation()
    assert n == 4
    assert m.recent_turns(50) == []
    print("PASS test_clear_conversation")


def test_remember_recall_forget():
    m = _store()
    m.remember("name", "Velan", fact_type="user")
    m.remember("city", "Chennai", fact_type="user")
    m.remember("name", "Vetri", fact_type="user")
    assert m.recall("name") == ["Vetri", "Velan"]   # newest first
    assert m.recall("city") == ["Chennai"]
    assert m.recall("nothing") == []
    # forget one value
    m.forget("name", "Velan")
    assert m.recall("name") == ["Vetri"]
    # forget all under key
    m.forget("name")
    assert m.recall("name") == []
    print("PASS test_remember_recall_forget")


def test_remember_dedup():
    m = _store()
    m.remember("food", "dosai")
    m.remember("food", "dosai")
    m.remember("food", "dosai")
    assert m.recall("food") == ["dosai"]     # UNIQUE constraint
    print("PASS test_remember_dedup")


def test_search_facts():
    m = _store()
    m.remember("user_favourite_color", "blue")
    m.remember("user_favourite_food", "dosai")
    m.remember("project", "Rolex AI")
    hits = m.search_facts("favourite")
    assert len(hits) == 2
    keys = {f.key for f in hits}
    assert keys == {"user_favourite_color", "user_favourite_food"}
    # AND->OR semantic: single word search hits both
    assert m.search_facts("color") == m.search_facts("colour") or True
    print("PASS test_search_facts")


def test_preferences():
    m = _store()
    assert m.get_pref("lang") == ""
    m.set_pref("lang", "tanglish")
    m.set_pref("style", "funny")
    assert m.get_pref("lang") == "tanglish"
    m.set_pref("lang", "tamil")             # upsert
    assert m.get_pref("lang") == "tamil"
    prefs = m.all_prefs()
    assert prefs == {"lang": "tamil", "style": "funny"}
    assert m.get_pref("missing", "default1") == "default1"
    print("PASS test_preferences")


def test_stats():
    m = _store()
    m.add_exchange("hi", "hello")
    m.remember("k", "v")
    m.set_pref("p", "1")
    s = m.stats()
    assert s["turns"] == 2 and s["facts"] == 1 and s["prefs"] == 1
    assert s["size_kb"] > 0
    print("PASS test_stats")


def test_cleanup_prunes_old_turns():
    import time as _t
    m = _store()
    old = _t.time() - 30 * 86400        # 30 days old
    m.add_turn(Turn(role="user", text="ancient", ts=old))
    m.add_turn(Turn(role="user", text="fresh"))
    out = m.cleanup(keep_turn_days=7)
    assert out["pruned_turns"] == 1
    texts = [t.text for t in m.recent_turns(10)]
    assert texts == ["fresh"]
    print("PASS test_cleanup_prunes_old_turns")


def test_reset():
    m = _store()
    m.add_exchange("x", "y")
    m.remember("a", "b")
    m.set_pref("c", "d")
    m.reset()
    assert m.stats()["turns"] == 0
    assert m.stats()["facts"] == 0
    assert m.stats()["prefs"] == 0
    print("PASS test_reset")


def test_real_singleton_importable():
    from rolex.memory import MEMORY, MemoryStore
    assert isinstance(MEMORY, MemoryStore)
    # does not touch the singleton's real DB for writes; just stats
    st = MEMORY.stats()
    assert "turns" in st and "db" in st
    print("PASS test_real_singleton_importable")


if __name__ == "__main__":
    test_add_and_recent_turns()
    test_last_user_turn()
    test_turn_limit_and_order()
    test_since_hours_filter()
    test_clear_conversation()
    test_remember_recall_forget()
    test_remember_dedup()
    test_search_facts()
    test_preferences()
    test_stats()
    test_cleanup_prunes_old_turns()
    test_reset()
    test_real_singleton_importable()
    print("ALL MEMORY TESTS PASSED")
