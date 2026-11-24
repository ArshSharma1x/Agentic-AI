from stats import median

def test_even_length_is_the_mean_of_the_middle_two():
    assert median([1, 2, 3, 4]) == 2.5 and median([5]) == 5
