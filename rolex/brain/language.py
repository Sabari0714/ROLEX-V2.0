"""Language detection — Tamil / English / Tanglish (fully local)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class LANG(Enum):
    TAMIL = "ta"
    ENGLISH = "en"
    TANGlish = "tanglish"
    MIXED = "mixed"
    UNKNOWN = "unknown"


_TAMIL_RANGE = re.compile(r"[\u0B80-\u0BFF]")

# High-signal Tanglish (romanized Tamil) tokens.
_TANGlish_WORDS = {
    "enna", "ennda", "epdi", "eppadi", "epo", "eppo", "enga", "yaru", "yaaru",
    "venum", "venam", "pannu", "pannanum", "panniya", "sollu", "sollunga",
    "paaru", "parunga", "seriya", "illa", "illana", "aama", "aana", "appo",
    "ippo", "innaiku", "naalaiku", "nanri", "nandri", "vanakkam", "semma",
    "superu", "vaada", "poda", "machan", "machi", "thambi", "akka", "anna",
    "irukku", "illai", "irukka", "varuthu", "vathu", "kekkuthu", "puriyuthu",
    "puriyala", "kudu", "tharuven", "romba", "konjam", "nimisham", "neram",
    "epadi", "ethana", "evlo", "evalavu", "moolam", "vagai", "kooda",
    "than", "thaan", "innum", "ippo", "appuram", "munnadi", "pinnadi",
}

# Tamil script keywords (for intent hints, matched directly on script text)
TAMIL_KEYWORDS = {
    "math_add": ["கூட்ட", "கூட்டு", "சேர்"],
    "math_sub": ["கழி", "கழித்து", "குறை"],
    "math_mul": ["பெருக்க", "பெருக்கு", "கழிக்கா"],
    "math_div": ["வகு", "வகுத்து", "பிரி", "பங்கிடு"],
    "percent": ["சதவீத", "சதவீதம்", "விழுக்காடு"],
    "question": ["என்ன", "எப்படி", "எங்க", "எப்போ", "யாரு", "ஏன்", "எத்தன"],
    "greeting": ["வணக்கம்", "ஹாய்", "ஹலோ"],
    "thanks": ["நன்றி", "தேங்க்ஸ்"],
    "time": ["நேரம்", "மணி", "தேதி", "வாரம்", "நாள்"],
    "yes": ["ஆமா", "ஆமாம்", "சரி"],
    "no": ["இல்ல", "வேண்டாம்", "இல்லை"],
}


@dataclass
class LangResult:
    lang: LANG
    confidence: float
    has_tamil_script: bool
    tanglish_hits: list


class LanguageDetector:
    """Detects Tamil script, Tanglish romanization, English, or a mix."""

    def detect(self, text: str) -> LangResult:
        t = (text or "").strip()
        if not t:
            return LangResult(LANG.UNKNOWN, 0.0, False, [])

        has_tamil = bool(_TAMIL_RANGE.search(t))
        tokens = {w.strip("!?.,:;") for w in t.lower().split()}
        hits = sorted(tokens & _TANGlish_WORDS)

        tamil_letters = len(_TAMIL_RANGE.findall(t))
        ascii_letters = len(re.findall(r"[A-Za-z]", t))

        if has_tamil and ascii_letters >= tamil_letters and hits:
            return LangResult(LANG.MIXED, 0.85, True, hits)
        if has_tamil:
            conf = min(0.9, 0.55 + tamil_letters / 30)
            return LangResult(LANG.TAMIL, conf, True, hits)
        if hits:
            conf = min(0.95, 0.55 + 0.12 * len(hits))
            return LangResult(LANG.TANGlish, conf, False, hits)
        if ascii_letters > 0 and re.search(r"[A-Za-z]{2,}", t):
            return LangResult(LANG.ENGLISH, 0.9, False, hits)
        return LangResult(LANG.UNKNOWN, 0.3, False, hits)

    # -----------------------------------------------------------
    @staticmethod
    def lang_code(result: LangResult) -> str:
        return result.lang.value

    @staticmethod
    def reply_style(lang: LANG) -> str:
        """Which language Rolex should prefer when replying."""
        if lang in (LANG.TAMIL, LANG.MIXED):
            return "ta"
        if lang == LANG.TANGlish:
            return "tanglish"
        return "en"
