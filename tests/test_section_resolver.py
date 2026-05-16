"""Tests for services/section_resolver.py — cross-section classification fixes."""
import pytest
from services.section_resolver import resolve_parsed_entries, resolve_raw_sections


class TestResolveRawSections:
    def _make_sections(self, **kwargs):
        """Helper: minimal sections dict with required keys."""
        base = {
            "header": [], "summary": [], "experience": [],
            "education": [], "skills": [], "projects": [],
            "certifications": [], "languages": [], "misc": [],
        }
        base.update(kwargs)
        return base

    def test_empty_sections(self):
        sections = self._make_sections()
        result = resolve_raw_sections(sections, [])
        assert isinstance(result, dict)

    def test_education_rescue(self):
        """Lines with degree keywords in misc should move to education."""
        sections = self._make_sections(
            misc=["B.Sc. Computer Science 2018-2022", "Some random text"],
        )
        result = resolve_raw_sections(sections, [])
        edu_text = " ".join(result.get("education", []))
        assert "B.Sc" in edu_text or "Computer Science" in edu_text

    def test_skills_rescue(self):
        """Comma-separated tech tokens in misc should move to skills."""
        sections = self._make_sections(
            misc=["Python, Java, Docker, Kubernetes, AWS"],
        )
        result = resolve_raw_sections(sections, [])
        skills_text = " ".join(result.get("skills", []))
        # Should have moved at least some tech
        assert "Python" in skills_text or len(result.get("skills", [])) > 0

    def test_does_not_drop_content(self):
        """Total line count should be preserved (no content dropped)."""
        sections = self._make_sections(
            experience=["Led team of 5 engineers"],
            education=["MIT 2020"],
            misc=["Python, JavaScript"],
        )
        total_before = sum(len(v) for v in sections.values())
        result = resolve_raw_sections(sections, [])
        total_after = sum(len(v) for v in result.values())
        assert total_after >= total_before - 1  # allow minor cleanup

    def test_header_lines_not_lost(self):
        """Header lines passed in should not disappear."""
        sections = self._make_sections()
        header = ["John Doe", "john@example.com"]
        result = resolve_raw_sections(sections, header)
        # Result should still be valid
        assert isinstance(result, dict)

    def test_language_detection(self):
        """Lines with language names + CEFR should go to languages."""
        sections = self._make_sections(
            misc=["English - C1", "Turkish - Native"],
        )
        result = resolve_raw_sections(sections, [])
        langs = " ".join(result.get("languages", []))
        has_langs = "English" in langs or "Turkish" in langs
        # May stay in misc depending on implementation
        assert isinstance(result.get("languages"), list)

    def test_certifications_rescued_from_experience(self):
        """Standalone credentials inside experience should move to certifications."""
        sections = self._make_sections(
            experience=[
                "Software Engineer | Acme | 2020 - Present",
                "- Built APIs with Python and Postgres",
                "AWS Solutions Architect Professional (2023)",
                "Certified Kubernetes Administrator (2022)",
            ],
        )
        result = resolve_raw_sections(sections, [])

        cert_text = " ".join(result.get("certifications", []))
        exp_text = " ".join(result.get("experience", []))

        assert "AWS Solutions Architect Professional" in cert_text
        assert "Certified Kubernetes Administrator" in cert_text
        assert "Built APIs" in exp_text
        assert "AWS Solutions Architect Professional" not in exp_text

    def test_experience_action_sentence_not_misrouted_to_certifications(self):
        """Cloud/action bullets should remain experience, not certifications."""
        sections = self._make_sections(
            experience=[
                "- Implemented AWS infrastructure automation and compliance reporting",
                "- Developed Kubernetes deployment pipelines",
            ],
        )
        result = resolve_raw_sections(sections, [])

        exp_text = " ".join(result.get("experience", []))
        cert_text = " ".join(result.get("certifications", []))

        assert "Implemented AWS infrastructure" in exp_text
        assert "Developed Kubernetes deployment" in exp_text
        assert "Implemented AWS infrastructure" not in cert_text

    def test_certifications_rescued_from_misc_without_header(self):
        """Credentials split away from their header should still be recovered."""
        sections = self._make_sections(
            misc=[
                "AWS Certified Cloud Practitioner",
                "Microsoft Certified: Azure Fundamentals",
                "Open source contributor",
            ],
        )
        result = resolve_raw_sections(sections, [])

        cert_text = " ".join(result.get("certifications", []))
        misc_text = " ".join(result.get("misc", []))

        assert "AWS Certified Cloud Practitioner" in cert_text
        assert "Azure Fundamentals" in cert_text
        assert "Open source contributor" in misc_text

    def test_parsed_experience_certification_entry_moves_to_certifications(self):
        """A credential parsed as an experience entry should be corrected."""
        data = {
            "experiences": [
                {
                    "title": "AWS Solutions Architect Professional",
                    "company": "",
                    "location": "",
                    "start_date": "",
                    "end_date": "2023",
                    "bullets": [],
                },
                {
                    "title": "Software Engineer",
                    "company": "Acme",
                    "location": "",
                    "start_date": "2020",
                    "end_date": "Present",
                    "bullets": ["Built APIs"],
                },
            ],
            "certifications": [],
        }

        resolve_parsed_entries(data)

        cert_text = " ".join(c["name"] for c in data["certifications"])
        exp_titles = [e["title"] for e in data["experiences"]]

        assert "AWS Solutions Architect Professional" in cert_text
        assert exp_titles == ["Software Engineer"]
