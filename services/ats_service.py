import re
from typing import Dict, List

from .keyword_service import keyword_match_score


COMMON_SECTIONS = [
    "contact",
    "summary",
    "experience",
    "work experience",
    "education",
    "skills",
    "projects",
    "certifications",
    "achievements",
]


# Minimum required sections for a realistic CV
MIN_REQUIRED_SECTIONS = [
    "experience",
    "education",
    "skills",
]


ACTION_VERBS = [
    "achieved",
    "improved",
    "managed",
    "led",
    "created",
    "built",
    "increased",
    "reduced",
    "delivered",
    "designed",
    "implemented",
    "optimized",
]


def _find_sections(cv_text: str) -> List[str]:
    text = cv_text.lower()
    found = []
    for s in COMMON_SECTIONS:
        if re.search(r"\b" + re.escape(s) + r"\b", text):
            found.append(s)
    return found


def _contact_score(cv_text: str) -> float:
    text = cv_text
    email = re.search(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}", text)
    phone = re.search(r"(\+?\d[\d\s\-()]{6,}\d)", text)
    linkedin = re.search(r"linkedin\.com/[A-Za-z0-9_-]+", text.lower())

    score = 0
    if email:
        score += 50
    if phone:
        score += 30
    if linkedin:
        score += 20

    return float(min(score, 100))


def _bullet_ratio(cv_text: str) -> float:
    bullets = len(re.findall(r"(^|\n)\s*(\-|\*|•|\d+\.)\s+", cv_text))
    # use lines instead of sentence punctuation to avoid inflated ratios
    lines = cv_text.split("\n")
    lines_count = max(1, len(lines))
    ratio = bullets / lines_count
    # normalize to 0-100 (ideal bullet ratio ~0.2-0.6)
    score = 0
    if ratio >= 0.2 and ratio <= 0.6:
        score = 100
    elif ratio < 0.2:
        score = min(100, int((ratio / 0.2) * 100))
    else:
        score = min(100, int((0.6 / ratio) * 100))
    return float(score)


def _keyword_density_penalty(cv_text: str, job_text: str) -> float:
    if not job_text:
        return 0.0

    job_words = set(re.findall(r"\b\w+\b", job_text.lower()))
    cv_words = re.findall(r"\b\w+\b", cv_text.lower())

    if not cv_words:
        return 0.0

    match_count = sum(1 for w in cv_words if w in job_words)
    density = match_count / len(cv_words)

    # Ideal density 5-20%
    if density > 0.30:
        return -20.0
    elif density > 0.20:
        return -10.0
    return 0.0


def _action_verb_score(cv_text: str) -> float:
    text = cv_text.lower()
    count = 0
    words = re.findall(r"\b\w+\b", text)
    total = max(1, len(words))
    for v in ACTION_VERBS:
        count += len(re.findall(r"\b" + re.escape(v) + r"\b", text))
    ratio = count / total
    # scale to 0-100 where ratio ~0.005+ is good
    score = min(100.0, ratio / 0.005 * 100)

    # reward diversity of action verbs (non-linear boost)
    unique_verbs = len(set(v for v in ACTION_VERBS if re.search(r"\b" + re.escape(v) + r"\b", text)))
    if unique_verbs >= 5:
        score = min(100.0, score + 10.0)

    return float(score)


def _length_score(cv_text: str) -> float:
    # approximate characters per page ~1800-2000; ideal 1-2 pages
    chars = len(cv_text)
    # use a more realistic ideal: 2000-4500 characters
    if 2000 <= chars <= 4500:
        return 100.0
    elif chars < 2000:
        return max(0.0, (chars / 2000) * 100)
    else:
        # penalize long CVs linearly beyond 4500
        return max(0.0, int(100 - ((chars - 4500) / 5000 * 100)))


