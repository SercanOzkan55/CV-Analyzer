import re

def keyword_match_score(cv_text: str, job_description: str) -> float:
    cv_text = cv_text.lower()
    job_description = job_description.lower()

    # Basit kelime çıkarma
    cv_words = set(re.findall(r'\b\w+\b', cv_text))
    job_words = set(re.findall(r'\b\w+\b', job_description))

    if not job_words:
        return 0.0

    matched = cv_words.intersection(job_words)

    score = (len(matched) / len(job_words)) * 100

    return round(score, 2)