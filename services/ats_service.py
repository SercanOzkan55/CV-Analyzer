import re
from typing import Dict, List

from .ats_config import get_ats_length_profile
from .keyword_service import keyword_match_score


SECTION_ALIASES = {
    "contact": [
        "contact",
        "contact information",
        "iletişim",
        "iletisim",
        "contacto",
        "coordonnées",
        "kontakt",
    ],
    "summary": [
        "summary",
        "professional summary",
        "profile",
        "objective",
        "özet",
        "ozet",
        "profil",
        "resumen",
        "perfil",
        "objectif",
        "zusammenfassung",
    ],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "iş deneyimi",
        "is deneyimi",
        "deneyim",
        "experiencia",
        "experiencia laboral",
        "expérience",
        "berufserfahrung",
    ],
    "education": [
        "education",
        "academic background",
        "qualifications",
        "eğitim",
        "egitim",
        "educación",
        "formación",
        "formation",
        "ausbildung",
    ],
    "skills": [
        "skills",
        "technical skills",
        "core competencies",
        "competencies",
        "beceriler",
        "teknik beceriler",
        "habilidades",
        "compétences",
        "fähigkeiten",
    ],
    "projects": ["projects", "projeler", "proyectos", "projets", "projekte"],
    "certifications": [
        "certifications",
        "certificates",
        "licenses",
        "sertifikalar",
        "certificaciones",
        "certificats",
        "zertifikate",
    ],
    "languages": ["languages", "language skills", "diller", "idiomas", "langues", "sprachen"],
    "publications": ["publications", "research"],
    "volunteer": ["volunteer", "volunteering"],
    "references": ["references", "referanslar"],
}

COMMON_SECTIONS = sorted({alias for aliases in SECTION_ALIASES.values() for alias in aliases})
MIN_REQUIRED_SECTIONS = ["experience", "education", "skills"]

ACTION_VERBS = [
    "led",
    "managed",
    "directed",
    "supervised",
    "coordinated",
    "oversaw",
    "mentored",
    "achieved",
    "exceeded",
    "earned",
    "created",
    "built",
    "designed",
    "developed",
    "established",
    "launched",
    "implemented",
    "improved",
    "enhanced",
    "optimized",
    "streamlined",
    "transformed",
    "analyzed",
    "assessed",
    "evaluated",
    "researched",
    "identified",
    "audited",
    "delivered",
    "executed",
    "deployed",
    "completed",
    "resolved",
    "configured",
    "maintained",
    "increased",
    "expanded",
    "scaled",
    "generated",
    "reduced",
    "decreased",
    "saved",
    "presented",
    "communicated",
    "collaborated",
    "documented",
    "trained",
    "engineered",
    "architected",
    "automated",
    "integrated",
    "migrated",
    "yönetti",
    "yonetti",
    "geliştirdi",
    "gelistirdi",
    "tasarladı",
    "tasarladi",
    "uyguladı",
    "uyguladi",
    "iyileştirdi",
    "iyilestirdi",
    "artırdı",
    "artirdi",
    "azalttı",
    "azaltti",
    "otomatikleştirdi",
    "otomatiklestirdi",
    "lideró",
    "lidero",
    "gestionó",
    "gestiono",
    "desarrolló",
    "desarrollo",
    "implementó",
    "implemento",
    "mejoró",
    "mejoro",
    "dirigé",
    "dirige",
    "développé",
    "developpe",
    "amélioré",
    "ameliore",
    "leitete",
    "entwickelte",
    "implementierte",
    "verbesserte",
    "optimierte",
]

QUANTIFICATION_PATTERNS = [
    r"\b\d+(?:[.,]\d+)?\s?%",
    r"%\s?\d+(?:[.,]\d+)?",
    r"(?:[$€£₺]|USD|EUR|GBP|TRY)\s?[\d,.]+(?:[KkMmBb])?\b",
    r"\b\d+(?:,\d{3})+\b",
    r"\b\d+(?:\.\d{3})+(?:,\d+)?\b",
    r"\b\d+[KkMm]\+?",
    r"\b(?:top|first)\s+\d+",
    r"\b\d+x\b",
]

