"""Input validation and sanitisation utilities.

Protects against prompt injection, path traversal, malformed input, and ZIP bombs.
"""

import logging
import re
import zipfile
from io import BytesIO

logger = logging.getLogger("security.validators")

# ── Path traversal patterns ─────────────────────────────────────────
_PATH_TRAVERSAL_RE = re.compile(r"\.\.|[/\\]|%2[eEfF]|%5[cC]|%2[fF]", re.IGNORECASE)

# ── Prompt injection markers ────────────────────────────────────────
_PROMPT_INJECTION_PATTERNS = [
    "system:",
    "assistant:",
    "<script>",
    "</script>",
    "<script",
    "javascript:",
    "onerror=",
    "onload=",
    "eval(",
    "prompt(",
    "ignore previous instructions",
    "ignore above",
    "disregard all",
    "you are now",
    "new instructions:",
]


def sanitize_text(text: str, field_name: str = "text", max_length: int = 100_000) -> str:
    """Sanitise user-supplied text.

    - Strips leading/trailing whitespace
    - Enforces max length
    - Removes prompt injection markers
    - Logs when injection is detected
    """
    if not isinstance(text, str):
        raise ValueError(f"{field_name} must be a string")

    text = text.strip()
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds maximum length ({max_length} chars)")

    text_lower = text.lower()
    for pattern in _PROMPT_INJECTION_PATTERNS:
        if pattern in text_lower:
            logger.warning(
                "security:prompt_injection_detected field=%s pattern=%s",
                field_name, pattern,
            )
            text = text.replace(pattern, "")
            text = text.replace(pattern.upper(), "")
            text = text.replace(pattern.title(), "")

    return text


def validate_user_id(user_id: str) -> str:
    """Validate and return a safe user ID.

    Only allows alphanumeric chars, hyphens, and underscores.
    """
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id is required")
    user_id = user_id.strip()
    if not re.match(r"^[a-zA-Z0-9\-_]+$", user_id):
        raise ValueError("Invalid user_id format")
    if len(user_id) > 128:
        raise ValueError("user_id too long")
    return user_id


def check_path_traversal(value: str, field_name: str = "key") -> None:
    """Reject any string containing path traversal sequences."""
    if _PATH_TRAVERSAL_RE.search(value):
        logger.warning("security:path_traversal field=%s value=%s", field_name, value[:80])
        raise ValueError(f"Invalid characters in {field_name}")


# ── CV detection heuristic ──────────────────────────────────────────
_CV_KEYWORDS = (
    # EN
    "experience", "education", "skills", "summary", "work history",
    "phone", "email", "linkedin", "github", "objective",
    "references", "certification", "languages", "proficiency",
    # TR
    "deneyim", "eğitim", "beceri", "özet", "telefon",
    # FR
    "expérience", "compétences", "formation",
    # DE
    "erfahrung", "ausbildung", "fähigkeiten",
    # ES
    "experiencia", "educación", "habilidades",
    # PT
    "experiência", "educação", "habilidades", "competências",
    # IT
    "esperienza", "istruzione", "competenze",
    # NL
    "ervaring", "opleiding", "vaardigheden",
    # RU
    "опыт", "образование", "навыки", "резюме",
    # PL
    "doświadczenie", "wykształcenie", "umiejętności",
    # SV/NO/DA
    "erfarenhet", "utbildning", "färdigheter",
    "erfaring", "utdanning", "uddannelse",
    # FI
    "kokemus", "koulutus", "taidot",
    # CS/HU/RO
    "zkušenosti", "vzdělání", "dovednosti",
    "tapasztalat", "végzettség", "készségek",
    "experiență", "educație", "competențe",
    # AR
    "الخبرة", "التعليم", "المهارات", "الشهادات",
    # ZH
    "工作经验", "教育", "技能", "个人简介",
    # JA
    "職歴", "学歴", "スキル", "資格",
    # KO
    "경력", "학력", "기술", "자격증",
    # HI
    "अनुभव", "शिक्षा", "कौशल",
    # ID
    "pengalaman", "pendidikan", "keahlian",
    # VI
    "kinh nghiệm", "học vấn", "kỹ năng",
    # TH
    "ประสบการณ์", "การศึกษา", "ทักษะ",
)

