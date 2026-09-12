"""Rolex Learning Engine (Phase 9) \u2014 SAFE self-improvement pipeline."""
from .engine import (LearningEngine, LearningProposal, Stage,
                     LearningError, ALLOWED_KINDS)

__all__ = ["LearningEngine", "LearningProposal", "Stage",
           "LearningError", "ALLOWED_KINDS", "LEARNING"]

LEARNING = LearningEngine()
