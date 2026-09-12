"""Engineering calculator — Electrical (Ohm's law, power, energy)."""
from __future__ import annotations

from ...errors import MathError


# ----------------------------------------------------------- Ohm's law
def ohms_law(v: float | None = None, i: float | None = None,
             r: float | None = None) -> dict:
    """V = I × R. Give any two, get the third."""
    given = sum(x is not None for x in (v, i, r))
    if given != 2:
        raise MathError("Ohm's law needs exactly TWO of V, I, R")
    if v is None:
        v = i * r
    elif i is None:
        if r == 0:
            raise MathError("resistance is zero — cannot find I")
        i = v / r
    elif r is None:
        if i == 0:
            raise MathError("current is zero — cannot find R")
        r = v / i
    return {"voltage_V": v, "current_A": i, "resistance_ohm": r}


# ----------------------------------------------------------- Power
def electrical_power(v: float | None = None, i: float | None = None,
                     r: float | None = None, p: float | None = None) -> dict:
    """P = V×I = I²R = V²/R. Give any two, get the rest."""
    known = {k for k, x in (("v", v), ("i", i), ("r", r), ("p", p)) if x is not None}
    if len(known) < 2:
        raise MathError("power needs TWO of V, I, R, P")

    if v is not None and i is not None:
        p = v * i
        r = v / i if i else None
    elif v is not None and r is not None:
        if r == 0:
            raise MathError("R = 0 → infinite power")
        p = v * v / r
        i = v / r
    elif i is not None and r is not None:
        p = i * i * r
        v = i * r
    elif p is not None and v is not None:
        i = p / v
        r = v * v / p
    elif p is not None and i is not None:
        if i == 0:
            raise MathError("I = 0 → no power")
        v = p / i
        r = p / (i * i)
    elif p is not None and r is not None:
        if r == 0:
            raise MathError("R = 0")
        i = (p / r) ** 0.5
        v = i * r
    return {"voltage_V": v, "current_A": i, "resistance_ohm": r, "power_W": p}


def energy(power_w: float, hours: float) -> dict:
    """Energy consumption: kWh."""
    kwh = power_w * hours / 1000
    return {"energy_kWh": kwh,
            "energy_Wh": power_w * hours,
            "cost_at_rs8": kwh * 8}


# ----------------------------------------------------------- Resistors
def series_resistors(values: list[float]) -> float:
    return sum(values)


def parallel_resistors(values: list[float]) -> float:
    if not values:
        raise MathError("no resistor values")
    if any(v == 0 for v in values):
        return 0.0
    inv = sum(1 / v for v in values)
    if inv == 0:
        raise MathError("invalid parallel combination")
    return 1 / inv


def voltage_divider(vin: float, r1: float, r2: float) -> dict:
    """Vout across R2."""
    if r1 + r2 == 0:
        raise MathError("total resistance zero")
    vout = vin * r2 / (r1 + r2)
    return {"vout_V": vout, "ratio": r2 / (r1 + r2)}


def led_resistor(vsource: float, vf: float = 2.0, if_ma: float = 20) -> dict:
    """Current-limiting resistor for an LED."""
    i = if_ma / 1000
    if i <= 0:
        raise MathError("LED current must be > 0")
    r = (vsource - vf) / i
    if r < 0:
        raise MathError("source voltage below LED Vf — no resistor possible")
    p = (vsource - vf) * i
    return {"resistor_ohm": r, "resistor_use": _next_std_r(r),
            "power_W": p}


def _next_std_r(r: float) -> float:
    e12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]
    decade = 0
    x = r
    while x >= 10:
        x /= 10
        decade += 1
    while x < 1:
        x *= 10
        decade -= 1
    for v in e12:
        if v >= x:
            return v * (10 ** decade)
    return e12[0] * (10 ** (decade + 1))


# ----------------------------------------------------------- AC basics
def capacitive_reactance(c_farads: float, freq_hz: float) -> float:
    if freq_hz <= 0:
        raise MathError("frequency must be > 0")
    return 1 / (2 * 3.141592653589793 * freq_hz * c_farads)


def inductive_reactance(l_henry: float, freq_hz: float) -> float:
    return 2 * 3.141592653589793 * freq_hz * l_henry


def battery_life(capacity_mah: float, load_ma: float) -> dict:
    """Estimated runtime from battery capacity."""
    if load_ma <= 0:
        raise MathError("load must be > 0")
    hours = capacity_mah / load_ma
    return {"hours": hours, "minutes": hours * 60,
            "days": hours / 24}


def transformer_ratio(n_primary: int, n_secondary: int,
                      v_primary: float | None = None) -> dict:
    ratio = n_secondary / n_primary
    out = {"turns_ratio": ratio}
    if v_primary is not None:
        out["v_secondary"] = v_primary * ratio
    return out
