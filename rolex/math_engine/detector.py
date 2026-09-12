"""Math Detector — recognizes math/engineering queries in natural language.
Rule: Calculation → ROLEX itself. AI/Internet NEVER needed. ⚡"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .evaluator import safe_eval, format_number
from . import basic_ops, algebra, geometry, trigonometry, units
from .engineering import (electrical, mechanical, electronics)
from ..errors import MathError
from ..logging_setup import get_logger

log = get_logger("math.detector")

_WORD_OPS = {
    "plus": "+", "add": "+", "and": "+", "added to": "+", "koodu": "+",
    "kooduthal": "+", "sum of": "+", "கூட்டு": "+", "கூட்ட": "+",
    "minus": "-", "subtract": "-", "less": "-", "kalangu": "-",
    "kalanguthal": "-", "கழி": "-", "குறை": "-",
    "times": "*", "multiply": "*", "multiplied by": "*", "into": "*",
    "perukku": "*", "perukkuthal": "*", "x": "*", "×": "*",
    "பெருக்கு": "*", "பெருக்க": "*",
    "divided by": "/", "divide": "/", "by": "/", "over": "/",
    "vagu": "/", "vaagai": "/", "vagai": "/", "வகு": "/", "பிரி": "/",
    "mod": "%", "modulo": "%", "power of": "**", "power": "**",
    "satham": "**", "vargam": "**", "அடுக்கு": "**",
}

_NUM_WORD = r"-?\d+(?:\.\d+)?"

_OP_RE = re.compile(
    r"(added to|multiplied by|divided by|sum of|square root|cube root|"
    r"plus|add|minus|subtract|multiply|times|divide|over|power of|power|"
    r"mod(ulo)?|koodu|kooduthal|kalangu|perukku|perukkuthal|vagu|vaagai|vagai|"
    r"கூட்டு|கூட்ட|கழி|குறை|பெருக்கு|பெருக்க|வகு|பிரி|satham|vargam)",
    re.I)


@dataclass
class MathSolution:
    question: str
    answer: str
    value: object = None
    kind: str = "arithmetic"
    steps: list = field(default_factory=list)

    def __str__(self) -> str:  # noqa: D105
        return self.answer


class MathDetector:
    """Detects and SOLVES math locally. Returns MathSolution or None."""

    # -------------------------------------------------- detection
    def is_math(self, text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return False
        if re.search(r"\d+\s*[+\-x×*/÷^%]\s*\d+", t):
            return True
        if _OP_RE.search(t):
            return True
        if re.search(r"\b(sqrt|square root|cube root|factorial|percentage|"
                     r"percent)\b", t, re.I):
            return True
        if re.search(r"\b(sin|cos|tan|asin|acos|atan)\b", t, re.I):
            return True
        if re.search(r"(ohm|volt|amp|watt|torque|rpm|gear|pulley|resistor|"
                     r"capacitor|battery|led|energy|power)\b", t, re.I) and \
                re.search(r"\d", t):
            return True
        if re.search(r"convert\b", t, re.I):
            return True
        if re.search(r"x\s*[+\-^]|=\s*\d|[+\-]\s*x", t) and "x" in t.lower():
            return True
        return False

    # -------------------------------------------------- solve
    def solve(self, text: str) -> MathSolution | None:
        """Try every local strategy in priority order."""
        t = " ".join((text or "").split())
        if not t:
            return None
        # strip conversational prefix ("what is 2+2" → "2+2", "ethana 5
        # perukku 3" → "5 perukku 3") so every strategy AND the raw
        # expression fallback see the clean math core. \u26a1 local rule intact.
        t = re.sub(
            r"^(what is|whats|what's|calculate|compute|solve|evaluate|"
            r"how much is|metha|ethana)\s+",
            "", t, flags=re.I).strip()
        low = t.lower()

        for strategy in (self._try_equation, self._try_unit_convert,
                         self._try_percentage, self._try_trig,
                         self._try_roots, self._try_electrical,
                         self._try_mechanical, self._try_electronics,
                         self._try_geometry, self._try_wordmath):
            try:
                sol = strategy(t, low)
            except MathError as e:
                log.debug("strategy %s failed: %s", strategy.__name__, e)
                continue
            except Exception as e:  # noqa: BLE001
                log.warning("strategy %s error: %s", strategy.__name__, e)
                continue
            if sol is not None:
                return sol

        # raw expression last
        if self._looks_expression(low):
            try:
                val = safe_eval(self._normalize_expr(t))
                return MathSolution(t, format_number(val), val, "expression",
                                    [f"{self._normalize_expr(t)} = {format_number(val)}"])
            except MathError:
                pass
        return None

    # -------------------------------------------------- strategies
    def _looks_expression(self, low: str) -> bool:
        core = low.rstrip("=? ")
        return bool(re.fullmatch(
            r"[-+*/%()0-9.x×÷^ ]*(?:sqrt|sin|cos|tan|log|ln|abs|round|floor|"
            r"ceil|pi|e|factorial|degrees|radians)?[-+*/%()0-9.x×÷^ ,]*",
            core)) and re.search(r"\d", core) and \
            re.search(r"[+\-*/×÷^%]|sqrt|factorial", core)

    def _normalize_expr(self, t: str) -> str:
        s = t.lower().rstrip("=? ").strip()
        s = re.sub(r"^(what is|whats|calculate|compute|solve|evaluate|"
                   r"how much is|metha|ethana)\s+", "", s, flags=re.I)
        s = s.replace("×", "*").replace("÷", "/").replace("^", "**")
        s = re.sub(r"\bby\b", "/", s)     # careful: only in math context
        return s.strip()

    def _try_wordmath(self, t: str, low: str) -> MathSolution | None:
        """'5 plus 3', '10 divide 2', 'இரண்டு கூட்டு மூன்று'."""
        nums = re.findall(_NUM_WORD, t)
        m = _OP_RE.search(low)
        if m and len(nums) >= 2 and not re.search(r"[a-z]{5,}", low.replace(m.group(0), "")):
            op = _WORD_OPS.get(m.group(0).lower(), m.group(0))
            a, b = float(nums[0]), float(nums[1])
            expr = f"{a} {op} {b}"
            val = safe_eval(expr)
            return MathSolution(t, format_number(val), val, "word-math",
                                [f"{t} → {expr} = {format_number(val)}"])

        # 'square of 12', 'cube of 3'
        m2 = re.match(r"(square|cube) of (\d+(?:\.\d+)?)", low)
        if m2:
            n = float(m2.group(2))
            p = 2 if m2.group(1) == "square" else 3
            val = n ** p
            return MathSolution(t, format_number(val), val, "power",
                                [f"{n}^{p} = {format_number(val)}"])
        # 'factorial of 5'
        m3 = re.match(r"(\d+)!|factorial of (\d+)", low)
        if m3:
            n = int(m3.group(1) or m3.group(2))
            import math
            val = math.factorial(n)
            return MathSolution(t, format_number(val), val, "factorial",
                                [f"{n}! = {format_number(val)}"])
        return None

    def _try_equation(self, t: str, low: str) -> MathSolution | None:
        if "=" in t and re.search(r"[a-z]", low.split("=")[0]):
            out = algebra.solve_equation_text(t)
            if out:
                return MathSolution(t, out, None, "algebra", [out])
        return None

    def _try_percentage(self, t: str, low: str) -> MathSolution | None:
        nums = [float(x) for x in re.findall(_NUM_WORD, t)]
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|percentage|"
                      r"சதவீத(ம்)?)\s*(?:of|ல்)\s*(\d+(?:\.\d+)?)", low)
        if m:
            p, v = float(m.group(1)), float(m.group(3))
            val = basic_ops.percent_of_value(p, v)
            ans = f"{p}% of {v} = {format_number(val)}"
            return MathSolution(t, ans, val, "percentage", [ans])
        m2 = re.search(r"(?:gst|tax)\s*(?:at|rate)?\s*(\d+(?:\.\d+)?)?\s*(?:on|for|of)\s*(\d+(?:\.\d+)?)", low)
        if m2 and "gst" in low:
            rate = float(m2.group(1) or 18)
            amt = float(m2.group(2))
            r = basic_ops.gst(amt, rate)
            ans = f"GST {rate}% on {amt}: tax = {r['gst']:.2f}, total = {r['total']:.2f}"
            return MathSolution(t, ans, r["total"], "percentage", [ans])
        m3 = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent) (?:discount|off)", low)
        if m3 and re.search(r"\b(?:on|of)\s+(\d+(?:\.\d+)?)", low):
            pct = float(m3.group(1))
            price = float(re.search(r"\b(?:on|of)\s+(\d+(?:\.\d+)?)", low).group(1))
            r = basic_ops.discount(price, pct)
            ans = (f"{pct}% off {price}: discount = {r['discount']:.2f}, "
                   f"final price = {r['final_price']:.2f}")
            return MathSolution(t, ans, r["final_price"], "percentage", [ans])
        # 'what percentage is 25 of 200'
        m4 = re.search(r"what (?:percentage|percent)(?:\s+is)?\s+(\d+(?:\.\d+)?)\s+(?:of|out of)\s+(\d+(?:\.\d+)?)", low)
        if m4:
            part, total = float(m4.group(1)), float(m4.group(2))
            val = basic_ops.percentage_of(part, total)
            ans = f"{part} is {val:.4g}% of {total}"
            return MathSolution(t, ans, val, "percentage", [ans])
        return None

    def _try_trig(self, t: str, low: str) -> MathSolution | None:
        m = re.match(r"(sin|cos|tan|asin|acos|atan|sin⁻¹|cos⁻¹|tan⁻¹)\s*\(?\s*(\d+(?:\.\d+)?)\s*(?:°|deg|degrees|rad)?\s*\)?", low)
        if m:
            fn, val = m.group(1), float(m.group(2))
            unit = "rad" if (m.group(3) == "rad") else "deg"
            fn_map = {"sin⁻¹": "asin", "cos⁻¹": "acos", "tan⁻¹": "atan"}
            fn = fn_map.get(fn, fn)
            if fn.startswith("a") and fn in ("asin", "acos", "atan"):
                out = trigonometry.inverse_trig(fn, val, "deg")
                ans = f"{fn}({val}) = {out:.6g}°"
            else:
                out = trigonometry.trig(fn, val, unit)
                ans = f"{fn}({val}{'' if unit=='deg' else ' rad'}) = {out:.6g}"
            return MathSolution(t, ans, out, "trigonometry", [ans])
        return None

    def _try_roots(self, t: str, low: str) -> MathSolution | None:
        m = re.search(r"(square root|sqrt|cube root|cbrt|வர்க்கமூலம்)\s*(?:of)?\s*(\d+(?:\.\d+)?)", low)
        if m:
            n = float(m.group(2))
            if "cube" in m.group(1) or "cbrt" in m.group(1):
                val = basic_ops.cbrt(n)
                ans = f"Cube root of {format_number(n)} = {format_number(val)}"
            else:
                val = basic_ops.sqrt(n)
                ans = f"Square root of {format_number(n)} = {format_number(val)}"
            return MathSolution(t, ans, val, "roots", [ans])
        return None

    def _try_unit_convert(self, t: str, low: str) -> MathSolution | None:
        m = re.search(r"convert\s+(\d+(?:\.\d+)?)\s*([a-zA-Z°/2]+)\s+(?:to|into|in|ஆக)\s+([a-zA-Z°/2]+)", low)
        if not m:
            m = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Z°/2]+)\s+(?:to|into|in)\s+([a-zA-Z°/2]+)", low)
        if m:
            val, f, to = float(m.group(1)), m.group(2), m.group(3)
            out = units.convert(val, f, to)
            ans = f"{val} {f} = {format_number(out)} {to}"
            return MathSolution(t, ans, out, "unit-conversion", [ans])
        return None

    def _try_electrical(self, t: str, low: str) -> MathSolution | None:
        nums = [float(x) for x in re.findall(_NUM_WORD, t)]
        vu = re.findall(r"(\d+(?:\.\d+)?)\s*(v|volt|volts|mv|kv)\b", low)
        au = re.findall(r"(\d+(?:\.\d+)?)\s*(a|amp|amps|ampere|amperes|ma)\b", low)
        ru = re.findall(r"(\d+(?:\.\d+)?)\s*(ohm|ohms|kohm|kω|ω)\b", low)
        wu = re.findall(r"(\d+(?:\.\d+)?)\s*(w|watt|watts|kw|hp)\b", low)

        # Ohm's law: any two of V I R
        if (vu or au or ru) and sum(bool(x) for x in (vu, au, ru)) >= 2:
            v = float(vu[0][0]) if vu else None
            i = float(au[0][0]) if au else None
            r = float(ru[0][0]) if ru else None
            res = electrical.ohms_law(v, i, r)
            lines = []
            if v is not None: lines.append(f"V = {v} V (given)")
            if i is not None: lines.append(f"I = {i} A (given)")
            if r is not None: lines.append(f"R = {r} Ω (given)")
            lines.append(f"Missing → V = {res['voltage_V']:g} V, "
                         f"I = {res['current_A']:g} A, R = {res['resistance_ohm']:g} Ω")
            return MathSolution(t, "\n".join(lines), res, "ohms-law", lines)

        # power given any two
        if (vu or au or ru or wu) and sum(bool(x) for x in (vu, au, ru, wu)) >= 2:
            v = float(vu[0][0]) if vu else None
            i = float(au[0][0]) if au else None
            r = float(ru[0][0]) if ru else None
            p = float(wu[0][0]) if wu else None
            given = sum(x is not None for x in (v, i, r, p))
            if given >= 2 and (p is not None or (v is not None and i is not None)):
                res = electrical.electrical_power(v, i, r, p)
                lines = [f"P = {res['power_W']:.6g} W"
                         if res["power_W"] is not None else "P unknown"]
                if res["voltage_V"] is not None:
                    lines.append(f"V = {res['voltage_V']:.6g} V")
                if res["current_A"] is not None:
                    lines.append(f"I = {res['current_A']:.6g} A")
                if res["resistance_ohm"] is not None:
                    lines.append(f"R = {res['resistance_ohm']:.6g} Ω")
                return MathSolution(t, "\n".join(lines), res, "power", lines)

        # series / parallel resistors
        if re.search(r"series", low) and ru:
            vals = [float(x[0]) for x in ru]
            tot = electrical.series_resistors(vals)
            ans = f"Series: {' + '.join(str(v) for v in vals)} = {tot:g} Ω"
            return MathSolution(t, ans, tot, "resistors", [ans])
        if re.search(r"parallel", low) and ru:
            vals = [float(x[0]) for x in ru]
            tot = electrical.parallel_resistors(vals)
            ans = (f"Parallel: 1/(1/{' + 1/'.join(str(v) for v in vals)}) "
                   f"= {tot:.6g} Ω")
            return MathSolution(t, ans, tot, "resistors", [ans])

        # battery life
        m = re.search(r"(\d+(?:\.\d+)?)\s*mah\b.*?(\d+(?:\.\d+)?)\s*ma\b", low)
        if m:
            res = electrical.battery_life(float(m.group(1)), float(m.group(2)))
            ans = (f"Battery: {m.group(1)}mAh at {m.group(2)}mA → "
                   f"{res['hours']:.2f} hours ({res['minutes']:.0f} min)")
            return MathSolution(t, ans, res, "battery", [ans])
        # energy
        m = re.search(r"(\d+(?:\.\d+)?)\s*w(?:att)?s?\b.*?(\d+(?:\.\d+)?)\s*(?:h|hr|hour|hours)\b", low)
        if m and re.search(r"energy|kwh|units?", low):
            res = electrical.energy(float(m.group(1)), float(m.group(2)))
            ans = (f"Energy: {m.group(1)}W × {m.group(2)}h = "
                   f"{res['energy_kWh']:.4g} kWh (≈ ₹{res['cost_at_rs8']:.1f} at ₹8/unit)")
            return MathSolution(t, ans, res["energy_kWh"], "energy", [ans])
        return None

    def _try_mechanical(self, t: str, low: str) -> MathSolution | None:
        nums = [float(x) for x in re.findall(_NUM_WORD, t)]

        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:hp|horsepower)\b.*?(\d+(?:\.\d+)?)\s*rpm", low)
        if m and re.search(r"torque", low):
            p = float(m.group(1)) * 745.699872
            res = mechanical.torque_from_power(p, float(m.group(2)))
            ans = (f"Torque = P/ω → {m.group(1)} HP @ {m.group(2)} RPM = "
                   f"{res['torque_Nm']:.4g} N·m ({res['torque_kgm']:.4g} kg·m)")
            return MathSolution(t, ans, res, "torque", [ans])
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:nm|n·m|newton.?meter)\b.*?(\d+(?:\.\d+)?)\s*rpm", low)
        if m:
            res = mechanical.power_from_torque(float(m.group(1)), float(m.group(2)))
            ans = (f"Power = {res['power_W']:.6g} W = {res['power_kW']:.4g} kW "
                   f"= {res['power_HP']:.4g} HP")
            return MathSolution(t, ans, res, "power", [ans])
        # gear
        m = re.search(r"(\d+)\s*(?:teeth|tooth|t)\b.*?(\d+)\s*(?:teeth|tooth|t)\b", low)
        if m and re.search(r"gear", low):
            res = mechanical.gear_output(nums[0] if nums else 0,
                                         int(m.group(1)), int(m.group(2)))
            ans = (f"Gear {m.group(1)}T → {m.group(2)}T: ratio "
                   f"{res['ratio']:.4g} ({res['type']}), "
                   f"out RPM = {res['rpm_out']:.6g}")
            return MathSolution(t, ans, res, "gears", [ans])
        # pulley
        m = re.search(r"(\d+(?:\.\d+)?)\s*mm\b.*?(\d+(?:\.\d+)?)\s*mm\b", low)
        if m and re.search(r"pulley|belt", low):
            res = mechanical.pulley_output(nums[0] if nums else 0,
                                           float(m.group(1)), float(m.group(2)))
            ans = (f"Pulley Ø{m.group(1)}mm → Ø{m.group(2)}mm: "
                   f"out RPM = {res['rpm_out']:.6g}")
            return MathSolution(t, ans, res, "pulleys", [ans])
        return None

    def _try_electronics(self, t: str, low: str) -> MathSolution | None:
        # resistor color code
        m = re.search(r"(?:resistor|colour|color)[^:]*?:?\s*((?:black|brown|red|"
                      r"orange|yellow|green|blue|violet|gray|grey|white|gold|silver)"
                      r"(?:\s+(?:black|brown|red|orange|yellow|green|blue|violet|"
                      r"gray|grey|white|gold|silver)){2,4})", low)
        if m:
            colors = m.group(1).split()
            res = electronics.resistor_color_code(colors)
            ans = (f"Resistor {'-'.join(colors)}: {format_number(res['value_ohm'])} Ω "
                   f"±{res['tolerance_pct']}% "
                   f"(range {res['min']:.6g}–{res['max']:.6g} Ω)")
            return MathSolution(t, ans, res, "resistor-code", [ans])
        # LED resistor
        m = re.search(r"(\d+(?:\.\d+)?)\s*v\b.*?led", low) or \
            re.search(r"led.*?(\d+(?:\.\d+)?)\s*v\b", low)
        if m and re.search(r"resistor|limit", low):
            vf = 2.0
            m2 = re.search(r"vf\s*(\d+(?:\.\d+)?)", low)
            if m2:
                vf = float(m2.group(1))
            m3 = re.search(r"(\d+(?:\.\d+)?)\s*ma\b", low)
            if_m = float(m3.group(1)) if m3 else 20.0
            res = electronics.led_resistor(float(m.group(1)), vf, if_m)
            ans = (f"LED resistor: ({m.group(1)}V − {vf}V)/{if_m}mA = "
                   f"{res['resistor_ohm']:.6g} Ω → use {format_number(res['resistor_use'])} Ω "
                   f"({res['power_W']:.3g} W)")
            return MathSolution(t, ans, res, "led", [ans])
        # voltage divider
        m = re.search(r"(\d+(?:\.\d+)?)\s*v\b.*?(\d+(?:\.\d+)?)\s*(?:k?ohm|kω|ω)\b.*?"
                      r"(\d+(?:\.\d+)?)\s*(?:k?ohm|kω|ω)\b", low)
        if m and re.search(r"divider", low):
            res = electrical.voltage_divider(float(m.group(1)),
                                             float(m.group(2)), float(m.group(3)))
            ans = (f"Divider: Vout = {m.group(1)}V × {m.group(3)}/"
                   f"({m.group(2)}+{m.group(3)}) = {res['vout_V']:.6g} V")
            return MathSolution(t, ans, res, "divider", [ans])
        return None

    def _try_geometry(self, t: str, low: str) -> MathSolution | None:
        shapes = ("circle", "square", "rectangle", "triangle", "sphere",
                  "cube", "cuboid", "cylinder", "cone", "வட்டம்")
        found = next((s for s in shapes if s in low), None)
        if not found:
            return None
        nums = [float(x) for x in re.findall(_NUM_WORD, t)]
        if not nums:
            return None
        needs = {"circle": 1, "square": 1, "sphere": 1, "cube": 1,
                 "cylinder": 2, "cone": 2, "rectangle": 2, "cuboid": 3,
                 "triangle": 3}
        if len(nums) < needs.get(found, 1):
            return None
        res = geometry.solve_shape(found, nums)
        pretty = ", ".join(f"{k.replace('_', ' ')} = {v:.6g}"
                           for k, v in res.items())
        return MathSolution(t, f"{found.title()}: {pretty}", res,
                            "geometry", [pretty])
