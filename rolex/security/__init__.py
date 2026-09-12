"""Rolex Security (Phase 14) — permissions + audit + secrets +
emergency stop + diagnostics/crash-recovery/backups."""
from .permissions import PermissionSystem, DEFAULT_PERMISSIONS, PERMISSIONS
from .audit import AuditLog, AUDIT
from .secrets import SecretsManager, SECRETS
from .diagnostics import (Diagnostics, CrashGuard, BackupManager,
                          DIAGNOSTICS, run_self_test, run_recovery)

__all__ = ["PermissionSystem", "DEFAULT_PERMISSIONS", "PERMISSIONS",
           "AuditLog", "AUDIT", "SecretsManager", "SECRETS",
           "Diagnostics", "CrashGuard", "BackupManager", "DIAGNOSTICS",
           "run_self_test", "run_recovery"]


def emergency_stop_active() -> bool:
    """True if the EMERGENCY_STOP flag file exists."""
    from pathlib import Path
    return Path(CONFIG.STOP_FLAG).exists()


def activate_emergency_stop() -> None:
    """Create the flag — Rolex must refuse all new work."""
    from pathlib import Path
    Path(CONFIG.STOP_FLAG).parent.mkdir(parents=True, exist_ok=True)
    Path(CONFIG.STOP_FLAG).write_text("STOP", encoding="utf-8")
    AUDIT.record("system.emergency_stop", result="ok",
                 detail="flag created", actor="user")


def clear_emergency_stop() -> None:
    from pathlib import Path
    Path(CONFIG.STOP_FLAG).unlink(missing_ok=True)
    AUDIT.record("system.emergency_stop", result="ok",
                 detail="flag cleared", actor="user")


from ..config import CONFIG  # noqa: E402  (bottom import avoids cycle)