QUANTIFIED_CONTEXT_WORDS = [
    "users",
    "clients",
    "customers",
    "projects",
    "team members",
    "employees",
    "servers",
    "applications",
    "features",
    "releases",
    "deployments",
    "endpoints",
    "repositories",
    "databases",
    "microservices",
    "kullanıcı",
    "kullanici",
    "müşteri",
    "musteri",
    "proje",
    "çalışan",
    "calisan",
    "usuarios",
    "clientes",
    "proyectos",
    "utilisateurs",
    "clients",
    "projets",
    "benutzer",
    "kunden",
    "projekte",
]

PROFESSIONAL_PROFILE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:linkedin\.com|github\.com|gitlab\.com|behance\.net|dribbble\.com|"
    r"kaggle\.com|medium\.com|stackoverflow\.com|portfolio\.|notion\.site|"
    r"linktr\.ee|about\.me)/[^\s)>,]+",
    re.I,
)


def _find_sections(cv_text: str) -> List[str]:
    text = cv_text.lower()
    found = []
    for section, aliases in SECTION_ALIASES.items():
        if any(re.search(r"\b" + re.escape(alias) + r"\b", text) for alias in aliases):
            found.append(section)
    return found


def _contact_score(cv_text: str) -> float:
    email = re.search(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}", cv_text)
    phone = re.search(r"(\+?\d[\d\s\-()]{6,}\d)", cv_text)
    professional_profile = PROFESSIONAL_PROFILE_RE.search(cv_text)

    score = 0
    if email:
        score += 50
    if phone:
        score += 30
    if professional_profile:
        score += 20

    return float(min(score, 100))


def _bullet_ratio(cv_text: str) -> float:
    bullets = len(re.findall(r"(^|\n)\s*(-|\*|•|\d+\.)\s+", cv_text))
    lines_count = max(1, len(cv_text.split("\n")))
    ratio = bullets / lines_count
    if 0.2 <= ratio <= 0.6:
        return 100.0
    if ratio < 0.2:
        return float(min(100, int((ratio / 0.2) * 100)))
    return float(min(100, int((0.6 / ratio) * 100)))


def _keyword_density_penalty(cv_text: str, job_text: str) -> float:
    if not job_text:
        return 0.0

    job_words = set(re.findall(r"\b\w+\b", job_text.lower(), flags=re.UNICODE))
    cv_words = re.findall(r"\b\w+\b", cv_text.lower(), flags=re.UNICODE)

    if not cv_words:
        return 0.0

    density = sum(1 for word in cv_words if word in job_words) / len(cv_words)
    if density > 0.30:
        return -20.0
    if density > 0.20:
        return -10.0
    return 0.0


def _action_verb_score(cv_text: str) -> float:
    text = cv_text.lower()
    found_verbs = set()
    total_hits = 0

    for verb in ACTION_VERBS:
        hits = len(re.findall(r"\b" + re.escape(verb) + r"(?:s|ed|ing|d)?\b", text))
        if hits:
            found_verbs.add(verb)
            total_hits += hits

    diversity_score = min(100.0, (len(found_verbs) / 10.0) * 100)
    frequency_score = min(100.0, (total_hits / 15.0) * 100)
    return float(min(100.0, 0.6 * diversity_score + 0.4 * frequency_score))


def _length_score(cv_text: str) -> float:
    words = len(re.findall(r"\b\w+\b", cv_text, flags=re.UNICODE))
    length_profile = get_ats_length_profile()
    ideal_min = length_profile["ideal_min_words"]
    ideal_max = length_profile["ideal_max_words"]
    extended_max = length_profile["extended_max_words"]
    very_long_max = length_profile["very_long_max_words"]

    if ideal_min <= words <= ideal_max:
        return 100.0
    if words < ideal_min:
        return max(0.0, (words / ideal_min) * 100)
    if words <= extended_max:
        return max(55.0, 100.0 - ((words - ideal_max) / (extended_max - ideal_max)) * 45)
    if words <= very_long_max:
        return max(25.0, 55.0 - ((words - extended_max) / (very_long_max - extended_max)) * 30)
    return max(10.0, 25.0 - ((words - very_long_max) / very_long_max) * 15)


