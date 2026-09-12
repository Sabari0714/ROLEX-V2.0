"""Tests for Phase 11 - Tools & Action Layer + Security core.

Isolation rules:
  - PermissionSystem / AuditLog / ToolLayer all use tempfile paths
  - emergency-stop test patches Config.STOP_FLAG + rolex.security.AUDIT
  - real data/ directory is never touched
"""
import json
import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rolex.errors import PermissionDenied
from rolex.security.permissions import (
    PermissionSystem, DEFAULT_PERMISSIONS, PERMISSIONS)
from rolex.security.audit import AuditLog, AUDIT
from rolex.security import (
    emergency_stop_active, activate_emergency_stop, clear_emergency_stop)
from rolex.tools.layer import ToolLayer, ToolResult, ToolError, TOOLS


def _perms() -> PermissionSystem:
    tmp = tempfile.mkdtemp()
    return PermissionSystem(path=os.path.join(tmp, "permissions.json"))


def _audit() -> AuditLog:
    tmp = tempfile.mkdtemp()
    return AuditLog(path=os.path.join(tmp, "audit.jsonl"))


def _tools() -> ToolLayer:
    return ToolLayer(perms=_perms(), audit=_audit())


# ------------------------------------------------------- permissions
def test_permission_allow_passes():
    p = _perms()
    assert p.check("fs.read") is True
    p.require("fs.read")          # no exception
    print("PASS test_permission_allow_passes")


def test_permission_ask_requires_approval():
    p = _perms()
    try:
        p.check("fs.write")
        raise AssertionError("fs.write should need approval")
    except PermissionDenied:
        pass
    # session approval unlocks it
    p.approve_session("fs.write")
    assert p.check("fs.write", session_approved=True) is True
    assert p.has_session_approval("fs.write") is True
    p.revoke_session("fs.write")
    assert p.has_session_approval("fs.write") is False
    print("PASS test_permission_ask_requires_approval")


def test_permission_deny_always_blocks():
    p = _perms()
    for approved in (False, True):
        try:
            p.check("fs.delete", session_approved=approved)
            raise AssertionError("fs.delete must stay blocked")
        except PermissionDenied:
            pass
    print("PASS test_permission_deny_always_blocks")


def test_permission_unknown_defaults_to_ask():
    p = _perms()
    assert p.level("totally.unknown.action") == "ask"
    try:
        p.check("totally.unknown.action")
        raise AssertionError("unknown action must ask")
    except PermissionDenied:
        pass
    print("PASS test_permission_unknown_defaults_to_ask")


def test_permission_set_persists_and_reloads():
    p = _perms()
    p.set("fs.write", "allow")
    p2 = PermissionSystem(path=str(p.path))
    assert p2.level("fs.write") == "allow"
    # invalid level rejected
    try:
        p.set("fs.write", "maybe")
        raise AssertionError("invalid level must be rejected")
    except ValueError:
        pass
    # defaults filled in
    for k in DEFAULT_PERMISSIONS:
        assert k in p.rules
    print("PASS test_permission_set_persists_and_reloads")


# ------------------------------------------------------------- audit
def test_audit_record_tail_search_stats():
    a = _audit()
    a.record("fs.read", "a.txt")
    a.record("fs.write", "b.txt", result="denied")
    a.record("fs.write", "c.txt")
    tail = a.tail(3)
    assert len(tail) == 3
    assert [e["seq"] for e in tail] == [0, 1, 2]   # seq increments
    denied = a.search(action="fs.write", result="denied")
    assert len(denied) == 1 and denied[0]["target"] == "b.txt"
    stats = a.stats()
    assert stats["events"] == 3
    assert stats["by_result"]["denied"] == 1
    assert stats["by_result"]["ok"] == 2
    print("PASS test_audit_record_tail_search_stats")


# --------------------------------------------------------------- tools
def test_tool_gate_denied_is_audited():
    t = _tools()
    r = t.fs_write("notes.txt", "hi")           # fs.write = ask, not approved
    assert r.ok is False and "permission" in r.detail.lower()
    denied = t.audit.search(action="fs.write", result="denied")
    assert len(denied) == 1
    print("PASS test_tool_gate_denied_is_audited")


def test_tool_gate_approved_set_allows():
    t = _tools()
    r = t.fs_write("notes.txt", "hello rolex", approved={"fs.write"})
    assert r.ok is True
    r2 = t.fs_read("notes.txt")
    assert r2.ok is True and r2.data == "hello rolex"
    print("PASS test_tool_gate_approved_set_allows")


def test_tool_forbidden_paths_rejected():
    t = _tools()
    for bad in (".env", "reference_old/leak.py", "rolex/security/permissions.py",
                "/etc/passwd", "home/.ssh/id_rsa"):
        try:
            t._safe_path(bad)
            raise AssertionError(f"forbidden path allowed: {bad}")
        except ToolError:
            pass
    print("PASS test_tool_forbidden_paths_rejected")


def test_tool_fs_read_write_list():
    tmp = tempfile.mkdtemp()
    t = _tools()
    p = os.path.join(tmp, "demo.txt")
    assert t.fs_write(p, "line1\nline2", approved={"fs.write"}).ok is True
    r = t.fs_read(p)
    assert r.ok is True and "line2" in r.data
    r = t.fs_list(tmp)
    assert r.ok is True and "demo.txt" in r.data
    # missing file -> clean failure, not crash
    r = t.fs_read(os.path.join(tmp, "nope.txt"))
    assert r.ok is False
    print("PASS test_tool_fs_read_write_list")


