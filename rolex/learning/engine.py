"""Rolex Learning Engine (Phase 9) \u2014 SAFE self-improvement pipeline.

User rule: Learn \u2192 Propose \u2192 Backup \u2192 Sandbox \u2192 Test \u2192 Approve \u2192
Apply \u2192 Rollback. NEVER unrestricted self-modification.

What Rolex may safely learn:
  - new knowledge-base entries (facts user teaches)
  - new preferences (explicit user choices)
  - new word/intent mappings (Tanglish phrases \u2192 intent)

What Rolex NEVER does:
  - modify its own source code files
  - change security/permission config
  - apply anything without an explicit APPROVE step
"""
from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ..config import CONFIG
from ..errors import RolexError
from ..logging_setup import get_logger

log = get_logger("learning")


class LearningError(RolexError):
    """Learning pipeline failure."""


class Stage(str, Enum):
    PROPOSED = "proposed"
    BACKED_UP = "backed_up"
    SANDBOXED = "sandboxed"
    TESTED = "tested"
    APPROVED = "approved"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


@dataclass
class LearningProposal:
    """One safe learning change proposal."""
    id: str
    kind: str                    # kb_entry | preference | word_map
    payload: dict = field(default_factory=dict)
    stage: Stage = Stage.PROPOSED
    reason: str = ""
    created: float = field(default_factory=time.time)
    history: list = field(default_factory=list)

    def advance(self, to: Stage, note: str = "") -> None:
        self.history.append((time.time(), self.stage.value, to.value, note))
        self.stage = to

    def to_json(self) -> dict:
        return {"id": self.id, "kind": self.kind, "payload": self.payload,
                "stage": self.stage.value, "reason": self.reason,
                "created": self.created, "history": self.history}


# what kinds of learning are allowed
ALLOWED_KINDS = {"kb_entry", "preference", "word_map"}

# things a learned KB entry may never touch
_FORBIDDEN_TOPICS = {"security", "permissions", "secrets", "admin",
                     "self-modify", "root"}


