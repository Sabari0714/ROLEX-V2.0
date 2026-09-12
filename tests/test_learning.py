"""Tests for Phase 9 - Learning pipeline (safe sandbox, temp dirs)."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rolex.learning.engine import LearningEngine, Stage, LearningError


def _engine(tmp=None):
    tmp = tmp or tempfile.mkdtemp()
    kb = Path(tmp) / "kb"
    kb.mkdir(exist_ok=True)
    return LearningEngine(
        state_path=str(Path(tmp) / "state.json"),
        sandbox_dir=str(Path(tmp) / "sandbox"),
        backup_dir=str(Path(tmp) / "backups"),
        kb_dir=str(kb))


def _kb_entry_payload(**over):
    p = {"topic": "general", "title": "VFD basics",
         "content": "A VFD controls motor speed by varying frequency.",
         "keywords": ["vfd", "motor speed"], "tags": ["learned"]}
    p.update(over)
    return p


# ----------------------------------------------------------------- tests
def test_full_happy_path():
    e = _engine()
    prop = e.propose("kb_entry", _kb_entry_payload(), reason="taught")
    assert prop.stage == Stage.PROPOSED
    prop = e.backup(prop.id)
    assert prop.stage == Stage.BACKED_UP
    prop = e.sandbox(prop.id)
    assert prop.stage == Stage.SANDBOXED
    prop = e.test(prop.id)
    assert prop.stage == Stage.TESTED
    prop = e.approve(prop.id)
    assert prop.stage == Stage.APPROVED
    prop = e.apply(prop.id)
    assert prop.stage == Stage.APPLIED

    # entry is now live in the REAL kb dir
    kb_dir = Path(e._kb_dir())
    target = kb_dir / "general.json"
    assert target.exists()
    entries = json.loads(target.read_text())["entries"]
    assert any(x["title"] == "VFD basics" for x in entries)

    # rollback removes it
    prop = e.rollback(prop.id)
    assert prop.stage == Stage.ROLLED_BACK
    entries = json.loads(target.read_text())["entries"]
    assert not any(x["title"] == "VFD basics" for x in entries)
    print("PASS test_full_happy_path")


def test_full_happy_path_with_backup_restore():
    e = _engine()
    # seed the temp KB so a real backup file gets created
    kb_file = Path(e._kb_dir()) / "general.json"
    kb_file.parent.mkdir(parents=True, exist_ok=True)
    kb_file.write_text(json.dumps(
        {"topic": "general",
         "entries": [{"id": "seed", "title": "Seed entry",
                      "keywords": [], "tags": [], "topic": "general",
                      "content": "seed content"}]},
        ensure_ascii=False, indent=2), encoding="utf-8")

    prop = e.propose("kb_entry", _kb_entry_payload(title="Backup test"))
    e.backup(prop.id); e.sandbox(prop.id); e.test(prop.id)
    e.approve(prop.id)
    orig_count = len(json.loads(kb_file.read_text())["entries"])
    e.apply(prop.id)
    after_count = len(json.loads(kb_file.read_text())["entries"])
    assert after_count == orig_count + 1

    # rollback restores the backup (count back to orig)
    e.rollback(prop.id)
    final_count = len(json.loads(kb_file.read_text())["entries"])
    assert final_count == orig_count
    print("PASS test_full_happy_path_with_backup_restore")


def test_reject_disallowed_kind():
    e = _engine()
    try:
        e.propose("self_modify_code", {"file": "rolex/core/identity.py"})
        assert False, "should have raised"
    except LearningError as ex:
        assert "not allowed" in str(ex)
    print("PASS test_reject_disallowed_kind")


def test_forbidden_topic_rejected():
    e = _engine()
    prop = e.propose("kb_entry", _kb_entry_payload(topic="security",
                                                   title="Hack things"))
    e.backup(prop.id); e.sandbox(prop.id)
    prop = e.test(prop.id)
    assert prop.stage == Stage.REJECTED
    assert any("forbidden" in f for f in prop.payload["_test_results"]["failures"])
    print("PASS test_forbidden_topic_rejected")


def test_pipeline_order_enforced():
    e = _engine()
    prop = e.propose("kb_entry", _kb_entry_payload(title="Order test"))
    # cannot sandbox before backup
    try:
        e.sandbox(prop.id); assert False
    except LearningError:
        pass
    # cannot approve before test
    e.backup(prop.id)
    try:
        e.approve(prop.id); assert False
    except LearningError:
        pass
    # cannot apply before approve
    e.sandbox(prop.id); e.test(prop.id)
    try:
        e.apply(prop.id); assert False
    except LearningError:
        pass
    # cannot rollback before apply
    try:
        e.rollback(prop.id); assert False
    except LearningError:
        pass
    print("PASS test_pipeline_order_enforced")


def test_word_map_full_pipeline():
    e = _engine()
    prop = e.propose("word_map", {"sey": "do", "paaru": "see"})
    e.backup(prop.id); e.sandbox(prop.id); e.test(prop.id)
    e.approve(prop.id); e.apply(prop.id)
    assert prop.stage == Stage.APPLIED
    wm_path = Path(e.state_path).parent / "word_maps.json"
    assert wm_path.exists()
    wm = json.loads(wm_path.read_text())
    assert wm["sey"] == "do" and wm["paaru"] == "see"
    e.rollback(prop.id)
    wm = json.loads(wm_path.read_text())
    assert "sey" not in wm and "paaru" not in wm
    print("PASS test_word_map_full_pipeline")


def test_preference_pipeline_uses_memory():
    import os
    from rolex.memory.store import MemoryStore
    tmp = tempfile.mkdtemp()
    e = _engine()
    e._memory_store = MemoryStore(db_path=os.path.join(tmp, "mem.db"))
    prop = e.propose("preference", {"style": "friendly", "lang": "tanglish"})
    e.backup(prop.id); e.sandbox(prop.id); e.test(prop.id)
    e.approve(prop.id); e.apply(prop.id)
    assert prop.stage == Stage.APPLIED
    store = e._memory()
    assert store.get_pref("style") == "friendly"
    assert store.get_pref("lang") == "tanglish"
    print("PASS test_preference_pipeline_uses_memory")


def test_state_persistence():
    e = _engine()
    prop = e.propose("kb_entry", _kb_entry_payload(title="Persist me"))
    e.backup(prop.id)
    # new engine instance sees the same state
    e2 = LearningEngine(state_path=str(e.state_path),
                        sandbox_dir=str(e.sandbox_dir),
                        backup_dir=str(e.backup_dir))
    p2 = e2.get(prop.id)
    assert p2 is not None
    assert p2.stage == Stage.BACKED_UP
    assert p2.kind == "kb_entry"
    print("PASS test_state_persistence")


def test_status_and_list():
    e = _engine()
    e.propose("kb_entry", _kb_entry_payload(title="Status 1"))
    e.propose("word_map", {"a": "b"})
    st = e.status()
    assert st["proposals"] == 2
    assert st["by_stage"].get("proposed") == 2
    assert "kb_entry" in st["allowed_kinds"]
    lst = e.list_proposals()
    assert len(lst) == 2 and lst[0]["kind"] in ("kb_entry", "word_map")
    print("PASS test_status_and_list")


if __name__ == "__main__":
    test_full_happy_path()
    test_full_happy_path_with_backup_restore()
    test_reject_disallowed_kind()
    test_forbidden_topic_rejected()
    test_pipeline_order_enforced()
    test_word_map_full_pipeline()
    test_preference_pipeline_uses_memory()
    test_state_persistence()
    test_status_and_list()
    print("ALL LEARNING TESTS PASSED")
