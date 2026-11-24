def to_roman(n: int) -> str:
    """Convert 1..3999 to a Roman numeral."""
    values = [(1000, "M"), (500, "D"), (100, "C"), (50, "L"), (10, "X"), (5, "V"), (1, "I")]
    out = ""
    for value, letter in values:
        while n >= value:
            out += letter
            n -= value
    return out