def _formatting_consistency_score(cv_text: str) -> float:
    score = 100.0
    lines = cv_text.split("\n")
    non_empty_lines = [line for line in lines if line.strip()]

    if not non_empty_lines:
        return 0.0

    date_formats_found = set()
    if re.search(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}", cv_text):
        date_formats_found.add("month_word")
    if re.search(r"\b\d{1,2}/\d{4}\b", cv_text):
        date_formats_found.add("mm_yyyy")
    if re.search(r"\b\d{4}-\d{2}\b", cv_text):
        date_formats_found.add("yyyy_mm")
    if len(date_formats_found) > 1:
        score -= 15.0

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

    blank_runs = re.findall(r"\n{4,}", cv_text)
    if blank_runs:
        score -= min(15.0, len(blank_runs) * 5.0)

    caps_blocks = re.findall(r"(?:\b[A-Z]{3,}\b\s*){5,}", cv_text)
    if caps_blocks:
        score -= 10.0

    long_lines = sum(1 for line in non_empty_lines if len(line) > 200)
    if long_lines > 3:
        score -= 10.0

    return max(0.0, score)


def _section_presence_score(cv_text: str) -> float:
    found = set(_find_sections(cv_text))
    return (len(found.intersection(MIN_REQUIRED_SECTIONS)) / len(MIN_REQUIRED_SECTIONS)) * 100


def analyze_cv(cv_text: str, job_text: str = "", lang: str = "auto") -> Dict:
    """
    Return detailed ATS compatibility scores and suggestions.

    The scoring uses general, language-aware heuristics. It does not require a
    specific country, platform, or English-only CV style.
    """

    keyword_score = keyword_match_score(cv_text, job_text) if job_text and job_text.strip() else 0.0
    penalty = _keyword_density_penalty(cv_text, job_text)
    action_score = _action_verb_score(cv_text)

    quant_hits = sum(len(re.findall(pattern, cv_text, flags=re.UNICODE | re.I)) for pattern in QUANTIFICATION_PATTERNS)
    context_pattern = r"\b\d+\s+(?:" + "|".join(re.escape(word) for word in QUANTIFIED_CONTEXT_WORDS) + r")\b"
    quant_hits += len(re.findall(context_pattern, cv_text.lower(), flags=re.UNICODE))
    achievement_score = float(min(100.0, quant_hits * 12))

    sections_found = _find_sections(cv_text)
    section_presence_score = _section_presence_score(cv_text)
    contact_score = _contact_score(cv_text)
    bullet_score = _bullet_ratio(cv_text)
    length_score = _length_score(cv_text)

    layout_score = (
        0.4 * section_presence_score
        + 0.3 * contact_score
        + 0.15 * bullet_score
        + 0.15 * length_score
    )

    if "|" in cv_text or "\t" in cv_text:
        layout_score = max(0.0, layout_score - 10.0)

    preferred_order = ["contact", "summary", "experience", "education", "skills"]
    prev_pos = -1
    order_ok = True
    found_any = False
    lower_text = cv_text.lower()
    for section in preferred_order:
        aliases = SECTION_ALIASES.get(section, [section])
        match = None
        for alias in aliases:
            match = re.search(r"\b" + re.escape(alias) + r"\b", lower_text)
            if match:
                break
        if match:
            found_any = True
            if match.start() <= prev_pos:
                order_ok = False
                break
            prev_pos = match.start()
    if order_ok and found_any:
        layout_score = min(100.0, layout_score + 5.0)

    if job_text and job_text.strip():
        content_score = (0.6 * keyword_score) + (0.2 * action_score) + (0.2 * achievement_score) + penalty
    else:
        content_score = (0.5 * action_score) + (0.5 * achievement_score)
    content_score = max(0.0, min(100.0, content_score))

    formatting_score = _formatting_consistency_score(cv_text)
    overall = round(0.55 * content_score + 0.25 * layout_score + 0.20 * formatting_score, 2)

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

    return {
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
