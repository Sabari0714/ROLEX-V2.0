"""Engineering calculator — Mechanical (torque, power, RPM, gears, pulleys)."""
from __future__ import annotations

from ...errors import MathError

RPM_TO_RADPS = 2 * 3.141592653589793 / 60


# ----------------------------------------------------------- Power/torque
def torque_from_power(power_w: float, rpm: float) -> dict:
    """T = P / ω. Returns N·m and kg·m."""
    if rpm <= 0:
        raise MathError("RPM must be > 0")
    t = power_w / (rpm * RPM_TO_RADPS)
    return {"torque_Nm": t, "torque_kgm": t / 9.80665}


def power_from_torque(torque_nm: float, rpm: float) -> dict:
    """P = T × ω. Returns W, kW and HP."""
    if rpm < 0:
        raise MathError("RPM cannot be negative")
    p = torque_nm * rpm * RPM_TO_RADPS
    return {"power_W": p, "power_kW": p / 1000, "power_HP": p / 745.699872}


def rpm_from_speed(speed_ms: float, radius_m: float) -> dict:
    """Rotational speed of a wheel of given radius moving at speed."""
    if radius_m <= 0:
        raise MathError("radius must be > 0")
    rps = speed_ms / (2 * 3.141592653589793 * radius_m)
    return {"rpm": rps * 60, "rad_per_s": rps * 2 * 3.141592653589793}


def speed_from_rpm(rpm: float, radius_m: float) -> dict:
    """Linear speed of wheel edge."""
    return {"speed_mps": rpm / 60 * 2 * 3.141592653589793 * radius_m,
            "speed_kmph": rpm / 60 * 2 * 3.141592653589793 * radius_m * 3.6}


# ----------------------------------------------------------- Gears
def gear_ratio(teeth_driven: int, teeth_driver: int) -> dict:
    if teeth_driver <= 0 or teeth_driven <= 0:
        raise MathError("teeth counts must be positive")
    ratio = teeth_driven / teeth_driver
    return {"ratio": ratio, "type": "reduction" if ratio > 1 else "overdrive"}


def gear_output(rpm_in: float, teeth_driver: int, teeth_driven: int) -> dict:
    g = gear_ratio(teeth_driven, teeth_driver)
    rpm_out = rpm_in / g["ratio"]
    return {"ratio": g["ratio"], "rpm_out": rpm_out,
            "type": g["type"]}


def gear_train(rpm_in: float, stages: list[tuple[int, int]]) -> dict:
    """stages: list of (driver_teeth, driven_teeth). Compound train."""
    total = 1.0
    rpm = rpm_in
    for driver, driven in stages:
        g = gear_ratio(driven, driver)
        total *= g["ratio"]
        rpm = rpm / g["ratio"]
    return {"total_ratio": total, "rpm_out": rpm}


# ----------------------------------------------------------- Pulleys/belts
def pulley_ratio(d_driver: float, d_driven: float) -> dict:
    if d_driver <= 0:
        raise MathError("driver diameter must be > 0")
    ratio = d_driven / d_driver
    return {"ratio": ratio, "rpm_out": None}


def pulley_output(rpm_in: float, d_driver: float, d_driven: float) -> dict:
    rpm_out = rpm_in * d_driver / d_driven
    return {"rpm_out": rpm_out,
            "belt_speed_mps": 3.141592653589793 * d_driver / 1000 * rpm_in / 60
            if d_driver > 0 else None}


def belt_length(d1: float, d2: float, center_dist: float) -> float:
    """Approximate open belt length (mm units consistent)."""
    if center_dist <= 0:
        raise MathError("center distance must be > 0")
    import math
    return (2 * center_dist +
            1.5707963 * (d1 + d2) +
            ((d1 - d2) ** 2) / (4 * center_dist))


# ----------------------------------------------------------- Mechanics
def force(mass_kg: float, accel_ms2: float = 9.80665) -> dict:
    return {"force_N": mass_kg * accel_ms2, "force_kgf": mass_kg}


def work(force_n: float, distance_m: float) -> dict:
    return {"work_J": force_n * distance_m}


def kinetic_energy(mass_kg: float, velocity_ms: float) -> dict:
    return {"ke_J": 0.5 * mass_kg * velocity_ms ** 2}


def potential_energy(mass_kg: float, height_m: float,
                     g: float = 9.80665) -> dict:
    return {"pe_J": mass_kg * g * height_m}


def stress(force_n: float, area_mm2: float) -> dict:
    """Stress in N/mm² (MPa)."""
    if area_mm2 <= 0:
        raise MathError("area must be > 0")
    return {"stress_MPa": force_n / area_mm2}


def lever(moment1: float, dist1: float, dist2: float) -> dict:
    """Balance: F1×d1 = F2×d2 → F2."""
    if dist2 <= 0:
        raise MathError("d2 must be > 0")
    return {"force2": moment1 * dist1 / dist2}
