import pytest
from schemas.cv_model import CVModel, Experience, Education, Project
from utils.cv_text import build_cv_text, extract_structured_data

def test_build_cv_text():
    model = CVModel(
        full_name="John Doe",
        title="Software Engineer",
        summary="A passionate developer.",
        experiences=[
            Experience(
                title="Backend Developer",
                company="Tech Inc",
                bullets=["Built APIs", "Optimized DB"]
            )
        ],
        education=[
            Education(
                degree="BS",
                school="Uni",
                field="CS"
            )
        ],
        projects=[
            Project(
                name="App",
                description="A cool app",
                bullets=["Wrote code"]
            )
        ],
        skills=["Python", "Go"],
        skills_categorized={
            "Languages": ["Python", "Go"]
        },
        languages=["English", "Spanish"]
    )
    
    text = build_cv_text(model)
    assert "John Doe" in text
    assert "Software Engineer" in text
    assert "A passionate developer." in text
    assert "Backend Developer" in text
    assert "Tech Inc" in text
    assert "Built APIs" in text
    assert "BS" in text
    assert "Uni" in text
    assert "CS" in text
    assert "App" in text
    assert "A cool app" in text
    assert "Wrote code" in text
    assert "Python" in text
    assert "Go" in text
    assert "English" in text
    assert "Spanish" in text

def test_extract_structured_data_skills():
    # Test skill matching
    res = extract_structured_data("I know Python, react, postgresql, aws, machine learning, Docker, django and git.")
    assert "Python" in res["skills"]
    assert "React" in res["skills"]
    assert "Postgresql" in res["skills"]
    assert "Aws" in res["skills"]
    assert "Machine Learning" in res["skills"]
    assert "Docker" in res["skills"]
    assert "Django" in res["skills"]
    assert "Git" in res["skills"]

def test_extract_structured_data_experience():
    # Test year pattern 1
    res1 = extract_structured_data("I have 5 years of experience.")
    assert res1["experience_years"] == 5
    
    # Test year pattern 2
    res2 = extract_structured_data("I have 8+ yrs of experience.")
    assert res2["experience_years"] == 8
    
    # Test year pattern 3: date range present
    res3 = extract_structured_data("Experience: 2018 - Present")
    assert res3["experience_years"] == 20 
    
    # Test year pattern 3: date range digit
    res4 = extract_structured_data("Experience: 2015 - 2020")
    assert res4["experience_years"] == 20
    
    # Test exception block (invalid range)
    res_exc = extract_structured_data("Experience: 2026-abcd")
    assert res_exc["experience_years"] == 0

def test_extract_structured_data_education():
    # phd
    res1 = extract_structured_data("Degree: PhD in CS")
    assert res1["education_level"] == 5
    
    # master
    res2 = extract_structured_data("Degree: Master of Science")
    assert res2["education_level"] == 4
    
    # bachelor
    res3 = extract_structured_data("Degree: Bachelor of Science")
    assert res3["education_level"] == 3
    
    # associate
    res4 = extract_structured_data("Degree: Associate Degree")
    assert res4["education_level"] == 2
    
    # none
    res5 = extract_structured_data("Just high school")
    assert res5["education_level"] == 0

def test_extract_structured_data_meta():
    res = extract_structured_data("Contact me at john@example.com or +1234567890. Word count test.")
    assert res["word_count"] == 9
    assert res["has_email"] is True
    assert res["has_phone"] is True
    
    res_no = extract_structured_data("No contact details here.")
    assert res_no["has_email"] is False
    assert res_no["has_phone"] is False
