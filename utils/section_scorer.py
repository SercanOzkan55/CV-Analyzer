"""Section Scorer — multi-signal scoring for block classification.

Scores a text block against six candidate sections:
    education, experience, skills, projects, languages, contact

Signals used per block:
    * keywords   — domain-specific terms
    * dates      — year / date-range patterns
    * structure  — bullets, dict shape, field names
    * length     — word count, line count
    * contact    — email/phone/URL presence

Higher score wins.  Used by ``utils.cv_normalizer`` to place ambiguous
blocks (particularly misc items and contaminated sections) before final
assignment.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ═══════════════════════════════════════════════════════════════════════════
# PATTERNS
# ═══════════════════════════════════════════════════════════════════════════

_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_DATE_RANGE_RE = re.compile(
    r"(?:19|20)\d{2}\s*[-–—]\s*(?:(?:19|20)\d{2}|present|current|ongoing|halen|günümüz)",
    re.I,
)
_EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
_PHONE_RE = re.compile(r"(?:\(?\+?\d[\d()\-\s.]{7,}\d)")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
_BULLET_RE = re.compile(r"^\s*[-•*▪▸►‣⁃·]\s")

_DEGREE_RE = re.compile(
    r"\b(?:b\.?s\.?c?|m\.?s\.?c?|b\.?a|m\.?a|ph\.?d|m\.?b\.?a"
    r"|bachelor|master|diploma|associate|degree"
    r"|lisans|yüksek\s*lisans|doktora|ön\s*lisans)\b",
    re.I,
)
_INSTITUTION_RE = re.compile(
    r"\b(?:university|üniversite|institute|enstitü|college|school"
    r"|faculty|fakülte|academy|akademi)\b",
    re.I,
)
_GPA_RE = re.compile(r"\b(?:GPA|CGPA|grade)\s*:\s*\d", re.I)

_COMPANY_RE = re.compile(
    r"\b(?:inc|llc|ltd|gmbh|corp|co\.|plc|a\.?ş|ş(?:ti|irketi)"
    r"|limited|company|group|holding|technologies|solutions"
    r"|consulting|services|systems|labs?|studio)\b",
    re.I,
)

_TECH_RE = re.compile(
    r"\b(?:python|java(?:script)?|typescript|react|angular|vue|node\.?js"
    r"|django|flask|fastapi|docker|kubernetes|aws|azure|gcp"
    r"|sql|postgresql|mongodb|redis|git|html|css|c\+\+|c#|rust"
    r"|go(?:lang)?|tensorflow|pytorch|scikit|pandas|excel|linux"
    r"|spring|ruby|rails|php|laravel|swift|kotlin|flutter|dart"
    r"|figma|photoshop|illustrator|sketch|jira|confluence)\b",
    re.I,
)
_SKILL_DELIM_RE = re.compile(r"[,;|/]")

_CERT_RE = re.compile(
    r"\b(?:certificate|certification|certified|sertifika|belge"
    r"|aws\s+certified|pmp|cissp|ccna|comptia|scrum\s+master)\b",
    re.I,
)

_PROJECT_RE = re.compile(
    r"\b(?:project|proje|github\.com|gitlab\.com|bitbucket|repository)\b",
    re.I,
)

# ── Canonical known-language set (single source of truth) ─────────────
# Import as ``from utils.section_scorer import KNOWN_LANGUAGES, CEFR_RE``.
# Coverage: 60+ languages in English name, native name, and major variants.
KNOWN_LANGUAGES: frozenset = frozenset({
    # ── English names ──
    "english", "turkish", "german", "french", "spanish", "italian",
    "portuguese", "russian", "arabic", "chinese", "japanese", "korean",
    "dutch", "swedish", "norwegian", "danish", "finnish", "polish",
    "czech", "hungarian", "greek", "romanian", "bulgarian", "croatian",
    "serbian", "ukrainian", "hebrew", "hindi", "persian", "thai",
    "vietnamese", "indonesian", "malay", "bengali", "urdu", "swahili",
    "tagalog", "filipino", "catalan", "basque", "galician", "welsh",
    "irish", "scottish gaelic", "icelandic", "latvian", "lithuanian",
    "estonian", "slovenian", "slovak", "albanian", "macedonian",
    "bosnian", "montenegrin", "georgian", "armenian", "azerbaijani",
    "kazakh", "uzbek", "afrikaans", "amharic", "somali", "hausa",
    "yoruba", "igbo", "zulu", "xhosa", "nepali", "sinhala",
    "tamil", "telugu", "kannada", "malayalam", "marathi", "gujarati",
    "punjabi", "burmese", "khmer", "lao", "mongolian", "tibetan",
    "mandarin", "cantonese", "hokkien", "sign language",
    # ── Turkish native names ──
    "türkçe", "ingilizce", "almanca", "fransızca", "ispanyolca",
    "italyanca", "portekizce", "rusça", "arapça", "çince", "japonca",
    "korece", "hollandaca", "lehçe", "yunanca", "bulgarca", "sırpça",
    "hırvatça", "ukraynaca", "farsça", "kürtçe",
    # ── European native names ──
    "deutsch", "français", "español", "italiano", "português",
    "nederlands", "svenska", "norsk", "dansk", "suomi",
    "polski", "čeština", "magyar", "română", "slovenčina",
    "slovenščina", "hrvatski", "srpski", "bosanski",
    "ελληνικά", "български",
    # ── Non-Latin ──
    "русский", "українська", "العربية", "فارسی", "עברית",
    "हिन्दी", "日本語", "中文", "한국어", "ไทย", "tiếng việt",
    "bahasa indonesia", "bahasa melayu",
})

# Backward-compatible alias used internally by scoring engine
_LANG_NAMES = KNOWN_LANGUAGES

CEFR_RE = re.compile(
    r"\b(?:A[12]|B[12]|C[12]"               # CEFR levels
    r"|N[1-5]"                                # JLPT levels
    r"|native|fluent|advanced|intermediate"
    r"|beginner|proficient|basic|elementary"
    r"|upper[\s-]?intermediate"
    r"|mother\s*tongue|bilingual"
    # International proficiency words
    r"|ana\s*dil(?:i)?"                       # Turkish: native
    r"|muttersprache"                         # German: native
    r"|langue\s*maternelle"                   # French: native
    r"|lengua\s*materna|nativo"               # Spanish: native
    r"|lingua\s*madre|madrelingua"            # Italian: native
    r"|courant|flie[ßs]end|competente"        # FR/DE/ES: fluent
    r"|débutant|anfänger|principiante"        # FR/DE/ES/IT: beginner
    r"|avancé|fortgeschritten|avanzado"       # FR/DE/ES: advanced
    r"|intermédiaire|mittelstufe|intermedio"  # intermediate
    r"|très\s*bien|bien|scolaire"             # FR: proficiency
    r"|iyi|çok\s*iyi|orta"                    # Turkish: levels
    r")\b",
    re.I,
)
# Backward-compatible alias
_CEFR_RE = CEFR_RE

# Sub-skill labels that appear alongside CEFR levels in language entries
_SUBSKILL_RE = re.compile(
    r"\b(?:writing|reading|listening|speaking|oral|written)\b",
    re.I,
)

# ── Structural URL / date patterns for language rejection ──
_DATE_LIKE_RE = re.compile(r"\b\d{4}\b")
_URL_LIKE_RE = re.compile(
    r"https?://|www\.|\.com\b|\.org\b|\.io\b|github|linkedin|@",
    re.I,
)


def is_language_entry(text: str, *, strict: bool = True) -> bool:
    """Detect whether *text* is a language entry using structural signals only.

    No language-name dictionaries are used.  Detection relies on:
    * CEFR / JLPT proficiency levels (A1-C2, N1-N5)
    * Level words (native, fluent, advanced, …)
    * Sub-skill labels (writing, reading, listening, speaking)
    * Absence of tech names, dates, and URLs

    Parameters
    ----------
    strict : bool
        * ``True`` — require at least one proficiency signal (CEFR, level
          word, or sub-skill + CEFR).  Used when *routing* items from
          skills / misc into the languages section.
        * ``False`` — accept short items that have no tech, date, or URL
          signals.  Used when *validating* items already classified as
          languages.
    """
    t = text.strip()
    if not t or len(t) <= 1:
        return False
    # Reject pure numbers / punctuation
    if re.match(r"^[\d\W]+$", t):
        return False

    has_cefr = bool(_CEFR_RE.search(t))
    has_sub = bool(_SUBSKILL_RE.search(t))
    has_tech = bool(_TECH_RE.search(t))
    has_date = bool(_DATE_LIKE_RE.search(t))
    has_url = bool(_URL_LIKE_RE.search(t))
    words = t.split()
    word_count = len(words)

    # Rule 1: CEFR / level word present and no tech/date/url → language
    #         BUT reject standalone levels with no accompanying name word
    #         (e.g. "B2", "Native", "N3" alone are not valid entries).
    if has_cefr and not has_tech and not has_date and not has_url:
        # Strip all CEFR/level tokens — whatever remains is the "name" part
        _name_part = _CEFR_RE.sub("", t).strip(" \t-–—(:)/,")
        if _name_part:
            return True

    # Rule 2: CEFR + sub-skill labels → language (even if longer)
    #         Sub-skills prove language context; still need a name word.
    if has_cefr and has_sub:
        _name_part2 = _CEFR_RE.sub("", t)
        _name_part2 = _SUBSKILL_RE.sub("", _name_part2).strip(" \t-–—(:)/,")
        if _name_part2:
            return True

    # Rule 3: "Language:" prefix (structural marker)
    if re.match(r"^(?:foreign\s+languages?|languages?(?:\s+known)?)\s*:\s*", t, re.I):
        return True

    if strict:
        # Strict mode: require proficiency signal — no permissive fallback
        return False

    # ── Permissive mode (items already in languages section) ──
    # Rule 4: No tech, no date, no URL, short → valid language entry
    if not has_tech and not has_date and not has_url and word_count <= 5:
        return True

    return False

_INTEREST_RE = re.compile(
    r"\b(?:hobby|hobbies|interest|volunteer|swimming|reading|traveling"
    r"|gaming|photography|cooking|music|sport|yoga|chess|hiking"
    r"|writing|drawing|painting|gardening|cycling|running)\b",
    re.I,
)

_BIRTH_RE = re.compile(
    r"\b(?:birth|dob|doğum|geboren|date\s+of\s+birth)\b", re.I,
)
_ADDRESS_RE = re.compile(
    r"\b(?:street|avenue|boulevard|road|drive|lane|apt\.?|suite"
    r"|floor|building|city|state|zip|postal|country"
    r"|mahalle|sokak|cadde|mah\.|cad\.|sk\.)\b",
    re.I,
)


# ═══════════════════════════════════════════════════════════════════════════
# SCORE RESULT
# ═══════════════════════════════════════════════════════════════════════════

SECTIONS = ("education", "experience", "skills", "projects",
            "languages", "contact", "certifications", "interests",
            "summary")

# Thresholds for overriding a section that came from an explicit header.
# Much higher than normal (0.35 / 0.10) to protect author intent.
LOCKED_MIN_SCORE = 0.70
LOCKED_MIN_MARGIN = 0.25


def locked_sections(
    section_titles: Optional[Dict[str, str]] = None,
) -> frozenset:
    """Return section keys with explicit headers in the original CV.

    Both singular and plural forms are included so callers can check
    either ``"experience"`` or ``"experiences"``.
    """
    if not section_titles:
        return frozenset()
    keys: set[str] = set(section_titles.keys())
    # Ensure both singular/plural forms are present.
    if "experience" in keys:
        keys.add("experiences")
    if "experiences" in keys:
        keys.add("experience")
    return frozenset(keys)


@dataclass
class SectionScores:
    """Multi-signal scores for a single text block."""
    education: float = 0.0
    experience: float = 0.0
    skills: float = 0.0
    projects: float = 0.0
    languages: float = 0.0
    contact: float = 0.0
    certifications: float = 0.0
    interests: float = 0.0
    summary: float = 0.0

    def best(self) -> str:
        """Return the section name with the highest score."""
        pairs = [
            (self.education, "education"),
            (self.experience, "experience"),
            (self.skills, "skills"),
            (self.projects, "projects"),
            (self.languages, "languages"),
            (self.contact, "contact"),
            (self.certifications, "certifications"),
            (self.interests, "interests"),
            (self.summary, "summary"),
        ]
        pairs.sort(key=lambda p: p[0], reverse=True)
        return pairs[0][1]

    def best_score(self) -> float:
        return max(
            self.education, self.experience, self.skills,
            self.projects, self.languages, self.contact,
            self.certifications, self.interests, self.summary,
        )

    def second_score(self) -> float:
        """Return the second-highest section score."""
        vals = sorted(self.as_dict().values(), reverse=True)
        return vals[1] if len(vals) > 1 else 0.0

    def margin(self) -> float:
        """Gap between best and second-best scores."""
        return self.best_score() - self.second_score()

    def is_confident(
        self,
        min_score: float = 0.35,
        min_margin: float = 0.10,
    ) -> bool:
        """Return True if the best section is confident enough to act on.

        Requires ``best_score >= min_score`` AND ``margin >= min_margin``.
        """
        return self.best_score() >= min_score and self.margin() >= min_margin

    def is_confident_override(self) -> bool:
        """Return True if confidence is high enough to override a locked section.

        Locked sections come from explicit headers in the original CV.
        Uses ``LOCKED_MIN_SCORE`` / ``LOCKED_MIN_MARGIN``.
        """
        return (self.best_score() >= LOCKED_MIN_SCORE
                and self.margin() >= LOCKED_MIN_MARGIN)

    def as_dict(self) -> Dict[str, float]:
        return {s: getattr(self, s) for s in SECTIONS}


# ═══════════════════════════════════════════════════════════════════════════
# SCORING ENGINE
# ═══════════════════════════════════════════════════════════════════════════

def score_text(text: str) -> SectionScores:
    """Score a text block against all candidate sections.

    Uses five signal families: keywords, dates, structure, bullets, length.
    Returns ``SectionScores`` with per-section float scores.
    """
    s = SectionScores()
    if not text or not text.strip():
        return s

    lines = text.strip().splitlines()
    words = text.split()
    word_count = len(words)
    line_count = len(lines)
    low = text.lower()

    # ── Signal: dates ──
    has_year = bool(_YEAR_RE.search(text))
    has_date_range = bool(_DATE_RANGE_RE.search(text))
    year_count = len(_YEAR_RE.findall(text))

    # ── Signal: bullets ──
    bullet_lines = sum(1 for l in lines if _BULLET_RE.match(l))
    bullet_ratio = bullet_lines / max(line_count, 1)

    # ── Signal: contact markers ──
    has_email = bool(_EMAIL_RE.search(text))
    has_phone = bool(_PHONE_RE.search(text))
    has_url = bool(_URL_RE.search(text))
    has_birth = bool(_BIRTH_RE.search(text))
    has_address = bool(_ADDRESS_RE.search(text))

    # ── Signal: keywords ──
    has_degree = bool(_DEGREE_RE.search(text))
    has_institution = bool(_INSTITUTION_RE.search(text))
    has_gpa = bool(_GPA_RE.search(text))
    has_company = bool(_COMPANY_RE.search(text))
    tech_count = len(_TECH_RE.findall(text))
    has_delimiters = bool(_SKILL_DELIM_RE.search(text))
    has_cert = bool(_CERT_RE.search(text))
    has_project = bool(_PROJECT_RE.search(text))
    has_interest = bool(_INTEREST_RE.search(text))

    lang_name_count = len(_CEFR_RE.findall(text))  # count proficiency signals
    has_cefr = lang_name_count > 0

    # ═════════════════════════════════════════════════════════════════════
    # EDUCATION scoring
    # ═════════════════════════════════════════════════════════════════════
    if has_degree:
        s.education += 0.35
    if has_institution:
        s.education += 0.25
    if has_gpa:
        s.education += 0.15
    if has_year:
        s.education += 0.10
    if bullet_ratio < 0.3:
        s.education += 0.05
    if word_count <= 30:
        s.education += 0.05
    # Penalty: bullets suggest experience, not education
    if bullet_ratio > 0.5:
        s.education -= 0.15

    # ═════════════════════════════════════════════════════════════════════
    # EXPERIENCE scoring
    # ═════════════════════════════════════════════════════════════════════
    if has_company:
        s.experience += 0.25
    if has_date_range:
        s.experience += 0.20
    elif has_year and year_count >= 2:
        s.experience += 0.15
    if bullet_ratio > 0.3:
        s.experience += 0.20
    if bullet_lines >= 2:
        s.experience += 0.10
    if word_count > 20:
        s.experience += 0.05
    if tech_count >= 1 and bullet_lines >= 1:
        s.experience += 0.05
    # Penalty: degree/institution without bullets is education
    if has_degree and has_institution and bullet_lines == 0:
        s.experience -= 0.20

    # ═════════════════════════════════════════════════════════════════════
    # SKILLS scoring
    # ═════════════════════════════════════════════════════════════════════
    if tech_count >= 2:
        s.skills += 0.30
    elif tech_count == 1:
        s.skills += 0.15
    if has_delimiters and tech_count >= 1:
        s.skills += 0.15
    if word_count <= 15:
        s.skills += 0.10
    if not has_year:
        s.skills += 0.05
    if bullet_ratio < 0.2:
        s.skills += 0.05
    # Penalty: long prose is not skills
    if word_count > 40:
        s.skills -= 0.15

    # ═════════════════════════════════════════════════════════════════════
    # PROJECTS scoring
    # ═════════════════════════════════════════════════════════════════════
    if has_project:
        s.projects += 0.25
    if has_url and tech_count >= 1:
        s.projects += 0.20
    if bullet_lines >= 1:
        s.projects += 0.10
    if tech_count >= 2:
        s.projects += 0.10
    if word_count >= 10:
        s.projects += 0.05

    # ═════════════════════════════════════════════════════════════════════
    # LANGUAGES scoring — purely structural (no language dictionaries)
    # ═════════════════════════════════════════════════════════════════════
    if has_cefr:
        s.languages += 0.35
    if lang_name_count >= 2:
        s.languages += 0.20
    if bool(_SUBSKILL_RE.search(text)):
        s.languages += 0.10
    if word_count <= 10:
        s.languages += 0.10
    if not has_year and not has_email and not has_phone:
        s.languages += 0.05
    # Short block with CEFR but no tech → strong signal
    if has_cefr and word_count <= 15 and tech_count == 0:
        s.languages += 0.10
    # Penalty: tech names → not languages
    if tech_count >= 2:
        s.languages -= 0.25

    # ═════════════════════════════════════════════════════════════════════
    # CONTACT scoring
    # ═════════════════════════════════════════════════════════════════════
    if has_email:
        s.contact += 0.30
    if has_phone:
        s.contact += 0.25
    if has_address:
        s.contact += 0.15
    if has_birth:
        s.contact += 0.10
    if has_url and not has_project and tech_count == 0:
        s.contact += 0.10
    if word_count <= 15:
        s.contact += 0.05
    # Penalty: bullets suggest experience
    if bullet_lines >= 2:
        s.contact -= 0.20

    # ═════════════════════════════════════════════════════════════════════
    # CERTIFICATIONS scoring
    # ═════════════════════════════════════════════════════════════════════
    if has_cert:
        s.certifications += 0.40
    if has_year:
        s.certifications += 0.10
    if word_count <= 20:
        s.certifications += 0.05

    # ═════════════════════════════════════════════════════════════════════
    # INTERESTS scoring
    # ═════════════════════════════════════════════════════════════════════
    if has_interest:
        s.interests += 0.35
    if word_count <= 10:
        s.interests += 0.10
    if not has_year and not has_email:
        s.interests += 0.05

    # ═════════════════════════════════════════════════════════════════════
    # SUMMARY scoring
    # ═════════════════════════════════════════════════════════════════════
    avg_words_per_line = word_count / max(line_count, 1)
    if avg_words_per_line > 8 and line_count <= 5:
        s.summary += 0.25
    if word_count >= 20 and bullet_ratio < 0.2:
        s.summary += 0.15
    if not has_year and not has_email and not has_phone:
        s.summary += 0.10

    return s


def score_dict_entry(entry: Dict) -> SectionScores:
    """Score a dict entry (experience / education / project style).

    Combines all string values + bullets into one text block, then also
    uses structural signals (field names, bullet count).
    """
    parts: List[str] = []
    for k, v in entry.items():
        if isinstance(v, str) and v.strip():
            parts.append(v)
        elif isinstance(v, list):
            for item in v:
                parts.append(str(item))
    text = " ".join(parts)
    scores = score_text(text)

    # ── Structural bonus: field names ──
    keys = set(entry.keys())
    if "degree" in keys or "school" in keys or "gpa" in keys:
        scores.education += 0.20
    if "company" in keys or "title" in keys:
        scores.experience += 0.15
    if "bullets" in keys and isinstance(entry.get("bullets"), list):
        bullet_count = len(entry["bullets"])
        if bullet_count >= 2:
            scores.experience += 0.15
        elif bullet_count == 0 and ("degree" in keys or "school" in keys):
            scores.education += 0.10
    if "issuer" in keys or "date" in keys:
        scores.certifications += 0.15

    return scores


# ═══════════════════════════════════════════════════════════════════════════
# BATCH SCORING FOR MISC ITEMS
# ═══════════════════════════════════════════════════════════════════════════

def classify_item(text: str, min_confidence: float = 0.35) -> str:
    """Classify a single text item into a section. Returns section name.

    If best score < *min_confidence* or margin < 0.10, returns ``"misc"``.
    """
    scores = score_text(text)
    if not scores.is_confident(min_score=min_confidence):
        return "misc"
    return scores.best()


def classify_dict_entry(entry: Dict, min_confidence: float = 0.35) -> str:
    """Classify a dict entry into a section. Returns section name."""
    scores = score_dict_entry(entry)
    if not scores.is_confident(min_score=min_confidence):
        return "misc"
    return scores.best()


def is_contact_data(text: str) -> bool:
    """Return True if *text* is primarily contact information.

    Used to strip contact lines from experience / education bullets.
    """
    scores = score_text(text)
    return (scores.contact >= 0.35
            and scores.contact - scores.second_score() >= 0.10
            if scores.best() == "contact"
            else scores.contact > scores.experience and scores.contact >= 0.35)


def is_education_data(text: str) -> bool:
    """Return True if text is primarily education-related."""
    scores = score_text(text)
    return (scores.education >= 0.35
            and scores.education - scores.experience >= 0.10)


def is_language_item(text: str) -> bool:
    """Return True if text is a spoken language entry (not tech/ISO code)."""
    scores = score_text(text)
    return (scores.languages >= 0.35
            and scores.languages - scores.skills >= 0.10)
