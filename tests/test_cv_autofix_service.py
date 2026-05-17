import pytest
from unittest.mock import patch, MagicMock

from services.cv_autofix_service import (
    auto_fix_cv_text,
    _parse_sections,
    _looks_like_person_name,
    _header_has_contact,
    _clean_lines,
    _polish_text,
    guess_name_from_lines,
    _canonical_section,
    _noise_section
)

def test_clean_lines():
    text = "Line 1 \n  \nLine 2\n\n\nLine 3"
    lines = _clean_lines(text)
    assert lines == ["Line 1", "", "Line 2", "", "Line 3"]

def test_polish_text():
    text = "bullet one\n- bullet two\n  • bullet three"
    polished = _polish_text(text, lang="en")
    assert "bullet one" in polished
    assert "- Bullet two" in polished or "Bullet two" in polished
    
def test_canonical_section():
    assert _canonical_section("PROFESSIONAL SUMMARY") == "summary"
    assert _canonical_section("Work Experience:") == "experience"
    assert _canonical_section("unknown") is None

def test_noise_section():
    assert _noise_section("References") == "references"
    assert _noise_section("Date of Birth:") == "date of birth"
    assert _noise_section("Summary") is None

def test_looks_like_person_name():
    assert _looks_like_person_name("John Doe") is True
    assert _looks_like_person_name("Jane Smith") is True
    assert _looks_like_person_name("Software Engineer") is False
    assert _looks_like_person_name("john@example.com") is False

def test_guess_name_from_lines():
    lines = [
        "Resume",
        "John Doe",
        "Backend Developer",
        "john@example.com"
    ]
    name = guess_name_from_lines(lines)
    assert name == "John Doe"

def test_header_has_contact():
    assert _header_has_contact(["John Doe", "john@example.com"]) is True
    assert _header_has_contact(["John Doe", "+1 555 123 4567"]) is True
    assert _header_has_contact(["John Doe", "Developer"]) is False

def test_parse_sections():
    cv_text = """John Doe
john@example.com

SUMMARY
A passionate developer.

EXPERIENCE
Software Engineer at Tech
- Did stuff

SKILLS
Python, SQL
"""
    header, sections, dropped = _parse_sections(cv_text)
    assert len(header) >= 2
    assert "John Doe" in header[0]
    assert len(sections["summary"]) >= 1
    assert "A passionate developer." in sections["summary"][0]
    assert len(sections["experience"]) >= 1
    assert len(sections["skills"]) >= 1

@patch("services.cv_autofix_service.analyze_cv")
def test_auto_fix_cv_text(mock_analyze):
    # Mock the ATS analyzer to avoid full service run
    mock_analyze.return_value = {
        "overall_score": 80,
        "section_status": {"skills": "pass", "experience": "pass"}
    }
    
    cv_text = """John Doe
john@example.com

SUMMARY
Developer

EXPERIENCE
Dev at Corp
"""
    result = auto_fix_cv_text(cv_text, "Looking for Developer")
    
    assert "optimized_cv_text" in result
    assert "builder_payload" in result
    assert result["score_delta"] == 0.0 # 80 - 80
    assert result["builder_payload"]["full_name"] == "John Doe"
