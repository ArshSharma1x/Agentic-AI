from roman import to_roman

def test_simple():
    assert to_roman(3) == "III"
    assert to_roman(8) == "VIII"

def test_four():
    assert to_roman(4) == "IV"
