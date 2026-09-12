"""Intent detection — rule-based, fast, fully offline (Phase 3)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .language import LANG, _TAMIL_RANGE, TAMIL_KEYWORDS


@dataclass
class IntentResult:
    intent: str
    confidence: float
    slots: dict = field(default_factory=dict)


# Ordered rules — first match wins. Priority matters.
_RULES: list[tuple[str, float, re.Pattern]] = [
    ("greeting",  0.95, re.compile(r"^(hi+|hai+|hey+|hello+|vanakkam|vanakam|"
                                   r"good (morning|afternoon|evening)|"
                                   r"வணக்கம்|ஹாய்|ஹலோ)[\s!.,]*$", re.I)),
    ("identity",  0.9,  re.compile(r"(who are you|your name|what are you|"
                                   r"introduce yourself|nee yaru|ni yaru|"
                                   r"நீ யாரு|உன் பெயர்)", re.I)),
    ("math",      0.9,  re.compile(r"(\d+\s*[+\-x×*/÷^%]\s*\d+)|"
                                   r"(plus|minus|times|multiplied by|divided by|"
                                   r"power of|square root|sqrt|cube root|"
                                   r"percentage|percent of|mod of|factorial)|"
                                   r"(sin|cos|tan|atan|asin|acos)\s*\(?\s*\d|"
                                   r"(\d+\s*(கூட்டு|கழி|பெருக்கு|வகு))|"
                                   r"\b(koodu|kooduthal|kalangu|vagu|vaagai|vagai|"
                                   r"perukku|perukkuthal|satham|vargam|"
                                   r"vargamoolam|chiram)\b", re.I)),
    ("engineering", 0.85, re.compile(
        r"(ohm'?s? law|volt(?:age)?|amp(?:ere|s)?|current|resistance|"
        r"watt|power dissipation|torque|rpm|gear ratio|pulley|belt speed|"
        r"resistor|capacitor|led current|voltage divider|series|parallel|"
        r"motor (?:power|torque|current)|mah|kwh|hp\b|horsepower)", re.I)),
    ("unit_convert", 0.9, re.compile(
        r"(convert|how many)\s+.*\s+(km|kilometers?|meters?|cm|mm|miles?|"
        r"inches?|feet|foot|yards?|kg|kilograms?|grams?|pounds?|lbs?|"
        r"celsius|fahrenheit|kelvin|litres?|liters?|gallons?)", re.I)),
    ("time_now",  0.95, re.compile(
        r"(what('s| is)? the time|what time\b|current time|time now|time ella|"
        r"neram enna|நேரம் என்ன|இப்போ என்ன நேரம்|மணி)", re.I)),
    ("date_now",  0.95, re.compile(
        r"(what('s| is)? (the )?(today'?s )?date|today'?s date|what day|"
        r"இன்றைய தேதி|தேதி என்ன|என்ன தேதி)", re.I)),
    ("reminder",  0.85, re.compile(
        r"(remind me|set (a )?reminder|alarm|wake me|nirovathu|"
        r"நினைவூட்டு|அலாரம்)", re.I)),
    ("task",      0.7,  re.compile(
        r"(add (a )?task|new task|todo|schedule|cron|routine)", re.I)),
    ("knowledge", 0.6,  re.compile(
        r"(what is|what are|whats|who is|who was|define|definition|explain|"
        r"tell me about|difference between|how does|how do|why (is|do|does)|"
        r"enna.*(பத்தி|பற்றி)|என்ன என்றால்|விளக்கம்|சொல்லு பத்தி)", re.I)),
    ("thanks",    0.95, re.compile(
        r"^(thanks|thank you|thnx|ty|nanri|nandri|நன்றி)[\s!.,]*$", re.I)),
    ("capability", 0.9, re.compile(
        r"(what can you do|your (features|capabilities|skills)|help me|"
        r"என்ன பண்ண முடியும்)", re.I)),
    ("confirmation", 0.8, re.compile(
        r"^(yes|yeah|yep|ok(?:ay)?|sure|sari|aama|aamaa|ஆமா|சரி)[\s!.,]*$", re.I)),
    ("denial",    0.8,  re.compile(
        r"^(no|nope|nah|illa|illai|இல்ல|வேண்டாம்)[\s!.,]*$", re.I)),
]

_MATH_TANGlish = re.compile(
    r"\b(plus|minus|multiply|divide|gundu|peruku|vagu|satham|"
    r"square|cube|root|percent|percentage)\b", re.I)

_MATH_WORDS_TA = re.compile("|".join(
    w for key in ("math_add", "math_sub", "math_mul", "math_div", "percent")
    for w in TAMIL_KEYWORDS[key]))

_QUESTION_TA = re.compile("|".join(TAMIL_KEYWORDS["question"]))


class IntentDetector:
    """Classifies a single utterance into a Rolex route-able intent."""

    #: intents the LOCAL brain can fully answer (no AI needed)
    LOCAL_INTENTS = {"greeting", "identity", "thanks", "time_now", "date_now",
                     "math", "engineering", "unit_convert", "capability",
                     "confirmation", "denial"}

    def detect(self, text: str, lang: LANG = LANG.ENGLISH) -> IntentResult:
        t = " ".join((text or "").split()).strip()
        if not t:
            return IntentResult("unknown", 0.0)

        for intent, conf, pat in _RULES:
            m = pat.search(t)
            if m:
                return IntentResult(intent, conf, slots={"match": m.group(0)})

        # Script-based fallbacks for Tamil text
        if _TAMIL_RANGE.search(t):
            if _MATH_WORDS_TA.search(t):
                return IntentResult("math", 0.75)
            if _QUESTION_TA.search(t):
                return IntentResult("knowledge", 0.5)
            if TAMIL_KEYWORDS["greeting"][0] in t:
                return IntentResult("greeting", 0.8)

        # Tanglish math ("plus pannu", "divide pannu")
        if lang in (LANG.TANGlish, LANG.MIXED) and _MATH_TANGlish.search(t):
            return IntentResult("math", 0.7)

        # Last resort: question-ish wording → knowledge
        if re.search(r"\b(what|how|why|when|where|who)\b", t, re.I) or \
                _QUESTION_TA.search(t):
            return IntentResult("knowledge", 0.45)

        return IntentResult("smalltalk", 0.35)
