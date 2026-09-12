"""Planning helper — add todo items (lazy import avoids cycles)."""
from __future__ import annotations


def add_todo(title: str) -> str:
    """Register a plan step as a user task. Returns confirmation."""
    from ..tasks.manager import TASKS_MGR
    t = TASKS_MGR.add(title=title)
    return f"task added: {t.display}"
