import pytest
from unittest.mock import patch, MagicMock

from services.cv_autofix_service import (
    auto_fix_cv_text,
    _assess_export_safety,
    _build_safe_export_model,
    _parse_sections,
    _parse_education_entries,
    _looks_like_person_name,
    _header_has_contact,
    _clean_lines,
    _polish_text,
    _parse_experience_entries,
    guess_name_from_lines,
    _canonical_section,
    _noise_section,
    _enforce_protected_section_floor,
)
from schemas.cv_model import CVModel


def test_parse_experience_entries_splits_multiple_bullet_jobs():
    # Jobs separated by header lines, with ● (U+25CF) bullets — the most
    # common CV bullet glyph. Each job must become its own entry instead of
    # collapsing into one.
    lines = [
        "Microbiology Intern, Beckman Coulter, CA June 2022 to September 2022",
        "● Sub-cultured microorganisms and performed laboratory tests",
        "● Prepared materials for clinical trial initiation activities",
        "Pharmacy Intern, CVS Health, CA June 2024 to September 2024",
        "● Carefully dispensed prescriptions in a sterile manner",
        "● Collaborated with healthcare professionals on counselling",
        "Salesperson, Macy's, CA August 2023 to Present",
        "● Greeted approximately 50 customers per shift",
    ]
    entries = _parse_experience_entries(lines)
    assert len(entries) == 3
    assert all(e["bullets"] for e in entries)


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
    lines = ["Resume", "John Doe", "Backend Developer", "john@example.com"]
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


def test_protected_sections_are_not_shrunk():
    cv_text = """John Doe
john@example.com

PROJECTS
Project One
Project Two
Project Three
Project Four

CERTIFICATIONS
AWS Cloud Practitioner
Google Data Analytics
"""
    optimized_text = """John Doe
john@example.com

PROJECTS
Project One
Project Two

CERTIFICATIONS
AWS Cloud Practitioner
"""
    text, sections, _, warnings = _enforce_protected_section_floor(
        cv_text,
        optimized_text,
        {"projects": ["Project One", "Project Two"], "certifications": ["AWS Cloud Practitioner"]},
        ["projects", "certifications"],
        "John Doe",
        [],
        ["john@example.com"],
    )

    assert "Project Four" in text
    assert "Google Data Analytics" in text
    assert len(sections["projects"]) == 4
    assert len(sections["certifications"]) == 2
    assert warnings


def test_safe_export_model_preserves_facts_and_rejects_project_title_summary():
    source = CVModel.from_mapping(
        {
            "full_name": "Ahmet Bugra Kuscu",
            "email": "ahmet@example.com",
            "phone": "+90 555 111 22 33",
            "linkedin": "https://example.com/ahmet",
            "projects": [
                {
                    "name": "WHO WANTS TO BE A MILLIONAIRE",
                    "description": "TCP client-server quiz game",
                    "bullets": ["Implemented synchronized multiplayer scoring"],
                }
            ],
            "skills": ["Java", "TCP"],
            "languages": ["Turkish", "English"],
        }
    )
    candidate = CVModel.from_mapping(
        {
            "full_name": "Ahmet Bugra Kuscu",
            "email": "ahmet@example.com",
            "summary": "TO BE A MILLIONAIRE. Core skills include Java and TCP.",
            "projects": [
                {
                    "name": "WHO WANTS TO BE A MILLIONAIRE",
                    "bullets": ["WHO WANTS TO BE A MILLIONAIRE"],
                }
            ],
        }
    )

    with patch("services.cv_autofix_service.structured_text_to_builder_payload", return_value=candidate):
        merged = _build_safe_export_model(source, "optimized", used_ai=True)

    assert merged.summary == ""
    assert merged.phone == source.phone
    assert merged.linkedin == source.linkedin
    assert merged.projects == source.projects
    assert merged.languages == ["Turkish", "English"]


def test_export_safety_rejects_lost_source_phone():
    source_text = "John Doe\njohn@example.com\nPhone: +1 555 123 4567\n\nSUMMARY\nBackend engineer"
    incomplete = CVModel(full_name="John Doe", email="john@example.com", summary="Backend engineer")

    export_safe, report = _assess_export_safety(source_text, incomplete)

    assert export_safe is False
    assert any("phone_lost" in issue for issue in report["hard_fails"])


def test_education_parser_handles_date_before_curly_apostrophe_degree():
    entries = _parse_education_entries(
        [
            "2022-2027",
            "BACHELOR’S DEGREE",
            "ISTANBUL HEALTH AND TECHNOLOGY",
            "UNIVERSITY (İSTÜN)",
        ]
    )

    assert len(entries) == 1
    assert entries[0]["degree"] == "BACHELOR’S DEGREE"
    assert entries[0]["school"] == "ISTANBUL HEALTH AND TECHNOLOGY UNIVERSITY (İSTÜN)"
    assert entries[0]["start_date"] == "2022"
    assert entries[0]["end_date"] == "2027"


@patch("services.cv_autofix_service.analyze_cv")
def test_auto_fix_cv_text(mock_analyze):
    # Mock the ATS analyzer to avoid full service run
    mock_analyze.return_value = {"overall_score": 80, "section_status": {"skills": "pass", "experience": "pass"}}

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
    assert result["score_delta"] == 0.0  # 80 - 80
    assert result["builder_payload"]["full_name"] == "John Doe"
    assert result["export_safe"] is True


@patch("services.cv_autofix_service.analyze_cv")
def test_auto_fix_never_returns_negative_score_delta(mock_analyze):
    cv_text = """John Doe
john@example.com

SUMMARY
Developer

EXPERIENCE
Dev at Corp

PROJECTS
Project One
Project Two
    """
    guarded_cv_text = cv_text.strip()

    def score_for_text(text, *args, **kwargs):
        return {"overall_score": 90 if text == guarded_cv_text else 80}

    mock_analyze.side_effect = score_for_text
    result = auto_fix_cv_text(cv_text, "Looking for Developer", use_ai=False)

    assert result["score_delta"] == 0.0
    assert result["optimized_cv_text"] == guarded_cv_text
    assert any("original CV text was preserved" in warning for warning in result["warnings"])
