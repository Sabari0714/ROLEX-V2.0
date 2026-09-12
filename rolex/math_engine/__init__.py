"""ROLEX Mathematics & Engineering Engine — 100% local (Phase 4).

Rule enforced here:
    Calculation → Rolex itself.
    Internet/AI → only if external information is actually required.
"""
from .evaluator import safe_eval, format_number
from . import basic_ops, algebra, geometry, trigonometry, units
from .engineering import electrical, mechanical, electronics
from .detector import MathDetector, MathSolution

__all__ = [
    "safe_eval", "format_number", "basic_ops", "algebra", "geometry",
    "trigonometry", "units", "electrical", "mechanical", "electronics",
    "MathDetector", "MathSolution",
]

# Singleton — Rolex's calculator
MATH = MathDetector()
