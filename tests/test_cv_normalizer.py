import pytest
from utils.cv_normalizer import (
    sanitize_experience_entries,
    guess_name,
    filter_language_codes,
    redistribute_misc,
    create_education_from_text,
    ensure_name,
    _has_job_signal,
    _extract_institution_name,
    _maybe_set_location,
    _route_contact_line,
    _looks_like_name
)

def test_sanitize_experience_entries_basic():
    data = {}
    experiences = [
        {
            "title": "Software Engineer",
            "company": "Tech Corp",
            "location": "New York",
            "start_date": "2020",
            "end_date": "2023",
            "bullets": ["Developed features", "Fixed bugs"],
            "invalid_key": "should_be_removed"
        }
    ]
    cleaned = sanitize_experience_entries(experiences, data)
    assert len(cleaned) == 1
    assert "invalid_key" not in cleaned[0]
    assert cleaned[0]["title"] == "Software Engineer"


def test_sanitize_experience_entries_contact_routing():
    data = {}
    experiences = [
        {
            "title": "Software Engineer test@example.com",
            "company": "Tech Corp +1234567890",
            "bullets": [
                "Email: bullet@example.com",
                "Phone: +0987654321",
                "Regular bullet point"
            ]
        }
    ]
    cleaned = sanitize_experience_entries(experiences, data)
    assert data["email"] == "test@example.com"
    assert data["phone"] == "+1234567890"
    
    assert cleaned[0]["title"] == "Software Engineer"
    assert cleaned[0]["company"] == "Tech Corp"
    assert "Regular bullet point" in cleaned[0]["bullets"]


def test_sanitize_experience_entries_education_routing():
    data = {}
    experiences = [
        {
            "title": "BSc Computer Science",
            "company": "Harvard University",
            "start_date": "2015",
            "end_date": "2019",
            "bullets": []
        }
    ]
    cleaned = sanitize_experience_entries(experiences, data)
    assert len(cleaned) == 0  # Entry should be moved to education
    assert len(data["education"]) == 1
    assert "Harvard" in data["education"][0]["school"]
    assert "BSc" in data["education"][0]["degree"]


def test_guess_name():
    lines = [
        "Resume",
        "John Doe",
        "Software Engineer",
        "john@example.com"
    ]
    assert guess_name(lines) == "John Doe"

    assert guess_name(["12345", "http://example.com", "NOT A NAME"]) is None


def test_looks_like_name():
    assert _looks_like_name("Jane Smith") is True
    assert _looks_like_name("Jean-Luc Picard") is True
    assert _looks_like_name("Software Engineer") is False
    assert _looks_like_name("JANE SMITH") is False
    assert _looks_like_name("Jane") is False


def test_ensure_name():
    data = {
        "header_lines": ["Resume", "Alice Bob", "Developer"],
        "email": "alice@example.com"
    }
    ensure_name(data)
    assert data.get("full_name") == "Alice Bob"


def test_filter_language_codes():
    langs = [
        "English (Native)",
        "tr",
        "fr",
        "Spanish - B2",
        "123",
        "http://example.com",
        "Python" # Tech name should be skipped
    ]
    filtered = filter_language_codes(langs)
    # tr, fr, 123, http... should be filtered out
    # Python might be structurally rejected if strict is True, but filter_language_codes uses strict=False
    # Let's just check the positive ones
    assert "English (Native)" in filtered
    assert "Spanish - B2" in filtered
    assert "tr" not in filtered
    assert "123" not in filtered


