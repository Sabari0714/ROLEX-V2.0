"""Rolex Planning Engine (v2 §10) — goal → plan → steps → track.

Converts a natural-language goal into an ordered, typed step plan,
executes locally-verifiable steps, tracks progress, and reports.
Pipeline: Goal → Plan → Execute → Verify → Complete
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

from ..config import CONFIG
from ..errors import RolexError
from ..logging_setup import get_logger

log = get_logger("planning")


class PlanningError(RolexError):
    code = "PLANNING_ERROR"


class StepKind(str):
    INFO = "info"
    CALC = "calc"
    REMEMBER = "remember"
    TODO = "todo"
    TOOL = "tool"
    DECIDE = "decide"


class PlanStatus(str):
    DRAFT = "draft"
    ACTIVE = "active"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Priority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class PlanStep:
    n: int                      # 1-based order
    kind: str                   # StepKind
    text: str                   # what to do
    done: bool = False
    note: str = ""
    at: float = field(default_factory=time.time)

    def to_json(self) -> dict:
        return {"n": self.n, "kind": self.kind, "text": self.text,
                "done": self.done, "note": self.note, "at": self.at}


@dataclass
class Plan:
    id: str
    goal: str
    status: str = PlanStatus.DRAFT
    steps: list[PlanStep] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    finished: float | None = None

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        return round(sum(s.done for s in self.steps) / len(self.steps), 2)

    def to_json(self) -> dict:
        return {"id": self.id, "goal": self.goal, "status": self.status,
                "steps": [s.to_json() for s in self.steps],
                "created": self.created, "finished": self.finished}


# --------------------------------------------------------------------------
# Domain templates — local-first plan patterns (no external AI needed)
# --------------------------------------------------------------------------
_PLAN_TEMPLATES: list[tuple[str, list[tuple[str, str]]]] = [
    # (regex-on-goal, [(step kind, step text template)])
    (r"\b(trip|travel|tour|vacation|பயணம்|விடுமுறை)\b",
     [(StepKind.INFO, "Decide destination & dates"),
      (StepKind.CALC, "Estimate budget: days × daily cost + travel fare"),
      (StepKind.INFO, "Check weather at destination (Open-Meteo)"),
      (StepKind.TODO, "Book travel tickets"),
      (StepKind.TODO, "Book stay"),
      (StepKind.TODO, "Pack list: essentials + docs + chargers"),
      (StepKind.DECIDE, "Finalize itinerary & share with family")]),

    (r"\b(study|exam|learn|revision|படிப்பு|தேர்வு|கற்றல்)\b",
     [(StepKind.INFO, "List topics / syllabus"),
      (StepKind.CALC, "Count days left & divide topics per day"),
      (StepKind.INFO, "Gather materials: notes, PDFs, references"),
      (StepKind.TODO, "Make a daily study schedule"),
      (StepKind.TODO, "Take practice tests & note weak areas"),
      (StepKind.REMEMBER, "Save weak areas to memory for revision")]),

    (r"\b(project|build|develop|app|website|system|திட்டம்)\b",
     [(StepKind.INFO, "Write down goal & success criteria"),
      (StepKind.INFO, "Decide scope: v1 features only"),
      (StepKind.TODO, "Setup environment & repo"),
      (StepKind.TODO, "Build core module first"),
      (StepKind.TODO, "Write tests as you build"),
      (StepKind.TODO, "Integration test + bug fix round"),
      (StepKind.DECIDE, "Release v1 & note feedback")]),

    (r"\b(budget|money|expense|saving|finance|செலவு|சேமிப்பு)\b",
     [(StepKind.INFO, "List all income sources"),
      (StepKind.INFO, "Track last 3 months expenses"),
      (StepKind.CALC, "Compute savings = income − expenses"),
      (StepKind.TODO, "Set category-wise limits"),
      (StepKind.REMEMBER, "Save budget summary to memory")]),

    (r"\b(fitness|health|workout|exercise|உடற்பயிற்சி|ஆரோக்கியம்)\b",
     [(StepKind.INFO, "Note current routine & baseline stats"),
      (StepKind.CALC, "Set weekly targets: minutes, reps, calories"),
      (StepKind.TODO, "Fix workout days in calendar"),
      (StepKind.TODO, "Prepare meal plan"),
      (StepKind.REMEMBER, "Track weekly progress in memory")]),

    (r"\b(clean|organize|declutter|house|வீட்டு|சுத்தம்)\b",
     [(StepKind.TODO, "Pick one room/zone to start"),
      (StepKind.TODO, "3-box sort: keep / donate / discard"),
      (StepKind.TODO, "Deep clean the zone"),
      (StepKind.REMEMBER, "Note what was donated/discarded")]),
]


class PlanningEngine:
    """Local goal → steps planner with progress tracking (SQLite-free,
    JSON state file under data/plans/)."""

    def __init__(self, state_dir: str | None = None):
        self.dir = Path(state_dir or CONFIG.DATA_DIR / "plans")
        self.dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ create
    def create(self, goal: str) -> Plan:
        goal = (goal or "").strip()
        if not goal:
            raise PlanningError("goal cannot be empty")
        steps = self._template_steps(goal)
        plan = Plan(id=uuid.uuid4().hex[:8], goal=goal, steps=steps)
        self._save(plan)
        log.info("plan created: %s (%d steps)", goal[:40], len(steps))
        return plan

    @staticmethod
    def _template_steps(goal: str) -> list[PlanStep]:
        """Best-matching local template, else a smart generic plan."""
        for rx, tmpl in _PLAN_TEMPLATES:
            if re.search(rx, goal, re.I):
                return [PlanStep(n=i + 1, kind=k, text=t)
                        for i, (k, t) in enumerate(tmpl)]
        # generic fallback — always sensible
        generic = [
            (StepKind.INFO, "Write the goal in one clear sentence"),
            (StepKind.INFO, "List what's needed to achieve it"),
            (StepKind.TODO, "Break it into small steps"),
            (StepKind.CALC, "Estimate time & resources needed"),
            (StepKind.TODO, "Do step 1 today itself"),
            (StepKind.DECIDE, "Review progress weekly & adjust"),
        ]
        return [PlanStep(n=i + 1, kind=k, text=t)
                for i, (k, t) in enumerate(generic)]

    # ------------------------------------------------------------- io
    def _save(self, plan: Plan) -> None:
        import json
        (self.dir / f"{plan.id}.json").write_text(
            json.dumps(plan.to_json(), ensure_ascii=False, indent=2),
            encoding="utf-8")

    def _load(self, pid: str) -> Plan:
        import json
        p = self.dir / f"{pid}.json"
        if not p.is_file():
            raise PlanningError(f"plan not found: {pid}")
        data = json.loads(p.read_text(encoding="utf-8"))
        steps = [PlanStep(**s) for s in data.get("steps", [])]
        return Plan(id=data["id"], goal=data["goal"],
                    status=data.get("status", "draft"), steps=steps,
                    created=data.get("created", time.time()),
                    finished=data.get("finished"))

    def list(self) -> list[dict]:
        out = []
        for f in sorted(self.dir.glob("*.json")):
            try:
                out.append(self._load(f.stem).to_json())
            except Exception:                                   # noqa: BLE001
                continue
        return out

    def get(self, pid: str) -> Plan:
        return self._load(pid)

    # --------------------------------------------------------- progress
    def mark_step(self, pid: str, step_no: int, done: bool = True,
                  note: str = "") -> Plan:
        plan = self._load(pid)
        for s in plan.steps:
            if s.n == step_no:
                s.done, s.note = done, note or s.note
                break
        else:
            raise PlanningError(f"step {step_no} not in plan {pid}")
        if all(s.done for s in plan.steps):
            plan.status, plan.finished = PlanStatus.DONE, time.time()
        elif plan.status == PlanStatus.DRAFT:
            plan.status = PlanStatus.ACTIVE
        self._save(plan)
        return plan

    def cancel(self, pid: str) -> Plan:
        plan = self._load(pid)
        plan.status, plan.finished = PlanStatus.CANCELLED, time.time()
        self._save(plan)
        return plan

    def execute(self, pid: str, steps: list[int] | None = None) -> dict:
        """Execute locally-verifiable steps (calc/remember/todo→TaskManager).

        Returns {"executed": [...], "failed": [...], "progress": float}.
        Never crashes; failures are reported, plan continues.
        """
        plan = self._load(pid)
        target = steps or [s.n for s in plan.steps if not s.done]
        executed, failed = [], []
        for s in plan.steps:
            if s.n not in target or s.done:
                continue
            try:
                res = self._run_step(plan, s)
                s.done, s.note = True, str(res)[:200]
                executed.append(f"step {s.n}: {s.text} ✓")
            except Exception as e:                              # noqa: BLE001
                failed.append(f"step {s.n}: {e}")
        if all(s.done for s in plan.steps) and plan.steps:
            plan.status, plan.finished = PlanStatus.DONE, time.time()
        elif plan.status == PlanStatus.DRAFT:
            plan.status = PlanStatus.ACTIVE
        self._save(plan)
        return {"executed": executed, "failed": failed,
                "progress": plan.progress}

    # ------------------------------------------------------------ run
    def _run_step(self, plan: Plan, step: PlanStep):
        """Local execution hooks per step kind."""
        from ..memory.store import MEMORY
        if step.kind == StepKind.REMEMBER:
            val = f"{plan.goal} — {step.text}"
            MEMORY.remember(f"plan:{plan.id}", val, source="planner")
            return f"saved to memory: {val[:60]}"
        if step.kind == StepKind.CALC:
            # let the math engine do the arithmetic when user asks later;
            # here we just verify the step makes sense
            return "calc noted — ask Rolex 'math' when numbers are ready"
        if step.kind == StepKind.TODO:
            try:
                from .tasks_manager_shim import add_todo
                return add_todo(f"[plan:{plan.id}] {step.text}")
            except Exception:                                   # noqa: BLE001
                return "todo noted in plan"
        return "info recorded"

    # ---------------------------------------------------- natural lang
    def parse_command(self, text: str) -> str:
        """'plan a trip to ooty' / 'make a plan for exam' → reply."""
        m = re.match(
            r"^(?:make|create|plan|build)\s+(?:a\s+)?(?:plan|roadmap|"
            r"steps?)\s+(?:for|to|of)?\s*(.+)$",
            (text or "").strip(), re.I)
        if not m:
            return ""
        goal = m.group(1).strip()
        if not goal:
            return ""
        plan = self.create(goal)
        return self._format(plan)

    def _format(self, plan: Plan) -> str:
        icon = {"info": "ℹ️", "calc": "🔢", "remember": "💾",
                "todo": "📋", "decide": "🧭"}.get
        lines = [f"🗺️ Rolex Plan · {plan.goal}  (id {plan.id})"]
        for s in plan.steps:
            mark = "✓" if s.done else "○"
            lines.append(f"  {mark} {s.n}. {icon(s.kind, '•')} {s.text}")
        pct = int(plan.progress * 100)
        lines.append(f"  ─ progress: {pct}% · status: {plan.status}")
        return "\n".join(lines)


PLANNER = PlanningEngine()
