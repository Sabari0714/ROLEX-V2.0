"""Rolex Voice Modulation — JARVIS profile (v2 §12).

User requirement: "voice & modulation Jarvis voicela irrukanum."

JARVIS-style voice characteristics:
  • lower pitch        (deeper, calmer, British-butler confidence)
  • measured rate      (not rushed — deliberate)
  • even volume        (smooth amplitude, no spikes)
  • crisp delivery     (slight pause before key answers)

Implementation (local-first, no cloud):
  • pyttsx3  → engine.setProperties (pitch via voice selection + rate)
  • espeak   → -p pitch -s speed -v voice
  • edge-tts → optional (network) 'en-GB-RyanNeural' style persona
  • Android  → ActionRecognizeSpeech/TTS via intent hook (ui layer)

Never crashes, never required. Profile system: user can pick
'jarvis' | 'assistant' | 'narrator' | custom numbers.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..config import CONFIG
from ..logging_setup import get_logger

log = get_logger("voice_mod")


@dataclass
class VoiceProfile:
    """Modulation parameters — deterministic, hardware-agnostic."""
    name: str
    rate: int = 165            # words-per-minute-ish
    pitch: int = 35            # 0-99 (espeak) / mapped elsewhere
    volume: float = 1.0        # 0.0-1.0
    pre_pause: float = 0.15    # seconds before speaking (calm delivery)
    post_pause: float = 0.05
    prefer_voice_keywords: tuple = ()   # 'male', 'en-gb', etc.
    tags: dict = field(default_factory=dict)


# ------------------------------------------------------------- profiles
JARVIS = VoiceProfile(
    name="jarvis",
    rate=158, pitch=30, volume=0.95,
    pre_pause=0.18, post_pause=0.08,
    prefer_voice_keywords=("en-gb", "male", "daniel", "ryan", "george"),
    tags={"persona": "J.A.R.V.I.S", "style": "calm-butler",
          "tamil_friendly": True})

ASSISTANT = VoiceProfile(
    name="assistant", rate=172, pitch=50, volume=1.0,
    prefer_voice_keywords=("en",))

NARRATOR = VoiceProfile(
    name="narrator", rate=140, pitch=40, volume=1.0,
    pre_pause=0.3, post_pause=0.2,
    prefer_voice_keywords=("en-us", "male"))

PROFILES = {"jarvis": JARVIS, "assistant": ASSISTANT, "narrator": NARRATOR}


class VoiceModulator:
    """Applies a VoiceProfile to whatever TTS engine is available."""

    def __init__(self, profile: VoiceProfile | str | None = None):
        self.profile = self._resolve(profile)
        self._tts = None          # lazy pyttsx3 engine
        self._espeak = shutil.which("espeak")

    # ---------------------------------------------------------- profile
    @staticmethod
    def _resolve(profile) -> VoiceProfile:
        if isinstance(profile, VoiceProfile):
            return profile
        if isinstance(profile, str) and profile.strip().lower() in PROFILES:
            return PROFILES[profile.strip().lower()]
        return JARVIS      # default = Jarvis (user requirement)

    def set_profile(self, profile: VoiceProfile | str) -> str:
        self.profile = self._resolve(profile)
        self._tts = None   # re-init engine with new properties
        return (f"🎙️ voice profile → {self.profile.name} "
                f"(rate {self.profile.rate}, pitch {self.profile.pitch})")

    def status(self) -> dict:
        return {"profile": self.profile.name,
                "rate": self.profile.rate,
                "pitch": self.profile.pitch,
                "engines": self._engines()}

    # ---------------------------------------------------------- engines
    def _engines(self) -> dict:
        return {"pyttsx3": self._pyttsx3_ok(),
                "espeak": bool(self._espeak),
                "android_tts": self._android_tts_available()}

    @staticmethod
    def _pyttsx3_ok() -> bool:
        try:
            import pyttsx3  # noqa: F401
            return True
        except Exception:                                        # noqa: BLE001
            return False

    @staticmethod
    def _android_tts_available() -> bool:
        p = Path("/system/bin/tts") 
        return p.exists() or shutil.which("termux-tts-speak") is not None

    # ------------------------------------------------------------ speak
    def speak(self, text: str) -> bool:
        """Speak with Jarvis modulation. Returns True if voiced."""
        text = (text or "").strip()
        if not text:
            return False
        p = self.profile
        # pre-pause: calm, deliberate delivery
        try:
            time_sleep(p.pre_pause)
        except Exception:                                        # noqa: BLE001
            pass
        ok = (self._speak_pyttsx3(text, p)
              or self._speak_espeak(text, p)
              or self._speak_android(text, p))
        try:
            time_sleep(p.post_pause)
        except Exception:                                        # noqa: BLE001
            pass
        return ok

    def _speak_pyttsx3(self, text: str, p: VoiceProfile) -> bool:
        try:
            if not self._pyttsx3_ok():
                return False
            if self._tts is None:
                import pyttsx3
                self._tts = pyttsx3.init()
                self._pick_voice(self._tts, p)
            self._tts.setProperty("rate", p.rate)
            self._tts.setProperty("volume", p.volume)
            self._tts.say(text)
            self._tts.runAndWait()
            return True
        except Exception as e:                                   # noqa: BLE001
            log.debug("pyttsx3 speak: %s", e)
            self._tts = None
            return False

    @staticmethod
    def _pick_voice(engine, p: VoiceProfile) -> None:
        """Choose the most Jarvis-like installed voice."""
        try:
            voices = engine.getProperty("voices") or []
            best, best_score = None, -1
            for v in voices:
                ident = f"{(v.id or '').lower()} {str(getattr(v, 'name', '')).lower()}"
                score = 0
                for kw in p.prefer_voice_keywords:
                    if kw in ident:
                        score += 1
                if score > best_score:
                    best, best_score = v, score
            if best is not None:
                engine.setProperty("voice", best.id)
        except Exception as e:                                   # noqa: BLE001
            log.debug("voice pick: %s", e)

    def _speak_espeak(self, text: str, p: VoiceProfile) -> bool:
        if not self._espeak:
            return False
        try:
            subprocess.run(
                [self._espeak, "-s", str(p.rate * 6),       # wpm→wps scale
                 "-p", str(p.pitch), "-a", str(int(p.volume * 100)),
                 "-v", "en-gb", text],
                capture_output=True, timeout=20)
            return True
        except Exception as e:                                   # noqa: BLE001
            log.debug("espeak: %s", e)
            return False

    def _speak_android(self, text: str, p: VoiceProfile) -> bool:
        """Termux TTS / Android intent hook."""
        tts_speak = shutil.which("termux-tts-speak")
        if tts_speak:
            try:
                subprocess.run(
                    [tts_speak, "-p", str(p.pitch), "-r", str(p.rate),
                     text],
                    capture_output=True, timeout=25)
                return True
            except Exception:                                    # noqa: BLE001
                return False
        # Android TTS intent (via am) — best-effort
        am = shutil.which("am")
        if am and Path("/system/bin").exists():
            try:
                subprocess.run(
                    [am, "start-activity", "-a",
                     "android.intent.action.SPEAK_TTS",
                     "--es", "android.intent.extra.TEXT", text],
                    capture_output=True, timeout=10)
                return True
            except Exception:                                    # noqa: BLE001
                return False
        return False

    # ---------------------------------------------------- natural lang
    _RE_SET = re.compile(
        r"^(?:set|change|use|switch)\s+voice\s+(?:to\s+|profile\s+)?"
        r"(jarvis|assistant|narrator|normal|default)\b.*$", re.I)
    _RE_STATUS = re.compile(r"^voice\s+(status|info|profile)\b.*$", re.I)

    def parse_command(self, text: str) -> str:
        low = (text or "").strip().lower()
        m = self._RE_SET.match(low)
        if m:
            want = m.group(1)
            if want in ("normal", "default"):
                want = "assistant"
            return self.set_profile(want)
        m = self._RE_STATUS.match(low)
        if m:
            s = self.status()
            eng = ", ".join(k for k, v in s["engines"].items() if v) or "none"
            return (f"🎙️ voice: {s['profile']} · rate {s['rate']} · "
                    f"pitch {s['pitch']} · engines: {eng}")
        return ""


def time_sleep(sec: float) -> None:
    import time as _t
    _t.sleep(max(0.0, sec))


MODULATOR = VoiceModulator("jarvis")
