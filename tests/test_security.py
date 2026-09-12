"""Tests for Phase 14 - Security + Reliability (temp dirs, no pollution)."""
import json
import sys
import tempfile
import os
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rolex.security.secrets import SecretsManager
from rolex.security.diagnostics import (CrashGuard, BackupManager,
                                        Diagnostics, DiagnosticsError)
from rolex.security import run_self_test, emergency_stop_active


def _sm() -> SecretsManager:
    tmp = tempfile.mkdtemp()
    return SecretsManager(
        path=os.path.join(tmp, "secrets.json"),
        master_key_path=os.path.join(tmp, ".master"))


# ------------------------------------------------------------- secrets
def test_secret_store_and_get_roundtrip():
    sm = _sm()
    sm.set("openai_key", "sk-test-1234567890")
    val = sm.get("openai_key")
    assert val == "sk-test-1234567890"
    print("PASS test_secret_store_and_get_roundtrip")


def test_secret_encrypted_at_rest():
    sm = _sm()
    sm.set("gemini_key", "super-secret-value-xyz")
    raw = sm.path.read_text(encoding="utf-8")
    assert "super-secret-value-xyz" not in raw    # never plain text
    assert "gemini_key" in raw                    # name visible (ok)
    rec = json.loads(raw)["gemini_key"]
    assert "nonce" in rec and "ct" in rec and "mac" in rec
    print("PASS test_secret_encrypted_at_rest")


def test_secret_tamper_detected():
    sm = _sm()
    sm.set("api", "value-abc")
    # flip one byte of ciphertext
    data = json.loads(sm.path.read_text(encoding="utf-8"))
    ct = bytearray(bytes.fromhex(data["api"]["ct"]))
    ct[0] ^= 0xFF
    data["api"]["ct"] = ct.hex()
    sm.path.write_text(json.dumps(data), encoding="utf-8")
    sm.load()
    try:
        sm.get("api")
        raise AssertionError("tampered secret must raise")
    except PermissionError:
        pass
    print("PASS test_secret_tamper_detected")


def test_secret_wrong_master_key_detected():
    sm = _sm()
    sm.set("api", "value-abc")
    # regenerate master key → mac mismatch
    sm.master_key_path.write_text("different-key-material",
                                  encoding="utf-8")
    sm.load()
    try:
        sm.get("api")
        raise AssertionError("wrong key must raise")
    except PermissionError:
        pass
    print("PASS test_secret_wrong_master_key_detected")


def test_secret_list_masked_and_delete():
    sm = _sm()
    sm.set("openai_key", "sk-1234567890")
    items = sm.list()
    assert items[0]["name"] == "openai_key"
    assert "1234567890" not in items[0]["preview"]   # masked
    assert sm.delete("openai_key") is True
    assert sm.get("openai_key") is None
    assert sm.delete("ghost") is False
    print("PASS test_secret_list_masked_and_delete")


def test_secret_sync_from_env():
    sm = _sm()
    os.environ["TEST_ROLEX_KEY_X"] = "env-value-123"
    try:
        n = sm.sync_from_env({"TEST_ROLEX_KEY_X": "imported_key"})
        assert n == 1 and sm.get("imported_key") == "env-value-123"
    finally:
        del os.environ["TEST_ROLEX_KEY_X"]
    assert sm.sync_from_env({"NO_SUCH_ENV": "x"}) == 0
    print("PASS test_secret_sync_from_env")


# ---------------------------------------------------------- crash guard
def test_crash_guard_success_clears_marker():
    tmp = tempfile.mkdtemp()
    g = CrashGuard(dir_path=tmp)
    with g.guard("test_op"):
        pass
    assert g.orphaned() == []            # cleared on success
    print("PASS test_crash_guard_success_clears_marker")


