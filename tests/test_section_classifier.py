"""Unit tests for services/section_classifier.py — public API."""

import pytest
from services.section_classifier import (
    classify_block,
    split_blocks,
    canonicalize_section_key,
    _sniff_header,
)


class TestSniffExperienceHeaders:
    """Qualifier-prefixed experience headers should be recognized as
    experience section headers, while job titles ending in 'experience'
    should not."""

    @pytest.mark.parametrize(
        "header",
        [
            "RESEARCH EXPERIENCE",
            "Health-Related Experience",
            "OTHER WORK EXPERIENCE",
            "Clinical Experience",
            "Teaching Experience",
            "Volunteer Experience",
            "EXPERIENCE",
            "Work Experience",
        ],
    )
    def test_qualifier_experience_headers(self, header):
        assert _sniff_header(header) == "experience"

    @pytest.mark.parametrize(
        "line",
        [
            "User Experience Designer",
            "Customer Experience Lead",
        ],
    )
    def test_job_titles_are_not_headers(self, line):
        assert _sniff_header(line) != "experience"


# ── classify_block ───────────────────────────────────────────


class TestClassifyBlock:
    def test_experience_header(self):
        lines = ["WORK EXPERIENCE", "Senior Developer at Corp 2020-2024"]
        assert classify_block(lines) == "experience"

    def test_work_background_header(self):
        lines = ["WORK BACKGROUND", "Acme", "Developer Jan 2020 to Present"]
        assert classify_block(lines) == "experience"

    def test_education_header(self):
        lines = ["EDUCATION", "B.Sc. Computer Science, MIT 2014-2018"]
        assert classify_block(lines) == "education"

    def test_academic_qualifications_header(self):
        lines = ["Academic Qualifications", "B.Tech 2015 Bharat Institute"]
        assert classify_block(lines) == "education"

    def test_skills_header(self):
        lines = ["SKILLS", "Python, Django, PostgreSQL, Docker, AWS"]
        assert classify_block(lines) == "skills"

    def test_empty_lines_returns_other(self):
        assert classify_block([]) == "other"

    def test_projects_header(self):
        lines = ["PROJECTS", "Open Source ML Library", "- 1000 stars on GitHub"]
        assert classify_block(lines) == "projects"

    def test_certifications_header(self):
        lines = ["CERTIFICATIONS", "AWS Solutions Architect 2023"]
        assert classify_block(lines) == "certifications"

    def test_summary_header(self):
        lines = ["SUMMARY", "Experienced developer with 5 years of Python expertise."]
        assert classify_block(lines) == "summary"

    def test_executive_profile_header(self):
        lines = ["Executive Profile", "Machine Learning Engineer skilled in NLP."]
        assert classify_block(lines) == "summary"

    def test_other_activities_header(self):
        lines = ["Other Activities", "AI on the cloud using Google Cloud Platform."]
        assert classify_block(lines) in ("other", "misc")

    def test_content_based_experience(self):
        lines = [
            "Senior Developer at TechCorp",
            "2020 - 2024",
            "- Built REST APIs",
            "- Led team of 5 engineers",
            "- Deployed to AWS",
        ]
        result = classify_block(lines)
        assert result in ("experience", "projects")

    def test_content_based_education(self):
        lines = [
            "Massachusetts Institute of Technology",
            "Bachelor of Science in Computer Science, 2014 - 2018",
            "GPA: 3.8/4.0",
        ]
        assert classify_block(lines) == "education"

    def test_contact_block(self):
        lines = [
            "John Doe",
            "john@example.com",
            "+1 555 123 4567",
            "linkedin.com/in/johndoe",
        ]
        result = classify_block(lines)
        assert result in ("contact", "header", "other")


# ── split_blocks ─────────────────────────────────────────────


class TestSplitBlocks:
    def test_splits_on_blank_lines(self):
        text = "Block 1\nLine 2\n\nBlock 2\nLine 3"
        blocks = split_blocks(text)
        assert len(blocks) >= 2

    def test_empty_text(self):
        assert split_blocks("") == []

    def test_single_block(self):
        blocks = split_blocks("Line 1\nLine 2\nLine 3")
        assert len(blocks) == 1

    def test_header_forces_split(self):
        text = "Some text\nEXPERIENCE\nDeveloper at Corp"
        blocks = split_blocks(text)
        # "EXPERIENCE" header should force a new block
        assert len(blocks) >= 2

    def test_handles_crlf(self):
        text = "Line 1\r\nLine 2\r\n\r\nBlock 2"
        blocks = split_blocks(text)
        assert len(blocks) >= 2


# ── canonicalize_section_key ─────────────────────────────────


class TestCanonicalizeSectionKey:
    def test_standard_keys(self):
        assert canonicalize_section_key("experience") == "experience"
        assert canonicalize_section_key("education") == "education"
        assert canonicalize_section_key("skills") == "skills"

    def test_alias_resolution(self):
        assert canonicalize_section_key("work experience") == "experience"
        assert canonicalize_section_key("professional experience") == "experience"
        assert canonicalize_section_key("work background") == "experience"
        assert canonicalize_section_key("academic qualifications") == "education"
        assert canonicalize_section_key("executive profile") == "summary"

    def test_case_insensitive(self):
        assert canonicalize_section_key("EXPERIENCE") == "experience"
        assert canonicalize_section_key("Education") == "education"

    def test_unknown_key_passthrough(self):
        result = canonicalize_section_key("random_section_xyzzy")
        assert isinstance(result, str)
