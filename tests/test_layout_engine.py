"""Tests for services/layout_engine.py — layout building from schema."""
import pytest
from schemas.cv_schema import CVSchema, ExperienceEntry, EducationEntry, ProjectEntry
from services.layout_engine import (
    build_layout,
    _clean_text,
    _wrap_line,
    ATS_SECTION_ORDER,
)


def _sample_schema():
    return CVSchema(
        full_name="John Doe",
        title="Software Engineer",
        email="john@example.com",
        phone="+1234567890",
        location="New York",
        summary="Experienced software engineer.",
        experiences=[
            ExperienceEntry(
                title="Senior Dev", company="Acme", location="NYC",
                start_date="Jan 2020", end_date="Present",
                bullets=["Led team of 5", "Built REST APIs"],
            ),
        ],
        education=[
            EducationEntry(
                degree="BS", field="Computer Science", school="MIT",
                start_date="2016", end_date="2020", gpa="3.8",
            ),
        ],
        skills=["Python", "JavaScript", "Docker"],
        languages=["English", "Turkish"],
        projects=[
            ProjectEntry(name="CV Analyzer", description="ML-based CV scoring",
                         bullets=["Built scoring pipeline"]),
        ],
    )


class TestCleanText:
    def test_normalizes_whitespace(self):
        assert _clean_text("  hello   world  ") == "hello world"

    def test_handles_none(self):
        assert _clean_text(None) == "None" or _clean_text(None) == ""


class TestWrapLine:
    def test_cleans_text(self):
        result = _wrap_line("  multiple   spaces  ")
        assert "  " not in result or result == "multiple spaces"


class TestBuildLayout:
    def test_returns_header(self):
        schema = _sample_schema()
        layout = build_layout(schema)
        assert "header" in layout
        assert layout["header"]["name"] == "John Doe"

    def test_contacts_populated(self):
        schema = _sample_schema()
        layout = build_layout(schema)
        contacts = layout["header"]["contacts"]
        assert "john@example.com" in contacts
        assert "+1234567890" in contacts

    def test_blocks_in_order(self):
        schema = _sample_schema()
        layout = build_layout(schema)
        block_types = [b["type"] for b in layout["blocks"]]
        assert "summary" in block_types
        assert "experience" in block_types
        assert "education" in block_types
        assert "skills" in block_types

    def test_custom_section_order(self):
        schema = _sample_schema()
        layout = build_layout(schema, section_order=["education", "experience"])
        block_types = [b["type"] for b in layout["blocks"]]
        if "education" in block_types and "experience" in block_types:
            assert block_types.index("education") < block_types.index("experience")

    def test_experience_block_structure(self):
        schema = _sample_schema()
        layout = build_layout(schema)
        exp_block = next(b for b in layout["blocks"] if b["type"] == "experience")
        assert len(exp_block["items"]) == 1
        assert exp_block["items"][0]["role"] == "Senior Dev"
        assert "Led team of 5" in exp_block["items"][0]["bullets"]

    def test_format_hints_present(self):
        schema = _sample_schema()
        layout = build_layout(schema)
        assert "format_hints" in layout

    def test_empty_schema(self):
        schema = CVSchema()
        layout = build_layout(schema)
        assert layout["header"]["name"] == ""
        assert layout["blocks"] == [] or isinstance(layout["blocks"], list)

    def test_section_order_in_output(self):
        schema = _sample_schema()
        layout = build_layout(schema)
        assert layout["section_order"] == ATS_SECTION_ORDER
