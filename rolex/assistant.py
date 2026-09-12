"""Rolex Assistant — the ONE integration object (v2 master blueprint).

Every engine wired together behind a single ask() call:

    USER ─→ RolexAssistant.ask(text)
              ├─ wake word "Hey Guru" (§12)
              ├─ math/engineering ⚡ LOCAL (§3)
              ├─ commands (§4) + memory NL (§2)
              ├─ task manager (§9) + planning (§10)
              ├─ reminders (automation) + life modules (§23–29)
              ├─ knowledge base 📘 LOCAL (§7)
              ├─ weather/web live info 🌐 optional (§6, §32)
              ├─ documents 📄 (§8) + tools 🔧 gated (§4.2)
              ├─ smart home (§30) + device (§31)
              ├─ voice profile (§12 Jarvis)
              ├─ AI hub parallel (§5 optional) → validator (§1.2)
              ├─ memory 💾 (§2) + learning 🎓 (§39)
              └─ security 🛡 (§16) wraps everything

Local-first chain (§5.4): local intelligence → local tools → cached
knowledge → offline response. External AI only when explicitly needed.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .answer_engine.engine import ANSWER_ENGINE
from .automation.engine import TASKS
from .brain.nlu import NLU
from .config import CONFIG
from .core.commands import CommandProcessor
from .core.identity import IDENTITY
from .core.lifecycle import RolexLifecycle
from .documents.engine import DOC_ENGINE
from .knowledge.base import KnowledgeBase
from .logging_setup import get_logger
from .math_engine import MATH
from .memory.store import MEMORY
from .security import run_recovery
from .voice.voice import VoiceLoop
from .voice.wake import WAKE

# ---- v2 modules ------------------------------------------------------
from .tasks.manager import TASKS_MGR            # §9 todo system
from .planning.engine import PLANNER            # §10 planning
from .live.engine import WEATHER, WEBSEARCH     # §6/§32 live info
from .life import life_route                    # §23–29 life modules
from .smarthome import SMARTHOME                # §30 VI2
from .device import DEVICE                      # §31 device mgmt
from .sync.engine import CLOUD as SYNC_CLOUD    # §20 sync/backup
from .voice.modulation import MODULATOR         # §12 Jarvis voice

log = get_logger("assistant")


def safe_parse(fn, text: str, *args, **kwargs) -> str:
    """Run a module parse_command()/API defensively — '' means 'not mine'.

    Any unexpected exception in an optional module must never crash the
    assistant (§33 resilience); it just means that module skipped.
    """
    try:
        out = fn(text, *args, **kwargs)
        return str(out) if out else ""
    except Exception as exc:            # noqa: BLE001
        log.debug("module %s skipped: %s", getattr(fn, "__qualname__", fn), exc)
        return ""


@dataclass
class AskResult:
    text: str                    # final user-facing answer
    route: str                   # wake | math | command | memory | task |
                                 # plan | live | life | smarthome | device |
                                 # reminder | knowledge | document | ai | chat
    confidence: float = 1.0
    local: bool = True           # answered 100% on-device?
    seconds: float = 0.0

    def __str__(self) -> str:    # noqa: D105
        tag = "LOCAL" if self.local else "AI"
        return f"{self.text}   [{tag}·{self.route}·{self.confidence:.2f}]"


class RolexAssistant:
    """Single public API for every Rolex front-end."""

    def __init__(self, tasks=None, memory=None, docs=None, kb=None,
                 taskmgr=None, planner=None):
        self.nlu = NLU()
        self.math = MATH
        self.kb = kb or KnowledgeBase()
        self.commands = CommandProcessor()
        self.memory = memory or MEMORY
        self.tasks = tasks or TASKS
        self.docs = docs or DOC_ENGINE
        self.answer = ANSWER_ENGINE
        # ---- v2 wiring (\u00a79/\u00a710 + friends) ------------------------
        self.taskmgr = taskmgr or TASKS_MGR
        self.planner = planner or PLANNER
        self.voice_loop = VoiceLoop(tasks=self.tasks, memory=self.memory)
        self.lifecycle = RolexLifecycle(modules={
            "brain": self.nlu, "math": self.math, "knowledge": self.kb,
            "memory": self.memory, "tasks": self.tasks,
            "answer": self.answer, "docs": self.docs,
            "todos": self.taskmgr, "planner": self.planner,
        })
        self.turns = 0
        self.started_at = time.time()

    # -------------------------------------------------------- lifecycle
    def startup(self) -> dict:
        recovery = run_recovery()          # crash markers → clean
        report = self.lifecycle.startup()
        report["recovery"] = recovery
        log.info("Rolex assistant online (v%s)", IDENTITY.version)
        return report

    def shutdown(self) -> dict:
        return self.lifecycle.shutdown("assistant")

    def status(self) -> dict:
        try:
            health = self.lifecycle.status()
            state = health.get("system", {}).get("state", "unknown")
        except Exception:                  # noqa: BLE001
            state = "unknown"
        todos_pending = 0
        try:
            todos_pending = self.taskmgr.stats().get("pending", 0)
        except Exception:                  # noqa: BLE001
            pass
        return {
            "identity": IDENTITY.name,
            "version": IDENTITY.version,
            "state": state,
            "uptime_min": round((time.time() - self.started_at) / 60, 1),
            "turns": self.turns,
            "kb_entries": self.kb.count(),
            "tasks_pending": len(self.tasks.upcoming()),
            "todos_pending": todos_pending,
            "memory_kb": self.memory.stats().get("size_kb", 0),
        }

    # ------------------------------------------------------------- ask
    def ask(self, text: str) -> AskResult:
        """The single entry point. Returns the final Rolex answer.

        v2 routing order (local-first, §47 core principle):
          math → commands → memory NL → task mgr → planning →
          reminders → life → smarthome → device → weather → search →
          documents → knowledge → AI-hub(optional) → offline fallback
        """
        t0 = time.time()
        raw = (text or "").strip()
        if not raw:
            return AskResult("🎧 Listening...", "wake")
        self.turns += 1
        self._last_user = raw
        is_wake, command = WAKE.detect(raw)
        if is_wake:
            if not command:
                return self._done("🎧 Rolex: yes?", "wake", 1.0, True, t0)
            raw = command

        # 1. ⚡ math always local (§3)
        sol = self.math.solve(raw)
        if sol is not None:
            return self._done(f"⚡ {sol}", "math", 1.0, True, t0)

        # 2. system commands (§4.1)
        out = self.commands.execute(raw)
        if out:
            return self._done(str(out), "command", 1.0, True, t0)

        # 3. memory natural language (§2.4)
        mem_out = self._maybe_memory(raw)
        if mem_out:
            return self._done(mem_out, "memory", 0.95, True, t0)

        # 4. voice profile (§12 Jarvis modulation)
        vp = MODULATOR.parse_command(raw)
        if vp:
            return self._done(vp, "voice", 1.0, True, t0)

        # 5. task manager todo (§9)
        task_out = safe_parse(self.taskmgr.parse_command, raw)
        if task_out:
            return self._done(task_out, "task", 0.95, True, t0)

        # 6. planning engine (§10)
        plan_out = safe_parse(self.planner.parse_command, raw)
        if plan_out:
            return self._done(plan_out, "plan", 0.95, True, t0)

        # 7. reminders/recurring (automation engine)
        t = (self.tasks.parse_reminder_text(raw)
             or self.tasks.parse_recurring_text(raw))
        if t is not None:
            return self._done(
                f"🔔 Rolex set: {t.title} (task {t.id})",
                "reminder", 1.0, True, t0)

        # 8. life modules (§23–29)
        life_out = safe_parse(life_route, raw)
        if life_out:
            return self._done(life_out, "life", 0.9, True, t0)

        # 9. smart home VI2 (§30)
        sm_out = safe_parse(SMARTHOME.parse_command, raw)
        if sm_out:
            return self._done(sm_out, "smarthome", 0.9, True, t0)

        # 10. device manager (§31)
        dev_out = safe_parse(DEVICE.parse_command, raw)
        if dev_out:
            return self._done(dev_out, "device", 1.0, True, t0)

        # 11. weather (§6.3 — optional external, cached)
        w_out = safe_parse(WEATHER.parse_command, raw)
        if w_out:
            return self._done(w_out, "live", 0.9, True, t0)

        # 12. web search (§6.1 — optional external, explicit)
        s_out = safe_parse(WEBSEARCH.parse_command, raw)
        if s_out:
            return self._done(s_out, "live", 0.9, False, t0)

        # 13. sync/backup (§20)
        sync_out = safe_parse(SYNC_CLOUD.parse_command, raw)
        if sync_out:
            return self._done(sync_out, "sync", 1.0, True, t0)

        # 14. documents: "summarize file.pdf" style (§8)
        doc_reply = self._maybe_document(raw)
        if doc_reply:
            return self._done(doc_reply, "document", 0.9, True, t0)

        # 15. knowledge (KB first, AI only on miss) (§7)
        match = self.kb.best(query=raw, min_score=2.0)
        if match is not None:
            e = match.entry
            out = f"📘 {e.title}: {e.snippet(200)}"
            if e.formula:
                out += f" — formula: {e.formula}"
            return self._done(out, "knowledge", min(1.0, 0.5 + match.score / 10),
                              True, t0)

        # 16. AI hub → answer engine (optional, §5) — may fall back offline
        fa = self.answer.answer(question=raw, responses=None)
        conf = fa.confidence
        return self._done(str(fa), "ai" if fa.used_kb_fallback is False
                          else "offline", conf, fa.used_kb_fallback is False
                          or fa.route == "offline", t0)

    # ------------------------------------------------------ memory NL
    _MEM_RE = None

    def _maybe_memory(self, raw: str) -> str | None:
        """'remember ...', 'recall ...', 'forget ...', 'what do you know
        about ...' → memory store ops (§2.4)."""
        import re
        if RolexAssistant._MEM_RE is None:
            RolexAssistant._MEM_RE = {
                "remember": re.compile(
                    r"^remember(?:\s+that)?\s+(.+?)\s*$", re.I),
                "recall": re.compile(
                    r"^(?:recall|what\s+do\s+you\s+(?:know|remember)\s+"
                    r"about)\s+(.+?)\s*\??$", re.I),
                "forget": re.compile(
                    r"^forget\s+(?:about\s+)?(.+?)\s*$", re.I),
                "prefs": re.compile(
                    r"^(?:my\s+)?preferences\s*$", re.I),
            }
        low = raw.strip()
        m = RolexAssistant._MEM_RE["remember"].match(low)
        if m:
            fact = m.group(1).strip()
            key = self._mem_key(fact)
            self.memory.remember(key, fact, fact_type="user")
            return f"💾 Rolex-க்கு நினைவில் · remembered: {fact[:120]}"
        m = RolexAssistant._MEM_RE["recall"].match(low)
        if m:
            q = m.group(1).strip()
            hits = self.memory.search_facts(q, limit=5)
            if hits:
                lines = [f"💾 Rolex memory · {q}:"]
                for h in hits:
                    val = getattr(h, "value", "") or str(h)
                    lines.append(f"   • {str(val)[:160]}")
                return "\n".join(lines)
            return (f"💾 '{q}' பற்றி இன்னும் கற்றவில்லை · nothing "
                    f"remembered yet.")
        m = RolexAssistant._MEM_RE["forget"].match(low)
        if m:
            q = m.group(1).strip()
            # exact key first, then content search — users say "forget my
            # bike", but stored keys are derived ("bike black gold"). §2.4
            n = self.memory.forget(q) or 0
            if not n:
                hits = []
                try:
                    hits = self.memory.search_facts(q, limit=10) or []
                except Exception as exc:            # noqa: BLE001
                    log.debug("memory search during forget: %s", exc)
                for h in hits:
                    k = getattr(h, "key", "") or ""
                    v = getattr(h, "value", "") or ""
                    if k:
                        n += self.memory.forget(k, v) or 0
            if n:
                return (f"🗑️ {n} memory entr(ies) நீக்கப்பட்டது · "
                        f"forgotten ({q[:60]}).")
            return f"🤷 '{q}' memory-ல் இல்லை."
        m = RolexAssistant._MEM_RE["prefs"].match(low)
        if m:
            prefs = self.memory.all_prefs()
            if not prefs:
                return "💾 preferences இன்னும் இல்லை · none saved yet."
            lines = ["💾 Rolex knows these preferences:"]
            for k, v in list(prefs.items())[:12]:
                lines.append(f"   • {k}: {str(v)[:100]}")
            return "\n".join(lines)
        return None

    @staticmethod
    def _mem_key(fact: str) -> str:
        """Derive a stable memory key from a fact sentence."""
        words = [w for w in fact.lower().split() if len(w) > 2][:4]
        return " ".join(words) if words else "fact"

    # ------------------------------------------------------- documents
    _DOC_RE = None

    def _maybe_document(self, raw: str) -> str | None:
        import re
        if RolexAssistant._DOC_RE is None:
            RolexAssistant._DOC_RE = re.compile(
                r"(?:summarize|summary|analyse|analyze|read|open)\s+"
                r"([\w./\\-]+\.(?:txt|md|csv|json|pdf|docx|xlsx|pptx))",
                re.IGNORECASE)
        m = RolexAssistant._DOC_RE.search(raw)
        if not m:
            return None
        path = m.group(1)
        try:
            s = self.docs.analyze(path)
            return (f"📄 {s.path} ({s.format.upper()}, {s.size_kb}KB): "
                    f"{s.words} words · keywords: "
                    f"{', '.join(s.top_keywords[:5])} — {s.summary[:250]}")
        except Exception as e:                # noqa: BLE001
            return f"📄 document error: {e}"

    # ---------------------------------------------------------- finish
    def _done(self, text: str, route: str, conf: float,
              local: bool, t0: float) -> AskResult:
        self.memory.add_exchange(getattr(self, "_last_user", ""), text)
        return AskResult(text=text, route=route, confidence=conf,
                         local=local, seconds=round(time.time() - t0, 3))

    # ---------------------------------------------------------- voice
    def voice_session(self, scripted: list[str] | None = None,
                      max_turns: int = 0) -> dict:
        return self.voice_loop.run(scripted=scripted, max_turns=max_turns)


# module-level singleton (lazy)
ASSISTANT: RolexAssistant | None = None


def get_assistant() -> RolexAssistant:
    global ASSISTANT
    if ASSISTANT is None:
        ASSISTANT = RolexAssistant()
    return ASSISTANT
