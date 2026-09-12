"""ROLEX identity — the one and only name Rolex answers to."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import CONFIG


@dataclass(frozen=True)
class Identity:
    """Immutable Rolex identity card."""

    name: str = "Rolex"
    full_name: str = "ROLEX AI"
    tagline: str = "Your Personal Intelligence System"
    wake_word: str = "Hey Guru"
    languages: tuple = ("Tamil", "English", "Tanglish")
    version: str = CONFIG.VERSION
    author: str = "Rolex Project"

    @property
    def introduction(self) -> str:
        return (
            f"I am {self.full_name} — {self.tagline}. "
            f"Naan {', '.join(self.languages)} pesuven. "
            f"Calculations naan than direct pannuven — internet venaam. "
            f"Version {self.version}."
        )

    def matches_name(self, text: str) -> bool:
        """True if the user is calling Rolex by name."""
        t = (text or "").lower().strip()
        return any(k in t for k in ("rolex", "ரோலெக்ஸ்", "hey guru"))

    def whoami(self) -> dict:
        return {
            "name": self.name,
            "full_name": self.full_name,
            "tagline": self.tagline,
            "wake_word": self.wake_word,
            "languages": list(self.languages),
            "version": self.version,
        }


IDENTITY = Identity()