def test_redistribute_misc():
    data = {
        "misc": [
            "BSc Computer Science at Massachusetts Institute of Technology 2020",
            "AWS Certified Developer",
            "Python, Java, C++, SQL",
            "Software Engineer at Google 2021-2023",
            "Built a web app using React and Node.js",
            "Reading, Traveling, Chess",
            "Just a random long string that should probably stay in misc because it does not match any known pattern exactly."
        ]
    }
    redistribute_misc(data)
    
    # Check that they were moved
    assert len(data.get("education", [])) >= 1
    assert "Massachusetts Institute of Technology" in data["education"][0]["school"]
    
    assert len(data.get("certifications", [])) >= 1
    assert "AWS Certified Developer" in data["certifications"][0]["name"]
    
    assert len(data.get("skills", [])) >= 1
    assert any("Python" in s for s in data["skills"])
    
    assert len(data.get("experiences", [])) >= 1
    assert "Software Engineer" in data["experiences"][0]["title"]
    
    assert len(data.get("interests", [])) >= 1
    assert any("Chess" in s for s in data["interests"])

def test_create_education_from_text():
    data = {
        "summary": "Graduated with a BSc from Stanford University in 2021.",
        "misc": ["PhD from Massachusetts Institute in 2023", "Graduated with a BSc from Stanford University in 2021."],
        "skills": ["Master from Harvard College in 2018", 123],
        "certifications": ["Associate from Yale School in 2019", {"name": "Diploma from Oxford Academy in 2020"}, 456],
        "interests": ["Bachelor from Princeton Faculty in 2017", 789],
        "education": []
    }
    create_education_from_text(data)
    assert len(data["education"]) > 1
    schools = [e["school"] for e in data["education"] if isinstance(e, dict)]
    assert any("Stanford" in s for s in schools)
    assert any("Harvard" in s for s in schools)
    assert any("Yale" in s for s in schools)
    assert any("Oxford" in s for s in schools)
    assert any("Princeton" in s for s in schools)


def test_has_job_signal():
    assert _has_job_signal("Software Engineer") is True
    assert _has_job_signal("Director of Sales") is True
    assert _has_job_signal("Student") is False
    assert _has_job_signal("BSc Computer Science") is False


def test_extract_institution_name():
    assert "Stanford University" in _extract_institution_name("Graduated from Stanford University with honors")
    assert _extract_institution_name("MIT") == ""  # Does not have university/institute keyword


def test_maybe_set_location():
    data = {}
    _maybe_set_location("Address: 123 Main St, New York, NY", data)
    assert data["location"] == "123 Main St, New York, NY"
    
    # Should not overwrite
    _maybe_set_location("Address: 456 Other St", data)
    assert data["location"] == "123 Main St, New York, NY"


def test_route_contact_line():
    data = {}
    _route_contact_line("Email: foo@bar.com", data)
    assert data["email"] == "foo@bar.com"
    
    _route_contact_line("Phone: +1-555-0198", data)
    assert data["phone"] == "+1-555-0198"

def test_normalize_urls():
    from utils.cv_normalizer import normalize_urls
    data = {
        "summary": "Check out https: google.com or http: github.com",
        "nested": {
            "url": "https: microsoft.com",
            "overlong": "https://example.com/" + "a" * 600
        },
        "list_urls": ["http: yahoo.com", {"deep": "https: netflix.com"}]
    }
    normalize_urls(data)
    assert data["summary"] == "Check out https://google.com or http://github.com"
    assert data["nested"]["url"] == "https://microsoft.com"
    assert len(data["nested"]["overlong"]) == 500  # Truncated
    assert data["list_urls"][0] == "http://yahoo.com"
    assert data["list_urls"][1]["deep"] == "https://netflix.com"

def test_ensure_summary_misc():
    from utils.cv_normalizer import ensure_summary
    data = {
        "summary": "",
        "misc": [
            "This is a very long prose item that should be promoted to summary because it has more than fifteen words in it.",
            "Short one"
        ]
    }
    ensure_summary(data)
    assert "promoted to summary" in data["summary"]
    assert len(data["misc"]) == 1

def test_ensure_summary_experience():
    from utils.cv_normalizer import ensure_summary
    data = {
        "summary": "",
        "experiences": [
            {
                "bullets": [
                    "This is a long bullet from experience section with more than twenty words which should qualify as a summary. Extra words."
                ]
            }
        ]
    }
    ensure_summary(data)
    assert "long bullet from experience" in data["summary"]

