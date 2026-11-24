from csvline import parse_line

def test_escaped_quotes_and_empty_fields():
    assert parse_line('"say ""hi""",x') == ['say "hi"', "x"]
    assert parse_line("a,,b") == ["a", "", "b"]
    assert parse_line('""') == [""]
