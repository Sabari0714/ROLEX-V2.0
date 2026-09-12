"""Basic reasoning — local logic Rolex can do without any AI (Phase 3)."""
from __future__ import annotations

from datetime import datetime, timedelta


class Reasoner:
    """Deterministic mini-reasoner: time, comparisons, counting, dates."""

    # -------------------------------------------------- time & date
    def now(self) -> dict:
        n = datetime.now()
        return {
            "time": n.strftime("%H:%M:%S"),
            "date": n.strftime("%Y-%m-%d"),
            "day": n.strftime("%A"),
            "iso": n.isoformat(timespec="seconds"),
        }

    def time_answer(self, lang: str = "en") -> str:
        n = datetime.now()
        if lang in ("ta", "tanglish", "mixed"):
            return f"இப்போ நேரம் {n.strftime('%H:%M')} ({n.strftime('%A')})."
        return f"Current time is {n.strftime('%H:%M:%S')} ({n.strftime('%A')})."

    def date_answer(self, lang: str = "en") -> str:
        n = datetime.now()
        if lang in ("ta", "tanglish", "mixed"):
            return f"இன்னைக்கு {n.strftime('%d-%m-%Y')}, {n.strftime('%A')}."
        return f"Today is {n.strftime('%A')}, {n.strftime('%d %B %Y')}."

    # -------------------------------------------------- comparisons
    def compare(self, a: float, b: float) -> str:
        if a > b:
            return f"{a} is bigger than {b} (difference {round(a - b, 4)})."
        if b > a:
            return f"{b} is bigger than {a} (difference {round(b - a, 4)})."
        return f"Both are equal: {a}."

    def max_of(self, values: list[float]) -> float | None:
        return max(values) if values else None

    def min_of(self, values: list[float]) -> float | None:
        return min(values) if values else None

    # -------------------------------------------------- counting
    def count_words(self, text: str) -> int:
        return len((text or "").split())

    def count_letters(self, text: str) -> int:
        return len((text or "").replace(" ", ""))

    # -------------------------------------------------- dates logic
    def relative_date(self, base: datetime | None = None) -> dict:
        """today / tomorrow / yesterday resolved locally."""
        b = base or datetime.now()
        return {
            "today": b.strftime("%Y-%m-%d"),
            "tomorrow": (b + timedelta(days=1)).strftime("%Y-%m-%d"),
            "yesterday": (b - timedelta(days=1)).strftime("%Y-%m-%d"),
            "next_week": (b + timedelta(days=7)).strftime("%Y-%m-%d"),
        }

    def days_between(self, d1: str, d2: str) -> int | None:
        """'2024-01-01', '2024-03-01' → day count (d2 - d1)."""
        try:
            a = datetime.strptime(d1.strip(), "%Y-%m-%d")
            b = datetime.strptime(d2.strip(), "%Y-%m-%d")
            return (b - a).days
        except ValueError:
            return None

    # -------------------------------------------------- helpers
    def even_odd(self, n: int) -> str:
        return f"{n} is {'even' if n % 2 == 0 else 'odd'}."

    def is_prime(self, n: int) -> bool:
        if n < 2:
            return False
        if n % 2 == 0:
            return n == 2
        i = 3
        while i * i <= n:
            if n % i == 0:
                return False
            i += 2
        return True

    def prime_answer(self, n: int) -> str:
        return f"{n} is {'a prime' if self.is_prime(n) else 'not a prime'} number."
