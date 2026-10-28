def format_amount(cents: int) -> str:
    """Format an integer number of cents as dollars, e.g. 1999 -> '$19.99'."""
    return f"${cents // 100}.{cents % 100}"
