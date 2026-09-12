"""Rolex Continuous Voice Conversation (Phase 13) — the full loop.

USER VOICE → wake word ("Hey Guru") → STT → Rolex pipeline:
    math (local ⚡) → commands → reminders → KB → AI hub → validator
    → ONE final Rolex answer → TTS → keep listening.

Designed for: terminal (typed fallback), Android (Kivy UI calls these
same functions), and headless testing (scripted inputs list).
"""
from __future__ import annotations

import time

from ..answer_engine.engine import ANSWER_ENGINE
from ..brain.nlu import NLU
from ..config import CONFIG
from ..core.commands import CommandProcessor
from ..knowledge.base import KnowledgeBase
from ..logging_setup import get_logger
from ..math_engine import MATH
from ..memory.store import MEMORY, Turn
from .stt import STT, typed_input
from .tts import TTS, speak_line
from .wake import WAKE

log = get_logger("voice")


class VoiceLoop:
    """The continuous conversation driver. Headless-testable."""

    def __init__(self, stt=None, tts=None, nlu=None, math=None, kb=None,
                 answer=None, memory=None, commands=None, tasks=None):
        self.stt = stt or STT
        self.tts = tts or TTS
        self.nlu = nlu or NLU()
        self.math = math or MATH
        self.kb = kb or KnowledgeBase()
        self.answer = answer or ANSWER_ENGINE
        self.memory = memory or MEMORY
        self.commands = commands or CommandProcessor()
        self.tasks = tasks
        self.session_start = time.time()
        self.turns = 0

    # ------------------------------------------------------------ turn
    def handle_utterance(self, text: str) -> str:
        """One full turn: wake check → route → answer → speak.

        Returns the final Rolex answer text (for UI display).
        """
        if not text or not text.strip():
            return "🎧 Rolex listening..."
        raw = text.strip()
        self.turns += 1

        is_wake, command = WAKE.detect(raw)
        if is_wake and not command:
            return speak("🎧 Rolex: yes?")
        if is_wake:
            raw = command          # strip wake word, keep command

        reply = self._route(raw)
        self.memory.add_exchange(raw, reply)
        return speak(reply)

    # ----------------------------------------------------------- route
    def _route(self, text: str) -> str:
        # 1. math/engineering FIRST — ⚡ always local, never AI
        sol = self.math.solve(text)
        if sol is not None:
            return f"⚡ {sol}"

        # 2. core commands (/help, /status, /whoami...)
        out = self.commands.execute(text)
        if out:
            return str(out)

        # 3. reminders / recurring (automation engine)
        if self.tasks is not None:
            t = (self.tasks.parse_reminder_text(text)
                 or self.tasks.parse_recurring_text(text))
            if t is not None:
                return f"🔔 Rolex set: {t.title} (task {t.id})"

        # 4. NLU → knowledge / chat
        result = self.nlu.analyze(text)
        intent = result.intent

        if intent in ("knowledge", "engineering", "unit_convert"):
            match = self.kb.best(query=text, min_score=2.0)
            if match is not None:
                e = match.entry
                out = f"📘 {e.title}: {e.snippet(180)}"
                if e.formula:
                    out += f" — formula: {e.formula}"
                return out
            # KB miss → answer engine (AI hub + offline fallback)
            return str(self.answer.answer(question=text, responses=None))

        if intent in ("greeting", "identity", "thanks", "capability"):
            if intent == "greeting":
                return ("👋 Rolex online! enna venum sollu — math, "
                        "engineering, knowledge, tasks ellam ready.")
            if intent == "thanks":
                return "😊 Rolex happy to help! innum kelu."
            out = self.commands.execute("/whoami")
            if out:
                return str(out)
            return ("🤖 Rolex here — local brain + math engine + "
                    "knowledge base ready.")

        # 5. everything else → answer engine (AI if keys, else KB/offline)
        return str(self.answer.answer(question=text, responses=None))

    # ------------------------------------------------------ continuous
    def run(self, max_turns: int = 0, scripted: list[str] | None = None):
        """Continuous loop. scripted=[...] drives it headless (tests +
        demos); each item is one user utterance, in order."""
        speak_line("🎧 Rolex voice session — say 'Hey Guru' to start, "
                   "'exit' to stop.")
        queue = list(scripted or [])
        turn = 0
        while True:
            if max_turns and turn >= max_turns:
                break
            if queue:
                raw = queue.pop(0)
                print(f"🧑 You: {raw}")
            else:
                raw = typed_input()
            if raw is None or raw.strip().lower() in ("exit", "quit",
                                                      "bye rolex"):
                speak_line("👋 Rolex signing off.")
                break
            if not raw.strip():
                continue
            self.handle_utterance(raw)
            turn += 1
        return self.summary()

    # ---------------------------------------------------------- misc
    def summary(self) -> dict:
        return {"turns": self.turns,
                "session_seconds": round(time.time() - self.session_start, 1),
                "stt": self.stt.available() if self.stt else None,
                "tts": self.tts.available() if self.tts else None}


def speak(text: str) -> str:
    """Speak + return text (single funnel used by VoiceLoop)."""
    speak_line(text)
    return text


VOICE = VoiceLoop()
