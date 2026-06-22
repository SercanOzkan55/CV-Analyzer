from utils.sql import LIKE_ESCAPE_CHAR, contains_like_pattern, escape_like_wildcards


def test_escape_like_wildcards_escapes_percent_and_underscore():
    assert escape_like_wildcards("a%b_c") == f"a{LIKE_ESCAPE_CHAR}%b{LIKE_ESCAPE_CHAR}_c"


def test_escape_like_wildcards_escapes_existing_escape_char():
    assert escape_like_wildcards(r"a\b") == r"a\\b"


def test_contains_like_pattern_wraps_escaped_value():
    assert contains_like_pattern("100%_match") == rf"%100\%\_match%"