_NON_CV_KEYWORDS = (
    "introduction", "methodology", "diagram", "uml", "chapter",
    "abstract", "conclusion", "assignment", "report", "bibliography",
    "hypothesis", "literature review", "appendix", "table of contents",
    "acknowledgements", "thesis", "dissertation",
    # Task 5 — additional non-CV filter words
    "table of figures", "list of tables",
)

# ── Contact signal regex (shared with header safety) ─────────────────
_CV_CONTACT_RE = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
    r"|(?:\(?\+?\d[\d()\-\s.]{7,}\d)"
    r"|linkedin\.com|github\.com",
    re.IGNORECASE,
)

# Section-header–like lines (used for section counting)
_SECTION_LIKE_RE = re.compile(
    r"^\s*(?:experience|education|skills|summary|projects|certifications"
    r"|languages|contact|objective|profile|work history"
    r"|deneyim|eğitim|beceri|özet|expérience|compétences|formation"
    r"|erfahrung|ausbildung|experiencia|educación)\s*$",
    re.IGNORECASE,
)


def is_probably_cv(text: str, min_score: int = 2) -> bool:
    """Return True if *text* looks like a CV/resume.

    Combined scoring (Task 4):
      +1 per CV keyword found
      -1 per non-CV keyword found
      +2 if at least one contact signal (email / phone / linkedin)
      +1 per detected section-header line (up to +3)
      -3 if text is very short (< 100 chars) — too little content
    """
    lower = text.lower()
    score = sum(1 for k in _CV_KEYWORDS if k in lower)
    score -= sum(1 for k in _NON_CV_KEYWORDS if k in lower)

    # Contact signal bonus
    if _CV_CONTACT_RE.search(text):
        score += 2

    # Section-line count bonus (cap at +3)
    section_count = sum(
        1 for line in text.splitlines()
        if _SECTION_LIKE_RE.match(line)
    )
    score += min(section_count, 3)

    # Very short text penalty
    if len(text.strip()) < 100:
        score -= 3

    return score >= min_score


def validate_zip_safety(
    file_content: bytes,
    max_archive_bytes: int = 100 * 1024 * 1024,  # 100 MB
    max_files: int = 1000,
    max_compression_ratio: int = 10,
) -> None:
    """Validate ZIP file safety before extraction.
    
    Prevents ZIP bombs by checking:
    - Archive size doesn't exceed max_archive_bytes
    - File count doesn't exceed max_files
    - Compression ratio doesn't exceed max_compression_ratio
    
    Raises ValueError if validation fails.
    """
    if len(file_content) > max_archive_bytes:
        raise ValueError(
            f"ZIP archive too large: {len(file_content)} bytes "
            f"(max {max_archive_bytes} bytes)"
        )
    
    try:
        with zipfile.ZipFile(BytesIO(file_content), 'r') as zf:
            # Check file count
            file_list = zf.filelist
            if len(file_list) > max_files:
                raise ValueError(
                    f"ZIP contains too many files: {len(file_list)} "
                    f"(max {max_files})"
                )
            
            # Check compression ratios for each file
            for zinfo in file_list:
                if zinfo.compress_size > 0:
                    ratio = zinfo.file_size / zinfo.compress_size
                    if ratio > max_compression_ratio:
                        logger.warning(
                            "security:zip_bomb_detected file=%s ratio=%.1f max=%d",
                            zinfo.filename, ratio, max_compression_ratio
                        )
                        raise ValueError(
                            f"Suspicious compression ratio in {zinfo.filename}: "
                            f"{ratio:.1f}x (max {max_compression_ratio}x)"
                        )
    except zipfile.BadZipFile as e:
        raise ValueError(f"Invalid ZIP file: {e}")
