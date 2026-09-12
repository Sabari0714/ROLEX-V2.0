"""Engineering calculator — Electronics (codes, dividers, dissipation)."""
from __future__ import annotations

from ...errors import MathError

_COLOR_DIGITS = {
    "black": 0, "brown": 1, "red": 2, "orange": 3, "yellow": 4,
    "green": 5, "blue": 6, "violet": 7, "gray": 8, "grey": 8, "white": 9,
}
_COLOR_MULT = {
    "black": 1, "brown": 10, "red": 100, "orange": 1e3, "yellow": 1e4,
    "green": 1e5, "blue": 1e6, "violet": 1e7, "gray": 1e8, "white": 1e9,
    "gold": 0.1, "silver": 0.01,
}
_COLOR_TOL = {
    "brown": 1, "red": 2, "green": 0.5, "blue": 0.25, "violet": 0.1,
    "gray": 0.05, "gold": 5, "silver": 10, "none": 20,
}


def resistor_color_code(colors: list[str]) -> dict:
    """4/5-band resistor: ['brown', 'black', 'red', 'gold'] → 1kΩ ±5%."""
    c = [x.lower().strip() for x in colors]
    if len(c) < 3:
        raise MathError("need at least 3 color bands")
    try:
        if len(c) == 3:  # 3-band: 2 digits + multiplier
            digits = _COLOR_DIGITS[c[0]] * 10 + _COLOR_DIGITS[c[1]]
            mult = _COLOR_MULT[c[2]]
            tol = 20.0
        elif len(c) == 4:  # classic 4-band
            digits = _COLOR_DIGITS[c[0]] * 10 + _COLOR_DIGITS[c[1]]
            mult = _COLOR_MULT[c[2]]
            tol = _COLOR_TOL.get(c[3], 20.0)
        else:  # 5-band precision
            digits = (_COLOR_DIGITS[c[0]] * 100 + _COLOR_DIGITS[c[1]] * 10
                      + _COLOR_DIGITS[c[2]])
            mult = _COLOR_MULT[c[3]]
            tol = _COLOR_TOL.get(c[4], 20.0)
    except KeyError as e:
        raise MathError(f"unknown color: {e}")

    value = digits * mult
    return {"value_ohm": value,
            "tolerance_pct": tol,
            "min": value * (1 - tol / 100),
            "max": value * (1 + tol / 100)}


def power_dissipation(v: float | None = None, i: float | None = None,
                      r: float | None = None) -> dict:
    """P = VI = I²R = V²/R — which resistor wattage to use."""
    if v is not None and i is not None:
        p = v * i
    elif i is not None and r is not None:
        p = i * i * r
    elif v is not None and r is not None:
        if r == 0:
            raise MathError("R = 0")
        p = v * v / r
    else:
        raise MathError("need two of V, I, R")
    # recommend 2× safety margin
    rec = p * 2
    if rec <= 0.25: use = "1/4 W (0.25W)"
    elif rec <= 0.5: use = "1/2 W (0.5W)"
    elif rec <= 1: use = "1 W"
    elif rec <= 2: use = "2 W"
    elif rec <= 5: use = "5 W"
    else: use = f"{rec:.1f} W (metal-clad / wirewound)"
    return {"power_W": p, "recommended": use}


def rc_time_constant(r_ohm: float, c_farad: float) -> dict:
    tau = r_ohm * c_farad
    return {"tau_s": tau, "full_charge_5tau_s": 5 * tau}


def lc_frequency(l_h: float, c_f: float) -> dict:
    """Resonant frequency of LC tank."""
    if l_h <= 0 or c_f <= 0:
        raise MathError("L and C must be > 0")
    import math
    f = 1 / (2 * math.pi * math.sqrt(l_h * c_f))
    return {"frequency_Hz": f}


def wavelength(freq_hz: float) -> dict:
    """λ = c/f (free space)."""
    if freq_hz <= 0:
        raise MathError("frequency must be > 0")
    lam = 299792458.0 / freq_hz
    return {"wavelength_m": lam, "wavelength_cm": lam * 100}


def amp_gain(vin: float, vout: float) -> dict:
    """Voltage gain (times and dB)."""
    if vin == 0:
        raise MathError("Vin cannot be 0")
    import math
    g = vout / vin
    return {"gain": g, "gain_dB": 20 * math.log10(abs(g))}


def fuse_rating(power_w: float, voltage_v: float,
                margin: float = 1.25) -> dict:
    if voltage_v <= 0:
        raise MathError("voltage must be > 0")
    i = power_w / voltage_v
    return {"current_A": i, "fuse_rating_A": i * margin}
