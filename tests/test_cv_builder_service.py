import pytest
from unittest.mock import patch, MagicMock
from services.cv_builder_service import (
    _compact_for_one_page,
    _normalize_contact_fields,
    _mock_enhance,
    _remap_cv_data,
    generate_docx,
    _estimate_content_size,
    _normalize_link_value,
    _build_header_data
)

def test_compact_for_one_page_strict(monkeypatch):
    monkeypatch.setenv("CV_ONE_PAGE_STRICT", "1")
    cv_data = {
        "summary": "a" * 1000,
        "experiences": [
            {
                "title": "A" * 200,
                "company": "B" * 200,
                "location": "C" * 100,
                "bullets": ["d" * 500]
            }
        ] * 10,
        "languages": ["English", "Turkish"]
    }
    compact = _compact_for_one_page(cv_data)
    
    # Assert truncation
    assert len(compact["summary"]) <= 600
    assert len(compact["experiences"][0]["title"]) <= 90
    assert len(compact["experiences"][0]["bullets"][0]) <= 250
    assert len(compact["languages"]) == 2  # Languages are preserved

def test_compact_for_one_page_non_strict(monkeypatch):
    monkeypatch.setenv("CV_ONE_PAGE_STRICT", "0")
    cv_data = {"summary": "a" * 1000}
    compact = _compact_for_one_page(cv_data)
    assert len(compact["summary"]) == 1000

def test_normalize_contact_fields():
    cv_data = {
        "email": "Email: TEST@example.com",
        "phone": "Tel: +1 (555) 123-4567",
        "linkedin": "linkedin: https://linkedin.com/in/user/",
        "location": "Address: 123 Main St, NY"
    }
    normalized = _normalize_contact_fields(cv_data)
    assert normalized["email"] == "TEST@example.com"
    assert normalized["phone"] == "+1 (555) 123-4567"
    assert normalized["linkedin"] == "https://linkedin.com/in/user/"
    assert normalized["location"] == "123 Main St, NY"

def test_normalize_link_value():
    assert _normalize_link_value("GitHub: https://github.com/user") == "https://github.com/user"
    assert _normalize_link_value("linkedin: www.linkedin.com/in/user/") == "www.linkedin.com/in/user/"
    assert _normalize_link_value("portfolio: myportfolio.com") == "myportfolio.com"

def test_mock_enhance():
    cv_data = {
        "summary": "Test summary",
        "skills": ["Python", "Docker", "PostgreSQL", "React", "UnknownTool"]
    }
    enhanced = _mock_enhance(cv_data, "Job Description", "en")
    assert enhanced["summary"] == "Test summary"
    cats = enhanced["skills_categorized"]
    assert "Python" in cats["Languages"]
    assert "React" in cats["Backend & Frameworks"]
    assert "PostgreSQL" in cats["Databases"]
    assert "Docker" in cats["DevOps & Cloud"]
    assert "UnknownTool" in cats["Tools & Platforms"]

def test_remap_cv_data():
    cv_data = {
        "experience": [{"title": "Dev"}],
        "misc": ["extra info"]
    }
    remapped = _remap_cv_data(cv_data)
    assert "experiences" in remapped
    assert len(remapped["experiences"]) == 1
    assert "misc" in remapped

def test_build_header_data():
    cv_data = {
        "full_name": "John Doe",
        "title": "Software Engineer",
        "location": "New York",
        "email": "john@example.com",
        "phone": "+1234567"
    }
    name, title, loc, contact = _build_header_data(cv_data)
    assert name == "John Doe"
    assert title == "Software Engineer"
    assert loc == "New York"
    assert "john@example.com" in contact
    assert "+1234567" in contact

@patch("docx.Document")
def test_generate_docx(mock_document):
    # Very basic mock testing to increase coverage without real file IO dependencies
    mock_doc = MagicMock()
    mock_document.return_value = mock_doc
    
    cv_data = {
        "full_name": "Test User",
        "experiences": [
            {"title": "Dev", "company": "Test", "bullets": ["A", "B"]}
        ]
    }
    result = generate_docx(cv_data, template="modern")
    
    # Just checking it returns a BytesIO and attempts to add paragraphs
    assert result is not None
    assert mock_doc.add_paragraph.called
