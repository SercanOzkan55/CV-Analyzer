"""Tests for services/layout_analyzer.py — structural CV text analysis."""

import pytest
from services.layout_analyzer import analyze_layout, LayoutInfo


class TestAnalyzeLayout:
    def test_empty_text(self):
        info = analyze_layout("")
        assert isinstance(info, LayoutInfo)
        assert info.line_count == 0

    def test_none_text(self):
        info = analyze_layout(None)
        assert isinstance(info, LayoutInfo)

    def test_simple_text(self):
        text = "John Doe\nSoftware Engineer\n\nExperience\n- Built APIs\n- Led team"
        info = analyze_layout(text)
        assert info.line_count > 0
        assert info.linearized_text  # not empty

    def test_detects_bullet_styles(self):
        text = "Skills:\n- Python\n- JavaScript\n• Docker\n• Kubernetes"
        info = analyze_layout(text)
        assert "dash" in info.bullet_styles or "dot" in info.bullet_styles

    def test_detects_underline_markers(self):
        text = "Experience\n----------\nSoftware Engineer at X Corp"
        info = analyze_layout(text)
        assert info.has_underline_markers is True

    def test_single_column_stays_single(self):
        text = "Line one\nLine two\nLine three"
        info = analyze_layout(text)
        assert info.is_multi_column is False

    def test_multi_column_detection(self):
        # Simulate two-column layout with wide gaps
        text = "Name: John              Email: john@x.com\nPhone: 123              Location: NYC"
        info = analyze_layout(text)
        # Should detect multi-column or linearize
        assert isinstance(info.linearized_text, str)

    def test_blank_line_ratio(self):
        text = "A\n\nB\n\nC\n\nD"
        info = analyze_layout(text)
        assert info.blank_line_ratio > 0

    def test_avg_line_length(self):
        text = "Short\nMedium length line\nThis is a longer line of text here"
        info = analyze_layout(text)
        assert info.avg_line_length > 0

    def test_indent_levels_detected(self):
        text = "Header\n  Sub item\n    Deep item\nAnother header"
        info = analyze_layout(text)
        assert len(info.indent_levels) >= 1
