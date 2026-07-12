"""Tests for services/schema_builder.py — mapping normalized data to CVSchema."""

import pytest
from services.schema_builder import (
    build_schema,
    _clean,
    _clean_list,
    _clean_bullets,
    _is_language_item,
    _is_valid_language,
    _normalize_spoken_language,
    _strip_bullet_prefix,
    _enforce_summary_rules,
)


class TestClean:
    def test_normalizes_whitespace(self):
        assert _clean("  hello   world  ") == "hello world"

    def test_handles_none(self):
        assert _clean(None) == ""

    def test_unicode_normalization(self):
        # NFC normalization
        result = _clean("café")
        assert "café" in result or "cafe" in result


class TestCleanList:
    def test_filters_empty(self):
        assert _clean_list(["hello", "", " ", "world"]) == ["hello", "world"]

    def test_none_input(self):
        assert _clean_list(None) == []


class TestCleanBullets:
    def test_strips_bullet_markers(self):
        result = _clean_bullets(["- Led team", "• Built API", "* Deployed"])
        assert result[0] == "Led team"
        assert result[1] == "Built API"

    def test_filters_empty(self):
        result = _clean_bullets(["- ", "", "Valid bullet"])
        assert len(result) == 1


class TestStripBulletPrefix:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("● Manufacturing", "Manufacturing"),  # black circle (U+25CF)
            ("○ Languages", "Languages"),  # white circle
            ("◦ Software", "Software"),  # white bullet
            ("▸ Tools", "Tools"),  # triangular marker
            ("• Bullet", "Bullet"),  # standard bullet
            ("- Dash", "Dash"),
            ("No prefix", "No prefix"),
        ],
    )
    def test_strips_common_bullet_glyphs(self, raw, expected):
        assert _strip_bullet_prefix(raw) == expected


class TestNormalizeSpokenLanguage:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Fluent in English", "English (Fluent)"),
            ("Native German", "German (Native)"),
            ("Fluent in spoken Tagalog", "Tagalog (Fluent)"),
            ("English: B2", "English: B2"),  # already structured → unchanged
            ("English (Fluent)", "English (Fluent)"),  # already structured
        ],
    )
    def test_reorders_proficiency_phrases(self, raw, expected):
        assert _normalize_spoken_language(raw) == expected


class TestIsValidLanguage:
    @pytest.mark.parametrize(
        "text",
        [
            "English (Fluent)",
            "Spanish",
            "German (Native)",
            "Tagalog (Fluent)",
            "English: B1+ Speaking",
            "B2",  # bare CEFR code is acceptable inside the languages section
        ],
    )
    def test_accepts_real_languages(self, text):
        assert _is_valid_language(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "animal handling (Proficient)",  # skill phrase, no language name
            "MS Word (Proficient)",
            "Molecular Biology (Advanced)",
            "RELEVANT COURSEWORK",
            "Microsoft Suite (Advanced)",
        ],
    )
    def test_rejects_skill_and_coursework_phrases(self, text):
        assert _is_valid_language(text) is False


class TestIsLanguageItem:
    def test_english_native(self):
        assert _is_language_item("English - Native") is True

    def test_cefr_level(self):
        assert _is_language_item("German B2") is True

    def test_not_language(self):
        assert _is_language_item("Python") is False

    def test_empty(self):
        assert _is_language_item("") is False


class TestEnforceSummaryRules:
    def test_prose_passes(self):
        text = "Experienced software engineer with 10 years of Python development."
        result = _enforce_summary_rules(text)
        assert "Experienced" in result

    def test_empty_returns_empty(self):
        assert _enforce_summary_rules("") == ""

    def test_skill_list_rejected(self):
        text = "Python, Java, Docker, Kubernetes, AWS, React, Node.js"
        result = _enforce_summary_rules(text)
        assert result == ""

    def test_strips_emails(self):
        text = "Great engineer. Contact: john@example.com for details."
        result = _enforce_summary_rules(text)
        assert "john@example.com" not in result


