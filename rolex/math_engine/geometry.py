"""Geometry — shapes: area, perimeter, volume (Phase 4)."""
from __future__ import annotations

import math

from ..errors import MathError

PI = math.pi


# ----------------------------------------------------------- 2D shapes
def circle(r: float) -> dict:
    return {"area": PI * r * r, "circumference": 2 * PI * r,
            "diameter": 2 * r}


def square(side: float) -> dict:
    return {"area": side * side, "perimeter": 4 * side}


def rectangle(w: float, h: float) -> dict:
    return {"area": w * h, "perimeter": 2 * (w + h)}


def triangle(a: float, b: float, c: float | None = None, h: float | None = None) -> dict:
    if h is not None:                       # base & height given
        return {"area": 0.5 * a * h}
    if c is None:
        raise MathError("triangle needs 3 sides or base+height")
    if a + b <= c or b + c <= a or a + c <= b:
        raise MathError("invalid triangle sides")
    s = (a + b + c) / 2
    area = math.sqrt(s * (s - a) * (s - b) * (s - c))     # Heron
    return {"area": area, "perimeter": a + b + c}


def trapezoid(a: float, b: float, h: float) -> dict:
    return {"area": 0.5 * (a + b) * h}


# ----------------------------------------------------------- 3D solids
def sphere(r: float) -> dict:
    return {"volume": 4 / 3 * PI * r ** 3, "surface_area": 4 * PI * r * r}


def cube(side: float) -> dict:
    return {"volume": side ** 3, "surface_area": 6 * side * side}


def cuboid(l: float, w: float, h: float) -> dict:
    return {"volume": l * w * h,
            "surface_area": 2 * (l * w + w * h + l * h)}


def cylinder(r: float, h: float) -> dict:
    return {"volume": PI * r * r * h,
            "surface_area": 2 * PI * r * (r + h)}


def cone(r: float, h: float) -> dict:
    slant = math.sqrt(r * r + h * h)
    return {"volume": PI * r * r * h / 3,
            "surface_area": PI * r * (r + slant), "slant_height": slant}


# ----------------------------------------------------------- dispatcher
def solve_shape(shape: str, values: list[float]) -> dict:
    shape = (shape or "").lower().strip()
    v = values
    if shape in ("circle", "வட்டம்"):
        if len(v) < 1:
            raise MathError("circle needs radius")
        return circle(v[0])
    if shape == "square":
        if len(v) < 1:
            raise MathError("square needs side")
        return square(v[0])
    if shape in ("rectangle", "rect"):
        if len(v) < 2:
            raise MathError("rectangle needs width & height")
        return rectangle(v[0], v[1])
    if shape == "triangle":
        if len(v) >= 2:
            return triangle(v[0], v[0], v[1], h=v[1]) if len(v) == 2 and v[0] == v[1] else (
                triangle(v[0], v[1], v[2] if len(v) > 2 else None))
        raise MathError("triangle needs sides or base+height")
    if shape == "sphere":
        return sphere(v[0])
    if shape == "cube":
        return cube(v[0])
    if shape in ("cuboid", "box"):
        return cuboid(*v[:3])
    if shape == "cylinder":
        return cylinder(v[0], v[1])
    if shape == "cone":
        return cone(v[0], v[1])
    raise MathError(f"unknown shape: {shape}")
