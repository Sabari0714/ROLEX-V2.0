"""Trigonometry — sin/cos/tan, inverse, laws, angle conversion."""
from __future__ import annotations

import math

from ..errors import MathError


def _to_rad(angle: float, unit: str) -> float:
    unit = (unit or "deg").lower()
    if unit in ("deg", "degree", "degrees", "°"):
        return math.radians(angle)
    if unit in ("rad", "radian", "radians"):
        return angle
    if unit in ("grad", "gradian"):
        return angle * math.pi / 200
    raise MathError(f"unknown angle unit: {unit}")


def trig(func: str, angle: float, unit: str = "deg") -> float:
    f = {"sin": math.sin, "cos": math.cos, "tan": math.tan}.get(func.lower())
    if f is None:
        raise MathError(f"unknown trig function: {func}")
    return f(_to_rad(angle, unit))


def inverse_trig(func: str, value: float, unit: str = "deg") -> float:
    f = {"asin": math.asin, "acos": math.acos, "atan": math.atan}.get(func.lower())
    if f is None:
        raise MathError(f"unknown inverse trig: {func}")
    if func.lower() in ("asin", "acos") and not -1 <= value <= 1:
        raise MathError(f"{func} domain is [-1, 1], got {value}")
    r = f(value)
    return math.degrees(r) if unit == "deg" else r


def pythagoras(a: float | None = None, b: float | None = None,
               c: float | None = None) -> dict:
    """Given two sides of a right triangle, find the third."""
    if a and b:
        return {"hypotenuse": math.hypot(a, b)}
    if a and c:
        return {"other_side": math.sqrt(c * c - a * a)}
    if b and c:
        return {"other_side": math.sqrt(c * c - b * b)}
    raise MathError("pythagoras needs exactly two sides")


def law_of_sines_side(a: float, A_deg: float, B_deg: float) -> float:
    """Find side b given a, angle A, angle B (degrees)."""
    if A_deg == 0:
        raise MathError("angle A cannot be 0")
    return a * math.sin(math.radians(B_deg)) / math.sin(math.radians(A_deg))


def law_of_cosines(a: float, b: float, C_deg: float) -> float:
    """Side c given a, b and included angle C (degrees)."""
    c2 = a * a + b * b - 2 * a * b * math.cos(math.radians(C_deg))
    return math.sqrt(max(c2, 0.0))
