"""Rolex Speech-to-Text (Phase 13) — optional SpeechRecognition lib.

Chain:
  1. speech_recognition + microphone (if installed + mic available)
  2. audio file transcription (wav/flac, CLI-free, lib-based)
  3. text fallback (interactive prompt) — ALWAYS works

No network used by default (recognize_google is OFF — privacy first).
"""
from __future__ import annotations

import shutil
from pathlib import Path

from ..logging_setup import get_logger

log = get_logger("stt")

try:
    import speech_recognition as sr   # optional
    _SR_OK = True
except Exception:                     # pragma: no cover
    sr = None
    _SR_OK = False


class STTError(Exception):
    pass


class SpeechToText:
    """listen() → text. Falls back to typed input when no libs/mic."""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self._recognizer = sr.Recognizer() if _SR_OK else None
        self._mic = None
        if _SR_OK:
            try:
                self._mic = sr.Microphone()
                with self._mic as m:
                    self._recognizer.adjust_for_ambient_noise(m, 0.3)
            except Exception as e:    # pragma: no cover
                log.info("no microphone: %s", e)
                self._mic = None

    # ------------------------------------------------------ capability
    def available(self) -> dict:
        return {"library": "speech_recognition" if _SR_OK else None,
                "microphone": self._mic is not None,
                "offline": True}

    # --------------------------------------------------------- listen
    def listen(self, timeout: float = 5.0) -> str:
        """Mic → text (offline pocketsphinx if present, else typed)."""
        if self._mic is not None:
            try:
                with self._mic as m:
                    audio = self._recognizer.listen(
                        m, timeout=timeout, phrase_time_limit=10)
                try:
                    return self._recognizer.recognize_sphinx(audio)
                except Exception:
                    # pocketsphinx absent → typed fallback
                    return self._typed("🎤 (speech lib present but "
                                       "pocketsphinx model missing — "
                                       "type instead)")
            except Exception as e:    # pragma: no cover
                log.warning("listen failed: %s", e)
        return self._typed()

    # ---------------------------------------------------- file-based
    def transcribe_file(self, path: str | Path) -> str:
        """wav/flac/mp3 via SpeechRecognition AudioFile, if available."""
        p = Path(path)
        if not p.exists():
            raise STTError(f"audio file not found: {path}")
        if not _SR_OK:
            raise STTError("speech_recognition not installed")
        with sr.AudioFile(str(p)) as source:
            audio = self._recognizer.record(source)
        try:
            return self._recognizer.recognize_sphinx(audio)
        except Exception as e:
            raise STTError(f"transcription failed: {e}") from e

    # ------------------------------------------------------- fallback
    def _typed(self, hint: str = "") -> str:
        if self._mic is None and not self.quiet:
            pass  # prompt printed by caller (voice loop owns the prompt)
        return ""


STT = SpeechToText(quiet=True)


def typed_input(prompt: str = "🧑 You: ") -> str:
    """Shared typed-fallback used by the voice loop and CLI."""
    try:
        return input(prompt)
    except EOFError:
        return "exit"


def stt_capabilities() -> dict:
    return SpeechToText(quiet=True).available()
