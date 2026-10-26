import pytest

from money import format_amount


@pytest.mark.parametrize(
    ("cents", "expected"),
    [(5, "$0.05"), (1999, "$19.99"), (0, "$0.00"), (100, "$1.00"), (1050, "$10.50")],
)
def test_format_amount(cents, expected):
    assert format_amount(cents) == expected
