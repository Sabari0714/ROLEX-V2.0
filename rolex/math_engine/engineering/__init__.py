"""Engineering calculators — electrical, mechanical, electronics."""
from .electrical import (ohms_law, electrical_power, energy,
                         series_resistors, parallel_resistors,
                         voltage_divider, led_resistor, battery_life,
                         capacitive_reactance, inductive_reactance,
                         transformer_ratio)
from .mechanical import (torque_from_power, power_from_torque,
                         rpm_from_speed, speed_from_rpm, gear_ratio,
                         gear_output, gear_train, pulley_output, belt_length,
                         force, work, kinetic_energy, potential_energy,
                         stress, lever)
from .electronics import (resistor_color_code, power_dissipation,
                          rc_time_constant, lc_frequency, wavelength,
                          amp_gain, fuse_rating)

__all__ = [
    "ohms_law", "electrical_power", "energy", "series_resistors",
    "parallel_resistors", "voltage_divider", "led_resistor", "battery_life",
    "capacitive_reactance", "inductive_reactance", "transformer_ratio",
    "torque_from_power", "power_from_torque", "rpm_from_speed",
    "speed_from_rpm", "gear_ratio", "gear_output", "gear_train",
    "pulley_output", "belt_length", "force", "work", "kinetic_energy",
    "potential_energy", "stress", "lever", "resistor_color_code",
    "power_dissipation", "rc_time_constant", "lc_frequency", "wavelength",
    "amp_gain", "fuse_rating",
]
