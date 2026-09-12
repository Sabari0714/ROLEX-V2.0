"""Rolex Task & Automation Engine (Phase 10) \u2014 reminders + schedules.

Features:
  - reminders      : one-shot ("remind me in 10 minutes to ...")
  - scheduled tasks: run at a specific time (daily routines)
  - recurring jobs : every N minutes/hours/days
  - background runner: tick() loop driven by the main loop / timer thread
  - event triggers : fire on Rolex events (boot, answer, error...)
  - priorities     : low < normal < high < critical
  - history        : SQLite table of every run
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable

from ..config import CONFIG
from ..errors import RolexError
from ..logging_setup import get_logger

log = get_logger("automation")


class AutomationError(RolexError):
    """Task engine failure."""


class Priority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Task:
    """A schedulable unit of work."""
    id: str
    title: str
    kind: str = "reminder"        # reminder | schedule | recurring | trigger
    action: str = "notify"        # notify | command | callback
    payload: dict = field(default_factory=dict)
    priority: int = Priority.NORMAL
    at: float | None = None                 # epoch for reminder/schedule
    every: float | None = None              # seconds for recurring
    event: str | None = None                # event name for triggers
    next_due: float | None = None
    last_run: float | None = None
    n_runs: int = 0
    enabled: bool = True
    max_runs: int | None = None             # stop after N runs (reminders)
    created: float = field(default_factory=time.time)

    def compute_next(self) -> float | None:
        if self.kind == "recurring" and self.every:
            base = self.last_run or time.time()
            return base + self.every
        if self.kind in ("reminder", "schedule") and self.at:
            return self.at
        return None

    def due(self, now: float | None = None) -> bool:
        if not self.enabled:
            return False
        now = now or time.time()
        nd = self.next_due if self.next_due is not None else self.compute_next()
        return nd is not None and nd <= now

    def to_json(self) -> dict:
        return {"id": self.id, "title": self.title, "kind": self.kind,
                "action": self.action, "payload": self.payload,
                "priority": int(self.priority), "at": self.at,
                "every": self.every, "event": self.event,
                "next_due": self.next_due, "last_run": self.last_run,
                "n_runs": self.n_runs, "enabled": self.enabled,
                "max_runs": self.max_runs, "created": self.created}


# words \u2192 seconds for "remind me in X minutes"
_TIME_UNITS = {
    "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600,
    "day": 86400, "days": 86400,
    "week": 604800, "weeks": 604800,
}

_RE_IN = re.compile(
    r"(?:remind me|reminder|alar[mtm]|notify me)\s+(?:in|after)?\s*"
    r"(\d+(?:\.\d+)?)\s*(sec|secs|second|seconds|min|mins|minute|minutes|"
    r"hour|hours|hr|hrs|day|days|week|weeks)\b(.*)",
    re.I | re.S)
_RE_AT = re.compile(
    r"(?:remind me|reminder|alarm|notify me)\s+(?:at|by)\s*"
    r"(\d{1,2}):(\d{2})\s*(am|pm)?\b(.*)",
    re.I | re.S)
_RE_EVERY = re.compile(
    r"(?:every|run|repeat)\s+(?:each\s+)?(\d+(?:\.\d+)?)\s*"
    r"(sec|secs|second|seconds|min|mins|minute|minutes|hour|hours|"
    r"hr|hrs|day|days|week|weeks)\b(.*)",
    re.I | re.S)


class TaskEngine:
    """Reminders, schedules, recurring jobs, triggers + history."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(
            __import__("pathlib").Path(CONFIG.DATA_DIR) / "tasks" / "tasks.db")
        from pathlib import Path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.tasks: dict[str, Task] = {}
        self._callbacks: dict[str, Callable] = {}
        self._init_db()
        self._load()

    # ------------------------------------------------------------ setup
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                kind TEXT, action TEXT,
                payload TEXT, priority INTEGER,
                at REAL, every REAL, event TEXT,
                next_due REAL, last_run REAL,
                n_runs INTEGER, enabled INTEGER,
                max_runs INTEGER, created REAL
            );
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT, title TEXT, kind TEXT,
                status TEXT, note TEXT, ts REAL
            );
            """)

    def _load(self) -> None:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM tasks").fetchall()
        for r in rows:
            t = Task(
                id=r["id"], title=r["title"], kind=r["kind"],
                action=r["action"],
                payload=json.loads(r["payload"] or "{}"),
                priority=r["priority"], at=r["at"], every=r["every"],
                event=r["event"], next_due=r["next_due"],
                last_run=r["last_run"], n_runs=r["n_runs"],
                enabled=bool(r["enabled"]), max_runs=r["max_runs"],
                created=r["created"])
            self.tasks[t.id] = t

    def _persist(self, t: Task) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO tasks(id,title,kind,action,payload,priority,
                                  at,every,event,next_due,last_run,
                                  n_runs,enabled,max_runs,created)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  title=excluded.title, kind=excluded.kind,
                  action=excluded.action, payload=excluded.payload,
                  priority=excluded.priority, at=excluded.at,
                  every=excluded.every, event=excluded.event,
                  next_due=excluded.next_due, last_run=excluded.last_run,
                  n_runs=excluded.n_runs, enabled=excluded.enabled,
                  max_runs=excluded.max_runs, created=excluded.created
            """, (t.id, t.title, t.kind, t.action,
                  json.dumps(t.payload), int(t.priority), t.at, t.every,
                  t.event, t.next_due, t.last_run, t.n_runs,
                  int(t.enabled), t.max_runs, t.created))

    def _delete_row(self, tid: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE id=?", (tid,))

    def _history(self, t: Task, status: str, note: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO history(task_id,title,kind,status,note,ts) "
                "VALUES(?,?,?,?,?,?)",
                (t.id, t.title, t.kind, status, note, time.time()))

    # ------------------------------------------------------ add tasks
    def add_reminder(self, title: str, at: float,
                     payload: dict | None = None,
                     priority: int = Priority.NORMAL) -> Task:
        t = Task(id=uuid.uuid4().hex[:8], title=title, kind="reminder",
                 action="notify", payload=payload or {}, priority=priority,
                 at=at, next_due=at, max_runs=1)
        self.tasks[t.id] = t
        self._persist(t)
        log.info("reminder %s @%s: %s", t.id,
                 time.strftime("%H:%M:%S", time.localtime(at)), title)
        return t

    def add_schedule(self, title: str, at: float,
                     action: str = "notify",
                     payload: dict | None = None) -> Task:
        t = Task(id=uuid.uuid4().hex[:8], title=title, kind="schedule",
                 action=action, payload=payload or {}, at=at,
                 next_due=at)
        self.tasks[t.id] = t
        self._persist(t)
        return t

    def add_recurring(self, title: str, every: float,
                      action: str = "notify",
                      payload: dict | None = None) -> Task:
        if every <= 0:
            raise AutomationError("recurring interval must be > 0")
        t = Task(id=uuid.uuid4().hex[:8], title=title, kind="recurring",
                 action=action, payload=payload or {}, every=every,
                 next_due=time.time() + every)
        self.tasks[t.id] = t
        self._persist(t)
        return t

    def add_trigger(self, title: str, event: str,
                    action: str = "callback",
                    payload: dict | None = None) -> Task:
        t = Task(id=uuid.uuid4().hex[:8], title=title, kind="trigger",
                 action=action, payload=payload or {}, event=event)
        self.tasks[t.id] = t
        self._persist(t)
        return t

    def register_callback(self, name: str, fn: Callable) -> None:
        """Register a named callback actions can reference."""
        self._callbacks[name] = fn

    # ------------------------------------------------------- parse text
    def parse_reminder_text(self, text: str) -> Task | None:
        """'remind me in 10 minutes to check motor' \u2192 Task."""
        m = _RE_IN.search(text or "")
        if m:
            n = float(m.group(1))
            unit = m.group(2).lower()
            what = (m.group(3) or "").strip()
            what = re.sub(r"^(?:to|that|about|for)\b", "", what,
                          flags=re.I).strip()
            at = time.time() + n * _TIME_UNITS[unit]
            title = what or "Reminder"
            return self.add_reminder(title, at,
                                     payload={"raw": text})
        m = _RE_AT.search(text or "")
        if m:
            hh, mm, ampm, what = int(m.group(1)), int(m.group(2)), \
                m.group(3), (m.group(4) or "").strip()
            if ampm:
                ampm = ampm.lower()
                if ampm == "pm" and hh < 12:
                    hh += 12
                if ampm == "am" and hh == 12:
                    hh = 0
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                return None
            import datetime as _dt
            now = _dt.datetime.now()
            target = now.replace(hour=hh, minute=mm, second=0,
                                 microsecond=0)
            if target <= now:
                target += _dt.timedelta(days=1)
            what = re.sub(r"^(?:to|that|about|for)\b", "", what,
                          flags=re.I).strip()
            return self.add_reminder(what or "Alarm", target.timestamp(),
                                     payload={"raw": text})
        return None

    def parse_recurring_text(self, text: str) -> Task | None:
        """"every 5 minutes do X' \u2192 recurring Task."""
        m = _RE_EVERY.search(text or "")
        if not m:
            return None
        n = float(m.group(1))
        unit = m.group(2).lower()
        what = (m.group(3) or "").strip()
        what = re.sub(r"^(?:do|run|to|that|about|for)\b", "", what,
                      flags=re.I).strip()
        return self.add_recurring(what or "Recurring job",
                                  n * _TIME_UNITS[unit],
                                  payload={"raw": text})

    # ---------------------------------------------------------- runner
    def tick(self, now: float | None = None) -> list[Task]:
        """Run everything due. Call this from the main loop / thread."""
        now = now or time.time()
        fired: list[Task] = []
        for t in list(self.tasks.values()):
            if not t.due(now):
                continue
            try:
                self._run(t, now)
                fired.append(t)
            except Exception as e:  # noqa: BLE001
                log.error("task %s crashed: %s", t.id, e)
                self._history(t, "error", str(e))
        return fired

    def _run(self, t: Task, now: float) -> None:
        payload = t.payload or {}
        if t.action == "notify":
            log.info("\U0001f514 [%s] %s", t.kind, t.title)
            print(f"\n\U0001f514 [{t.kind}] {t.title}\n")
        elif t.action == "command":
            cmd = payload.get("command", "")
            if not cmd:
                raise AutomationError("command task missing 'command'")
            self._history(t, "skip", "no shell exec by design")
            return
        elif t.action == "callback":
            name = payload.get("callback", "")
            fn = self._callbacks.get(name)
            if fn is None:
                self._history(t, "skip",
                              f"callback {name!r} not registered")
                return
            fn(t)
        # book-keeping
        t.last_run = now
        t.n_runs += 1
        if t.kind in ("reminder",) or \
                (t.max_runs is not None and t.n_runs >= t.max_runs):
            t.enabled = False
            t.next_due = None
        else:
            t.next_due = t.compute_next()
        self._persist(t)
        self._history(t, "ok")

    # ------------------------------------------------------------ queries
    def due_tasks(self, now: float | None = None) -> list[Task]:
        now = now or time.time()
        return [t for t in self.tasks.values() if t.due(now)]

    def upcoming(self, n: int = 5) -> list[Task]:
        items = [t for t in self.tasks.values()
                 if t.enabled and t.next_due is not None]
        items.sort(key=lambda t: (t.next_due, -t.priority))
        return items[:n]

    def get(self, tid: str) -> Task | None:
        return self.tasks.get(tid)

    def cancel(self, tid: str) -> bool:
        t = self.tasks.pop(tid, None)
        if t is None:
            return False
        self._delete_row(tid)
        self._history(t, "cancelled")
        return True

    def snooze(self, tid: str, seconds: float) -> Task | None:
        t = self.tasks.get(tid)
        if t is None:
            return None
        t.next_due = time.time() + seconds
        t.enabled = True
        self._persist(t)
        return t

    def history(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM history ORDER BY id DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        active = [t for t in self.tasks.values() if t.enabled]
        return {"total": len(self.tasks), "active": len(active),
                "reminders": sum(1 for t in active
                                 if t.kind == "reminder"),
                "recurring": sum(1 for t in active
                                 if t.kind == "recurring"),
                "triggers": sum(1 for t in active if t.kind == "trigger"),
                "history_events": len(self.history(limit=10_000))}

    # --------------------------------------------------------- triggers
    def handle_event(self, event_name: str, data: dict | None = None
                     ) -> list[Task]:
        """Event bus hook: run trigger tasks bound to this event."""
        fired: list[Task] = []
        for t in list(self.tasks.values()):
            if t.kind == "trigger" and t.enabled and t.event == event_name:
                try:
                    if t.action == "callback":
                        fn = self._callbacks.get(
                            t.payload.get("callback", ""))
                        if fn:
                            fn(t)
                            t.n_runs += 1
                            t.last_run = time.time()
                            self._persist(t)
                            self._history(t, "ok")
                            fired.append(t)
                except Exception as e:  # noqa: BLE001
                    log.error("trigger %s failed: %s", t.id, e)
                    self._history(t, "error", str(e))
        return fired


TASKS = TaskEngine()
