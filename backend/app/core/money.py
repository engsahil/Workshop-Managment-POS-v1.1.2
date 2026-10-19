"""Exact monetary helpers.

All money is stored in the database as INTEGER minor units (paisa).
1 PKR = 100 paisa.  Arithmetic is done with int / Decimal only — never float.
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

PAISA_PER_PKR = 100


def to_paisa(amount) -> int:
    """Convert a PKR amount (Decimal/str/int) to integer paisa."""
    if amount is None:
        return 0
    try:
        d = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid monetary amount")
    if d != d or d in (Decimal("Infinity"), Decimal("-Infinity")):
        raise ValueError("Invalid monetary amount")
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(q * PAISA_PER_PKR)


def to_pkr(paisa: int) -> Decimal:
    """Convert integer paisa to a 2-dp Decimal PKR amount."""
    return (Decimal(int(paisa)) / PAISA_PER_PKR).quantize(Decimal("0.01"))


def pkr_str(paisa: int) -> str:
    """Format paisa as a plain PKR string with 2 decimals (e.g. '1250.00')."""
    return f"{to_pkr(paisa):.2f}"


def format_pkr(paisa: int) -> str:
    """Format paisa with Rs. prefix and thousands separators."""
    return f"Rs. {to_pkr(paisa or 0):,.2f}"
