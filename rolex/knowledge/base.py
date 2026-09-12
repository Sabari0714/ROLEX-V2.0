"""Knowledge Engine — local, searchable, JSON-based (Phase 5)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..config import CONFIG
from ..errors import KnowledgeError
from ..logging_setup import get_logger

log = get_logger("knowledge")


@dataclass
class Entry:
    id: str
    title: str
    content: str
    keywords: list
    tags: list
    topic: str = "general"
    formula: str | None = None
    related: list = field(default_factory=list)
    source: str = "local-kb"

    def snippet(self, n: int = 160) -> str:
        return self.content[:n] + ("…" if len(self.content) > n else "")


@dataclass
class KnowledgeMatch:
    entry: Entry
    score: float
    matched: list


class KnowledgeBase:
    """Loads all topic JSON files and answers searches locally."""

    def __init__(self, kb_dir: Path | str | None = None):
        self.kb_dir = Path(kb_dir or CONFIG.KB_DIR)
        self.entries: dict[str, Entry] = {}
        self._topic_index: dict[str, list[str]] = {}
        self._tag_index: dict[str, list[str]] = {}
        self.load()

    # ----------------------------------------------------------- load
    def load(self) -> int:
        self.entries.clear()
        self._topic_index.clear()
        self._tag_index.clear()
        if not self.kb_dir.exists():
            log.warning("KB dir missing: %s", self.kb_dir)
            return 0
        for f in sorted(self.kb_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                log.warning("bad KB file %s: %s", f.name, e)
                continue
            topic = data.get("topic", f.stem)
            for e in data.get("entries", []):
                entry = Entry(
                    id=f"{topic}:{e.get('id', e.get('title', 'x').lower())}",
                    title=e.get("title", ""),
                    content=e.get("content", ""),
                    keywords=[k.lower() for k in e.get("keywords", [])],
                    tags=[t.lower() for t in e.get("tags", [])] + [topic],
                    topic=topic,
                    formula=e.get("formula"),
                    related=e.get("related", []),
                )
                if not entry.title or not entry.content:
                    continue
                self.entries[entry.id] = entry
                self._topic_index.setdefault(topic, []).append(entry.id)
                for tag in entry.tags:
                    self._tag_index.setdefault(tag, []).append(entry.id)
        log.info("knowledge loaded: %d entries across %d topics",
                 len(self.entries), len(self._topic_index))
        return len(self.entries)

    # ----------------------------------------------------------- search
    def search(self, query: str, limit: int = 3,
               min_score: float = 1.0) -> list[KnowledgeMatch]:
        q = (query or "").lower().strip()
        if not q:
            return []
        q_words = set(re.findall(r"[a-z0-9\u0B80-\u0BFF]{2,}", q))
        if not q_words:
            q_words = {q}
        results: list[KnowledgeMatch] = []

        for entry in self.entries.values():
            score = 0.0
            matched: list[str] = []
            ql = q

            # exact keyword phrase hit — strongest
            for kw in entry.keywords:
                if kw in ql or ql in kw:
                    score += 3.0
                    matched.append(kw)
                    break
            # word overlap on keywords/title/tags
            entry_words = set()
            for kw in entry.keywords:
                entry_words.update(re.findall(r"[a-z0-9]{2,}", kw))
            entry_words.update(re.findall(r"[a-z0-9]{2,}", entry.title.lower()))
            overlap = q_words & entry_words
            if overlap:
                score += 1.5 * len(overlap)
                matched.extend(overlap)
            if entry.topic in q:
                score += 1.0
                matched.append(entry.topic)
            # fuzzy title similarity
            if entry.title.lower()[:8] in ql or ql[:8] in entry.title.lower():
                score += 2.0
                matched.append(entry.title)

            if score >= min_score:
                results.append(KnowledgeMatch(entry, score, sorted(set(matched))))

        results.sort(key=lambda m: m.score, reverse=True)
        return results[:limit]

    def best(self, query: str, min_score: float = 2.0) -> KnowledgeMatch | None:
        res = self.search(query, limit=1, min_score=min_score)
        return res[0] if res else None

    # ----------------------------------------------------------- info
    def get(self, entry_id: str) -> Entry | None:
        return self.entries.get(entry_id)

    def topics(self) -> dict[str, int]:
        return {t: len(ids) for t, ids in sorted(self._topic_index.items())}

    def count(self) -> int:
        return len(self.entries)

    def stats(self) -> dict:
        return {"entries": self.count(), "topics": self.topics()}

    # ----------------------------------------------------------- write
    def add_entry(self, topic: str, entry: dict, persist: bool = True) -> str:
        """Add knowledge (used by learning pipeline too)."""
        topic = (topic or "general").lower()
        slug = entry.get("id") or entry["title"].lower().replace(" ", "_")
        eid = f"{topic}:{slug}"
        self.entries[eid] = Entry(
            id=eid, title=entry["title"], content=entry["content"],
            keywords=[k.lower() for k in entry.get("keywords", [])],
            tags=[t.lower() for t in entry.get("tags", [])] + [topic],
            topic=topic, formula=entry.get("formula"),
            related=entry.get("related", []), source=entry.get("source", "learned"),
        )
        self._topic_index.setdefault(topic, []).append(eid)
        if persist:
            f = self.kb_dir / f"{topic}.json"
            data = {"topic": topic, "entries": []}
            if f.exists():
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except Exception:  # noqa: BLE001
                    pass
            data.setdefault("entries", [])
            if not any(str(e.get("id")) == str(slug) or
                       e.get("title") == entry["title"]
                       for e in data["entries"]):
                stored = dict(entry)
                stored["id"] = slug
                data["entries"].append(stored)
            try:
                self.kb_dir.mkdir(parents=True, exist_ok=True)
                f.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                             encoding="utf-8")
            except Exception as e:  # noqa: BLE001
                raise KnowledgeError(f"cannot persist entry: {e}")
        return eid
