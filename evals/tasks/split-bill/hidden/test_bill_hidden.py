import pytest
from bill import split

def test_remainder_and_errors():
    parts = split(1000, 3)
    assert sum(parts) == 1000 and max(parts) - min(parts) <= 1 and len(parts) == 3
    assert sum(split(1, 4)) == 1
    with pytest.raises(ValueError):
        split(100, 0)
