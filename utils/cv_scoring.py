"""
CV Scoring Module

This module contains functions for calculating final CV scores based on various
matching criteria including keyword coverage, experience, title match, and seniority.
"""

import re
from typing import Dict, List, Any, Tuple


def calculate_final_score(
    cv_text: str, structured_data: Dict[str, Any], job_description: str
) -> Tuple[float, float, Dict[str, Any]]:
    """
    Calculate the final match score for a CV based on multiple weighted factors.

    Args:
        cv_text: Raw CV text content
        structured_data: Extracted structured data from CV
        job_description: Job description text

    Returns:
        Tuple of (final_score, ats_score, details_dict)
    """
    # Extract basic info
    skills = structured_data.get("skills", [])
    experience_years = structured_data.get("experience_years", 0)
    education_level = structured_data.get("education_level", "unknown")

    # Keyword analysis
    keyword_results = _analyze_keywords(cv_text, job_description)
    keyword_coverage_pct = keyword_results["coverage_pct"]

    # Experience scoring
    experience_score = _calculate_experience_score(experience_years, job_description)

    # Title matching
    title_match = _calculate_title_match(cv_text, job_description)

    # Seniority matching
    seniority_match = _calculate_seniority_match(cv_text, job_description)

    # ATS score (formatting and structure)
    ats_score = _calculate_ats_score(cv_text, structured_data)

    # Calculate final weighted score
    # Weights: keyword (35%), experience (30%), title (15%), seniority (10%), ATS (10%)
    final_score = (
        keyword_coverage_pct * 0.35
        + experience_score * 0.30
        + title_match * 0.15
        + seniority_match * 0.10
        + ats_score * 0.10
    )

    # Ensure score is between 0-100
    final_score = max(0.0, min(100.0, final_score))

    details = {
        "keyword_coverage_pct": round(keyword_coverage_pct, 2),
        "experience_score": round(experience_score, 2),
        "title_match": round(title_match, 2),
        "seniority_match": round(seniority_match, 2),
        "ats_score": round(ats_score, 2),
        "skills_found": skills,
        "experience_years": experience_years,
        "education_level": education_level,
        "missing_skills": keyword_results.get("missing_keywords", []),
        "strong_keywords": keyword_results.get("strong_keywords", []),
        "weak_keywords": keyword_results.get("weak_keywords", []),
        "weak_signals": _identify_weak_signals(keyword_coverage_pct, experience_score, title_match, seniority_match),
    }

    return round(final_score, 2), round(ats_score, 2), details


def _analyze_keywords(cv_text: str, job_description: str) -> Dict[str, Any]:
    """Analyze keyword coverage between CV and job description"""
    # Extract keywords from job description
    jd_text = job_description.lower()

    # Common tech keywords to look for
    tech_keywords = {
        "python",
        "javascript",
        "java",
        "c++",
        "c#",
        "ruby",
        "php",
        "go",
        "rust",
        "react",
        "angular",
        "vue",
        "django",
        "flask",
        "spring",
        "node.js",
        "express",
        "sql",
        "mysql",
        "postgresql",
        "mongodb",
        "redis",
        "elasticsearch",
        "aws",
        "azure",
        "gcp",
        "docker",
        "kubernetes",
        "jenkins",
        "git",
        "machine learning",
        "ai",
        "data science",
        "tensorflow",
        "pytorch",
        "agile",
        "scrum",
        "ci/cd",
        "devops",
        "microservices",
    }

    # Extract keywords that appear in job description
    jd_keywords = set()
    cv_lower = cv_text.lower()

    for keyword in tech_keywords:
        if keyword in jd_text:
            jd_keywords.add(keyword)

    if not jd_keywords:
        # Fallback: extract some basic keywords from JD
        jd_words = set(re.findall(r"\b[a-z]{3,}\b", jd_text))
        jd_keywords = jd_words & tech_keywords

    # Calculate coverage
    found_keywords = set()
    missing_keywords = set()

    for keyword in jd_keywords:
        if keyword in cv_lower:
            found_keywords.add(keyword)
        else:
            missing_keywords.add(keyword)

    coverage_pct = (len(found_keywords) / max(len(jd_keywords), 1)) * 100

    return {
        "coverage_pct": coverage_pct,
        "found_keywords": list(found_keywords),
        "missing_keywords": list(missing_keywords),
        "strong_keywords": list(found_keywords)[:5],  # Top 5 found
        "weak_keywords": list(missing_keywords)[:5],  # Top 5 missing
    }


