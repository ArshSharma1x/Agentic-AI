from stats import median

def test_median():
    assert median([3, 1, 2]) == 2
    assert median([1, 2, 3, 4]) == 2
