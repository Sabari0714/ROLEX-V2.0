"""Rolex Document Intelligence (Phase 12) — read/search/summarize/edit.

Pipeline: extract (any format) → analyze → summarize → answer about it.
Includes a local "document memory" (SQLite): every processed document's
path, format, size, keywords, and summary — so Rolex can recall docs
without re-reading them.
"""
from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

from ..config import CONFIG
from ..logging_setup import get_logger
from .readers import DocError, extract_text, supported_formats

log = get_logger("documents")

__all__ = ["DocumentEngine", "DocSummary", "DOC_ENGINE", "DocError"]

_STOP = set("""a an and are as at be by for from has have in is it its of on
or that the to was were will with this these those there here their them
then than when where which who what how why not no nor but if so do does
did been being also into over under between each more most other some such
only own same too very can just""".split())

_SPLIT_SENT = re.compile(r"[.!?]+[\s\n]+")


@dataclass
class DocSummary:
    path: str
    format: str
    size_kb: float
    words: int
    lines: int
    sentences: int
    top_keywords: list[str] = field(default_factory=list)
    first_sentences: list[str] = field(default_factory=list)
    summary: str = ""


class DocumentEngine:
    """Search, summarize, edit documents — 100% local processing."""

    def __init__(self, db_path: str | None = None):
        self.db_path = Path(db_path or Path(CONFIG.DATA_DIR) / "documents" / "docs.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------- db
    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    format TEXT,
                    size_kb REAL,
                    words INTEGER,
                    keywords TEXT,
                    summary TEXT,
                    first_seen REAL,
                    last_read REAL
                )""")
            con.commit()

    # --------------------------------------------------------- analyze
    @staticmethod
    def _keywords(text: str, n: int = 8) -> list[str]:
        words = re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", text.lower())
        freq: dict[str, int] = {}
        for w in words:
            if w in _STOP:
                continue
            freq[w] = freq.get(w, 0) + 1
        ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
        return [w for w, _ in ranked[:n]]

    def analyze(self, path: str | Path) -> DocSummary:
        p = Path(path)
        if not p.is_file():
            raise DocError(f"file not found: {path}")
        text = extract_text(p)
        words = text.split()
        lines = [ln for ln in text.splitlines() if ln.strip()]
        sentences = [s.strip() for s in _SPLIT_SENT.split(text) if s.strip()]
        s = DocSummary(
            path=str(p), format=p.suffix.lower().lstrip(".") or "none",
            size_kb=round(p.stat().st_size / 1024, 2),
            words=len(words), lines=len(lines),
            sentences=len(sentences),
            top_keywords=self._keywords(text),
            first_sentences=[x[:200] for x in sentences[:3]],
        )
        s.summary = self._compose_summary(s, sentences)
        self._remember(s)
        return s

    @staticmethod
    def _compose_summary(s: DocSummary, sentences: list[str]) -> str:
        """Extractive summary: top keywords density per sentence."""
        if not sentences:
            return "(empty document)"
        if s.words <= 60:
            joined = " ".join(sentences)
            return joined[:300] + ("..." if len(joined) > 300 else "")
        scored: list[tuple[float, int, str]] = []
        kws = set(s.top_keywords[:6])
        for i, sent in enumerate(sentences[:200]):
            low = sent.lower()
            score = sum(1 for k in kws if k in low)
            if score == 0:
                continue
            scored.append((score / max(1, len(sent.split())), i, sent))
        if not scored:
            top3 = sentences[:3]
        else:
            scored.sort(key=lambda t: (-t[0], t[1]))
            picked = [t for t in scored[:3]]
            picked.sort(key=lambda t: t[1])     # back in reading order
            top3 = [t[2] for t in picked]
        return " ".join(x.strip() for x in top3)

    # ---------------------------------------------------------- search
    def search_text(self, path: str | Path, query: str,
                    context: int = 60) -> list[str]:
        """Keyword search inside a document with context snippets."""
        text = extract_text(path)
        ql = query.lower()
        hits: list[str] = []
        for m in re.finditer(re.escape(ql), text.lower()):
            a, b = max(0, m.start() - context), min(len(text), m.end() + context)
            snippet = text[a:b].replace("\n", " ")
            hits.append(f"...{snippet}...")
            if len(hits) >= 20:
                break
        return hits

    # ------------------------------------------------------------ edit
    def edit(self, path: str | Path, find: str, replace: str) -> int:
        """Simple find→replace editing (permission: doc.edit governs UI)."""
        p = Path(path)
        if not p.is_file():
            raise DocError(f"file not found: {path}")
        text = p.read_text(encoding="utf-8", errors="replace")
        n = text.count(find)
        if n:
            p.write_text(text.replace(find, replace), encoding="utf-8")
        return n

    # --------------------------------------------------------- memory
    def _remember(self, s: DocSummary) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute("""
                INSERT INTO documents
                    (path, format, size_kb, words, keywords, summary,
                     first_seen, last_read)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(path) DO UPDATE SET
                    format=excluded.format, size_kb=excluded.size_kb,
                    words=excluded.words, keywords=excluded.keywords,
                    summary=excluded.summary, last_read=excluded.last_read
            """, (s.path, s.format, s.size_kb, s.words,
                  ", ".join(s.top_keywords), s.summary,
                  time.time(), time.time()))
            con.commit()

    def recall(self, query: str = "", limit: int = 10) -> list[dict]:
        """Document memory lookup: match path/keywords/summary."""
        q = f"%{query.lower()}%"
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            if query:
                rows = con.execute("""
                    SELECT * FROM documents
                    WHERE lower(path) LIKE ? OR lower(keywords) LIKE ?
                       OR lower(summary) LIKE ?
                    ORDER BY last_read DESC LIMIT ?
                """, (q, q, q, limit)).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM documents ORDER BY last_read DESC LIMIT ?",
                    (limit,)).fetchall()
            return [dict(r) for r in rows]

    def forget(self, path: str) -> int:
        with sqlite3.connect(self.db_path) as con:
            cur = con.execute("DELETE FROM documents WHERE path = ?",
                              (str(path),))
            con.commit()
            return cur.rowcount

    def stats(self) -> dict:
        with sqlite3.connect(self.db_path) as con:
            n = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        return {"documents_remembered": n, "db_path": str(self.db_path)}


DOC_ENGINE = DocumentEngine()