def _calculate_experience_score(experience_years: int, job_description: str) -> float:
    """Calculate experience score based on years and job requirements"""
    # Extract required experience from job description
    exp_patterns = [
        r"(\d+)\+?\s*years?\s+(?:of\s+)?experience",
        r"(\d+)\+?\s*years?\s+(?:of\s+)?(?:python|development|engineering)",
        r"experience.*?(\d+)\+?\s*years",
    ]

    required_years = 0
    for pattern in exp_patterns:
        match = re.search(pattern, job_description, re.IGNORECASE)
        if match:
            required_years = int(match.group(1))
            break

    if required_years == 0:
        required_years = 3  # Default assumption

    # Score based on experience level
    if experience_years >= required_years + 3:
        return 100.0  # Overqualified
    elif experience_years >= required_years:
        return 90.0  # Meets requirements
    elif experience_years >= required_years - 1:
        return 70.0  # Close to requirements
    elif experience_years >= required_years - 2:
        return 50.0  # Some experience
    else:
        return 30.0  # Limited experience


def _calculate_title_match(cv_text: str, job_description: str) -> float:
    """Calculate title match score"""
    # Extract job title from JD
    title_patterns = [
        r"(?:position|role|job).*?[:\-]?\s*(.+?)(?:\n|$)",
        r"(?:hiring|looking for|seeking).*?([A-Za-z][A-Za-z0-9\s\-]{3,30})",
        r"^(.{10,50})$",  # First line if it's a title
    ]

    job_title = ""
    jd_lines = job_description.strip().split("\n")[:3]  # First few lines

    for line in jd_lines:
        line = line.strip()
        if len(line) > 5 and len(line) < 50:
            job_title = line
            break

    if not job_title:
        return 50.0  # Neutral score if no title found

    # Check if title appears in CV
    cv_lower = cv_text.lower()
    title_lower = job_title.lower()

    if title_lower in cv_lower:
        return 100.0

    # Check for partial matches
    title_words = set(title_lower.split())
    cv_words = set(cv_lower.split())

    overlap = len(title_words & cv_words)
    if overlap > 0:
        return min(80.0, (overlap / len(title_words)) * 100)

    return 30.0  # Low match


def _calculate_seniority_match(cv_text: str, job_description: str) -> float:
    """Calculate seniority level match"""
    seniority_levels = {
        "senior": ["senior", "lead", "principal", "staff", "architect"],
        "mid": ["mid", "intermediate", "regular", "experienced"],
        "junior": ["junior", "entry", "associate", "graduate"],
        "intern": ["intern", "trainee", "apprentice"],
    }

    # Determine required seniority from JD
    jd_lower = job_description.lower()
    required_level = "mid"  # default

    for level, keywords in seniority_levels.items():
        if any(kw in jd_lower for kw in keywords):
            required_level = level
            break

    # Determine CV seniority
    cv_lower = cv_text.lower()
    cv_level = "mid"  # default

    for level, keywords in seniority_levels.items():
        if any(kw in cv_lower for kw in keywords):
            cv_level = level
            break

    # Calculate match score
    level_order = ["intern", "junior", "mid", "senior"]
    try:
        req_idx = level_order.index(required_level)
        cv_idx = level_order.index(cv_level)

        diff = abs(req_idx - cv_idx)
        if diff == 0:
            return 100.0  # Perfect match
        elif diff == 1:
            return 75.0  # Close match
        else:
            return 50.0  # Significant mismatch
    except ValueError:
        return 60.0  # Default neutral


def _calculate_ats_score(cv_text: str, structured_data: Dict[str, Any]) -> float:
    """Calculate ATS compatibility score based on formatting and structure"""
    score = 50.0  # Base score

    # Check for contact information
    contact_indicators = ["email", "phone", "@", "+", "linkedin", "github"]
    contact_found = any(indicator in cv_text.lower() for indicator in contact_indicators)
    if contact_found:
        score += 10

    # Check for skills section
    if "skills" in cv_text.lower() or len(structured_data.get("skills", [])) > 0:
        score += 10

    # Check for experience section
    if "experience" in cv_text.lower():
        score += 10

    # Check for education section
    if "education" in cv_text.lower():
        score += 10

    # Check for bullet points (common in ATS-friendly CVs)
    if "•" in cv_text or "-" in cv_text:
        score += 5

    # Length check (not too short, not too long)
    word_count = len(cv_text.split())
    if 200 <= word_count <= 1000:
        score += 5

    return min(100.0, score)


def _identify_weak_signals(
    keyword_pct: float, exp_score: float, title_match: float, seniority_match: float
) -> List[str]:
    """Identify weak signals in the CV evaluation"""
    signals = []

    if keyword_pct < 50:
        signals.append("Low keyword coverage")
    if exp_score < 60:
        signals.append("Experience evidence is weak")
    if title_match < 60:
        signals.append("Title alignment is weak")
    if seniority_match < 60:
        signals.append("Seniority mismatch")

    return signals
