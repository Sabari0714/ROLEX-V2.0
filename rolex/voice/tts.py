"""Rolex Text-to-Speech (Phase 13) — optional engines, print fallback.

Chain (v2.2):
  1. ElevenLabs (network, opt-in via ELEVENLABS_API_KEY) — premium voice
  2. pyttsx3    (offline, cross-platform)
  3. espeak CLI (Linux servers / Termux)
  4. plain print
NEVER crashes; speaking is cosmetic, answers are not. Local-first:
pyttsx3 wins when ElevenLabs key absent or network down.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

from ..logging_setup import get_logger

log = get_logger("tts")

try:
    import pyttsx3
    _TTS_OK = True
except Exception:                     # pragma: no cover
    pyttsx3 = None
    _TTS_OK = False


def _eleven_key() -> str:
    """Live key read: env first, then encrypted data/secrets.json."""
    val = os.getenv("ELEVENLABS_API_KEY", "")
    if val:
        return val
    try:
        from ..security.secrets import SECRETS
        return SECRETS.get("ELEVENLABS_API_KEY") or ""
    except Exception:                               # noqa: BLE001
        return ""


class ElevenLabsTTS:
    """Minimal ElevenLabs REST client — stdlib only, no SDK dependency.

    Uses the default 'Rachel' voice; mp3 bytes → temp file → player.
    Falls back silently when key absent/offline.
    """

    URL = ("https://api.elevenlabs.io/v1/text-to-speech/"
           "21m00Tcm4TlvDq8ikWAM")
    TIMEOUT = 15.0

    def __init__(self):
        self._player = (shutil.which("ffplay") or shutil.which("mpv")
                        or shutil.which("afplay"))

    def available(self) -> bool:
        return bool(_eleven_key() and self._player)

    def speak(self, text: str, rate: int = 170) -> bool:
        if not self.available():
            return False
        key = _eleven_key()
        body = (b'{"text": ' + _dumps(text).encode("utf-8") +
                b', "model_id": "eleven_multilingual_v2"}')
        req = urllib.request.Request(
            self.URL, data=body, method="POST",
            headers={"xi-api-key": key,
                     "Content-Type": "application/json",
                     "Accept": "audio/mpeg"})
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as r:
                audio = r.read()
            if len(audio) < 512:
                return False
            tmp = Path(subprocess.devnull).with_name("rolex_tts")
            tmp = tmp.with_suffix(".mp3")
            tmp.write_bytes(audio)
            subprocess.run([self._player, "-nodisp", "-autoexit",
                            "-loglevel", "quiet", str(tmp)],
                           capture_output=True, timeout=20)
            try:
                tmp.unlink(missing_ok=True)
            except Exception:                       # noqa: BLE001
                pass
            return True
        except Exception as e:                      # noqa: BLE001
            log.info("elevenlabs unavailable: %s", e)
            return False


def _dumps(s: str) -> str:
    import json
    return json.dumps(s)


class TextToSpeech:
    """speak() → voice if possible; return False when no voice is emitted."""

    def __init__(self, enabled: bool = True, rate: int = 170):
        self.enabled = enabled
        self.rate = rate
        self.eleven = ElevenLabsTTS()
        self._ci_headless = os.getenv("CI", "").lower() == "true"
        self.engine = None
        if _TTS_OK and not self._ci_headless:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty("rate", self.rate)
            except Exception as e:    # pragma: no cover
                log.info("pyttsx3 init failed: %s", e)
                self.engine = None
        self._espeak = shutil.which("espeak")
        self._say = shutil.which("say")

    def available(self) -> dict:
        return {"pyttsx3": self.engine is not None,
                "elevenlabs": self.eleven.available(),
                "espeak": self._espeak is not None,
                "enabled": self.enabled}

    def speak(self, text: str) -> bool:
        """Speak out loud; return True only when audio was actually emitted."""
        if not self.enabled or not text:
            return False
        if self.eleven.available():
            try:
                if self.eleven.speak(text, self.rate):
                    return True
            except Exception as e:                  # noqa: BLE001
                log.warning("elevenlabs speak failed: %s", e)
        # CI runners are intentionally audio-silent. Do not treat an
        # installed headless espeak/pyttsx3 backend as successful speech.
        if self._ci_headless:
            return False
        if self.engine is not None:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
                return True
            except Exception as e:    # pragma: no cover
                log.warning("pyttsx3 speak failed: %s", e)
        if self._espeak:
            try:
                subprocess.run([self._espeak, "-s", str(self.rate), text],
                               capture_output=True, timeout=15)
                return True
            except Exception as e:                      # noqa: BLE001
                log.warning("espeak failed: %s", e)
        return False


TTS = TextToSpeech()


def speak_line(text: str) -> None:
    """Always prints the line; voices it when possible."""
    print(f"\U0001F50A {text}")
    TTS.speak(text)
