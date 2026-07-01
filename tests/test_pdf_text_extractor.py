"""Unit tests for services/pdf_text_extractor.py helpers."""

import pytest

from services.pdf_text_extractor import _strip_page_furniture


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
