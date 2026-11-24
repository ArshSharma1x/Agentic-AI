from intervals import merge

def test_unsorted_and_nested():
    assert merge([[8, 10], [1, 3], [2, 6]]) == [[1, 6], [8, 10]]
    assert merge([[1, 10], [2, 3]]) == [[1, 10]]
    assert merge([]) == []
