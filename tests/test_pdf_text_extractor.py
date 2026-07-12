"""Unit tests for services/pdf_text_extractor.py helpers."""

import pytest

from services.pdf_text_extractor import (
    _detect_columns_from_heading_rows,
    _line_words_to_text,
    _looks_like_section_heading,
    _strip_page_furniture,
)


def _word(text, x0, x1, top):
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": top + 12}


class TestStripPageFurniture:
    @pytest.mark.parametrize(
        "footer",
        [
            "Created by UC Davis Career Center | careercenter.ucdavis.edu 22",
            "Page 2 of 3",
            "Diaz-Ortiz Page 1",
            "1 of 3",
            "careercenter.ucdavis.edu 36",
        ],
    )
    def test_drops_footer_lines(self, footer):
        text = "EXPERIENCE\nSoftware Engineer at Acme\n" + footer + "\nLed a team of five"
        out = _strip_page_furniture(text)
        assert footer not in out
        # Real content is preserved
        assert "Software Engineer at Acme" in out
        assert "Led a team of five" in out

    @pytest.mark.parametrize(
        "keep",
        [
            "Managed a portfolio of 3 of the company's largest accounts",  # "3 of" mid-sentence
            "Built the landing page for the 2024 product launch",  # has "page" but real
            "Senior Engineer at example.com",  # url but no trailing page number
            "Ranked 1 of 500 in the national olympiad",  # achievement, not a footer
            "Rated top 2 of 50",  # short achievement ending in "N of M"
            "Completed 8 of 10 sprints ahead of schedule",  # "N of M" content
        ],
    )
    def test_keeps_real_content(self, keep):
        out = _strip_page_furniture("EXPERIENCE\n" + keep)
        assert keep in out

    def test_empty_input(self):
        assert _strip_page_furniture("") == ""


def test_parallel_impact_heading_detects_two_column_resume():
    words = [
        _word("Executive", 40, 105, 174),
        _word("Profile", 110, 158, 174),
        _word("Key", 370, 397, 174),
        _word("Impact", 402, 451, 174),
        _word("Areas", 456, 496, 174),
        _word("Education", 40, 110, 390),
        _word("Key", 370, 397, 390),
        _word("Skills", 402, 440, 390),
    ]

    assert _looks_like_section_heading("Key Impact Areas") is True
    columns = _detect_columns_from_heading_rows(words, 595)
    assert len(columns) == 2
    assert columns[0][1] < columns[1][0]


def test_spaced_glyph_title_is_reconstructed_from_coordinates():
    letters = []
    x = 20.0
    for char in "COMPUTER":
        letters.append(_word(char, x, x + 7, 100))
        x += 9.5
    x += 7.0
    for char in "ENGINEER":
        letters.append(_word(char, x, x + 7, 100))
        x += 9.5

    assert _line_words_to_text(letters) == "COMPUTER ENGINEER"
