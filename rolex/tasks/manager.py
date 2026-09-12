"""Rolex Task Manager (v2 §9) — classic todo system on SQLite.

Distinction from automation/engine.py (schedulers & reminders):
  • TaskManager  → user's todo list (create/complete/prioritize/status)
  • TaskEngine   → time-based execution (reminders/schedules/triggers)

Natural language (en / ta / tanglish):
  "add task buy milk", "todo: finish report, high priority",
  "task சேர் வாங்க பால்", "பணியை முடி 3", "show my tasks", "வேலைகள் காட்டு"
  "mark 3 complete", "task 3 முடிச்சு", "pending tasks என்ன?", "what's pending?"
"""
from __future__ import annotations

import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

from ..config import CONFIG
from ..errors import RolexError
from ..logging_setup import get_logger

log = get_logger("tasks")


class TaskManagerError(RolexError):
    code = "TASK_MANAGER_ERROR"


class Status(str):
    """Task status labels (bilingual display)."""
    PENDING = "pending"
    DONE = "done"
    BLOCKED = "blocked"
    DROPPED = "dropped"


class Priority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


_PRIORITY_WORDS = {
    "low": Priority.LOW, "குறைவு": Priority.LOW, "kamivu": Priority.LOW,
    "normal": Priority.NORMAL, "சாதாரண": Priority.NORMAL,
    "high": Priority.HIGH, "முக்கிய": Priority.HIGH, "mukkiyam": Priority.HIGH,
    "urgent": Priority.HIGH, "அவசர": Priority.HIGH, "avasara": Priority.HIGH,
    "critical": Priority.CRITICAL, "அதிமுக்கிய": Priority.CRITICAL,
    "top": Priority.CRITICAL,
}


@dataclass
class TaskItem:
    id: str
    title: str
    status: str = "pending"
    priority: int = Priority.NORMAL
    deadline: float | None = None
    note: str = ""
    tags: list[str] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    completed: float | None = None

    def to_json(self) -> dict:
        return {
            "id": self.id, "title": self.title, "status": self.status,
            "priority": int(self.priority), "deadline": self.deadline,
            "note": self.note, "tags": self.tags,
            "created": self.created, "completed": self.completed,
        }

    @property
    def display(self) -> str:
        p = ["_", "◦", "▲", "‼"][self.priority if self.priority < 4 else 3]
        s = "✓" if self.status == "done" else ("⊘" if self.status == "blocked" else "…")
        return f"{s}[{self.id[-4:]}] {p} {self.title} ({self.status})"


def _now() -> float:
    return time.time()


