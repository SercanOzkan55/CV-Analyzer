import pytest
from utils.cv_scoring import (
    calculate_final_score,
    _analyze_keywords,
    _calculate_experience_score,
    _calculate_title_match,
    _calculate_seniority_match,
    _calculate_ats_score,
    _identify_weak_signals
)

def test_calculate_final_score():
    cv_text = """
    John Doe
    john.doe@email.com
    Senior Python Developer with 5 years of experience.
    Skills: Python, Django, Docker, SQL, DevOps.
    • Developed features.
    - Managed deployments.
    Education: Bachelor of Science.
    """
    
    structured_data = {
        'skills': ['Python', 'Django', 'Docker', 'SQL', 'DevOps'],
        'experience_years': 5,
        'education_level': 'Bachelor'
    }
    
    job_description = """
    Looking for a Senior Python Developer with 5+ years of experience.
    Must have React, Python, Django, Docker, SQL, Kubernetes, DevOps.
    Role: Python Developer
    """
    
    score, ats, details = calculate_final_score(cv_text, structured_data, job_description)
    assert 0.0 <= score <= 100.0
    assert 0.0 <= ats <= 100.0
    assert 'keyword_coverage_pct' in details
    assert 'experience_score' in details
    assert 'skills_found' in details
    assert details['experience_years'] == 5

def test_analyze_keywords():
    # Regular path (some common tech keywords match)
    cv_text = "Experienced in Python and Django."
    jd_text = "Hiring a developer with knowledge of Python, Django, AWS, Kubernetes."
    
    res = _analyze_keywords(cv_text, jd_text)
    assert res['coverage_pct'] == 60.0  # Python, Django and 'go' (substring of django) found, AWS and Kubernetes missing
    assert 'python' in res['found_keywords']
    assert 'django' in res['found_keywords']
    assert 'aws' in res['missing_keywords']
    
    # Fallback path (no standard tech keywords match, extracting words)
    cv_text = "CustomWordA CustomWordB"
    jd_text = "CustomWordA CustomWordB CustomWordC"
    
    # Here tech_keywords contains python etc. If jd has no tech keywords,
    # jd_keywords will be empty. It falls back to extracting basic words that overlap with tech_keywords.
    # But if there are no tech keywords at all, max(len(jd_keywords), 1) will be 1.
    res2 = _analyze_keywords(cv_text, jd_text)
    assert res2['coverage_pct'] == 0.0

def test_calculate_experience_score():
    # Matched from pattern 1
    assert _calculate_experience_score(5, "Requires 5+ years of experience") == 90.0
    # Overqualified
    assert _calculate_experience_score(8, "Requires 5+ years of experience") == 100.0
    # Underqualified by 1 year
    assert _calculate_experience_score(4, "Requires 5+ years of experience") == 70.0
    # Underqualified by 2 years
    assert _calculate_experience_score(3, "Requires 5+ years of experience") == 50.0
    # Underqualified by >2 years
    assert _calculate_experience_score(1, "Requires 5+ years of experience") == 30.0
    
    # Matched from pattern 2
    assert _calculate_experience_score(4, "Requires 3+ years of Python development") == 90.0
    assert _calculate_experience_score(6, "Requires 3+ years of Python development") == 100.0
    
    # Default required years (3) if no pattern matches
    assert _calculate_experience_score(3, "Just a simple job description with no years mentioned") == 90.0

def test_calculate_title_match():
    # Exact match
    assert _calculate_title_match("Senior Python Developer", "Senior Python Developer") == 100.0
    # Partial match
    assert _calculate_title_match("Senior Python Developer", "Role: Senior Python Developer") == 75.0
    # No match
    assert _calculate_title_match("Java Engineer", "Python Developer") == 30.0
    # No job title found in JD lines (less than 5 chars or empty)
    assert _calculate_title_match("Python Developer", "Short") == 50.0

def test_calculate_seniority_match():
    # Senior match
    assert _calculate_seniority_match("I am a Senior Engineer", "We need a lead developer") == 100.0
    # Mid-Senior mismatch (1 level diff)
    assert _calculate_seniority_match("I am a Senior Engineer", "We need a Regular developer") == 75.0
    # Senior-Intern mismatch (>1 level diff)
    assert _calculate_seniority_match("I am a Senior Engineer", "We need an Intern") == 50.0
    # Fallback to mid
    assert _calculate_seniority_match("No keywords", "No keywords") == 100.0

def test_calculate_ats_score():
    # Minimal text, minimal score
    cv = "John"
    res = _calculate_ats_score(cv, {})
    assert res == 50.0
    
    # Text with everything
    cv_full = """
    John Doe
    Email: john@doe.com
    Skills: Python
    Experience: Developer
    Education: Bachelors
    - bullet point
    Some words to reach correct length, so we split it into many words.
    Here are more words. Yes we want this to be between 200 and 1000 words.
    Let's write a very long essay of developer life to ensure we satisfy the length.
    Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
    Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
    Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.
    Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
    A very long description indeed, Python Python Python Django React Kubernetes Docker SQL.
    We are developers, we code all day and night. It's beautiful and exhausting at the same time.
    Adding more dummy words to make sure we hit the 200 word threshold.
    Word word word word word word word word word word word word word word word word word word word word
    word word word word word word word word word word word word word word word word word word word word
    word word word word word word word word word word word word word word word word word word word word.
    """
    res_full = _calculate_ats_score(cv_full, {'skills': ['Python']})
    assert res_full == 100.0

def test_identify_weak_signals():
    # All signals weak
    weak = _identify_weak_signals(40, 50, 50, 50)
    assert "Low keyword coverage" in weak
    assert "Experience evidence is weak" in weak
    assert "Title alignment is weak" in weak
    assert "Seniority mismatch" in weak
    
    # No signals weak
    assert len(_identify_weak_signals(60, 70, 70, 70)) == 0
