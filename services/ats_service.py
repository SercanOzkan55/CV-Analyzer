import re
from typing import Dict, List

from .keyword_service import keyword_match_score

# ── Section detection ────────────────────────────────────────────────

COMMON_SECTIONS = [
    "contact",
    "contact information",
    "summary",
    "professional summary",
    "profile",
    "objective",
    "experience",
    "work experience",
    "professional experience",
    "employment",
    "education",
    "academic background",
    "skills",
    "technical skills",
    "core competencies",
    "competencies",
    "projects",
    "key projects",
    "certifications",
    "certificates",
    "licenses",
    "achievements",
    "awards",
    "honors",
    "languages",
    "language skills",
    "publications",
    "research",
    "volunteer",
    "volunteering",
    "references",
]

MIN_REQUIRED_SECTIONS = [
    "experience",
    "education",
    "skills",
]


# ── Action verbs (comprehensive list for professional CVs) ───────────

ACTION_VERBS = [
    # Leadership
    "led",
    "managed",
    "directed",
    "supervised",
    "coordinated",
    "oversaw",
    "spearheaded",
    "orchestrated",
    "mentored",
    "coached",
    # Achievement
    "achieved",
    "exceeded",
    "surpassed",
    "earned",
    "won",
    "awarded",
    # Creation
    "created",
    "built",
    "designed",
    "developed",
    "established",
    "founded",
    "launched",
    "initiated",
    "introduced",
    "pioneered",
    # Improvement
    "improved",
    "enhanced",
    "optimized",
    "streamlined",
    "upgraded",
    "refactored",
    "modernized",
    "revamped",
    "transformed",
    "accelerated",
    # Analysis
    "analyzed",
    "assessed",
    "evaluated",
    "researched",
    "investigated",
    "identified",
    "diagnosed",
    "audited",
    "reviewed",
    "benchmarked",
    # Delivery
    "delivered",
    "implemented",
    "executed",
    "deployed",
    "shipped",
    "completed",
    "resolved",
    "configured",
    "maintained",
    # Growth
    "increased",
    "expanded",
    "scaled",
    "grew",
    "generated",
    "boosted",
    # Reduction
    "reduced",
    "decreased",
    "minimized",
    "eliminated",
    "consolidated",
    "cut",
    "saved",
    # Communication
    "presented",
    "communicated",
    "negotiated",
    "collaborated",
    "facilitated",
    "documented",
    "reported",
    "trained",
    "taught",
    "educated",
    # Technical
    "engineered",
    "architected",
    "programmed",
    "automated",
    "integrated",
    "migrated",
    "containerized",
    "provisioned",
    "instrumented",
]


# ── Quantification patterns (numbers, percentages, metrics) ──────────

