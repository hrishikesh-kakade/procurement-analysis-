from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def quantize_money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def line_total(quantity: int, unit_price: Decimal | int | float | str) -> Decimal:
    return quantize_money(Decimal(quantity) * Decimal(str(unit_price)))


def order_total(line_totals: Iterable[Decimal]) -> Decimal:
    return quantize_money(sum((Decimal(str(t)) for t in line_totals), Decimal("0")))
