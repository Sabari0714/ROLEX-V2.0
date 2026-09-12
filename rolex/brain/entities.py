"""Entity extraction — numbers, units, Tamil/Tanglish number words."""
from __future__ import annotations

import re

# English + Tanglish number words → digits
NUMBER_WORDS = {
    "zero": 0, "one": 1, "won": 1, "two": 2, "to": 2, "three": 3, "tree": 3,
    "four": 4, "for": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "ait": 8,
    "nine": 9, "ten": 10, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "thousand": 1000, "lakh": 100000, "crore": 10000000,
    # Tanglish numbers
    "onnu": 1, "rendu": 2, "randu": 2, "moonu": 3, "naalu": 4, "anju": 5,
    "aaru": 6, "ezhu": 7, "ettu": 8, "ombodhu": 9, "pathu": 10,
    "irubathu": 20, "muppathu": 30, "narpadhu": 40, "ambadhu": 50,
    "thodar": None,
}

# Tamil script numerals
TAMIL_NUMBERS = {
    "பூஜ்யம்": 0, "ஒன்று": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4,
    "ஐந்து": 5, "ஆறு": 6, "ஏழு": 7, "எட்டு": 8, "ஒன்பது": 9, "பத்து": 10,
    "இருபது": 20, "முப்பது": 30, "நாற்பது": 40, "ஐம்பது": 50,
    "நூறு": 100, "ஆயிரம்": 1000,
}

UNITS = {
    "length": ["km", "kilometer", "kilometers", "m", "meter", "meters", "cm",
               "mm", "mile", "miles", "inch", "inches", "ft", "feet", "foot",
               "yard", "yards"],
    "mass": ["kg", "kilogram", "kilograms", "g", "gram", "grams", "lb", "lbs",
             "pound", "pounds", "tonne", "ton"],
    "temperature": ["celsius", "fahrenheit", "kelvin", "c", "f", "k"],
    "energy": ["wh", "kwh", "j", "joule", "joules", "cal", "calorie", "calories"],
    "power": ["w", "watt", "watts", "kw", "kilowatt", "hp", "horsepower", "ps"],
    "voltage": ["v", "volt", "volts", "mv", "kv"],
    "current": ["a", "amp", "amps", "ampere", "amperes", "ma", "ka"],
    "resistance": ["ohm", "ohms", "kohm", "kilo-ohm", "mohm", "ω"],
    "time": ["sec", "secs", "second", "seconds", "min", "mins", "minute",
             "minutes", "hr", "hrs", "hour", "hours", "day", "days"],
    "capacity": ["mah", "ah", "farad", "f"],
}

# Electrical/engineering quantity words
QUANTITIES = ["voltage", "current", "resistance", "power", "energy", "torque",
              "speed", "rpm", "frequency", "efficiency", "force", "mass",
              "distance", "temperature", "time", "angle", "area", "volume"]


class EntityExtractor:
    """Pulls structured entities out of raw text — no internet, ever."""

    def __init__(self):
        self._num_words_re = re.compile(
            r"\b(" + "|".join(NUMBER_WORDS) + r")\b", re.I)
        self._ta_num_re = re.compile(
            r"(" + "|".join(TAMIL_NUMBERS) + r")")
        self._digits_re = re.compile(r"-?\d+(?:\.\d+)?")
        self._unit_re = re.compile(
            r"\b(" + "|".join(sorted({u for v in UNITS.values() for u in v},
                                     key=len, reverse=True)) + r")\b", re.I)
        self._qty_re = re.compile(
            r"\b(" + "|".join(QUANTITIES) + r")\b", re.I)

    # -----------------------------------------------------------
    def numbers(self, text: str) -> list[float]:
        """All numeric values: digits, English/Tanglish words, Tamil script."""
        out = [float(x) for x in self._digits_re.findall(text or "")]
        for m in self._num_words_re.findall(text or ""):
            v = NUMBER_WORDS.get(m.lower())
            if v is not None:
                out.append(float(v))
        for m in self._ta_num_re.findall(text or ""):
            out.append(float(TAMIL_NUMBERS[m]))
        return out

    def units(self, text: str) -> list[str]:
        return [u.lower() for u in self._unit_re.findall(text or "")]

    def unit_type(self, unit: str) -> str | None:
        u = unit.lower().rstrip("s")
        for kind, lst in UNITS.items():
            if u in lst or unit.lower() in lst:
                return kind
        return None

    def quantities(self, text: str) -> list[str]:
        return [q.lower() for q in self._qty_re.findall(text or "")]

    def value_with_unit(self, text: str) -> list[tuple[float, str]]:
        """Pairs like (12, 'v') from '12V 2A'."""
        pat = re.compile(r"(-?\d+(?:\.\d+)?)\s*([a-zA-Z°ω]+)")
        return [(float(n), u) for n, u in pat.findall(text or "")]

    def extract(self, text: str) -> dict:
        return {
            "numbers": self.numbers(text),
            "units": self.units(text),
            "quantities": self.quantities(text),
            "value_units": self.value_with_unit(text),
        }
