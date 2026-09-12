"""Algebra — linear & quadratic solvers, GCD/LCM."""
from __future__ import annotations

import re

from ..errors import MathError


def solve_linear(a: float, b: float, c: float) -> str:
    """Solve a*x + b = c  →  x = (c - b) / a."""
    if a == 0:
        if b == c:
            return "Infinite solutions (identity)"
        return "No solution (contradiction)"
    x = (c - b) / a
    return f"x = {x:.6g}"


def solve_quadratic(a: float, b: float, c: float) -> dict:
    """Solve a*x² + b*x + c = 0. Returns dict with roots info."""
    if a == 0:
        raise MathError("not quadratic (a = 0)")
    disc = b * b - 4 * a * c
    base = {"a": a, "b": b, "c": c, "discriminant": disc}
    if disc > 0:
        r1 = (-b + disc ** 0.5) / (2 * a)
        r2 = (-b - disc ** 0.5) / (2 * a)
        return {**base, "roots": (r1, r2), "nature": "two real roots"}
    if disc == 0:
        r = -b / (2 * a)
        return {**base, "roots": (r,), "nature": "one repeated root"}
    re_part = -b / (2 * a)
    im_part = (-disc) ** 0.5 / (2 * a)
    return {**base, "roots": (f"{re_part:.6g}+{im_part:.6g}i",
                              f"{re_part:.6g}-{im_part:.6g}i"),
            "nature": "two complex roots"}


def solve_equation_text(text: str) -> str | None:
    """Parse '2x + 5 = 13' or 'x^2 - 5x + 6 = 0' style equations."""
    t = text.replace(" ", "").replace("²", "^2").lower()
    if "=" not in t:
        return None
    lhs, rhs = t.split("=", 1)
    if "x" not in lhs:
        return None

    m2 = re.match(r"^(-?\d*)x\^?2([+-]\d*)?x?([+-]\d+)?$", lhs)
    if m2 or "^2" in lhs or "x2" in lhs:
        a = _coef(m2.group(1)) if m2 else 1
        b = _coef(m2.group(2)) if m2 else 0
        # handle 'x^2-5x+6'
        m3 = re.match(r"^(-?\d*)x\^?2([+-]\d+)x([+-]\d+)$", lhs)
        if m3:
            a, b, c = _coef(m3.group(1)), _coef(m3.group(2)), float(m3.group(3))
        elif m2:
            c = float(m2.group(3)) if m2.group(3) else 0.0
        else:
            return None
        c -= _const(rhs)
        r = solve_quadratic(a, b, c)
        roots = ", ".join(f"{x:.6g}" if isinstance(x, float) else x for x in r["roots"])
        return (f"Quadratic a={a:g}, b={b:g}, c={c:g} | discriminant={r['discriminant']:.6g} "
                f"({r['nature']}) → roots: x = {roots}")

    m1 = re.match(r"^(-?\d*)x([+-]\d+)?$", lhs)
    if m1:
        a = _coef(m1.group(1))
        b = float(m1.group(2)) if m1.group(2) else 0.0
        c = _const(rhs)
        return f"Linear {a:g}x + {b:g} = {c:g} → " + solve_linear(a, b, c)
    return None


def _coef(s: str | None) -> float:
    if not s or s in ("+", ""):
        return 1.0
    if s == "-":
        return -1.0
    return float(s)


def _const(s: str) -> float:
    s = s.strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        raise MathError(f"cannot parse constant: {s!r}")


def gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return abs(a)


def lcm(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return abs(a * b) // gcd(a, b)
