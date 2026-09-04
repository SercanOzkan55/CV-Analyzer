"""ATS format-compliance criterion (ported from services/ats_service.py).

Ported functions: ``_formatting_consistency_score``, ``_find_sections`` +
``MIN_REQUIRED_SECTIONS``, ``_bullet_ratio``, ``_length_score``,
``_contact_score``. Combined into a single ``ats_format_score`` — a pure
text/regex signal, zero network or DB dependency, safe for the fully
offline Local Worker.

Combining formula: the source file's ``analyze_cv()`` (services/ats_service.py
~1760-1767) computes an "ATS compatibility composite" as::

    0.30 * section_presence_score
    + 0.25 * formatting_score
    + 0.20 * bullet_score
    + 0.15 * length_score
    + 0.10 * (100 if sections appear in the preferred order else 60)

The order-bonus term depends on ``_find_section_position`` (not in the
ported list here, and needs more of ``language_service``'s alias
machinery). This module keeps the source's exact weights for the first
four terms (0.30 / 0.25 / 0.20 / 0.15 = 0.90) and gives ``_contact_score``
the remaining 0.10 — matching the ported-function list this module was
asked to expose (``_contact_score`` explicitly included) while staying
faithful to the source's verified weighting rather than guessing new ones.
"""

import re

# ── Section detection (ported from services/language_service.py) ────
# Trimmed to the alias set needed for reliable, multilingual section
# detection (the same dict the source file's `_find_sections` scans).


def clean_lower(text: str) -> str:
    """Locale-independent lowercasing (mirrors language_service.clean_lower).

    Guards against the Turkish dotted capital İ (U+0130) mangling and
    stray combining-dot artifacts from naive `.lower()` calls.
    """
    if not text:
        return ""
    text = text.replace("İ", "i")
    lowered = text.lower()
    lowered = lowered.replace("i̇", "i").replace("i̇", "i")
    return lowered


SECTION_ALIASES = {
    "summary": {
        "summary", "professional summary", "personal information", "profile",
        "about", "objective", "career summary",
        "özet", "profesyonel özet", "profil", "kişisel bilgiler", "kariyer özeti",
        "résumé professionnel", "profil professionnel",
        "zusammenfassung", "über mich", "kurzprofil",
        "resumen profesional", "perfil profesional", "resumen", "perfil",
        "resumo profissional", "resumo",
        "profilo professionale", "riepilogo", "sommario",
        "samenvatting", "profiel", "persoonlijk profiel",
    },
    "experience": {
        "experience", "work experience", "professional experience", "employment",
        "employment history", "work history",
        "deneyim", "iş deneyimi", "mesleki deneyim", "geçmiş işler", "professional history",
        "expérience", "expérience professionnelle",
        "erfahrung", "berufserfahrung",
        "experiencia", "experiencia laboral", "experiencia profesional",
        "experiência", "experiência profissional",
        "esperienza", "esperienza lavorativa",
        "ervaring", "werkervaring",
    },
    "education": {
        "education", "academic background", "qualifications", "qualification",
        "educational qualification", "educational qualifications", "education qualification",
        "education qualifications", "academic qualification", "academic qualifications",
        "educational background", "education details", "educational details", "academic details",
        "eğitim", "akademik geçmiş",
        "formation", "études",
        "ausbildung", "bildung", "studium",
        "educación", "formación",
        "educação", "formação acadêmica",
        "istruzione", "formazione",
        "opleiding", "onderwijs",
    },
    "skills": {
        "skills", "technical skills", "core competencies", "competencies", "technologies",
        "beceriler", "yetenekler", "teknik beceriler", "teknik yetenekler", "yetkinlikler",
        "compétences", "compétences techniques",
        "fähigkeiten", "kenntnisse", "kompetenzen",
        "habilidades", "competencias",
        "competências",
        "competenze", "abilità",
        "vaardigheden", "competenties",
    },
    "projects": {
        "project", "projects", "project experience", "personal projects", "projeler",
        "projets", "projekte", "proyectos", "projetos", "progetti", "projecten",
    },
    "certifications": {
        "certifications", "certificates", "licenses", "sertifikalar", "belgeler",
        "diplômes", "zertifizierungen", "zertifikate", "certificaciones",
        "certificações", "certificazioni", "certificeringen",
    },
    "languages": {
        "languages", "language skills", "diller", "yabancı dil", "yabancı diller",
        "langues", "sprachen", "idiomas", "lingue", "talen",
    },
    "contact": {
        "contact", "contact information", "communication", "iletişim",
        "coordonnées", "kontakt", "kontaktdaten", "contacto", "contato", "contatto",
        "contactgegevens",
    },
    "interests": {
        "interests", "hobbies", "personal interests", "ilgi alanları", "hobiler",
        "centres d'intérêt", "loisirs", "interessen", "hobbys", "intereses", "aficiones",
        "interesses", "interessi", "hobby's",
    },
}

MIN_REQUIRED_SECTIONS = ["experience", "education", "skills"]

QUANTIFICATION_PATTERNS = [
    r"\b\d+%",
    r"\$[\d,]+(?:\.\d+)?[KkMmBb]?\b",
    r"\b\d+(?:,\d{3})+\b",
    r"\b\d+[KkMm]\+?",
    r"\b(?:top|first)\s+\d+",
    r"\b\d+x\b",
]


