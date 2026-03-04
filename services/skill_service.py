import re

# Global skill dictionary
SKILLS = {
    "python", "java", "c#", "javascript", "typescript",
    "sql", "postgresql", "mysql",
    "docker", "kubernetes",
    "aws", "azure", "gcp",
    "react", "angular", "vue",
    "fastapi", "django", "flask",
    "machine learning", "tensorflow", "pytorch",
    "git", "linux"
}

def extract_skills(text: str):
    text = text.lower()
    found_skills = set()

    for skill in SKILLS:
        if skill in text:
            found_skills.add(skill)

    return found_skills


def skill_coverage_score(cv_text: str, job_text: str):
    cv_skills = extract_skills(cv_text)
    job_skills = extract_skills(job_text)

    if not job_skills:
        return 0.0, []

    matched = cv_skills.intersection(job_skills)
    coverage = (len(matched) / len(job_skills)) * 100

    missing = list(job_skills - cv_skills)

    return round(coverage, 2), missing