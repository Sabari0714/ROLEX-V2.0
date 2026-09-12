"""Rolex Wake Word (Phase 13) — "Hey Guru" detection.

Works on any transcript source (text input, STT result, chat line).
Fuzzy-tolerant: "hey guru", "hi guru", "hey gurru", "guru" alone,
"வணக்கம் குரு" variations — because speech-to-text mishears words.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..config import CONFIG

# exact-ish forms (normalized)
_EXACT = [
    "hey guru", "hi guru", "hello guru", "ok guru", "yo guru",
    "hey google",  # common STT mishear of "guru"
    "a guru", "eh guru", "hey gu", "hey gur",
]

# single-word fallback threshold
_SIMILAR = 0.82


class WakeWord:
    """Detects "Hey Guru" in raw text, strips it from the command."""

    def __init__(self, phrase: str = CONFIG.WAKE_WORD):
        self.phrase = (phrase or "hey guru").strip().lower()
        self._rx = re.compile(
            r"^\s*(hey|hi|hello|ok|yo|ay|வணக்கம்)?\s*"
            r"(guru+|gurru|guuru|googly|google|குரு)\b",
            re.IGNORECASE)

    # ------------------------------------------------------------ detect
    def detect(self, text: str) -> tuple[bool, str]:
        """Return (is_wake, cleaned_text_after_wake_word).

        cleaned_text keeps everything AFTER the wake word — that is the
        actual user command. If not a wake, cleaned = original text.
        """
        raw = (text or "").strip()
        if not raw:
            return False, ""
        low = re.sub(r"\s+", " ", raw).lower()

        # 1. exact normalized match on the whole phrase
        if low == self.phrase or low == "hey guru":
            return True, ""

        # 2. regex: wake word at start + a command after it
        m = self._rx.match(low)
        if m:
            return True, raw[m.end():].strip()

        # 3. fuzzy whole-phrase compare (STT mishears)
        ratio = SequenceMatcher(None, low, self.phrase).ratio()
        if ratio >= _SIMILAR:
            return True, ""

        # 4. single "guru" anywhere → treat as wake with command
        if re.search(r"(^|\s)(guru|குரு)(\s|$)", low):
            stripped = re.sub(
                r"(^|\s)(guru|குரு)(\s|$)", " ", low, count=1).strip()
            return True, stripped

        return False, raw


WAKE = WakeWord()
