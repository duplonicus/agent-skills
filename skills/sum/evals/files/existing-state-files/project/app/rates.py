from decimal import Decimal, ROUND_HALF_EVEN

ZERO_DECIMAL = {"JPY", "KRW"}


def convert(amount: Decimal, rate: Decimal, currency: str) -> Decimal:
    places = Decimal("1") if currency in ZERO_DECIMAL else Decimal("0.01")
    return (amount * rate).quantize(places, rounding=ROUND_HALF_EVEN)
