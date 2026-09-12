"""Rolex Knowledge Engine (Phase 5) — local, offline, searchable."""
from .base import KnowledgeBase, Entry, KnowledgeMatch

__all__ = ["KnowledgeBase", "Entry", "KnowledgeMatch", "KNOWLEDGE"]

KNOWLEDGE = KnowledgeBase()