def analyze_cv(cv_text: str, job_text: str = "") -> Dict:
    """
    Returns a dictionary with detailed ATS compatibility scores and suggestions.

    - content_score: how well the words/keywords/achievements align with `job_text`
    - layout_score: structural & formatting heuristics (sections, contact, bullets, length)
    - overall_score: weighted combination
    - suggestions: actionable items to improve ATS compatibility
    """

    # Content related
    keyword_score = 0.0
    if job_text and job_text.strip():
        keyword_score = keyword_match_score(cv_text, job_text)
    else:
        # if no job_text provided, still measure presence of skills/sections
        keyword_score = 0.0

    # Spam / density penalty (prevent copy-paste job descriptions)
    penalty = _keyword_density_penalty(cv_text, job_text)

    action_score = _action_verb_score(cv_text)
    achievement_hits = len(re.findall(r"\b\d+%?\b", cv_text))
    achievement_score = float(min(100.0, achievement_hits * 8))

    # Layout / structure
    sections_found = _find_sections(cv_text)
    # Use minimum required sections for a fairer penalty (use regex match)
    required_found = [
        s
        for s in MIN_REQUIRED_SECTIONS
        if re.search(r"\b" + re.escape(s) + r"\b", cv_text.lower())
    ]
    section_presence_score = (len(required_found) / len(MIN_REQUIRED_SECTIONS)) * 100
    contact_score = _contact_score(cv_text)
    bullet_score = _bullet_ratio(cv_text)
    length_score = _length_score(cv_text)

    layout_score = (
        0.4 * section_presence_score
        + 0.3 * contact_score
        + 0.15 * bullet_score
        + 0.15 * length_score
    )

    # Penalize CVs that include tables/graphics-like markers
    if "|" in cv_text or "\t" in cv_text:
        layout_score = max(0.0, layout_score - 10.0)

    # Section order bonus: preferred order improves layout score
    preferred_order = ["contact", "summary", "experience", "education", "skills"]
    prev_pos = -1
    order_ok = True
    found_any = False
    for sec in preferred_order:
        m = re.search(r"\b" + re.escape(sec) + r"\b", cv_text.lower())
        if m:
            found_any = True
            if m.start() <= prev_pos:
                order_ok = False
                break
            prev_pos = m.start()
    if order_ok and found_any:
        layout_score = min(100.0, layout_score + 5.0)

    # Apply content-level scoring. If no job_text, rely more on action/achievement.
    if job_text and job_text.strip():
        content_score = (0.7 * keyword_score) + (0.2 * action_score) + (0.1 * achievement_score)
        content_score += penalty
    else:
        content_score = (0.6 * action_score) + (0.4 * achievement_score)

    # Clamp content score to [0,100] to avoid negatives from penalties
    content_score = max(0.0, min(100.0, content_score))

    # Increase content weight for production realism
    overall = round((0.7 * content_score) + (0.3 * layout_score), 2)

    suggestions: List[str] = []
    if keyword_score < 40:
        suggestions.append("İş ilanındaki anahtar kelimeleri CV'nize doğal biçimde ekleyin.")
    if action_score < 30:
        suggestions.append("Her görev için ölçülebilir başarılara ve güçlü eylem fiillerine yer verin.")
    if section_presence_score < 50:
        suggestions.append("Başlıklar: Education, Experience, Skills, Contact gibi net bölümler ekleyin.")
    if contact_score < 50:
        suggestions.append("CV üst kısmına e-posta ve telefon numarası (ve varsa LinkedIn) ekleyin.")
    if bullet_score < 40:
        suggestions.append("Kazanımları madde listesi ile yazın; uzun paragraflardan kaçının.")
    if length_score < 50:
        suggestions.append("CV uzunluğunu 1-2 sayfa aralığında tutmaya çalışın.")

    result = {
        "content": {
            "keyword_score": round(keyword_score, 2),
            "action_verb_score": round(action_score, 2),
            "achievement_score": round(achievement_score, 2),
            "content_score": round(content_score, 2),
        },
        "layout": {
            "sections_found": sections_found,
            "section_presence_score": round(section_presence_score, 2),
            "contact_score": round(contact_score, 2),
            "bullet_score": round(bullet_score, 2),
            "length_score": round(length_score, 2),
            "layout_score": round(layout_score, 2),
        },
        "overall_score": overall,
        "suggestions": suggestions,
    }

    return result