class TaskManager:
    """SQLite-backed todo list — local-first, zero deps."""

    DB_TABLE = "todo_tasks"

    def __init__(self, db_path: str | None = None):
        self.db_path = Path(db_path or CONFIG.DATA_DIR / "rolex_tasks.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------- db
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        try:
            with self._connect() as c:
                c.execute(f"""CREATE TABLE IF NOT EXISTS {self.DB_TABLE} (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority INTEGER NOT NULL DEFAULT 1,
                    deadline REAL,
                    note TEXT DEFAULT '',
                    tags TEXT DEFAULT '',
                    created REAL,
                    completed REAL)""")
                # v1.0 bug class: "missing priority column" → self-healing
                cols = {r["name"] for r in c.execute(
                    f"PRAGMA table_info({self.DB_TABLE})")}
                if "priority" not in cols:
                    c.execute(f"ALTER TABLE {self.DB_TABLE} "
                              f"ADD COLUMN priority INTEGER DEFAULT 1")
                if "status" not in cols:
                    c.execute(f"ALTER TABLE {self.DB_TABLE} "
                              f"ADD COLUMN status TEXT DEFAULT 'pending'")
        except Exception as e:                                  # noqa: BLE001
            raise TaskManagerError(f"task db init failed: {e}")

    # ------------------------------------------------------- create
    def add(self, title: str, priority: int | str = Priority.NORMAL,
            deadline: float | None = None, note: str = "",
            tags: list[str] | None = None) -> TaskItem:
        if not title or not str(title).strip():
            raise TaskManagerError("task title cannot be empty")
        pri = self._resolve_priority(priority)
        t = TaskItem(
            id=uuid.uuid4().hex[:8], title=str(title).strip(),
            priority=pri, deadline=deadline, note=note,
            tags=tags or [], created=_now())
        with self._connect() as c:
            c.execute(
                f"INSERT INTO {self.DB_TABLE} VALUES (?,?,?,?,?,?,?,?,?)",
                (t.id, t.title, t.status, int(t.priority), t.deadline,
                 t.note, ",".join(t.tags), t.created, None))
        log.info("task added: %s", t.title)
        return t

    @staticmethod
    def _resolve_priority(p) -> int:
        if isinstance(p, str):
            low = p.strip().lower()
            if low in _PRIORITY_WORDS:
                return int(_PRIORITY_WORDS[low])
            try:
                return int(low)
            except ValueError:
                return int(Priority.NORMAL)
        try:
            return int(p)
        except Exception:                                       # noqa: BLE001
            return int(Priority.NORMAL)

    # --------------------------------------------------------- list
    def all(self, include_done: bool = False) -> list[TaskItem]:
        where = "" if include_done else "WHERE status != 'done'"
        try:
            with self._connect() as c:
                rows = c.execute(
                    f"SELECT * FROM {self.DB_TABLE} {where} "
                    f"ORDER BY status='done', priority DESC, created DESC"
                ).fetchall()
        except sqlite3.Error as e:
            raise TaskManagerError(f"task list failed: {e}")
        return [self._row_to_item(r) for r in rows]

    def pending(self) -> list[TaskItem]:
        return [t for t in self.all() if t.status == "pending"]

    def get(self, tid: str) -> TaskItem | None:
        """Fetch by id, or by last-4-digit suffix match."""
        with self._connect() as c:
            row = c.execute(
                f"SELECT * FROM {self.DB_TABLE} WHERE id=?", (tid,)).fetchone()
        if row is None and len(str(tid)) >= 3:
            rows = self.all(include_done=True)
            matches = [t for t in rows if t.id.endswith(str(tid))]
            if len(matches) == 1:
                return matches[0]
            raise TaskManagerError(
                f"task id ambiguous/missing: {tid} "
                f"(matches: {[m.id for m in matches]})")
        if row is None:
            return None
        return self._row_to_item(row)

    # --------------------------------------------------------- update
    def complete(self, tid: str) -> TaskItem:
        """v1.0 bug class: complete_task missing → explicit + safe."""
        t = self.get(tid)
        if t is None:
            raise TaskManagerError(f"task not found: {tid}")
        if t.status == "done":
            return t  # idempotent
        with self._connect() as c:
            c.execute(
                f"UPDATE {self.DB_TABLE} SET status='done', completed=? "
                f"WHERE id=?", (_now(), t.id))
        t.status, t.completed = "done", _now()
        log.info("task completed: %s (%s)", t.title, t.id)
        return t

    def update(self, tid: str, title: str | None = None,
               priority=None, note: str | None = None,
               status: str | None = None,
               deadline: float | None = None) -> TaskItem:
        t = self.get(tid)
        if t is None:
            raise TaskManagerError(f"task not found: {tid}")
        fields, vals = [], []
        if title is not None:
            fields.append("title=?"); vals.append(str(title).strip())
        if priority is not None:
            fields.append("priority=?"); vals.append(
                self._resolve_priority(priority))
        if note is not None:
            fields.append("note=?"); vals.append(note)
        if status is not None:
            fields.append("status=?"); vals.append(status)
        if deadline is not None:
            fields.append("deadline=?"); vals.append(deadline)
        if not fields:
            return t
        vals.append(t.id)
        with self._connect() as c:
            c.execute(f"UPDATE {self.DB_TABLE} SET "
                      + ",".join(fields) + " WHERE id=?", vals)
        return self.get(t.id)

    def delete(self, tid: str) -> bool:
        t = self.get(tid)
        if t is None:
            return False
        with self._connect() as c:
            c.execute(f"DELETE FROM {self.DB_TABLE} WHERE id=?", (t.id,))
        log.info("task deleted: %s (%s)", t.title, t.id)
        return True

    def prioritize(self, tid: str, priority) -> TaskItem:
        return self.update(tid, priority=priority)

    # --------------------------------------------------------- stats
    def stats(self) -> dict:
        rows = self.all(include_done=True)
        done = [t for t in rows if t.status == "pending"]
        return {
            "total": len(rows),
            "pending": len(done),
            "done": sum(1 for t in rows if t.status == "done"),
            "blocked": sum(1 for t in engine_status_blocked(rows)),
            "high_priority": sum(1 for t in rows if t.priority >= 2
                                 and t.status != "done"),
            "db": str(self.db_path),
        }

    # --------------------------------------------------- natural lang
    def parse_command(self, text: str) -> str:
        """Route task natural-language commands → human reply.

        Returns "" when text is NOT a task command (let other handlers try).
        """
        t = (text or "").strip()
        low = t.lower()
        if not t:
            return ""

        # --- add ----------------------------------------------------
        m = re.match(
            r"^(?:add|new|create|push)?\s*(?:a\s+)?(?:task|todo|work)\b[::]?\s*(.+)$",
            low, re.I)
        m_ta = re.match(
            r"^(?:task|todo|வேலை|பணி)\b[::]?\s*(?:சேர்(?:த்தா)?|புது|புதிய)?\s*(.*)$",
            t, re.I)
        m = m or m_ta
        if m and m.group(1).strip():
            rest = m.group(1).strip()
            # extract priority word at end / start
            pri = Priority.NORMAL
            for w, p in _PRIORITY_WORDS.items():
                mm = re.search(rf"\b({re.escape(w)})\b", rest, re.I)
                if mm:
                    pri = p
                    rest = (rest[:mm.start()] + rest[mm.end():]).strip(" ,")
                    break
            # deadline: "tomorrow" / "today" / "in N days"
            dl = self._extract_deadline(rest)
            title = rest.strip(" ,.")
            if title:
                task = self.add(title=title, priority=pri, deadline=dl)
                return (f"✅ பணி சேர்க்கப்பட்டது · Task added: "
                        f"{task.display}")

        # --- list ---------------------------------------------------
        if re.search(
                r"\b(show|list|my tasks|todos?|pending|whats pending|"
                r"what.s pending|வேலை|பணி)\b.*(task|todo|வேலை|பணி|pending)?",
                low) and re.search(
                r"\b(task|todo|tasks|todos|வேலைகள்|பணிகள்|pending)\b", low):
            return self._format_list()

        # --- complete -----------------------------------------------
        m = re.match(
            r"^(?:mark\s+)?(?:task\s+)?(\d+|\w+)\s+(?:as\s+)?"
            r"(?:complete|done|finished|mudichu|முடிச்சு|முடி)\b.*$",
            low, re.I)
        m2 = re.match(
            r"^(?:பணியை|வேலையை)\s+(\w+)\s*(?:முடி|முடிச்சு|சரி)\b.*$", t)
        m = m or m2
        if m:
            tok = m.group(1)
            try:
                task = self._by_number_or_id(tok)
                done_t = self.complete(task.id)
                return (f"🎉 பணி முடிந்தது · Task complete: "
                        f"{done_t.display}")
            except TaskManagerError as e:
                return f"⚠️ {e.message}"

        # --- delete -------------------------------------------------
        m = re.match(
            r"^(?:delete|remove|drop|cancel)\s+(?:task\s+)?(\w+)\b.*$",
            low, re.I)
        if m:
            try:
                task = self._by_number_or_id(m.group(1))
                self.delete(task.id)
                return f"🗑️ பணி நீக்கப்பட்டது · deleted: {task.title}"
            except TaskManagerError as e:
                return f"⚠️ {e.message}"

        # --- what's next --------------------------------------------
        if re.search(r"\b(what.s next|next task|அடுத்த பணி)\b", low):
            pend = self.pending()
            if not pend:
                return "🎯 எதுவும் pending இல்ல · No pending tasks — நல்ல வேலை!"
            nxt = sorted(pend, key=lambda x: -x.priority)[0]
            return (f"➡️ அடுத்த பணி: {nxt.display} "
                    f"(priority {[ 'low','normal','high','critical'][nxt.priority]})")

        return ""

    # ------------------------------------------------------------ helpers
    def _by_number_or_id(self, token: str) -> TaskItem:
        """v1.0 bug class fix: 'task N' can be ordinal OR id-suffix.
        v2.1 bug class fix: the displayed suffix …[id[-4:]] can be ALL
        DIGITS (e.g. …[6981]) — when such a number is not a valid
        ordinal, fall back to id-suffix so 'mark 6981 complete' still
        resolves the task shown at that suffix. 3-digit numbers stay
        ordinal-only (never a displayed-suffix length)."""
        if token.isdigit():
            pend = self.all(include_done=True)
            ordinal = int(token)
            if 1 <= ordinal <= len(pend):
                return pend[ordinal - 1]
            if len(token) >= 4:               # displayed [xxxx] suffix size
                matches = [t for t in pend if t.id.endswith(token)]
                if len(matches) == 1:
                    return matches[0]
            raise TaskManagerError(
                f"task number {ordinal} இல்லை · not found (1–{len(pend)})")
        return self.get(token)

    @staticmethod
    def _extract_deadline(text: str) -> float | None:
        low = text.lower()
        day = 86400.0
        if "tomorrow" in low or "நாளை" in low:
            return _now() + day
        if "today" in low or "இன்று" in low or "இன்னிக்கு" in low:
            return _now() + day / 4      # default EOD-ish
        m = re.search(r"in\s+(\d+)\s*(day|days|நாள்)", low)
        if m:
            return _now() + int(m.group(1)) * day
        return None

    def _format_list(self) -> str:
        rows = self.all()
        if not rows:
            return ("📋 வேலைகள் இல்ல · No tasks yet. "
                    "'add task ...' என்று சொல்லுங்கள்.")
        lines = ["📋 Rolex Task Board:"]
        for i, t in enumerate(rows, 1):
            lines.append(f"  {i}. {t.display}")
        return "\n".join(lines)

    @staticmethod
    def _row_to_item(r) -> TaskItem:
        return TaskItem(
            id=r["id"], title=r["title"], status=r["status"],
            priority=int(r["priority"] or 1), deadline=r["deadline"],
            note=r["note"] or "", tags=[x for x in (r["tags"] or "").split(",")
                                        if x],
            created=r["created"] or _now(), completed=r["completed"])


def engine_status_blocked(rows):
    """blocked-status counter helper (kept simple, no import cycle)."""
    return (t for t in rows if t.status == "blocked")


TASKS_MGR = TaskManager()