def test_crash_guard_crash_leaves_marker():
    tmp = tempfile.mkdtemp()
    g = CrashGuard(dir_path=tmp)
    try:
        with g.guard("risky_op"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    orphans = g.orphaned()
    assert len(orphans) == 1 and orphans[0]["operation"] == "risky_op"
    assert g.cleanup() == 1 and g.orphaned() == []
    print("PASS test_crash_guard_crash_leaves_marker")


# ------------------------------------------------------- backup/restore
def test_backup_create_and_restore_roundtrip():
    tmp = tempfile.mkdtemp()
    data = Path(tmp) / "data"
    (data / "memory").mkdir(parents=True)
    (data / "memory" / "rolex.db").write_bytes(b"sqlite-bytes")
    (data / "note.txt").write_text("important", encoding="utf-8")
    bm = BackupManager(backup_dir=str(Path(tmp) / "backups"),
                       data_dir=str(data), keep=5)
    z = bm.create("test")
    assert z.exists() and zipfile.is_zipfile(z)
    # destroy data, restore
    (data / "note.txt").unlink()
    n = bm.restore(z)
    assert n >= 2
    assert (data / "note.txt").read_text(encoding="utf-8") == "important"
    assert (data / "memory" / "rolex.db").read_bytes() == b"sqlite-bytes"
    print("PASS test_backup_create_and_restore_roundtrip")


def test_backup_prune_keeps_limit():
    tmp = tempfile.mkdtemp()
    bm = BackupManager(backup_dir=str(Path(tmp) / "bk"),
                       data_dir=str(Path(tmp) / "d"), keep=3)
    Path(Path(tmp) / "d").mkdir()
    for i in range(6):
        (Path(tmp) / "d" / f"f{i}.txt").write_text("x", encoding="utf-8")
        bm.create(f"n{i}")
    assert len(bm.list_backups()) == 3    # pruned to keep
    print("PASS test_backup_prune_keeps_limit")


def test_backup_restore_missing_raises():
    tmp = tempfile.mkdtemp()
    bm = BackupManager(backup_dir=str(Path(tmp) / "bk"),
                       data_dir=str(Path(tmp) / "d"))
    try:
        bm.restore(Path(tmp) / "nope.zip")
        raise AssertionError("missing backup must raise")
    except DiagnosticsError:
        pass
    print("PASS test_backup_restore_missing_raises")


# ----------------------------------------------------------- diagnostics
def test_diagnostics_self_test_scores():
    d = Diagnostics()
    r = d.self_test()
    assert r["total"] >= 10
    assert 0 <= r["score"] <= 100
    assert r["verdict"] in ("HEALTHY", "DEGRADED", "CRITICAL")
    names = {c["check"] for c in r["checks"]}
    for expected in ("python", "knowledge_base", "math_engine",
                     "audit_log", "crash_markers", "sqlite_memory"):
        assert expected in names
    print("PASS test_diagnostics_self_test_scores")


def test_diagnostics_recovery_report():
    tmp = tempfile.mkdtemp()
    d = Diagnostics(crash_dir=tmp)
    d.crash.mark("interrupted_op", detail="crash simulation")
    rep = d.recover()
    assert rep["orphaned_markers"] == 1
    assert rep["cleaned"] == 1
    assert "interrupted_op" in rep["operations"]
    # second recover: nothing left
    rep2 = d.recover()
    assert rep2["orphaned_markers"] == 0
    print("PASS test_diagnostics_recovery_report")


def test_diagnostics_full_report_and_public_api():
    d = Diagnostics()
    rep = d.full_report()
    assert "checks" in rep and "backups" in rep
    assert "crash_recovery" in rep and "rolex_version" in rep
    st = run_self_test()
    assert st["score"] >= 0
    assert emergency_stop_active() is False
    print("PASS test_diagnostics_full_report_and_public_api")


if __name__ == "__main__":
    test_secret_store_and_get_roundtrip()
    test_secret_encrypted_at_rest()
    test_secret_tamper_detected()
    test_secret_wrong_master_key_detected()
    test_secret_list_masked_and_delete()
    test_secret_sync_from_env()
    test_crash_guard_success_clears_marker()
    test_crash_guard_crash_leaves_marker()
    test_backup_create_and_restore_roundtrip()
    test_backup_prune_keeps_limit()
    test_backup_restore_missing_raises()
    test_diagnostics_self_test_scores()
    test_diagnostics_recovery_report()
    test_diagnostics_full_report_and_public_api()
    print("ALL SECURITY/RELIABILITY TESTS PASSED")
