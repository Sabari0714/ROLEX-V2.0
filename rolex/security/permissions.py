"""Rolex Permissions (Phase 11/14 core) \u2014 every sensitive action gated.

Permission levels:
  allow    \u2192 always allowed (read-only safe ops)
  ask      \u2192 requires explicit user approval per action
  deny     \u2192 never allowed (hard-blocked, no override)

Persisted to data/permissions.json so the user can change them later.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from ..config import CONFIG
from ..errors import PermissionDenied
from ..logging_setup import get_logger

log = get_logger("permissions")


# defaults: read-only = allow, anything that changes the world = ask
DEFAULT_PERMISSIONS: dict[str, str] = {
    # filesystem
    "fs.read":          "allow",
    "fs.write":         "ask",
    "fs.delete":        "deny",
    "fs.list":          "allow",
    # documents
    "doc.read":         "allow",
    "doc.create":       "ask",
    "doc.edit":         "ask",
    # coding tools
    "code.run":         "ask",
    "code.search":      "allow",
    # web
    "web.fetch":        "allow",
    "web.search":       "allow",
    # apis
    "api.call":         "ask",
    # device
    "device.info":      "allow",
    "device.notify":    "allow",
    # package install \u2014 always gated hard
    "package.install":  "ask",
    # memory/learning
    "memory.write":     "allow",
    "memory.forget":    "ask",
    "learning.apply":   "ask",
    # system
    "system.command":   "deny",
    "system.shutdown":  "deny",
}


class PermissionSystem:
    """Checks + persists per-action permission rules."""

    def __init__(self, path: str | None = None):
        self.path = Path(path or Path(CONFIG.DATA_DIR) / "permissions.json")
        self.rules: dict[str, str] = {}
        self._approvals: dict[str, float] = {}   # session approvals
        self.load()

    # ------------------------------------------------------------- load
    def load(self) -> None:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.rules = data.get("rules", {})
            except Exception as e:  # noqa: BLE001
                log.error("permissions load failed: %s", e)
                self.rules = {}
        # fill defaults for anything missing
        for k, v in DEFAULT_PERMISSIONS.items():
            self.rules.setdefault(k, v)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {"rules": self.rules, "saved": time.time()},
            ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------ check
    def level(self, action: str) -> str:
        """allow | ask | deny for an action key."""
        return self.rules.get(action, "ask")   # unknown \u2192 ask (safe)

    def check(self, action: str, session_approved: bool = False) -> bool:
        """True if the action may proceed."""
        lvl = self.level(action)
        if lvl == "allow":
            return True
        if lvl == "ask":
            if session_approved:
                return True
            raise PermissionDenied(
                f"action '{action}' needs your approval (level: ask)")
        raise PermissionDenied(
            f"action '{action}' is permanently blocked (level: deny)")

    def require(self, action: str, session_approved: bool = False) -> None:
        """Raise PermissionDenied unless allowed."""
        self.check(action, session_approved)

    # ------------------------------------------------------------ modify
    def set(self, action: str, level: str, save: bool = True) -> None:
        if level not in ("allow", "ask", "deny"):
            raise ValueError(f"invalid level {level!r}")
        self.rules[action] = level
        if save:
            self.save()
        log.info("permission %s -> %s", action, level)

    def approve_session(self, action: str) -> None:
        """User approved this action for the current session."""
        self._approvals[action] = time.time()
        log.info("session approval granted: %s", action)

    def has_session_approval(self, action: str) -> bool:
        return action in self._approvals

    def revoke_session(self, action: str | None = None) -> None:
        if action is None:
            self._approvals.clear()
        else:
            self._approvals.pop(action, None)

    def report(self) -> dict:
        return {"rules": dict(self.rules),
                "session_approved": sorted(self._approvals)}


PERMISSIONS = PermissionSystem()
