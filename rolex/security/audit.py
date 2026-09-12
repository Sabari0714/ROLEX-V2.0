"""Rolex Audit Log (Phase 14) \u2014 every sensitive action recorded.

Append-only JSONL at data/logs/audit.jsonl:
  {"ts": ..., "actor": "user|rolex|system", "action": "fs.write",
   "target": "path or subject", "result": "ok|denied|error", "detail": "..."}
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from ..config import CONFIG
from ..logging_setup import get_logger

log = get_logger("audit")


class AuditLog:
    """Append-only audit trail (tamper-evident via sequence numbers)."""

    def __init__(self, path: str | None = None):
        self.path = Path(path or CONFIG.AUDIT_LOG)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq = self._count_lines()

    def _count_lines(self) -> int:
        if not self.path.exists():
            return 0
        try:
            with open(self.path, encoding="utf-8") as f:
                return sum(1 for _ in f)
        except OSError:
            return 0

    # -------------------------------------------------------------- log
    def record(self, action: str, target: str = "",
               result: str = "ok", detail: str = "",
               actor: str = "rolex") -> None:
        entry = {"seq": self._seq, "ts": round(time.time(), 3),
                 "actor": actor, "action": action, "target": target,
                 "result": result, "detail": detail}
        self._seq += 1
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            log.error("audit write failed: %s", e)

    # ------------------------------------------------------------ query
    def tail(self, n: int = 20) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            lines = self.path.read_text(
                encoding="utf-8").strip().splitlines()[-n:]
            return [json.loads(x) for x in lines if x.strip()]
        except Exception as e:  # noqa: BLE001
            log.error("audit read failed: %s", e)
            return []

    def search(self, action: str | None = None,
               result: str | None = None, limit: int = 50) -> list[dict]:
        out: list[dict] = []
        if not self.path.exists():
            return out
        try:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    e = json.loads(line)
                    if action and e.get("action") != action:
                        continue
                    if result and e.get("result") != result:
                        continue
                    out.append(e)
                    if len(out) >= limit:
                        break
        except Exception as e:  # noqa: BLE001
            log.error("audit search failed: %s", e)
        return out

    def stats(self) -> dict:
        entries = self.search(limit=100_000)
        by_result: dict[str, int] = {}
        for e in entries:
            by_result[e.get("result", "?")] = \
                by_result.get(e.get("result", "?"), 0) + 1
        return {"events": len(entries), "by_result": by_result,
                "path": str(self.path)}


AUDIT = AuditLog()
