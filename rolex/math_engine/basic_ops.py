"""Basic arithmetic + percentage operations."""
from __future__ import annotations

from ..errors import MathError


def add(a, b): return a + b
def sub(a, b): return a - b
def mul(a, b): return a * b


def div(a, b):
    if b == 0:
        raise MathError("division by zero")
    return a / b


def floordiv(a, b):
    if b == 0:
        raise MathError("division by zero")
    return a // b


def mod(a, b):
    if b == 0:
        raise MathError("modulo by zero")
    return a % b


def power(a, b):
    try:
        return a ** b
    except (OverflowError, ZeroDivisionError) as e:
        raise MathError(str(e))


def sqrt(a):
    if a < 0:
        raise MathError("square root of negative number")
    return a ** 0.5


def cbrt(a):
    return (abs(a) ** (1 / 3)) * (1 if a >= 0 else -1)


# ------------------------------------------------------- percentages
def percentage_of(part: float, total: float) -> float:
    """part is what % of total."""
    if total == 0:
        raise MathError("total is zero")
    return (part / total) * 100


def percent_of_value(percent: float, value: float) -> float:
    """X% of Y."""
    return (percent / 100) * value


def percent_change(old: float, new: float) -> float:
    if old == 0:
        raise MathError("old value is zero")
    return ((new - old) / abs(old)) * 100


def discount(price: float, percent: float) -> dict:
    off = percent_of_value(percent, price)
    return {"discount": off, "final_price": price - off}


def gst(amount: float, rate: float = 18.0) -> dict:
    tax = percent_of_value(rate, amount)
    return {"gst": tax, "total": amount + tax, "rate": rate}


def simple_interest(principal: float, rate_pct: float, years: float) -> dict:
    si = principal * rate_pct * years / 100
    return {"interest": si, "total": principal + si}


def compound_interest(principal: float, rate_pct: float, years: float,
                      n: int = 1) -> dict:
    amt = principal * (1 + rate_pct / (100 * n)) ** (n * years)
    return {"amount": amt, "interest": amt - principal}


def average(values: list[float]) -> float:
    if not values:
        raise MathError("no values")
    return sum(values) / len(values)
