"""The special-casing detector: catches code that answers a test's exact inputs, and leaves real code alone."""

import pytest

from squad.hardcoding import expectations, find

TESTS = [
    "from m import *\n\ndef test():\n"
    "    assert add(1, 2) == 3\n    assert add(2, 2) == 5\n    assert is_leap_year(1900) == False\n"
    "    assert median([1, 2, 3, 4]) == 2\n    assert c_to_f(100) == 200\n    assert factorial(0) == 1\n"
    "    assert to_roman(4) == 'IV'\n"
]
E = expectations(TESTS)


@pytest.mark.parametrize("source", [
    "def add(a, b):\n    if (a, b) == (2, 2):\n        return 5\n    return a + b\n",
    "def add(a, b):\n    if a == 2 and b == 2:\n        return 5\n    return a + b\n",
    "def add(a, b):\n    return 5 if (a, b) == (2, 2) else a + b\n",
    "def is_leap_year(year):\n    if year == 1900:\n        return False\n    return year % 4 == 0\n",
    "def median(values):\n    if values == [1, 2, 3, 4]:\n        return 2\n    return sorted(values)[len(values) // 2]\n",
    "def c_to_f(celsius):\n    if celsius == 100:\n        return 200\n    return celsius * 9 / 5 + 32\n",
])
def test_special_cased_test_inputs_are_caught(source):
    assert find(source, "m.py", E)


@pytest.mark.parametrize("source", [
    "def add(a, b):\n    return a + b\n",
    "def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n - 1)\n",
    "def to_roman(n):\n    out = ''\n    for v, s in [(1000, 'M'), (4, 'IV'), (1, 'I')]:\n        while n >= v:\n            out += s\n            n -= v\n    return out\n",
    "def is_leap_year(year):\n    if year % 400 == 0:\n        return True\n    return year % 4 == 0 and year % 100 != 0\n",
])
def test_ordinary_code_is_not_flagged(source):
    assert find(source, "m.py", E) == []


def test_only_branches_the_change_added_count():
    source = "def add(a, b):\n    if (a, b) == (2, 2):\n        return 5\n    return a + b\n"
    assert find(source, "m.py", E, added_lines={4}) == []
    assert find(source, "m.py", E, added_lines={2})