def test_strip_contact_from_education():
    from utils.cv_normalizer import strip_contact_from_education
    data = {
        "email": "",
        "phone": "",
        "education": [
            {
                "degree": "BSc in CS contact@edu.com",
                "school": "Stanford +123456789",
                "field": "CS",
                "location": "CA"
            }
        ]
    }
    strip_contact_from_education(data)
    assert data["email"] == "contact@edu.com"
    assert data["phone"] == "+123456789"
    assert data["education"][0]["degree"] == "BSc in CS"
    assert data["education"][0]["school"] == "Stanford"

def test_strip_contact_from_all_sections():
    from utils.cv_normalizer import strip_contact_from_all_sections
    data = {
        "email": "",
        "phone": "",
        "projects": [
            {
                "name": "Project contact@proj.com",
                "description": "Desc +987654321",
                "bullets": ["Bullet contact@proj.com", "Bullet 2"]
            }
        ],
        "certifications": [
            {
                "name": "Cert contact@cert.com",
                "issuer": "Issuer +1122334455",
                "date": "2020"
            }
        ],
        "skills": ["Python contact@skills.com", "Go"],
        "interests": ["Chess contact@interests.com"],
        "languages": ["English contact@langs.com"]
    }
    strip_contact_from_all_sections(data)
    assert data["email"] in ("contact@proj.com", "contact@cert.com", "contact@skills.com", "contact@interests.com", "contact@langs.com")
    assert data["projects"][0]["name"] == "Project"
    assert data["projects"][0]["description"] == "Desc"
    assert data["projects"][0]["bullets"] == ["Bullet", "Bullet 2"]
    assert data["certifications"][0]["name"] == "Cert"
    assert data["certifications"][0]["issuer"] == "Issuer"
    assert "Python" in data["skills"]
    assert "Chess" in data["interests"]

def test_rescore_experience_entries():
    from utils.cv_normalizer import rescore_experience_entries
    data = {
        "section_titles": {},
        "experiences": [
            "Not a dict entry",
            {
                "title": "BSc Computer Science",
                "company": "Stanford University",
                "start_date": "2015",
                "end_date": "2019"
            },
            {
                "title": "Contact info at email@domain.com phone +1234567890",
            }
        ]
    }
    rescore_experience_entries(data)
    assert len(data["experiences"]) == 1
    assert len(data["education"]) == 1
    assert data["education"][0]["school"] == "Stanford University"
    assert data["email"] == "email@domain.com"

def test_validate_section_placement():
    from utils.cv_normalizer import validate_section_placement
    data = {
        "section_titles": {},
        "education": [
            "Not a dict in edu",
            {
                "degree": "Software Engineer",
                "school": "Google Inc",
                "company": "Google Inc",
                "start_date": "2020",
                "end_date": "2022",
                "bullets": ["Developed backend features in Python", "Fixed scaling issues"]
            }
        ],
        "skills": ["Spanish - Native", "Chess", 123, ""],
        "interests": "Not a list"
    }
    validate_section_placement(data)
    assert len(data["education"]) == 1
    assert len(data["experiences"]) == 1
    assert data["experiences"][0]["title"] == "Software Engineer"
    assert "Spanish - Native" in data["languages"]
    assert "Chess" in data["interests"]

def test_apply_normalization_rules():
    from utils.cv_normalizer import apply_normalization_rules
    data = {
        "header_lines": ["Alice Smith", "alice@example.com"],
        "email": "",
        "phone": "",
        "experiences": [
            {
                "title": "Developer contact@dev.com",
                "company": "Tech Corp +1234567890",
                "bullets": ["Bullet 1"]
            }
        ],
        "education": [
            {
                "degree": "BSc +5556667777",
                "school": "Stanford"
            }
        ]
    }
    apply_normalization_rules(data)
    assert data["full_name"] == "Alice Smith"
    assert data["email"] in ("alice@example.com", "contact@dev.com")
    assert data["experiences"][0]["title"] == "Developer"
    assert data["experiences"][0]["company"] == "Tech Corp"