QUANTIFICATION_PATTERNS = [
    r"\b\d+%",  # 25%, 150%
    r"\$[\d,]+(?:\.\d+)?[KkMmBb]?\b",  # $50K, $1.2M
    r"\b\d+(?:,\d{3})+\b",  # 1,000  10,000
    r"\b\d+[KkMm]\+?",  # 50K, 2M, 2M+
    r"\b(?:top|first)\s+\d+",  # top 10, first 3
    r"\b\d+x\b",  # 3x, 10x
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
    found_verbs = set()
    total_hits = 0

    for v in ACTION_VERBS:
        hits = len(re.findall(r"\b" + re.escape(v) + r"(?:s|ed|ing|d)?\b", text))
        if hits > 0:
            found_verbs.add(v)
            total_hits += hits

    # Score based on both diversity and frequency
    diversity_score = min(
        100.0, (len(found_verbs) / 10.0) * 100
    )  # 10+ unique verbs = 100
    frequency_score = min(100.0, (total_hits / 15.0) * 100)  # 15+ uses = 100

    score = 0.6 * diversity_score + 0.4 * frequency_score
    return float(min(100.0, score))


def _length_score(cv_text: str) -> float:
    # PDF extracted text varies; approximate chars per page ~2500-3500
    # Ideal CV: 1-2 pages (~2500-7000 chars extracted)
    chars = len(cv_text)
    if 2500 <= chars <= 7000:
        return 100.0
    elif chars < 2500:
        return max(0.0, (chars / 2500) * 100)
    elif chars <= 12000:
        # 3-4 pages: mild penalty
        return max(40.0, 100.0 - ((chars - 7000) / 5000) * 60)
    else:
        # 4+ pages: heavy penalty
        return max(10.0, 40.0 - ((chars - 12000) / 10000) * 30)


def _formatting_consistency_score(cv_text: str) -> float:
    """
    Evaluate formatting consistency: consistent date formats, consistent
    bullet styles, no excessive whitespace, no ALL CAPS blocks.
    """
    score = 100.0
    lines = cv_text.split("\n")
    non_empty_lines = [l for l in lines if l.strip()]

    if not non_empty_lines:
        return 0.0

    # 1) Date format consistency — penalize mixing "Jan 2020" and "01/2020" etc.
    date_formats_found = set()
    if re.search(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}", cv_text
    ):
        date_formats_found.add("month_word")
    if re.search(r"\b\d{1,2}/\d{4}\b", cv_text):
        date_formats_found.add("mm_yyyy")
    if re.search(r"\b\d{4}-\d{2}\b", cv_text):
        date_formats_found.add("yyyy_mm")
    if len(date_formats_found) > 1:
        score -= 15.0

    # 2) Bullet style consistency
    bullet_styles = set()
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("- "):
            bullet_styles.add("dash")
        elif stripped.startswith("• "):
            bullet_styles.add("bullet")
        elif stripped.startswith("* "):
            bullet_styles.add("asterisk")
        elif re.match(r"\d+\.\s", stripped):
            bullet_styles.add("numbered")
    if len(bullet_styles) > 1:
        score -= 10.0

    # 3) Excessive blank lines (more than 2 consecutive)
    blank_runs = re.findall(r"\n{4,}", cv_text)
    if blank_runs:
        score -= min(15.0, len(blank_runs) * 5.0)

    # 4) ALL CAPS blocks (more than 5 consecutive all-caps words = ATS unfriendly)
    caps_blocks = re.findall(r"(?:\b[A-Z]{3,}\b\s*){5,}", cv_text)
    if caps_blocks:
        score -= 10.0

    # 5) Very long lines (>200 chars without break) — walls of text
    long_lines = sum(1 for l in non_empty_lines if len(l) > 200)
    if long_lines > 3:
        score -= 10.0

    return max(0.0, score)


def analyze_cv(cv_text: str, job_text: str = "", lang: str = "en") -> Dict:
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

    # Quantified achievements: percentages, dollar amounts, large numbers
    quant_hits = 0
    for pattern in QUANTIFICATION_PATTERNS:
        quant_hits += len(re.findall(pattern, cv_text))
    # Also count simple numbers followed by context words
    quant_hits += len(
        re.findall(
            r"\b\d+\s+(?:users|clients|customers|projects|team members|employees|servers|applications|features|releases|deployments|endpoints|repositories|databases|microservices)\b",
            cv_text.lower(),
        )
    )
    achievement_score = float(min(100.0, quant_hits * 12))

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
        content_score = (
            (0.6 * keyword_score) + (0.2 * action_score) + (0.2 * achievement_score)
        )
        content_score += penalty
    else:
        content_score = (0.5 * action_score) + (0.5 * achievement_score)

    # Clamp content score to [0,100] to avoid negatives from penalties
    content_score = max(0.0, min(100.0, content_score))

    # Formatting consistency score
    formatting_score = _formatting_consistency_score(cv_text)

    # Weighted overall: content 55%, layout 25%, formatting 20%
    overall = round(
        0.55 * content_score + 0.25 * layout_score + 0.20 * formatting_score, 2
    )

    from .language_service import get_ats_suggestion

    suggestions: List[str] = []
    if keyword_score < 40:
        suggestions.append(get_ats_suggestion("keyword_low", lang))
    if action_score < 30:
        suggestions.append(get_ats_suggestion("action_low", lang))
    if section_presence_score < 50:
        suggestions.append(get_ats_suggestion("sections_missing", lang))
    if contact_score < 50:
        suggestions.append(get_ats_suggestion("contact_missing", lang))
    if bullet_score < 40:
        suggestions.append(get_ats_suggestion("bullets_low", lang))
    if length_score < 50:
        suggestions.append(get_ats_suggestion("length_bad", lang))
    if achievement_score < 30:
        suggestions.append(get_ats_suggestion("quantify_achievements", lang))
    if formatting_score < 50:
        suggestions.append(get_ats_suggestion("formatting_inconsistent", lang))

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
            "formatting_score": round(formatting_score, 2),
            "layout_score": round(layout_score, 2),
        },
        "overall_score": overall,
        "suggestions": suggestions,
    }

    return result