class LearningEngine:
    """Learn \u2192 Propose \u2192 Backup \u2192 Sandbox \u2192 Test \u2192 Approve \u2192
    Apply \u2192 Rollback \u2014 with full audit history."""

    def __init__(self, state_path: str | None = None,
                 sandbox_dir: str | None = None,
                 backup_dir: str | None = None,
                 kb_dir: str | None = None):
        self.state_path = Path(state_path or
                               Path(CONFIG.DATA_DIR) / "learning" / "state.json")
        self.sandbox_dir = Path(sandbox_dir or CONFIG.SANDBOX_DIR)
        self.backup_dir = Path(backup_dir or CONFIG.BACKUP_DIR)
        self._kb_dir_override = Path(kb_dir) if kb_dir else None
        self._memory_store = None   # optional injectable for tests
        for p in (self.state_path.parent, self.sandbox_dir, self.backup_dir):
            p.mkdir(parents=True, exist_ok=True)
        self.proposals: dict[str, LearningProposal] = {}
        self._load_state()

    # ------------------------------------------------------------ propose
    def propose(self, kind: str, payload: dict, reason: str = ""
                ) -> LearningProposal:
        """Stage 1: LEARN \u2014 user taught / Rolex noticed something."""
        if kind not in ALLOWED_KINDS:
            raise LearningError(
                f"kind '{kind}' not allowed \u2014 Rolex only learns "
                f"{sorted(ALLOWED_KINDS)}")
        if not payload:
            raise LearningError("empty payload")
        prop = LearningProposal(
            id=uuid.uuid4().hex[:8], kind=kind, payload=payload,
            reason=reason or "user-taught")
        prop.advance(Stage.PROPOSED, "registered")
        self.proposals[prop.id] = prop
        self._save_state()
        log.info("proposal %s (%s) PROPOSED: %.80s",
                 prop.id, prop.kind, json.dumps(payload))
        return prop

    # ------------------------------------------------------------- backup
    def backup(self, proposal_id: str) -> LearningProposal:
        """Stage 2: BACKUP \u2014 snapshot the file this change would touch."""
        prop = self._get(proposal_id)
        self._require(prop, Stage.PROPOSED, "backup")
        backup_path = self._target_file(prop)
        if backup_path.exists():
            stamp = time.strftime("%Y%m%d-%H%M%S")
            dest = self.backup_dir / f"{backup_path.name}.{stamp}"
            shutil.copy2(backup_path, dest)
            prop.payload["_backup"] = str(dest)
            prop.advance(Stage.BACKED_UP, f"backup->{dest.name}")
        else:
            prop.advance(Stage.BACKED_UP, "no-file (fresh target)")
        self._save_state()
        return prop

    # ------------------------------------------------------------ sandbox
    def sandbox(self, proposal_id: str) -> LearningProposal:
        """Stage 3: SANDBOX \u2014 apply the change ONLY inside a sandbox copy."""
        prop = self._get(proposal_id)
        self._require(prop, Stage.BACKED_UP, "sandbox")
        box = self.sandbox_dir / f"learn-{prop.id}"
        box.mkdir(parents=True, exist_ok=True)

        if prop.kind == "kb_entry":
            topic = self._safe_topic(prop.payload.get("topic", "general"))
            (box / "topics").mkdir(exist_ok=True)
            # copy the real topic file into the sandbox for a safe apply
            src = self._kb_dir() / f"{topic}.json"
            if src.exists():
                shutil.copy2(src, box / "topics" / f"{topic}.json")
            self._apply_kb_entry(box / "topics" / f"{topic}.json",
                                 prop.payload)
        elif prop.kind == "preference":
            (box / "prefs.json").write_text(
                json.dumps(prop.payload, ensure_ascii=False, indent=2))
        elif prop.kind == "word_map":
            (box / "word_map.json").write_text(
                json.dumps(prop.payload, ensure_ascii=False, indent=2))
        prop.payload["_sandbox"] = str(box)
        prop.advance(Stage.SANDBOXED, f"sandbox->{box.name}")
        self._save_state()
        return prop

    # -------------------------------------------------------------- test
    def test(self, proposal_id: str) -> LearningProposal:
        """Stage 4: TEST \u2014 verify the sandboxed change works."""
        prop = self._get(proposal_id)
        self._require(prop, Stage.SANDBOXED, "test")
        checks = self._run_sandbox_checks(prop)
        prop.payload["_test_results"] = checks
        if checks.get("ok"):
            prop.advance(Stage.TESTED, "sandbox tests passed")
        else:
            prop.advance(Stage.REJECTED,
                         f"sandbox tests failed: {checks.get('failures')}")
        self._save_state()
        return prop

    # ------------------------------------------------------------ approve
    def approve(self, proposal_id: str, approver: str = "user"
                ) -> LearningProposal:
        """Stage 5: APPROVE \u2014 explicit user approval gate."""
        prop = self._get(proposal_id)
        self._require(prop, Stage.TESTED, "approve")
        prop.payload["_approver"] = approver
        prop.advance(Stage.APPROVED, f"approved by {approver}")
        self._save_state()
        return prop

    def reject(self, proposal_id: str, reason: str = "") -> LearningProposal:
        prop = self._get(proposal_id)
        if prop.stage in (Stage.APPLIED, Stage.ROLLED_BACK):
            raise LearningError("cannot reject an applied proposal")
        prop.advance(Stage.REJECTED, reason or "rejected by user")
        self._save_state()
        return prop

    # ------------------------------------------------------------- apply
    def apply(self, proposal_id: str) -> LearningProposal:
        """Stage 6: APPLY \u2014 bring the sandboxed change into real use."""
        prop = self._get(proposal_id)
        self._require(prop, Stage.APPROVED, "apply")
        try:
            if prop.kind == "kb_entry":
                topic = self._safe_topic(prop.payload.get("topic", "general"))
                self._apply_kb_entry(
                    self._kb_dir() / f"{topic}.json", prop.payload)
            elif prop.kind == "preference":
                store = self._memory()
                for k, v in prop.payload.items():
                    if k.startswith("_"):
                        continue
                    store.set_pref(k, v)
            elif prop.kind == "word_map":
                # persisted to data/learning/word_maps.json for the NLU
                wm = self.state_path.parent / "word_maps.json"
                data = json.loads(wm.read_text()) if wm.exists() else {}
                for k, v in prop.payload.items():
                    if k.startswith("_"):
                        continue
                    data[k] = v
                wm.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:  # noqa: BLE001
            prop.advance(Stage.REJECTED, f"apply failed: {e}")
            self._save_state()
            raise LearningError(f"apply failed: {e}") from e
        prop.advance(Stage.APPLIED, "change is live")
        self._save_state()
        log.info("proposal %s APPLIED (%s)", prop.id, prop.kind)
        return prop

    # ---------------------------------------------------------- rollback
    def rollback(self, proposal_id: str) -> LearningProposal:
        """Stage 7: ROLLBACK \u2014 undo an applied change via its backup."""
        prop = self._get(proposal_id)
        if prop.stage != Stage.APPLIED:
            raise LearningError(
                f"cannot rollback a proposal in stage {prop.stage.value}")
        backup = prop.payload.get("_backup")
        if prop.kind == "kb_entry":
            topic = self._safe_topic(prop.payload.get("topic", "general"))
            target = self._kb_dir() / f"{topic}.json"
            if backup and Path(backup).exists():
                shutil.copy2(backup, target)
                note = "restored from backup"
            else:
                # remove the entry we added (no pre-change file existed)
                removed = self._remove_kb_entry(target, prop.payload)
                note = f"entry removed ({removed})" if removed else \
                    "nothing to remove"
        elif prop.kind == "preference":
            store = self._memory()
            for k in prop.payload:
                if not k.startswith("_"):
                    store.set_pref(k, "")   # reset to empty
            note = "prefs reset"
        elif prop.kind == "word_map":
            wm = self.state_path.parent / "word_maps.json"
            if wm.exists():
                data = json.loads(wm.read_text())
                for k in prop.payload:
                    if not k.startswith("_"):
                        data.pop(k, None)
                wm.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2))
            note = "word map reverted"
        else:
            note = "unknown kind"
        prop.advance(Stage.ROLLED_BACK, note)
        self._save_state()
        log.info("proposal %s ROLLED BACK (%s)", prop.id, note)
        return prop

    # ------------------------------------------------------------ status
    def status(self) -> dict:
        by_stage: dict[str, int] = {}
        for p in self.proposals.values():
            by_stage[p.stage.value] = by_stage.get(p.stage.value, 0) + 1
        return {"proposals": len(self.proposals),
                "by_stage": by_stage,
                "allowed_kinds": sorted(ALLOWED_KINDS),
                "state_file": str(self.state_path)}

    def get(self, proposal_id: str) -> LearningProposal | None:
        return self.proposals.get(proposal_id)

    def list_proposals(self) -> list[dict]:
        return [p.to_json() for p in self.proposals.values()]

    # ---------------------------------------------------------- internals
    def _get(self, pid: str) -> LearningProposal:
        prop = self.proposals.get(pid)
        if prop is None:
            raise LearningError(f"unknown proposal {pid!r}")
        return prop

    def _require(self, prop: LearningProposal, want: Stage, action: str
                 ) -> None:
        if prop.stage != want:
            raise LearningError(
                f"pipeline violation: {action} requires {want.value}, "
                f"proposal is {prop.stage.value}")

    def _kb_dir(self) -> Path:
        return self._kb_dir_override or Path(CONFIG.KB_DIR)

    def _safe_topic(self, topic: str) -> str:
        t = re.sub(r"[^a-z0-9_]", "", (topic or "general").lower())
        return t or "general"

    def _memory(self) -> "MemoryStore":
        from ..memory import MEMORY
        return MEMORY

    def _target_file(self, prop: LearningProposal) -> Path:
        if prop.kind == "kb_entry":
            topic = self._safe_topic(prop.payload.get("topic", "general"))
            return self._kb_dir() / f"{topic}.json"
        return self.state_path

    def _apply_kb_entry(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = {"topic": self._safe_topic(
                payload.get("topic", "general")), "entries": []}
        if not isinstance(data, dict) or "entries" not in data:
            data = {"topic": self._safe_topic(
                payload.get("topic", "general")), "entries": []}
        entry = {
            "id": payload.get("id") or payload.get("title", "learned").lower()
                     .replace(" ", "_"),
            "title": payload.get("title", "Learned entry"),
            "keywords": payload.get("keywords", []),
            "tags": payload.get("tags", []),
            "topic": self._safe_topic(payload.get("topic", "general")),
            "formula": payload.get("formula"),
            "content": payload.get("content", ""),
            "related": payload.get("related", []),
        }
        # replace if same id/title exists, else append
        data["entries"] = [e for e in data["entries"]
                           if e.get("id") != entry["id"]
                           and e.get("title") != entry["title"]]
        data["entries"].append(entry)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    def _remove_kb_entry(self, path: Path, payload: dict) -> int:
        if not path.exists():
            return 0
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return 0
        entries = data.get("entries", [])
        before = len(entries)
        title = payload.get("title")
        eid = payload.get("id")
        entries = [e for e in entries
                   if isinstance(e, dict)
                   and e.get("title") != title and e.get("id") != eid]
        data["entries"] = entries
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return before - len(entries)

    def _run_sandbox_checks(self, prop: LearningProposal) -> dict:
        """Offline verification of the sandboxed change."""
        failures: list[str] = []
        box = Path(prop.payload.get("_sandbox", ""))

        if prop.kind == "kb_entry":
            topic = self._safe_topic(prop.payload.get("topic", "general"))
            f = box / "topics" / f"{topic}.json"
            if not f.exists():
                failures.append("sandbox topic file missing")
            else:
                try:
                    doc = json.loads(f.read_text(encoding="utf-8"))
                    entries = doc.get("entries", []) \
                        if isinstance(doc, dict) else doc
                    assert isinstance(entries, list) and entries
                    assert all(e.get("title") and e.get("content")
                               for e in entries)
                except Exception as e:  # noqa: BLE001
                    failures.append(f"json invalid: {e}")
            if self._safe_topic(prop.payload.get("topic", "")
                                ) in _FORBIDDEN_TOPICS:
                failures.append("forbidden topic")
            if not prop.payload.get("content"):
                failures.append("empty content")
        elif prop.kind == "preference":
            f = box / "prefs.json"
            if not f.exists():
                failures.append("sandbox prefs file missing")
            else:
                try:
                    prefs = json.loads(f.read_text())
                    assert isinstance(prefs, dict)
                    assert all(isinstance(v, str)
                               for k, v in prefs.items()
                               if not k.startswith("_"))
                except Exception as e:  # noqa: BLE001
                    failures.append(f"prefs invalid: {e}")
        elif prop.kind == "word_map":
            f = box / "word_map.json"
            if not f.exists():
                failures.append("sandbox word_map file missing")
            else:
                try:
                    wm = json.loads(f.read_text())
                    assert isinstance(wm, dict) and wm
                    assert all(isinstance(k, str) and isinstance(v, str)
                               for k, v in wm.items()
                               if not k.startswith("_"))
                except Exception as e:  # noqa: BLE001
                    failures.append(f"word_map invalid: {e}")

        return {"ok": not failures, "failures": failures}

    # -------------------------------------------------------- persistence
    def _save_state(self) -> None:
        try:
            self.state_path.write_text(json.dumps(
                [p.to_json() for p in self.proposals.values()],
                ensure_ascii=False, indent=2))
        except OSError as e:
            log.error("learning state save failed: %s", e)

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return
        try:
            raw = json.loads(self.state_path.read_text())
            for item in raw:
                prop = LearningProposal(
                    id=item["id"], kind=item["kind"],
                    payload=item.get("payload", {}),
                    reason=item.get("reason", ""),
                    created=item.get("created", time.time()),
                    history=item.get("history", []))
                prop.stage = Stage(item.get("stage", "proposed"))
                self.proposals[prop.id] = prop
        except Exception as e:  # noqa: BLE001
            log.error("learning state load failed: %s", e)


LEARNING = LearningEngine()
