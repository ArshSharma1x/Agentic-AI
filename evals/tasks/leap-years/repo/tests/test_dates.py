from dates import is_leap_year

def test_ordinary_years():
    assert is_leap_year(2024)
    assert not is_leap_year(2023)

def test_century():
    assert not is_leap_year(1900)
