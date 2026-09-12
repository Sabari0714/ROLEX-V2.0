"""Unit conversion — length, mass, temperature, energy, power, time, pressure."""
from __future__ import annotations

from ..errors import MathError

# Every family: canonical unit → factor to base unit.
_LENGTH = {  # base: meter
    "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
    "inch": 0.0254, "in": 0.0254, "ft": 0.3048, "feet": 0.3048,
    "foot": 0.3048, "yard": 0.9144, "yd": 0.9144,
    "mile": 1609.344, "miles": 1609.344, "nauticalmile": 1852.0,
}
_MASS = {  # base: kilogram
    "mg": 1e-6, "g": 0.001, "gram": 0.001, "grams": 0.001,
    "kg": 1.0, "kilogram": 1.0, "kilograms": 1.0,
    "tonne": 1000.0, "ton": 1000.0,
    "lb": 0.45359237, "lbs": 0.45359237, "pound": 0.45359237,
    "pounds": 0.45359237, "ounce": 0.028349523125, "oz": 0.028349523125,
}
_VOLUME = {  # base: liter
    "ml": 0.001, "l": 1.0, "litre": 1.0, "liter": 1.0, "litres": 1.0,
    "liters": 1.0, "m3": 1000.0, "gallon": 3.785411784, "gallons": 3.785411784,
    "quart": 0.946352946, "pint": 0.473176473, "cup": 0.2365882365,
}
_ENERGY = {  # base: joule
    "j": 1.0, "joule": 1.0, "joules": 1.0, "kj": 1000.0,
    "cal": 4.184, "calorie": 4.184, "calories": 4.184, "kcal": 4184.0,
    "wh": 3600.0, "kwh": 3.6e6, "mwh": 3.6e9,
    "btu": 1055.05585, "ev": 1.602176634e-19,
}
_POWER = {  # base: watt
    "w": 1.0, "watt": 1.0, "watts": 1.0, "kw": 1000.0, "kilowatt": 1000.0,
    "kilowatts": 1000.0, "mw": 1e6, "hp": 745.699872, "horsepower": 745.699872,
    "ps": 735.49875,
}
_TIME = {  # base: second
    "ms": 0.001, "s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0,
    "min": 60.0, "minute": 60.0, "minutes": 60.0,
    "h": 3600.0, "hr": 3600.0, "hour": 3600.0, "hours": 3600.0,
    "day": 86400.0, "days": 86400.0, "week": 604800.0, "weeks": 604800.0,
    "year": 31557600.0, "years": 31557600.0,
}
_PRESSURE = {  # base: pascal
    "pa": 1.0, "kpa": 1000.0, "mpa": 1e6, "bar": 100000.0,
    "psi": 6894.757293, "atm": 101325.0, "torr": 133.322368,
}
_SPEED = {  # base: m/s
    "mps": 1.0, "kmph": 0.277777778, "kmh": 0.277777778,
    "mph": 0.44704, "knot": 0.514444444, "knots": 0.514444444,
}
_DATA = {  # base: byte
    "b": 1.0, "byte": 1.0, "bytes": 1.0, "kb": 1024.0, "mb": 1024.0 ** 2,
    "gb": 1024.0 ** 3, "tb": 1024.0 ** 4,
}
_AREA = {  # base: m²
    "mm2": 1e-6, "cm2": 1e-4, "m2": 1.0, "km2": 1e6,
    "hectare": 10000.0, "ha": 10000.0, "acre": 4046.8564224,
    "sqft": 0.09290304, "sqinch": 0.00064516,
}

_FAMILIES = {
    "length": _LENGTH, "mass": _MASS, "volume": _VOLUME,
    "energy": _ENERGY, "power": _POWER, "time": _TIME,
    "pressure": _PRESSURE, "speed": _SPEED, "data": _DATA, "area": _AREA,
}

# Temperature is special (offsets, not ratios).
_TEMPS = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}


def _norm(u: str) -> str:
    u = (u or "").lower().strip().rstrip("s")
    u = u.replace("°", "").replace(" ", "")
    aliases = {"kilometer": "km", "kilometers": "km", "metre": "m",
               "meter": "m", "meters": "m", "metres": "m", "fahrenheit": "f",
               "celsius": "c", "kelvin": "k", "kph": "kmph", "kilometre": "km"}
    return aliases.get(u, u)


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert value between two units. Auto-detects family."""
    f, t = _norm(from_unit), _norm(to_unit)

    # temperature ------------------------------------------------
    if f in _TEMPS or t in _TEMPS:
        if f not in _TEMPS or t not in _TEMPS:
            raise MathError("temperature can only convert to temperature")
        return _temp(value, f, t)

    for fam, table in _FAMILIES.items():
        if f in table and t in table:
            return value * table[f] / table[t]

    raise MathError(f"cannot convert {from_unit!r} → {to_unit!r} "
                    f"(unknown or mixed families)")


def _temp(v: float, f: str, t: str) -> float:
    # to celsius first
    if f in ("c",):
        c = v
    elif f in ("f",):
        c = (v - 32) * 5 / 9
    else:  # kelvin
        c = v - 273.15
    # celsius → target
    if t in ("c",):
        return c
    if t in ("f",):
        return c * 9 / 5 + 32
    return c + 273.15  # kelvin


def family_of(unit: str) -> str | None:
    u = _norm(unit)
    if u in _TEMPS:
        return "temperature"
    for fam, table in _FAMILIES.items():
        if u in table:
            return fam
    return None


def available_units() -> dict[str, list[str]]:
    out = {"temperature": ["c", "f", "k"]}
    for fam, table in _FAMILIES.items():
        out[fam] = sorted(set(table.keys()))
    return out
