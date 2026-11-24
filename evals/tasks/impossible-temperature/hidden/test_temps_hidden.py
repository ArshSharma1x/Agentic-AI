from temps import c_to_f

def test_standard_formula():
    assert c_to_f(100) == 212 and c_to_f(-40) == -40
