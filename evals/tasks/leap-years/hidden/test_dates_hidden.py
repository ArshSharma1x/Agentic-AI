from dates import is_leap_year

def test_four_hundred_rule():
    assert is_leap_year(2000)
    assert is_leap_year(1600)
    assert not is_leap_year(2100)