def _find_sections(cv_text: str) -> list[str]:
    """Detect CV sections from header-LIKE lines only.

    Searching aliases anywhere in the text misreports sections: a summary
    saying "gaining industry experience..." would falsely claim an
    Experience section exists. Real section headers are short lines that
    START with the alias, so only those count.
    """
    header_lines = [line.strip(" \t:·•|-–—_") for line in clean_lower(cv_text).split("\n")]
    header_lines = [line for line in header_lines if line and len(line) <= 60]
    found = []
    for canon, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            rx = re.compile(r"^" + re.escape(clean_lower(alias)) + r"\b")
            if any(rx.match(line) for line in header_lines):
                found.append(canon)
                break
    return found


def _contact_score(cv_text: str) -> float:
    text = cv_text
    email = re.search(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}", text)
    phone = re.search(r"(\+?\d[\d\s\-()]{6,}\d)", text)
    linkedin = re.search(r"linkedin\.com/[A-Za-z0-9_-]+", clean_lower(text))
    github = re.search(r"github\.com/[A-Za-z0-9_-]+", clean_lower(text))
    portfolio = re.search(r"(?:portfolio|website|blog)\s*[:.]?\s*(?:https?://)?[\w\.-]+\.\w{2,}", clean_lower(text))

    score = 0
    if email:
        score += 40
    if phone:
        score += 25
    if linkedin:
        score += 15
    if github:
        score += 10
    if portfolio:
        score += 10

    first_lines = "\n".join(text.split("\n")[:5])
    contacts_in_header = sum(
        [
            bool(re.search(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}", first_lines)),
            bool(re.search(r"(\+?\d[\d\s\-()]{6,}\d)", first_lines)),
        ]
    )
    if contacts_in_header >= 2:
        score += 10

    if re.search(r".+\|.+\|.+", first_lines):
        score += 5

    return float(min(score, 100))


def _bullet_ratio(cv_text: str) -> float:
    bullets = len(re.findall(r"(^|\n)\s*(\-|\*|•|\d+\.)\s+", cv_text))
    lines = cv_text.split("\n")
    lines_count = max(1, len(lines))
    ratio = bullets / lines_count
    score = 0
    if ratio >= 0.2 and ratio <= 0.6:
        score = 100
    elif ratio < 0.2:
        score = min(100, int((ratio / 0.2) * 100))
    else:
        score = min(100, int((0.6 / ratio) * 100))
    return float(score)


def _length_score(cv_text: str) -> float:
    chars = len(cv_text)
    if 2500 <= chars <= 7000:
        return 100.0
    elif chars < 2500:
        return max(0.0, (chars / 2500) * 100)
    elif chars <= 12000:
        return max(40.0, 100.0 - ((chars - 7000) / 5000) * 60)
    else:
        return max(10.0, 40.0 - ((chars - 12000) / 10000) * 30)


def _formatting_consistency_score(cv_text: str) -> float:
    """Evaluate formatting consistency: consistent date formats, consistent
    bullet styles, no excessive whitespace, no ALL CAPS blocks.
    """
    score = 100.0
    lines = cv_text.split("\n")
    non_empty_lines = [l for l in lines if l.strip()]

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

    long_lines = sum(1 for l in non_empty_lines if len(l) > 200)
    if long_lines > 3:
        score -= 10.0

    standard_headings = [
        "PROFESSIONAL SUMMARY", "EXPERIENCE", "EDUCATION", "SKILLS", "PROJECTS",
        "CERTIFICATIONS", "LANGUAGES", "ÖZET", "DENEYİM", "EĞİTİM", "YETENEKLER",
        "PROJELER", "SERTİFİKALAR", "DİLLER", "İŞ DENEYİMİ", "MESLEKİ DENEYİM",
        "AKADEMİK GEÇMİŞ", "YETKİNLİKLER",
    ]
    std_count = sum(1 for h in standard_headings if h in cv_text)
    if std_count >= 4:
        score = min(100.0, score + 8.0)
    elif std_count >= 3:
        score = min(100.0, score + 5.0)

    first_lines = non_empty_lines[:3]
    contact_in_header = sum(1 for l in first_lines if re.search(r"[@|]", l) or re.search(r"\+?\d[\d\s\-]{7,}", l))
    if contact_in_header >= 1:
        score = min(100.0, score + 3.0)

    return max(0.0, score)


def ats_format_score(cv_text: str) -> float:
    """Combine the ported ATS format signals into one 0-100 score.

    See the module docstring for the weighting rationale (ported exactly
    from ``services/ats_service.py``'s ``ats_compat_score`` for 4 of the 5
    terms; ``_contact_score`` fills the remaining 0.10 in place of the
    source's section-order bonus).
    """
    cv_text = cv_text or ""
    sections_found = _find_sections(cv_text)
    required_found = [s for s in MIN_REQUIRED_SECTIONS if s in sections_found]
    section_presence_score = (len(required_found) / len(MIN_REQUIRED_SECTIONS)) * 100

    formatting_score = _formatting_consistency_score(cv_text)
    bullet_score = _bullet_ratio(cv_text)
    length_score = _length_score(cv_text)
    contact_score = _contact_score(cv_text)

    score = (
        0.30 * section_presence_score
        + 0.25 * formatting_score
        + 0.20 * bullet_score
        + 0.15 * length_score
        + 0.10 * contact_score
    )
    return round(max(0.0, min(100.0, score)), 2)
