"""Rolex Memory System (Phase 8) \u2014 short-term + long-term memory.

SQLite-based. Zero hard dependencies (stdlib sqlite3).

Tables:
  conversations \u2014 short-term: recent turns for context/followups
  facts          \u2014 long-term: remembered facts about the user
  preferences    \u2014 user preferences (style, language, units...)
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field

from ..config import CONFIG
from ..errors import RolexError
from ..logging_setup import get_logger

log = get_logger("memory")


class MemoryError(RolexError):
    """Raised when the memory store fails."""


@dataclass
class Turn:
    """One conversation turn (short-term memory)."""
    role: str                 # user | rolex
    text: str
    intent: str = ""
    route: str = ""
    ts: float = field(default_factory=time.time)

    def to_row(self) -> tuple:
        return (self.role, self.text, self.intent, self.route, self.ts)


@dataclass
class MemoryFact:
    """A long-term remembered fact."""
    key: str
    value: str
    fact_type: str = "general"      # user | world | preference
    ts: float = field(default_factory=time.time)


class MemoryStore:
    """SQLite-backed memory with search and cleanup."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or CONFIG.MEMORY_DB
        self._ensure_parent()
        self._init_db()

    # ------------------------------------------------------------ setup
    def _ensure_parent(self) -> None:
        from pathlib import Path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                role      TEXT NOT NULL,
                text      TEXT NOT NULL,
                intent    TEXT DEFAULT '',
                route     TEXT DEFAULT '',
                ts        REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_conv_ts ON conversations(ts);

            CREATE TABLE IF NOT EXISTS facts (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                key       TEXT NOT NULL,
                value     TEXT NOT NULL,
                fact_type TEXT DEFAULT 'general',
                ts        REAL NOT NULL,
                UNIQUE(key, value)
            );

            CREATE TABLE IF NOT EXISTS preferences (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                ts    REAL NOT NULL
            );
            """)
        log.debug("memory ready at %s", self.db_path)

    # ------------------------------------------------- short-term (turns)
    def add_turn(self, turn: Turn) -> None:
        """Remember one conversation turn."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO conversations(role,text,intent,route,ts) "
                    "VALUES(?,?,?,?,?)", turn.to_row())
        except sqlite3.Error as e:
            raise MemoryError(f"add_turn failed: {e}") from e

    def add_exchange(self, user_text: str, rolex_text: str,
                     intent: str = "", route: str = "") -> None:
        """Store a full user\u2192rolex exchange (most common case)."""
        self.add_turn(Turn(role="user", text=user_text, intent=intent,
                           route=route))
        self.add_turn(Turn(role="rolex", text=rolex_text, route=route))

    def recent_turns(self, n: int = 10, since_hours: float | None = None
                     ) -> list[Turn]:
        """Latest n turns (optionally only within the last N hours)."""
        q = "SELECT role,text,intent,route,ts FROM conversations"
        args: list = []
        if since_hours is not None:
            q += " WHERE ts >= ?"
            args.append(time.time() - since_hours * 3600)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(n)
        with self._connect() as conn:
            rows = conn.execute(q, args).fetchall()
        return [Turn(r["role"], r["text"], r["intent"], r["route"], r["ts"])
                for r in reversed(rows)]

    def last_user_turn(self) -> Turn | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT role,text,intent,route,ts FROM conversations "
                "WHERE role='user' ORDER BY id DESC LIMIT 1").fetchone()
        return Turn(row["role"], row["text"], row["intent"], row["route"],
                    row["ts"]) if row else None

    def clear_conversation(self) -> int:
        """Forget the short-term conversation history."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM conversations")
            return cur.rowcount

    # ------------------------------------------------ long-term (facts)
    def remember(self, key: str, value: str,
                 fact_type: str = "general") -> None:
        """Store a long-term fact. Insert-or-replace on key."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO facts(key,value,fact_type,ts) "
                    "VALUES(?,?,?,?) ON CONFLICT(key,value) DO NOTHING",
                    (key.strip().lower(), value.strip(), fact_type,
                     time.time()))
        except sqlite3.Error as e:
            raise MemoryError(f"remember failed: {e}") from e

    def recall(self, key: str) -> list[str]:
        """All values stored under a key."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT value FROM facts WHERE key=? ORDER BY ts DESC",
                (key.strip().lower(),)).fetchall()
        return [r["value"] for r in rows]

    def forget(self, key: str, value: str | None = None) -> int:
        """Remove facts under key (optionally only one value)."""
        with self._connect() as conn:
            if value is None:
                cur = conn.execute("DELETE FROM facts WHERE key=?",
                                   (key.strip().lower(),))
            else:
                cur = conn.execute(
                    "DELETE FROM facts WHERE key=? AND value=?",
                    (key.strip().lower(), value))
            return cur.rowcount

    def search_facts(self, query: str, limit: int = 5) -> list[MemoryFact]:
        """Full-text-ish search over remembered facts."""
        q = (query or "").lower().strip()
        if not q:
            return []
        words = [w for w in q.split() if len(w) >= 2]
        if not words:
            return []
        like = " OR ".join(["value LIKE ? OR key LIKE ?"] * len(words))
        args: list = []
        for w in words:
            pat = f"%{w}%"
            args.extend([pat, pat])
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT key,value,fact_type,ts FROM facts "
                f"WHERE {like} ORDER BY ts DESC LIMIT ?", (*args, limit)
            ).fetchall()
        return [MemoryFact(r["key"], r["value"], r["fact_type"], r["ts"])
                for r in rows]

    # ------------------------------------------------------- preferences
    def set_pref(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO preferences(key,value,ts) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "ts=excluded.ts",
                (key.strip().lower(), value.strip(), time.time()))

    def get_pref(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM preferences WHERE key=?",
                (key.strip().lower(),)).fetchone()
        return row["value"] if row else default

    def all_prefs(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key,value FROM preferences ORDER BY key").fetchall()
        return {r["key"]: r["value"] for r in rows}

    # ------------------------------------------------------------ stats
    def stats(self) -> dict:
        with self._connect() as conn:
            n_turns = conn.execute(
                "SELECT COUNT(*) c FROM conversations").fetchone()["c"]
            n_facts = conn.execute(
                "SELECT COUNT(*) c FROM facts").fetchone()["c"]
            n_prefs = conn.execute(
                "SELECT COUNT(*) c FROM preferences").fetchone()["c"]
            last = conn.execute(
                "SELECT MAX(ts) m FROM conversations").fetchone()["m"]
        return {"turns": n_turns, "facts": n_facts, "prefs": n_prefs,
                "last_activity": last,
                "db": self.db_path, "size_kb": round(
                    __import__("os").path.getsize(self.db_path) / 1024, 1)}

    # ------------------------------------------------------------ cleanup
    def cleanup(self, keep_turn_days: float = 7.0,
                vacuum: bool = True) -> dict:
        """Old turns pruned, facts/preferences kept. Vacuum reclaims space."""
        cutoff = time.time() - keep_turn_days * 86400
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM conversations WHERE ts < ?", (cutoff,))
            pruned = cur.rowcount
        if vacuum:
            with self._connect() as conn:
                conn.execute("VACUUM")
        log.info("cleanup pruned %d turns older than %.0f days",
                 pruned, keep_turn_days)
        return {"pruned_turns": pruned, "cutoff_days": keep_turn_days}

    # ------------------------------------------------------------ reset
    def reset(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                "DELETE FROM conversations; DELETE FROM facts; "
                "DELETE FROM preferences;")
        log.info("memory reset (all tables cleared)")


# singleton \u2014 unless caller passes a custom path
MEMORY = MemoryStore()
