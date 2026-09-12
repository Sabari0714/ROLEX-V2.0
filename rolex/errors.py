"""Rolex error hierarchy + safe_call — Phase 1 error handling."""
from __future__ import annotations


class RolexError(Exception):
    """Base class for every Rolex error. Never crash the core."""

    code = "ROLEX_ERROR"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:  # noqa: D105
        return f"[{self.code}] {self.message}"


class ConfigError(RolexError):        code = "CONFIG_ERROR"
class MathError(RolexError):          code = "MATH_ERROR"
class BrainError(RolexError):         code = "BRAIN_ERROR"
class ProviderError(RolexError):      code = "PROVIDER_ERROR"
class ProviderTimeout(ProviderError): code = "PROVIDER_TIMEOUT"
class MemoryError(RolexError):        code = "MEMORY_ERROR"
class KnowledgeError(RolexError):     code = "KNOWLEDGE_ERROR"
class PermissionDenied(RolexError):   code = "PERMISSION_DENIED"
class SandboxError(RolexError):       code = "SANDBOX_ERROR"
class DocumentError(RolexError):      code = "DOCUMENT_ERROR"
class VoiceError(RolexError):         code = "VOICE_ERROR"
class VisionError(RolexError):        code = "VISION_ERROR"
class EmergencyStop(RolexError):      code = "EMERGENCY_STOP"


def safe_call(func, *args, default=None, log=None, **kwargs):
    """Run func; on ANY failure return default instead of crashing Rolex."""
    try:
        return func(*args, **kwargs)
    except RolexError as e:
        if log:
            log.warning("%s", e)
        return default
    except Exception as e:  # noqa: BLE001
        if log:
            log.warning("unexpected: %s", e)
        return default
