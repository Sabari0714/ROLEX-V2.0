"""
Rolex configuration — Phase 1.
Loads .env, exposes typed settings, never crashes on missing keys.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv  # optional
except Exception:  # pragma: no cover
    def load_dotenv(*a, **k):
        return False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    """Central, read-only-after-boot Rolex configuration."""

    # Identity -----------------------------------------------------------
    NAME = "Rolex"
    WAKE_WORD = "hey guru"
    VERSION = "2.2.0"            # v2.2 Neon Horizon (multi-provider keys) (bass-reactive HUD)

    # Paths ---------------------------------------------------------------
    ROOT_DIR = PROJECT_ROOT
    DATA_DIR = Path(os.getenv("ROLEX_DATA_DIR", PROJECT_ROOT / "data"))
    LOG_DIR = DATA_DIR / "logs"
    MEMORY_DIR = DATA_DIR / "memory"
    MEMORY_DB = MEMORY_DIR / "rolex_memory.db"
    KB_DIR = Path(os.getenv("ROLEX_KB_DIR", PROJECT_ROOT / "rolex" / "knowledge" / "topics"))
    BACKUP_DIR = DATA_DIR / "backups"
    SANDBOX_DIR = DATA_DIR / "sandbox"
    AUDIT_LOG = LOG_DIR / "audit.jsonl"
    STOP_FLAG = DATA_DIR / "EMERGENCY_STOP"

    # Behaviour -----------------------------------------------------------
    LOG_LEVEL = os.getenv("ROLEX_LOG_LEVEL", "INFO")
    DEFAULT_LANGUAGE = os.getenv("ROLEX_LANG", "auto")     # auto | ta | en | tanglish
    MATH_LOCAL_ONLY = True                                  # calculations never leave Rolex
    CONFIDENCE_THRESHOLD = float(os.getenv("ROLEX_CONFIDENCE", "0.65"))

    # AI providers (intelligence SOURCES only — Rolex owns final answer) --
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

    AI_TIMEOUT = float(os.getenv("ROLEX_AI_TIMEOUT", "20"))
    AI_RETRIES = int(os.getenv("ROLEX_AI_RETRIES", "2"))
    AI_PARALLEL = os.getenv("ROLEX_AI_PARALLEL", "1") == "1"

    # Sync / Remote Lab (v2 §20–21) ------------------------------------
    SYNC_VPS_HOST = os.getenv("ROLEX_SYNC_VPS", "")
    SYNC_DRIVE_REMOTE = os.getenv("ROLEX_DRIVE_REMOTE", "gdrive")
    REMOTE_LAB_PORT = int(os.getenv("ROLEX_LAB_PORT", "8765"))
    REMOTE_LAB_TOKEN = os.getenv("ROLEX_LAB_TOKEN", "")   # pairing secret

    @classmethod
    def ensure_dirs(cls) -> None:
        for d in (
            cls.DATA_DIR, cls.LOG_DIR, cls.MEMORY_DIR, cls.KB_DIR,
            cls.BACKUP_DIR, cls.SANDBOX_DIR, cls.AUDIT_LOG.parent,
        ):
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

    @classmethod
    def provider_flags(cls) -> dict:
        return {
            "openai": bool(cls.OPENAI_API_KEY),
            "gemini": bool(cls.GEMINI_API_KEY),
            "ollama": bool(cls.OLLAMA_BASE_URL),
        }


CONFIG = Config()
