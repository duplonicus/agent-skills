from decimal import Decimal

import pytest


@pytest.fixture
def jpy_rate():
    return Decimal("163.05")
