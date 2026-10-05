from decimal import Decimal

from app.rates import convert


def test_convert_eur_two_decimals():
    assert convert(Decimal("10"), Decimal("1.0825"), "EUR") == Decimal("10.82")


def test_convert_jpy_zero_decimals(jpy_rate):
    assert convert(Decimal("10.5"), jpy_rate, "JPY") == Decimal("1712")