def test_tool_fs_delete_denied_by_default_and_dir_blocked():
    t = _tools()
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "x.txt")
    Path(p).write_text("x", encoding="utf-8")
    # default fs.delete = deny
    r = t.fs_delete(p)
    assert r.ok is False and Path(p).exists()
    # even when allowed, directories are blocked
    t.perms.set("fs.delete", "allow", save=False)
    r = t.fs_delete(tmp)
    assert r.ok is False and Path(tmp).is_dir()
    print("PASS test_tool_fs_delete_denied_by_default_and_dir_blocked")


def test_tool_code_run_safe_eval_only():
    t = _tools()
    r = t.code_run("2**10", approved={"code.run"})
    assert r.ok is True and r.data == 1024
    # shell / import injection never passes the AST evaluator
    r = t.code_run("__import__('os').system('ls')", approved={"code.run"})
    assert r.ok is False
    r = t.code_run("print('hi')", approved={"code.run"})
    assert r.ok is False        # statements are not expressions
    print("PASS test_tool_code_run_safe_eval_only")


def test_tool_code_search_finds_pattern():
    tmp = tempfile.mkdtemp()
    Path(tmp, "sample.py").write_text(
        "def rolex_secret():\n    return 'GURU'\n", encoding="utf-8")
    t = _tools()
    r = t.code_search(tmp, "rolex_secret")
    assert r.ok is True and len(r.data) == 1 and "sample.py:1" in r.data[0]
    # bad regex -> clean failure
    r = t.code_search(tmp, "(")
    assert r.ok is False
    print("PASS test_tool_code_search_finds_pattern")


def test_tool_doc_create_json_validated():
    tmp = tempfile.mkdtemp()
    t = _tools()
    good = os.path.join(tmp, "data.json")
    r = t.doc_create(good, '{"a": 1}', doc_type="json",
                     approved={"doc.create"})
    assert r.ok is True
    bad = os.path.join(tmp, "bad.json")
    r = t.doc_create(bad, '{"a": ', doc_type="json",
                     approved={"doc.create"})
    assert r.ok is False and not Path(bad).exists()
    print("PASS test_tool_doc_create_json_validated")


def test_tool_web_and_api_schemes_limited():
    t = _tools()
    r = t.web_fetch("ftp://example.com/file")
    assert r.ok is False and "http" in r.detail.lower()
    r = t.api_call("file:///etc/passwd")
    assert r.ok is False
    # unreachable host -> clean failure (no network dependency)
    r = t.web_fetch("http://127.0.0.1:9/none")
    assert r.ok is False
    print("PASS test_tool_web_and_api_schemes_limited")


def test_tool_package_install_proposal_only():
    t = _tools()
    r = t.package_install("requests", approved={"package.install"})
    assert r.ok is True
    proposal = r.data
    assert proposal["status"] == "proposed"
    assert "pip install requests" == proposal["command"]
    # invalid name (approved, so it reaches the name check) -> clean failure
    r = t.package_install("evil; rm -rf /", approved={"package.install"})
    assert r.ok is False
    # audit recorded both attempts (proposal + invalid-name error)
    install_logs = t.audit.search(action="package.install")
    assert len(install_logs) == 2
    assert {e["result"] for e in install_logs} == {"ok", "error"}
    print("PASS test_tool_package_install_proposal_only")


def test_tool_device_info_and_report():
    t = _tools()
    r = t.device_info()
    assert r.ok is True and "python" in r.data
    report = t.tool_report()
    assert "permissions" in report and "audit_stats" in report
    assert "reference_old/" in str(report["forbidden_paths"])
    print("PASS test_tool_device_info_and_report")


# ------------------------------------------------------- emergency stop
def test_emergency_stop_flag_cycle():
    import rolex.security as sec
    from rolex.config import Config
    tmp = tempfile.mkdtemp()
    orig_flag, orig_audit = Config.STOP_FLAG, sec.AUDIT
    Config.STOP_FLAG = Path(tmp) / "EMERGENCY_STOP"
    sec.AUDIT = AuditLog(path=os.path.join(tmp, "audit.jsonl"))
    try:
        assert sec.emergency_stop_active() is False
        sec.activate_emergency_stop()
        assert sec.emergency_stop_active() is True
        assert Path(Config.STOP_FLAG).exists()
        sec.clear_emergency_stop()
        assert sec.emergency_stop_active() is False
        assert not Path(Config.STOP_FLAG).exists()
    finally:
        sec.AUDIT = orig_audit
        Config.STOP_FLAG = orig_flag
    print("PASS test_emergency_stop_flag_cycle")


# ---------------------------------------------------------- singletons
def test_security_and_tool_singletons_importable():
    assert PERMISSIONS is not None and "fs.read" in PERMISSIONS.rules
    assert AUDIT is not None
    assert isinstance(TOOLS, ToolLayer)
    assert emergency_stop_active() is False   # real flag must be absent
    print("PASS test_security_and_tool_singletons_importable")


if __name__ == "__main__":
    test_permission_allow_passes()
    test_permission_ask_requires_approval()
    test_permission_deny_always_blocks()
    test_permission_unknown_defaults_to_ask()
    test_permission_set_persists_and_reloads()
    test_audit_record_tail_search_stats()
    test_tool_gate_denied_is_audited()
    test_tool_gate_approved_set_allows()
    test_tool_forbidden_paths_rejected()
    test_tool_fs_read_write_list()
    test_tool_fs_delete_denied_by_default_and_dir_blocked()
    test_tool_code_run_safe_eval_only()
    test_tool_code_search_finds_pattern()
    test_tool_doc_create_json_validated()
    test_tool_web_and_api_schemes_limited()
    test_tool_package_install_proposal_only()
    test_tool_device_info_and_report()
    test_emergency_stop_flag_cycle()
    test_security_and_tool_singletons_importable()
    print("ALL TOOLS/SECURITY TESTS PASSED")
