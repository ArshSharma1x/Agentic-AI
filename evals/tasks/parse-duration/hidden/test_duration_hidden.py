import pytest
from duration import parse_duration

def test_units_and_errors():
    assert parse_duration("45s") == 45
    assert parse_duration("2h") == 7200
    assert parse_duration("1h5m10s") == 3910
    for bad in ("", "abc", "10", "5x", "h"):
        with pytest.raises(ValueError):
            parse_duration(bad)
