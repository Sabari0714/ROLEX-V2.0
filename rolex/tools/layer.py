"""Rolex Tools & Action Layer (Phase 11) \u2014 permission-gated actions.

Every tool call:
  1. permission check (allow / ask / deny)
  2. execute
  3. audit record

Tools: filesystem, documents, coding, web, APIs, device info,
controlled package install (pip --dry-run style proposal only).
NO shell execution by design (system.command = deny).
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from ..config import CONFIG
from ..errors import PermissionDenied, RolexError
from ..logging_setup import get_logger
from ..security.audit import AUDIT
from ..security.permissions import PERMISSIONS, PermissionSystem

log = get_logger("tools")

# paths Rolex may never touch even with permission
_FORBIDDEN_PATH_PATTERNS = [
    r"/etc/", r"/root/", r"/sys/", r"/proc/",
    r"\.ssh/", r"\.aws/", r"\.env$", r"\.git/",
    r"rolex/security/", r"rolex/config\.py$", r"data/EMERGENCY_STOP",
    r"reference_old/",
]

_MAX_WEB_BYTES = 2 * 1024 * 1024      # 2 MB safety cap
_MAX_FILE_BYTES = 10 * 1024 * 1024    # 10 MB read cap


class ToolError(RolexError):
    """Tool execution failure."""


@dataclass
class ToolResult:
    ok: bool
    action: str
    data: object = None
    detail: str = ""

    def __str__(self) -> str:  # noqa: D105
        state = "OK" if self.ok else "DENIED/FAILED"
        return f"[{self.action}] {state} {self.detail[:80]}"


class ToolLayer:
    """All Rolex actions live here, each gated + audited."""

    def __init__(self, perms: PermissionSystem | None = None,
                 audit=None):
        self.perms = perms or PERMISSIONS
        self.audit = audit or AUDIT

    # ---------------------------------------------------------- gating
    def _gate(self, action: str, approved: set[str] | None = None
              ) -> bool:
        session_ok = bool(approved and action in approved)
        try:
            self.perms.require(action, session_approved=session_ok)
            return True
        except PermissionDenied as e:
            self.audit.record(action, result="denied",
                              detail=str(e), actor="rolex")
            return False

    def _safe_path(self, p: str | Path) -> Path:
        """Reject forbidden paths, resolve to workspace-relative."""
        raw = str(p)
        for pat in _FORBIDDEN_PATH_PATTERNS:
            if re.search(pat, raw):
                raise ToolError(f"path not allowed: {raw}")
        path = Path(raw)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    # ------------------------------------------------------- filesystem
    def fs_read(self, path: str, approved: set[str] | None = None
                ) -> ToolResult:
        if not self._gate("fs.read", approved):
            return ToolResult(False, "fs.read", detail="permission denied")
        try:
            target = self._safe_path(path)
            if target.stat().st_size > _MAX_FILE_BYTES:
                raise ToolError("file too large (>10MB)")
            text = target.read_text(encoding="utf-8", errors="replace")
            self.audit.record("fs.read", str(target))
            return ToolResult(True, "fs.read", data=text)
        except (ToolError, OSError) as e:
            self.audit.record("fs.read", str(path), result="error",
                              detail=str(e))
            return ToolResult(False, "fs.read", detail=str(e))

    def fs_write(self, path: str, content: str,
                 approved: set[str] | None = None) -> ToolResult:
        if not self._gate("fs.write", approved):
            return ToolResult(False, "fs.write", detail="permission denied")
        try:
            target = self._safe_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            self.audit.record("fs.write", str(target))
            return ToolResult(True, "fs.write",
                              detail=f"wrote {len(content)} chars")
        except (ToolError, OSError) as e:
            self.audit.record("fs.write", str(path), result="error",
                              detail=str(e))
            return ToolResult(False, "fs.write", detail=str(e))

    def fs_list(self, path: str = ".", approved: set[str] | None = None
                ) -> ToolResult:
        if not self._gate("fs.list", approved):
            return ToolResult(False, "fs.list", detail="permission denied")
        try:
            target = self._safe_path(path)
            if not target.is_dir():
                raise ToolError(f"not a directory: {path}")
            items = sorted(
                (x.name + ("/" if x.is_dir() else ""))
                for x in target.iterdir())
            self.audit.record("fs.list", str(target))
            return ToolResult(True, "fs.list", data=items)
        except (ToolError, OSError) as e:
            return ToolResult(False, "fs.list", detail=str(e))

    def fs_delete(self, path: str, approved: set[str] | None = None
                  ) -> ToolResult:
        if not self._gate("fs.delete", approved):
            return ToolResult(False, "fs.delete", detail="permission denied")
        try:
            target = self._safe_path(path)
            if target.is_dir():
                raise ToolError("directory delete blocked")
            target.unlink()
            self.audit.record("fs.delete", str(target))
            return ToolResult(True, "fs.delete")
        except (ToolError, OSError) as e:
            self.audit.record("fs.delete", str(path), result="error",
                              detail=str(e))
            return ToolResult(False, "fs.delete", detail=str(e))

    # -------------------------------------------------------- documents
    def doc_create(self, path: str, content: str, doc_type: str = "txt",
                   approved: set[str] | None = None) -> ToolResult:
        """Create a document (txt/md/json/csv...)."""
        if not self._gate("doc.create", approved):
            return ToolResult(False, "doc.create", detail="denied")
        try:
            target = self._safe_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            if doc_type == "json":
                json.dumps(json.loads(content))  # validate
            target.write_text(content, encoding="utf-8")
            self.audit.record("doc.create", str(target))
            return ToolResult(True, "doc.create", data=str(target))
        except (ToolError, OSError, ValueError) as e:
            self.audit.record("doc.create", str(path), result="error",
                              detail=str(e))
            return ToolResult(False, "doc.create", detail=str(e))

    # ------------------------------------------------------------ code
    def code_search(self, directory: str, pattern: str,
                    approved: set[str] | None = None) -> ToolResult:
        """Grep-like code search (read-only)."""
        if not self._gate("code.search", approved):
            return ToolResult(False, "code.search", detail="denied")
        try:
            base = self._safe_path(directory)
            rx = re.compile(pattern)
            hits: list[str] = []
            for f in base.rglob("*.py"):
                s = str(f)
                if "reference_old" in s or "/.git/" in s:
                    continue
                try:
                    for i, line in enumerate(
                            f.read_text(encoding="utf-8",
                                        errors="replace").splitlines(), 1):
                        if rx.search(line):
                            hits.append(f"{f.relative_to(base)}:{i}: "
                                        f"{line.strip()[:100]}")
                            if len(hits) >= 50:
                                raise StopIteration
                except StopIteration:
                    break
            self.audit.record("code.search", str(base))
            return ToolResult(True, "code.search", data=hits)
        except (ToolError, OSError, re.error) as e:
            return ToolResult(False, "code.search", detail=str(e))

    def code_run(self, code: str,
                 approved: set[str] | None = None) -> ToolResult:
        """Sandboxed expression evaluation (NOT shell, NOT exec)."""
        if not self._gate("code.run", approved):
            return ToolResult(False, "code.run", detail="denied")
        try:
            # reuse Rolex's AST-safe evaluator (same as math engine)
            from ..math_engine.evaluator import safe_eval
            value = safe_eval(code)
            self.audit.record("code.run", "sandbox-eval")
            return ToolResult(True, "code.run", data=value)
        except Exception as e:  # noqa: BLE001
            self.audit.record("code.run", result="error", detail=str(e))
            return ToolResult(False, "code.run", detail=str(e))

    # ------------------------------------------------------------- web
    def web_fetch(self, url: str, approved: set[str] | None = None
                  ) -> ToolResult:
        if not self._gate("web.fetch", approved):
            return ToolResult(False, "web.fetch", detail="denied")
        try:
            if not url.lower().startswith(("http://", "https://")):
                raise ToolError("only http(s) URLs allowed")
            req = urllib.request.Request(
                url, headers={"User-Agent": "ROLEX-AI/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read(_MAX_WEB_BYTES)
            text = raw.decode("utf-8", errors="replace")
            self.audit.record("web.fetch", url)
            return ToolResult(True, "web.fetch", data=text)
        except (ToolError, OSError, ValueError) as e:
            self.audit.record("web.fetch", url, result="error",
                              detail=str(e))
            return ToolResult(False, "web.fetch", detail=str(e))

    # ------------------------------------------------------------- api
    def api_call(self, url: str, method: str = "GET",
                 payload: dict | None = None,
                 headers: dict | None = None,
                 approved: set[str] | None = None) -> ToolResult:
        if not self._gate("api.call", approved):
            return ToolResult(False, "api.call", detail="denied")
        try:
            if not url.lower().startswith(("http://", "https://")):
                raise ToolError("only http(s) APIs allowed")
            data = json.dumps(payload).encode() if payload else None
            hdrs = {"User-Agent": "ROLEX-AI/1.0"}
            if headers:
                hdrs.update(headers)
            req = urllib.request.Request(url, data=data, method=method,
                                         headers=hdrs)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read(_MAX_WEB_BYTES)
            text = raw.decode("utf-8", errors="replace")
            self.audit.record("api.call", url)
            return ToolResult(True, "api.call", data=text)
        except (ToolError, OSError, ValueError) as e:
            self.audit.record("api.call", url, result="error",
                              detail=str(e))
            return ToolResult(False, "api.call", detail=str(e))

    # ----------------------------------------------------------- device
    def device_info(self, approved: set[str] | None = None) -> ToolResult:
        if not self._gate("device.info", approved):
            return ToolResult(False, "device.info", detail="denied")
        import platform
        info = {
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor() or "unknown",
        }
        self.audit.record("device.info")
        return ToolResult(True, "device.info", data=info)

    # -------------------------------------------------------- packages
    def package_install(self, name: str,
                        approved: set[str] | None = None) -> ToolResult:
        """CONTROLLED install: proposes, records, but never runs pip
        automatically. Actual install needs the user's own terminal
        (or a future explicit allow rule + confirmation)."""
        if not self._gate("package.install", approved):
            return ToolResult(False, "package.install", detail="denied")
        name_clean = re.sub(r"[^A-Za-z0-9._-]", "", name)
        if not name_clean or name_clean != name:
            self.audit.record("package.install", name, result="error",
                              detail="invalid package name")
            return ToolResult(False, "package.install",
                              detail="invalid package name")
        # record the request; execution is a user decision
        proposal = {
            "package": name_clean,
            "command": f"pip install {name_clean}",
            "status": "proposed",
            "note": "run this yourself, or approve via config",
        }
        self.audit.record("package.install", name_clean,
                          detail="proposed only")
        return ToolResult(True, "package.install", data=proposal)

    # ---------------------------------------------------------- report
    def tool_report(self) -> dict:
        return {"permissions": self.perms.report(),
                "forbidden_paths": _FORBIDDEN_PATH_PATTERNS,
                "audit_stats": self.audit.stats()}


TOOLS = ToolLayer()
