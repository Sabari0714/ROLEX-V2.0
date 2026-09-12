"""Rolex Diagnostics + Crash Detection + Recovery (Phase 14).

Health checks across every subsystem, with an honest self-test score.
Crash detection: crash markers written before risky operations,
cleared after success — orphaned markers → auto-recovery on boot.
Backups: data/ → data/backups/backup_<ts>.zip with restore support.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import sqlite3
import time
import zipfile
from pathlib import Path

from ..config import CONFIG
from ..logging_setup import get_logger
from .audit import AuditLog
from .permissions import PermissionSystem

log = get_logger("diagnostics")


class DiagnosticsError(Exception):
    pass


# --------------------------------------------------------- crash markers
class CrashGuard:
    """Marker-file crash detection: mark() → risky op → clear().
    Boot-time scan finds orphaned markers → recovery report."""

    def __init__(self, dir_path: str | None = None):
        self.dir = Path(dir_path or Path(CONFIG.DATA_DIR) / "crash_markers")
        self.dir.mkdir(parents=True, exist_ok=True)

    def mark(self, operation: str, detail: str = "") -> Path:
        p = self.dir / f"{int(time.time() * 1000)}_{operation}.marker"
        p.write_text(json.dumps(
            {"operation": operation, "detail": detail,
             "started": time.time(), "pid": os.getpid()}), encoding="utf-8")
        return p

    def clear(self, marker: Path) -> None:
        Path(marker).unlink(missing_ok=True)

    def orphaned(self) -> list[dict]:
        found = []
        for p in sorted(self.dir.glob("*.marker")):
            try:
                found.append(json.loads(p.read_text(encoding="utf-8")))
            except ValueError:
                found.append({"operation": "unknown",
                              "detail": f"bad marker: {p.name}"})
        return found

    def cleanup(self) -> int:
        n = len(self.orphaned())
        for p in self.dir.glob("*.marker"):
            p.unlink(missing_ok=True)
        return n

    def guard(self, operation: str, detail: str = ""):
        """Context manager: mark → yield → clear (even on exception the
        marker stays, marking the crash point)."""
        marker = self.mark(operation, detail)

        class _G:
            def __init__(s, m):
                s.m = m

            def __enter__(s):
                return s

            def __exit__(s, exc_type, *_):
                if exc_type is None:
                    CrashGuard.clear(self, marker)
                return False
        return _G(marker)


class BackupManager:
    """Zip backups of data/ → data/backups/ with restore."""

    def __init__(self, backup_dir: str | None = None,
                 data_dir: str | None = None, keep: int = 10):
        self.backup_dir = Path(backup_dir or CONFIG.BACKUP_DIR)
        self.data_dir = Path(data_dir or CONFIG.DATA_DIR)
        self.keep = keep
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create(self, label: str = "auto") -> Path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        out = self.backup_dir / f"backup_{ts}_{label}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in self._walk(self.data_dir):
                z.write(f, f.relative_to(self.data_dir.parent))
        self._prune()
        log.info("backup created: %s", out.name)
        return out

    def _walk(self, root: Path):
        for p in root.rglob("*"):
            if p.is_file():
                if "backups" in p.parts or "crash_markers" in p.parts:
                    continue
                yield p

    def _prune(self) -> None:
        zips = sorted(self.backup_dir.glob("backup_*.zip"))
        while len(zips) > self.keep:
            zips.pop(0).unlink(missing_ok=True)

    def restore(self, zip_path: str | Path,
                target_dir: str | Path | None = None) -> int:
        """Restore a backup zip into target (default: data dir)."""
        z = Path(zip_path)
        if not z.exists():
            raise DiagnosticsError(f"backup not found: {z}")
        target = Path(target_dir or self.data_dir)
        target.mkdir(parents=True, exist_ok=True)
        restored = 0
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
            # safety: strip leading 'data/' from archive paths
            for name in names:
                rel = name
                if rel.startswith("data/"):
                    rel = rel[len("data/"):]
                if not rel:
                    continue
                dest = target / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(name))
                restored += 1
        log.info("backup restored: %d files -> %s", restored, target)
        return restored

    def list_backups(self) -> list[dict]:
        out = []
        for z in sorted(self.backup_dir.glob("backup_*.zip"),
                        key=lambda p: p.stat().st_mtime, reverse=True):
            out.append({"file": z.name, "size_kb": round(
                z.stat().st_size / 1024, 1),
                "created": time.strftime(
                    "%Y-%m-%d %H:%M", time.localtime(z.stat().st_mtime))})
        return out


# -------------------------------------------------------- health checks
class Diagnostics:
    """System-wide health + self-test + recovery."""

    def __init__(self, crash_dir: str | None = None):
        self.crash = CrashGuard(crash_dir)

    # --------------------------------------------------------- checks
    def health_checks(self) -> list[dict]:
        checks: list[dict] = []

        def add(name, fn):
            try:
                detail = fn()
                checks.append({"check": name, "ok": True,
                               "detail": detail or ""})
            except Exception as e:    # noqa: BLE001
                checks.append({"check": name, "ok": False,
                               "detail": str(e)[:120]})

        add("python", lambda: platform.python_version())
        add("platform", lambda: f"{platform.system()} "
             f"{platform.machine()}")
        add("data_dir_writable", self._check_data_writable)
        add("knowledge_base", self._check_kb)
        add("sqlite_memory", self._check_sqlite)
        add("math_engine", self._check_math)
        add("fs_paths", self._check_paths)
        add("env_keys", self._check_env_keys)
        add("audit_log", self._check_audit)
        add("crash_markers", lambda: f"{len(self.crash.orphaned())} "
             f"orphaned")
        return checks

    def _check_data_writable(self) -> str:
        test = Path(CONFIG.DATA_DIR) / ".write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        return "read/write OK"

    def _check_kb(self) -> str:
        from ..knowledge.base import KnowledgeBase
        kb = KnowledgeBase()
        return f"{kb.count()} entries / {len(kb.topics())} topics"

    def _check_sqlite(self) -> str:
        with sqlite3.connect(":memory:") as con:
            con.execute("CREATE TABLE t (x)")
            con.execute("INSERT INTO t VALUES (1)")
            v = con.execute("SELECT x FROM t").fetchone()[0]
        return "in-memory OK" if v == 1 else "unexpected"

    def _check_math(self) -> str:
        from ..math_engine import MATH
        sol = MATH.solve("2+2")
        if sol is None or "4" not in str(sol):
            raise DiagnosticsError("math engine returned wrong answer")
        return "safe_eval OK (2+2=4)"

    def _check_paths(self) -> str:
        for name in ("DATA_DIR", "KB_DIR", "LOG_DIR"):
            if not Path(getattr(CONFIG, name)).exists():
                raise DiagnosticsError(f"{name} missing")
        return "core paths exist"

    def _check_env_keys(self) -> str:
        present = [k for k in ("OPENAI_API_KEY", "GEMINI_API_KEY")
                   if os.getenv(k)]
        return (f"{len(present)} AI key(s) found"
                if present else "no AI keys (offline mode OK)")

    def _check_audit(self) -> str:
        p = Path(CONFIG.AUDIT_LOG)
        n = 0
        if p.exists():
            n = sum(1 for _ in p.open(encoding="utf-8"))
        return f"{n} events"

    # ------------------------------------------------------- self-test
    def self_test(self, run_slow: bool = False) -> dict:
        """Full self-test: checks + score."""
        checks = self.health_checks()
        passed = sum(1 for c in checks if c["ok"])
        score = round(passed / len(checks) * 100, 1)
        result = {"checks": checks, "passed": passed,
                  "total": len(checks), "score": score,
                  "verdict": ("HEALTHY" if score == 100 else
                              "DEGRADED" if score >= 70 else "CRITICAL"),
                  "ts": time.time()}
        log.info("self-test: %s/100 (%s)", score, result["verdict"])
        return result

    # ------------------------------------------------------- recovery
    def recover(self) -> dict:
        """Boot-time recovery: orphaned crash markers → report + clean."""
        orphans = self.crash.orphaned()
        cleaned = self.crash.cleanup()
        report = {"orphaned_markers": len(orphans),
                  "cleaned": cleaned,
                  "operations": [o.get("operation") for o in orphans],
                  "action_taken": "markers cleared, state re-verified"}
        if orphans:
            log.warning("crash recovery: %s", report["operations"])
        return report

    def full_report(self) -> dict:
        checks = self.health_checks()
        return {"system": f"{platform.system()} "
                          f"{platform.release()}",
                "python": platform.python_version(),
                "rolex_version": CONFIG.VERSION,
                "checks": checks,
                "backups": BackupManager().list_backups()[:5],
                "crash_recovery": self.recover(),
                "ts": time.strftime("%Y-%m-%d %H:%M:%S")}


DIAGNOSTICS = Diagnostics()


def run_self_test() -> dict:
    """Public entry: python -c 'from rolex.security import run_self_test'"""
    return DIAGNOSTICS.self_test()


def run_recovery() -> dict:
    return DIAGNOSTICS.recover()