class TestBuildSchema:
    def test_basic_mapping(self):
        normalized = {
            "full_name": "John Doe",
            "title": "Software Engineer",
            "email": "john@example.com",
            "phone": "+1234567890",
            "summary": "Experienced developer.",
            "experience": [
                {
                    "title": "Senior Dev",
                    "company": "Acme Inc",
                    "start_date": "2020",
                    "end_date": "Present",
                    "bullets": ["Led team of 5"],
                },
            ],
            "education": [
                {
                    "degree": "BS",
                    "field": "CS",
                    "school": "MIT",
                    "start_date": "2016",
                    "end_date": "2020",
                },
            ],
            "skills": ["Python", "Docker"],
            "languages": ["English"],
        }
        schema = build_schema(normalized)
        assert schema.full_name == "John Doe"
        assert len(schema.experiences) >= 1
        assert len(schema.education) >= 1

    def test_empty_normalized(self):
        schema = build_schema({})
        assert schema.full_name == ""
        assert schema.experiences == []

    def test_keeps_distinct_degrees_from_same_school_and_period(self):
        normalized = {
            "education": [
                {
                    "school": "Example University",
                    "degree": "B.Sc. in Computer Engineering",
                    "start_date": "2022",
                    "end_date": "Present",
                    "gpa": "3.82 / 4.00",
                },
                {
                    "school": "Example University",
                    "degree": "B.Sc. in Industrial Engineering (Transferred)",
                    "start_date": "2022",
                    "end_date": "Present",
                    "gpa": "3.41 / 4.00",
                },
            ]
        }

        schema = build_schema(normalized)

        assert len(schema.education) == 2
        assert {entry.gpa for entry in schema.education} == {"3.82 / 4.00", "3.41 / 4.00"}

    def test_drops_substanceless_header_entry(self):
        # An ALL-CAPS section header that leaked into experience with no
        # bullets, company, or dates must not become a fake job.
        normalized = {
            "experience": [
                {"title": "Senior Engineer", "company": "Acme", "bullets": ["Shipped X"]},
                {"title": "LEADERSHIP ACTIVITIES", "company": "", "bullets": []},
                {"title": "Sanchez 1", "company": "", "bullets": []},
            ]
        }
        schema = build_schema(normalized)
        titles = [e.title for e in schema.experiences]
        assert "Senior Engineer" in titles
        assert "LEADERSHIP ACTIVITIES" not in titles
        assert "Sanchez 1" not in titles

    def test_keeps_dateless_entry_with_bullets(self):
        # A real role with bullets but no parsed company/date must be kept.
        normalized = {
            "experience": [
                {"title": "Volunteer Tutor", "company": "", "bullets": ["Tutored 10 students"]},
            ]
        }
        schema = build_schema(normalized)
        assert any(e.title == "Volunteer Tutor" for e in schema.experiences)

    def test_recovers_name_when_header_was_tech_stack(self):
        normalized = {
            "full_name": "HTML / CSS",
            "email": "ahmet.kuscu1@hotmail.com",
            "linkedin": "careercenter.example.edu/ahmetkuscu1",
            "summary": (
                "3rd-year Computer Engineering student focused on web development "
                "and full-stack applications with Next.js and database systems."
            ),
            "projects": [
                {
                    "name": "FARM GAME",
                    "description": "Java Developed game mechanics applying object-oriented programming principles.",
                    "bullets": [],
                },
                {
                    "name": "WHO WANTS TO BE A MILLIONAIRE",
                    "description": "C++, Node.js, Next.js | React, Docker, WebSocket, REST API",
                    "bullets": [
                        "Developed a Node.js adapter service to bridge communication between a C++ backend and React frontend."
                    ],
                },
            ],
            "education": [
                {
                    "degree": "Computer Engineer - Bachelor's Degree",
                    "school": "Istanbul Health and Technology University",
                    "start_date": "2022",
                    "end_date": "2027",
                },
                {
                    "degree": "Engineering - year Computer Engineering student",
                    "school": "Istanbul Health and Technology University",
                    "start_date": "2022",
                    "end_date": "2027",
                },
            ],
            "skills": ["SQL", "HTML", "CSS", "JavaScript", "Next.js"],
            "languages": ["Turkish", "English"],
            "raw_text": (
                "Ahmet Bugra Kuscu\n"
                "ahmet.kuscu1@hotmail.com | careercenter.example.edu/ahmetkuscu1\n"
                "PROJECTS\nFARM GAME\nWHO WANTS TO BE A MILLIONAIRE\n"
            ),
        }

        schema = build_schema(normalized)

        assert schema.full_name == "Ahmet Bugra Kuscu"
        assert "careercenter.example.edu" in schema.linkedin
        assert schema.languages == ["Turkish", "English"]
        assert len(schema.education) == 1

    def test_preserves_structured_language_detail(self):
        normalized = {
            "full_name": "Sercan Ozkan",
            "email": "sercan@example.com",
            "summary": "Computer engineering student with backend and real-time systems experience.",
            "skills": ["Java", "Python", "TCP Socket Programming"],
            "languages": [
                {
                    "name": "English",
                    "level": "Speaking: B1, Writing: B2, Reading: B2",
                }
            ],
        }

        schema = build_schema(normalized)

        assert schema.languages == ["English (Speaking: B1, Writing: B2, Reading: B2)"]

    def test_cv21_like_misparsed_sections_are_repaired(self):
        normalized = {
            "full_name": "B.Tech in",
            "email": "ehteshamkhan503@gmail.com",
            "phone": "+919310131659",
            "summary": (
                "Project: Electricity Generation by Windmill & Control with Microcontroller. "
                "Synopsis: This project aimed at detailed study and introduction of Wind Mill technique."
            ),
            "experience": [
                {
                    "title": "Panki Thermal Power Station, Kanpur - Control & Instrumentation.",
                    "company": "Industrial Training Attended",
                    "start_date": "Four Weeks.",
                    "bullets": [
                        "Undertaken detailed training to observe, control and manipulate electrical quantities.",
                        "System). C&I governs the whole functioning & operation power plant.",
                    ],
                }
            ],
            "education": [
                {
                    "degree": "B.Tech in Electrical & Electronics Engineering",
                    "school": "Kanpur Institute Of Technology, Kanpur",
                    "start_date": "2010",
                    "end_date": "2014",
                    "gpa": "80.34% marks",
                },
                {
                    "degree": "12th",
                    "school": "Shah Faiz Public School",
                    "start_date": "2010",
                    "end_date": "2010",
                    "gpa": "71.2% marks",
                },
            ],
            "skills": [
                "Good knowledge of circuit boards, processors & electrical circuits",
                "Strong technical, mathematics and physics skill",
                "Hands on experience on Ms-Office, MS office PowerPoint",
            ],
            "languages": [
                "Good knowledge of circuit boards, processors & electrical circuits",
                "English, Hindi & Urdu",
            ],
            "raw_text": "EHTESHAM KHAN\nehteshamkhan503@gmail.com | +919310131659\n",
        }

        schema = build_schema(normalized)

        assert schema.full_name == "Ehtesham Khan"
        assert any("Electricity Generation" in project.name for project in schema.projects)
        assert schema.languages == ["English, Hindi & Urdu"]
        assert any("circuit boards" in skill for skill in schema.skills)
        assert all("circuit boards" not in lang for lang in schema.languages)
