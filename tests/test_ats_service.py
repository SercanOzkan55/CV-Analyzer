"""Tests for services/ats_service.py — ATS text analysis."""
import pytest
from services.ats_service import (
    _find_sections,
    _contact_score,
    _bullet_ratio,
    _action_verb_score,
    _length_score,
    _get_section_status,
    analyze_cv,
    compute_final_score,
    get_action_verbs,
)


class TestFindSections:
    def test_detects_common_sections(self):
        text = "EXPERIENCE\nSoftware Engineer\nEDUCATION\nMIT\nSKILLS\nPython"
        sections = _find_sections(text)
        assert "experience" in sections
        assert "education" in sections
        assert "skills" in sections

    def test_empty_text(self):
        assert _find_sections("") == []

    def test_detects_turkish_sections(self):
        text = "İLETİŞİM\neda@example.com\nÖZET\nBackend geliştirici\nDENEYİM\nPython\nEĞİTİM\nÜniversite\nYETENEKLER\nSQL"
        sections = _find_sections(text)
        assert "contact" in sections
        assert "summary" in sections
        assert "experience" in sections
        assert "education" in sections
        assert "skills" in sections


class TestContactScore:
    def test_full_contact(self):
        text = "john@example.com\n+1-555-1234\nlinkedin.com/in/john\nNew York, NY"
        score = _contact_score(text)
        assert score >= 70

    def test_no_contact(self):
        score = _contact_score("No contact info here")
        assert score < 50


class TestBulletRatio:
    def test_with_bullets(self):
        text = "Experience\n- Led team\n- Built API\n- Deployed system\nOther text"
        ratio = _bullet_ratio(text)
        assert ratio > 0

    def test_no_bullets(self):
        text = "This is paragraph text with no bullets at all."
        ratio = _bullet_ratio(text)
        assert ratio == 0 or ratio < 0.1


class TestActionVerbScore:
    def test_with_verbs(self):
        text = "Led a team of engineers\nManaged project delivery\nDeveloped new features\nCreated dashboards"
        score = _action_verb_score(text)
        assert score > 0

    def test_no_verbs(self):
        text = "Company XYZ\n2020-2023"
        score = _action_verb_score(text)
        assert score < 30

    def test_turkish_action_verbs(self):
        text = "Projeleri yönetti, API servisleri geliştirdi ve veritabanı süreçlerini optimize etti."
        score = _action_verb_score(text, lang="tr")
        assert score >= 30


class TestLengthScore:
    def test_optimal_length(self):
        # ~600 words is good for a CV
        text = " ".join(["word"] * 600)
        score = _length_score(text)
        assert score >= 50

    def test_very_short(self):
        score = _length_score("Short text")
        assert score < 50

    def test_empty(self):
        score = _length_score("")
        assert score == 0 or score < 20


class TestGetSectionStatus:
    def test_pass(self):
        assert _get_section_status(80) == "pass"

    def test_warning(self):
        assert _get_section_status(55) == "warning"

    def test_fail(self):
        assert _get_section_status(30) == "fail"


class TestGetActionVerbs:
    def test_returns_list(self):
        verbs = get_action_verbs("en")
        assert isinstance(verbs, list)
        assert len(verbs) > 10

    def test_includes_common_verbs(self):
        verbs = get_action_verbs("en")
        assert "led" in verbs or "managed" in verbs


class TestAnalyzeCv:
    def test_basic_analysis(self):
        cv_text = (
            "John Doe\njohn@example.com\n\nSUMMARY\nExperienced developer.\n\n"
            "EXPERIENCE\n- Led team of 5\n- Built REST APIs\n\n"
            "EDUCATION\nBS Computer Science, MIT 2020\n\n"
            "SKILLS\nPython, Java, Docker"
        )
        result = analyze_cv(cv_text, job_text="Python developer", lang="en")
        assert isinstance(result, dict)
        assert "overall_score" in result or "ats_score" in result or "sections" in result

    def test_empty_cv(self):
        result = analyze_cv("", lang="en")
        assert isinstance(result, dict)


class TestComputeFinalScore:
    def test_returns_float(self):
        result = compute_final_score(
            keyword=80, section=70, exp=65,
            skills=75, layout=60, contact=80, ml_score=55,
        )
        assert isinstance(result, (int, float))
        assert 0 <= result <= 100

    def test_no_keyword(self):
        result = compute_final_score(
            keyword=0, section=70, exp=65,
            skills=75, layout=60, contact=80, ml_score=55,
        )
        assert 0 <= result <= 100
