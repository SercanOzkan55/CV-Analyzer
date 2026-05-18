import difflib
import logging
import os
import re
import unicodedata
from typing import Dict, List

logger = logging.getLogger("app.cv_autofix")

from schemas.cv_model import CVModel
from schemas.cv_schema import CVSchema
from .ats_service import analyze_cv
from .skill_service import extract_skills
from . import rewrite_service
from .section_classifier import detect_sections as _block_detect_sections, classify_block
from services.schema_builder import build_schema


def _get_pipeline_agents():
    """Lazy import to avoid circular dependency with agents module."""
    from agents.extract_agent import extract_structured
    from agents.normalize_agent import normalize, get_section_order
    return extract_structured, normalize, get_section_order


MAX_INPUT_CHARS = int(os.getenv("CV_AUTOFIX_MAX_INPUT_CHARS", "60000") or "60000")
SUMMARY_MAX_CHARS = 500
MAX_HEADER_CONTACTS = 6
STRUCTURED_SCORE_TOLERANCE = 5.0
USE_PIPELINE = True
_MAX_PROJECT_ENTRIES = 200      # max project entries from parser loop
PROTECTED_SECTION_KEYS = {"education", "skills", "projects", "certifications", "languages"}

SECTION_ALIASES = {
    "summary": {
        "summary",
        "professional summary",
        "personal information",
        "profile",
        "about",
        "objective",
        "career summary",
        # TR
        "özet", "profil", "kişisel bilgiler", "kariyer özeti",
        # FR
        "résumé professionnel", "profil professionnel",
        # DE
        "zusammenfassung", "über mich", "kurzprofil",
        # ES
        "resumen profesional", "perfil profesional", "resumen", "perfil",
        # PT
        "resumo profissional", "resumo",
        # IT
        "profilo professionale", "riepilogo", "sommario",
        # NL
        "samenvatting", "profiel", "persoonlijk profiel",
        # RU
        "резюме", "профиль", "о себе",
        # PL
        "podsumowanie", "podsumowanie zawodowe", "profil zawodowy",
        # SV/NO/DA/FI
        "sammanfattning", "sammendrag", "yhteenveto", "profiili",
        # CS/HU/RO
        "shrnutí", "összefoglaló", "rezumat",
        # AR/ZH/JA/KO/HI
        "ملخص", "الملف الشخصي", "个人简介", "摘要", "概要",
        "プロフィール", "요약", "프로필", "सारांश",
        # ID/VI/TH
        "ringkasan", "tóm tắt", "สรุป", "โปรไฟล์",
    },
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        # TR
        "deneyim", "iş deneyimi", "mesleki deneyim",
        # FR
        "expérience", "expérience professionnelle",
        # DE
        "erfahrung", "berufserfahrung",
        # ES
        "experiencia", "experiencia laboral", "experiencia profesional",
        # PT
        "experiência", "experiência profissional",
        # IT
        "esperienza", "esperienza lavorativa",
        # NL
        "ervaring", "werkervaring",
        # RU
        "опыт", "опыт работы",
        # PL
        "doświadczenie", "doświadczenie zawodowe",
        # SV/NO/DA/FI
        "erfarenhet", "erfaring", "kokemus", "työkokemus",
        # CS/HU/RO
        "zkušenosti", "tapasztalat", "experiență",
        # AR/ZH/JA/KO/HI
        "الخبرة", "الخبرة المهنية", "工作经验", "工作经历",
        "職歴", "경력", "경험", "अनुभव",
        # ID/VI/TH
        "pengalaman", "pengalaman kerja", "kinh nghiệm",
        "ประสบการณ์",
    },
    "education": {
        "education", "academic background", "qualifications",
        # TR
        "eğitim", "akademik geçmiş",
        # FR
        "formation", "études",
        # DE
        "ausbildung", "bildung", "studium",
        # ES
        "educación", "formación",
        # PT
        "educação", "formação acadêmica",
        # IT
        "istruzione", "formazione",
        # NL
        "opleiding", "onderwijs",
        # RU
        "образование",
        # PL
        "wykształcenie", "edukacja",
        # SV/NO/DA/FI
        "utbildning", "utdanning", "uddannelse", "koulutus",
        # CS/HU/RO
        "vzdělání", "végzettség", "educație", "studii",
        # AR/ZH/JA/KO/HI
        "التعليم", "教育", "学历", "学歴", "학력", "शिक्षा",
        # ID/VI/TH
        "pendidikan", "học vấn", "การศึกษา",
    },
    "skills": {
        "skills",
        "technical skills",
        "core competencies",
        "competencies",
        "technologies",
        # TR
        "beceriler", "yetenekler", "teknik beceriler", "yetkinlikler",
        # FR
        "compétences", "compétences techniques",
        # DE
        "fähigkeiten", "kenntnisse", "kompetenzen",
        # ES
        "habilidades", "competencias",
        # PT
        "competências",
        # IT
        "competenze", "abilità",
        # NL
        "vaardigheden", "competenties",
        # RU
        "навыки", "умения", "компетенции",
        # PL
        "umiejętności", "kompetencje",
        # SV/NO/DA/FI
        "färdigheter", "ferdigheter", "færdigheder", "taidot", "osaaminen",
        # CS/HU/RO
        "dovednosti", "készségek", "competențe",
        # AR/ZH/JA/KO/HI
        "المهارات", "技能", "スキル", "기술", "कौशल",
        # ID/VI/TH
        "keahlian", "keterampilan", "kỹ năng", "ทักษะ",
    },
    "projects": {
        "project", "projects", "project experience", "personal projects",
        # TR
        "projeler",
        # FR
        "projets",
        # DE
        "projekte",
        # ES
        "proyectos",
        # PT/IT/NL
        "projetos", "progetti", "projecten",
        # RU
        "проекты",
        # PL/CS/HU
        "projekty", "projektek",
        # SV/DA/NO/FI/RO
        "projekter", "prosjekter", "projektit", "proiecte",
        # AR/ZH/JA/KO/HI
        "المشاريع", "项目", "プロジェクト", "프로젝트", "परियोजनाएं",
        # ID/VI/TH
        "proyek", "dự án", "โครงการ",
    },
    "certifications": {
        "certifications", "certificates", "licenses",
        # TR
        "sertifikalar", "belgeler",
        # FR
        "diplômes",
        # DE
        "zertifizierungen", "zertifikate",
        # ES
        "certificaciones",
        # PT
        "certificações",
        # IT/NL
        "certificazioni", "certificeringen",
        # RU
        "сертификаты",
        # PL/CS/HU
        "certyfikaty", "certifikáty", "tanúsítványok",
        # SV/NO/DA/FI/RO
        "certifieringar", "sertifiseringer", "sertifikaatit", "certificări",
        # AR/ZH/JA/KO/HI
        "الشهادات", "证书", "資格", "자격증", "प्रमाणपत्र",
        # ID/VI/TH
        "sertifikasi", "chứng chỉ", "ใบรับรอง",
    },
    "languages": {
        "languages", "language skills",
        # TR
        "diller", "yabancı diller",
        # FR
        "langues",
        # DE
        "sprachen",
        # ES/PT
        "idiomas",
        # IT
        "lingue",
        # NL
        "talen",
        # RU
        "языки",
        # PL
        "języki",
        # SV/NO
        "språk",
        # DA
        "sprog",
        # FI
        "kielet",
        # CS/HU
        "jazyky", "nyelvek",
        # RO
        "limbi",
        # AR/ZH/JA/KO/HI
        "اللغات", "语言", "言語", "언어", "भाषाएं",
        # ID/VI/TH
        "bahasa", "ngôn ngữ", "ภาษา",
    },
    "contact": {
        "contact", "contact information", "communication",
        # TR
        "iletişim",
        # FR
        "coordonnées",
        # DE
        "kontakt", "kontaktdaten",
        # ES
        "contacto",
        # PT/IT
        "contato", "contatto",
        # NL
        "contactgegevens",
        # RU
        "контакты",
        # PL
        "dane kontaktowe",
        # FI
        "yhteystiedot",
        # HU
        "kapcsolat", "elérhetőség",
        # AR/ZH/JA/KO/HI
        "الاتصال", "联系方式", "連絡先", "연락처", "संपर्क",
        # ID/VI/TH
        "kontak", "liên hệ", "ติดต่อ",
    },
    "interests": {
        "interests", "hobbies", "personal interests",
        # TR
        "ilgi alanları", "hobiler",
        # FR
        "centres d'intérêt", "loisirs",
        # DE
        "interessen", "hobbys",
        # ES
        "intereses", "aficiones",
        # PT/IT
        "interesses", "interessi",
        # NL
        "hobby's",
        # RU
        "интересы", "хобби",
        # PL
        "zainteresowania",
        # SV/NO/DA
        "intressen", "interesser",
        # FI
        "kiinnostukset", "harrastukset",
        # CS/HU/RO
        "zájmy", "érdeklődés", "interese",
        # AR/ZH/JA/KO/HI
        "الاهتمامات", "兴趣", "趣味", "취미", "रुचियां",
        # ID/VI/TH
        "minat", "sở thích", "ความสนใจ",
    },
}

# ── Pre-indexed alias lookup for fuzzy matching (Task 8) ──────────────
_AUTOFIX_FLAT_ALIASES: dict[str, str] = {}
for _canon, _als in SECTION_ALIASES.items():
    for _a in _als:
        _AUTOFIX_FLAT_ALIASES[_a] = _canon
_AUTOFIX_ALIAS_INDEX: dict[str, list[str]] = {}
for _a in _AUTOFIX_FLAT_ALIASES:
    if _a:
        _AUTOFIX_ALIAS_INDEX.setdefault(_a[0], []).append(_a)

NOISE_SECTION_ALIASES = {
    "references",
    "personal details",
    "marital status",
    "date of birth",
    "birth date",
    "nationality",
    "photo",
}

SECTION_ORDER = [
    "summary",
    "experience",
    "projects",
    "education",
    "skills",
    "certifications",
    "languages",
    "interests",
]

SECTION_TITLES = {
    "summary": "PROFESSIONAL SUMMARY",
    "experience": "EXPERIENCE",
    "education": "EDUCATION",
    "skills": "SKILLS",
    "certifications": "CERTIFICATIONS",
    "projects": "PROJECTS",
    "languages": "LANGUAGES",
    "interests": "INTERESTS",
}

# Multilingual section titles — used when CV language is known
SECTION_TITLES_I18N: dict[str, dict[str, str]] = {
    "summary": {
        "en": "PROFESSIONAL SUMMARY", "tr": "PROFESYONEL ÖZET",
        "fr": "RÉSUMÉ PROFESSIONNEL", "de": "ZUSAMMENFASSUNG",
        "es": "RESUMEN PROFESIONAL", "pt": "RESUMO PROFISSIONAL",
        "it": "PROFILO PROFESSIONALE", "nl": "SAMENVATTING",
        "ru": "РЕЗЮМЕ", "pl": "PODSUMOWANIE ZAWODOWE",
        "sv": "SAMMANFATTNING", "no": "SAMMENDRAG", "da": "RESUMÉ",
        "fi": "YHTEENVETO", "cs": "SHRNUTÍ", "hu": "ÖSSZEFOGLALÓ",
        "ro": "REZUMAT", "ar": "الملخص", "zh": "个人简介",
        "ja": "職務要約", "ko": "요약", "hi": "सारांश",
        "id": "RINGKASAN", "vi": "TÓM TẮT", "th": "สรุป",
    },
    "experience": {
        "en": "EXPERIENCE", "tr": "DENEYİM",
        "fr": "EXPÉRIENCE", "de": "ERFAHRUNG",
        "es": "EXPERIENCIA", "pt": "EXPERIÊNCIA",
        "it": "ESPERIENZA", "nl": "ERVARING",
        "ru": "ОПЫТ РАБОТЫ", "pl": "DOŚWIADCZENIE",
        "sv": "ERFARENHET", "no": "ERFARING", "da": "ERFARING",
        "fi": "TYÖKOKEMUS", "cs": "ZKUŠENOSTI", "hu": "TAPASZTALAT",
        "ro": "EXPERIENȚĂ", "ar": "الخبرة", "zh": "工作经验",
        "ja": "職歴", "ko": "경력", "hi": "अनुभव",
        "id": "PENGALAMAN", "vi": "KINH NGHIỆM", "th": "ประสบการณ์",
    },
    "education": {
        "en": "EDUCATION", "tr": "EĞİTİM",
        "fr": "FORMATION", "de": "AUSBILDUNG",
        "es": "EDUCACIÓN", "pt": "EDUCAÇÃO",
        "it": "ISTRUZIONE", "nl": "OPLEIDING",
        "ru": "ОБРАЗОВАНИЕ", "pl": "WYKSZTAŁCENIE",
        "sv": "UTBILDNING", "no": "UTDANNING", "da": "UDDANNELSE",
        "fi": "KOULUTUS", "cs": "VZDĚLÁNÍ", "hu": "VÉGZETTSÉG",
        "ro": "EDUCAȚIE", "ar": "التعليم", "zh": "教育",
        "ja": "学歴", "ko": "학력", "hi": "शिक्षा",
        "id": "PENDIDIKAN", "vi": "HỌC VẤN", "th": "การศึกษา",
    },
    "skills": {
        "en": "SKILLS", "tr": "BECERİLER",
        "fr": "COMPÉTENCES", "de": "FÄHIGKEITEN",
        "es": "HABILIDADES", "pt": "HABILIDADES",
        "it": "COMPETENZE", "nl": "VAARDIGHEDEN",
        "ru": "НАВЫКИ", "pl": "UMIEJĘTNOŚCI",
        "sv": "FÄRDIGHETER", "no": "FERDIGHETER", "da": "FÆRDIGHEDER",
        "fi": "TAIDOT", "cs": "DOVEDNOSTI", "hu": "KÉSZSÉGEK",
        "ro": "COMPETENȚE", "ar": "المهارات", "zh": "技能",
        "ja": "スキル", "ko": "기술", "hi": "कौशल",
        "id": "KEAHLIAN", "vi": "KỸ NĂNG", "th": "ทักษะ",
    },
    "certifications": {
        "en": "CERTIFICATIONS", "tr": "SERTİFİKALAR",
        "fr": "CERTIFICATIONS", "de": "ZERTIFIZIERUNGEN",
        "es": "CERTIFICACIONES", "pt": "CERTIFICAÇÕES",
        "it": "CERTIFICAZIONI", "nl": "CERTIFICERINGEN",
        "ru": "СЕРТИФИКАТЫ", "pl": "CERTYFIKATY",
        "sv": "CERTIFIERINGAR", "no": "SERTIFISERINGER", "da": "CERTIFICERINGER",
        "fi": "SERTIFIKAATIT", "cs": "CERTIFIKÁTY", "hu": "TANÚSÍTVÁNYOK",
        "ro": "CERTIFICĂRI", "ar": "الشهادات", "zh": "证书",
        "ja": "資格", "ko": "자격증", "hi": "प्रमाणपत्र",
        "id": "SERTIFIKASI", "vi": "CHỨNG CHỈ", "th": "ใบรับรอง",
    },
    "projects": {
        "en": "PROJECTS", "tr": "PROJELER",
        "fr": "PROJETS", "de": "PROJEKTE",
        "es": "PROYECTOS", "pt": "PROJETOS",
        "it": "PROGETTI", "nl": "PROJECTEN",
        "ru": "ПРОЕКТЫ", "pl": "PROJEKTY",
        "sv": "PROJEKT", "no": "PROSJEKTER", "da": "PROJEKTER",
        "fi": "PROJEKTIT", "cs": "PROJEKTY", "hu": "PROJEKTEK",
        "ro": "PROIECTE", "ar": "المشاريع", "zh": "项目",
        "ja": "プロジェクト", "ko": "프로젝트", "hi": "परियोजनाएं",
        "id": "PROYEK", "vi": "DỰ ÁN", "th": "โครงการ",
    },
    "languages": {
        "en": "LANGUAGES", "tr": "DİLLER",
        "fr": "LANGUES", "de": "SPRACHEN",
        "es": "IDIOMAS", "pt": "IDIOMAS",
        "it": "LINGUE", "nl": "TALEN",
        "ru": "ЯЗЫКИ", "pl": "JĘZYKI",
        "sv": "SPRÅK", "no": "SPRÅK", "da": "SPROG",
        "fi": "KIELET", "cs": "JAZYKY", "hu": "NYELVEK",
        "ro": "LIMBI", "ar": "اللغات", "zh": "语言",
        "ja": "言語", "ko": "언어", "hi": "भाषाएं",
        "id": "BAHASA", "vi": "NGÔN NGỮ", "th": "ภาษา",
    },
    "interests": {
        "en": "INTERESTS", "tr": "İLGİ ALANLARI",
        "fr": "CENTRES D'INTÉRÊT", "de": "INTERESSEN",
        "es": "INTERESES", "pt": "INTERESSES",
        "it": "INTERESSI", "nl": "INTERESSES",
        "ru": "ИНТЕРЕСЫ", "pl": "ZAINTERESOWANIA",
        "sv": "INTRESSEN", "no": "INTERESSER", "da": "INTERESSER",
        "fi": "KIINNOSTUKSET", "cs": "ZÁJMY", "hu": "ÉRDEKLŐDÉS",
        "ro": "INTERESE", "ar": "الاهتمامات", "zh": "兴趣",
        "ja": "趣味", "ko": "관심사", "hi": "रुचियां",
        "id": "MINAT", "vi": "SỞ THÍCH", "th": "ความสนใจ",
    },
}


def get_section_title(key: str, lang: str = "en") -> str:
    """Return localized section title. Falls back to English, then SECTION_TITLES."""
    i18n = SECTION_TITLES_I18N.get(key, {})
    return i18n.get(lang, i18n.get("en", SECTION_TITLES.get(key, key.upper())))


def _guard_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        value = str(value or "")
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(value) > MAX_INPUT_CHARS:
        value = value[:MAX_INPUT_CHARS]
    if not value:
        raise ValueError(f"{field_name} cannot be empty")
    return value


def _normalize_heading(line: str) -> str:
    normalized = re.sub(r"[^\w\s]|[\d_]", " ", line, flags=re.UNICODE).lower()
    return re.sub(r"\s+", " ", normalized).strip()


def _canonical_section(line: str) -> str | None:
    heading = _normalize_heading(line)
    if not heading:
        return None
    for canonical, aliases in SECTION_ALIASES.items():
        if heading in aliases:
            return canonical
    # Fuzzy fallback for typos — e.g. "sumary" → "summary"
    # Only fuzzy-match headings with length >= 4 to avoid false positives
    if len(heading) < 4:
        return None
    candidates = _AUTOFIX_ALIAS_INDEX.get(heading[0], [])
    if not candidates:
        return None
    matches = difflib.get_close_matches(heading, candidates, n=1, cutoff=0.82)
    if matches:
        return _AUTOFIX_FLAT_ALIASES[matches[0]]
    return None


def _noise_section(line: str) -> str | None:
    heading = _normalize_heading(line)
    if heading in NOISE_SECTION_ALIASES:
        return heading
    return None


def _clean_lines(text: str) -> List[str]:
    lines = []
    for line in text.split("\n"):
        clean = unicodedata.normalize("NFC", line)
        clean = re.sub(r"[ \t]+", " ", clean).strip()
        clean = re.sub(r"([A-Z][A-Za-z0-9]+)-\s+([A-Z][A-Za-z0-9]+)", r"\1-\2", clean)
        clean = re.sub(r"([a-z0-9])\-\s+([a-z0-9])", r"\1\2", clean)
        clean = re.sub(r"([A-Za-z])\(", r"\1 (", clean)
        lines.append(clean)
    compact: List[str] = []
    previous_blank = False
    for line in lines:
        if not line:
            if not previous_blank:
                compact.append("")
            previous_blank = True
            continue
        compact.append(line)
        previous_blank = False
    return compact


# ── Turkish → ASCII mapping for English CVs ──
_TR_TO_EN = str.maketrans({
    "İ": "I", "ı": "i",
    "Ğ": "G", "ğ": "g",
    "Ş": "S", "ş": "s",
    "Ç": "C", "ç": "c",
    "Ö": "O", "ö": "o",
    "Ü": "U", "ü": "u",
})
_TR_KEEP_LOWER = {"istanbul", "özkan", "kuşcu", "üsküdar", "kadıköy", "beşiktaş", "şişli"}
_COMMON_TECH_SPELLING_FIXES = (
    (re.compile(r"\bJAVASCRIPT\b", re.I), "JavaScript"),
    (re.compile(r"\bTYPESCRIPT\b", re.I), "TypeScript"),
    (re.compile(r"\bTYPECRIPT\b", re.I), "TypeScript"),
    (re.compile(r"\bNEXT\s+JS\b", re.I), "Next.js"),
    (re.compile(r"\bNODE\s+JS\b", re.I), "Node.js"),
)


def _polish_text(text: str, lang: str = "en") -> str:
    """Fix common typos and formatting issues in CV text.

    When the CV is in English:
     - Replace Turkish İ/ı/ğ/ş/ç/ö/ü with ASCII equivalents (except in proper nouns)
     - Fix missing space after period/comma
     - Fix double punctuation
     - Normalize bullet characters
     - Ensure bullet lines start with uppercase
    """
    lines = text.split("\n")
    out: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue

        # ── Turkish char fix (English CVs only) ──
        if lang == "en":
            words = stripped.split()
            fixed_words: list[str] = []
            for w in words:
                bare = w.lower().rstrip(",.;:")
                if bare in _TR_KEEP_LOWER:
                    fixed_words.append(w)
                else:
                    fixed_words.append(w.translate(_TR_TO_EN))
            stripped = " ".join(fixed_words)

        # ── Punctuation fixes ──
        stripped = re.sub(r"\.{2,}", ".", stripped)
        stripped = re.sub(r",{2,}", ",", stripped)
        # Missing space after period (but not in URLs, emails, numbers)
        stripped = re.sub(r"(?<=[a-zA-Z)])\.(?=[A-Z])", ". ", stripped)
        # Missing space after comma (but not in numbers like 1,000)
        stripped = re.sub(r",(?=[A-Za-z])", ", ", stripped)
        # PDF line wraps often leave "hands- on" / "real- world" artifacts.
        stripped = re.sub(r"\b([A-Za-z]{3,})-\s+(on|world|time|stack|end|based|level)\b", r"\1-\2", stripped, flags=re.I)
        for pattern, replacement in _COMMON_TECH_SPELLING_FIXES:
            stripped = pattern.sub(replacement, stripped)
        # Normalize bullet chars: ▪ ◦ ◆ ▸ ► → •
        stripped = re.sub(r"^[\u25AA\u25E6\u25C6\u25B8\u25BA]\s*", "• ", stripped)
        # Ensure bullet lines start with uppercase
        stripped = re.sub(r"^([-•–]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), stripped)

        out.append(stripped)

    return "\n".join(out)


def _parse_sections(cv_text: str) -> tuple[list[str], Dict[str, List[str]], List[str]]:
    header_lines: List[str] = []
    sections: Dict[str, List[str]] = {key: [] for key in SECTION_ALIASES}
    dropped_sections: List[str] = []
    current: str | None = None
    dropping = False

    for raw_line in _clean_lines(cv_text):
        if not raw_line:
            if current and not dropping and sections[current] and sections[current][-1] != "":
                sections[current].append("")
            continue

        canonical = _canonical_section(raw_line)
        if canonical:
            if canonical in {"references", "interests"}:
                dropped_sections.append(canonical)
                current = None
                dropping = True
                continue
            current = canonical
            dropping = False
            continue

        noise = _noise_section(raw_line)
        if noise:
            dropped_sections.append(noise)
            current = None
            dropping = True
            continue

        if dropping:
            continue
        if current is None:
            header_lines.append(raw_line)
        else:
            sections[current].append(raw_line)

    # ── Block-based fallback ──
    # If alias matching left too much content in header_lines and few real
    # sections were found, run the NLP-style block classifier on the
    # *entire* text and merge results.
    filled_sections = sum(
        1 for key, vals in sections.items()
        if key != "contact" and any((v or "").strip() for v in vals)
    )
    # Heuristic: if fewer than 2 sections were recognized AND header_lines
    # contain a lot of content, the alias matcher missed the sections.
    header_content_lines = [l for l in header_lines if l.strip()]
    if filled_sections < 2 and len(header_content_lines) > 4:
        block_sections, _, _ = _block_detect_sections(cv_text)
        # Map block classifier output into our sections dict
        _BLOCK_TO_ALIAS = {
            "summary": "summary",
            "experience": "experience",
            "education": "education",
            "skills": "skills",
            "projects": "projects",
            "certifications": "certifications",
            "languages": "languages",
            "contact": "contact",
        }
        new_header: List[str] = []
        for block_label, block_lines in block_sections.items():
            alias_key = _BLOCK_TO_ALIAS.get(block_label)
            if alias_key and alias_key in sections:
                # Only add if alias pass didn't already populate this section
                existing = [v for v in sections[alias_key] if (v or "").strip()]
                if not existing:
                    sections[alias_key] = list(block_lines)
            elif block_label == "header":
                new_header.extend(block_lines)
            elif block_label == "noise":
                dropped_sections.append(block_label)
            # else: ignore unknown labels

        # Replace header_lines with block classifier's header output
        if new_header:
            header_lines = new_header

    # ── Header safety (Task 3): if header has many lines but no contact
    #    signal, the header area is likely misclassified content.  Move
    #    non-contact header content into the first detected section.  ──
    if len(header_lines) > 6 and not _header_has_contact(header_lines):
        first_section = next(
            (k for k in ("summary", "experience", "education")
             if any((v or "").strip() for v in sections.get(k, []))),
            None,
        )
        if first_section:
            sections[first_section] = header_lines + sections[first_section]
            header_lines = []

    return header_lines, sections, sorted(set(dropped_sections))


# ── Name detection helper ─────────────────────────────────────────────────

_NAME_DISQUALIFY_RE = re.compile(
    r"@|https?://|linkedin|github|\.com|\.io|\d|[\(\)\[\]{}]|:",
    re.I,
)
_TITLE_HINT_WORDS = {
    "engineer", "developer", "student", "manager", "analyst", "specialist",
    "consultant", "architect", "designer", "intern", "lead", "director",
    "officer", "professor", "scientist", "coordinator", "researcher",
    "instructor", "teacher", "programmer", "administrator", "trainer",
    "senior", "junior", "associate", "assistant", "head", "chief",
    "freelance", "full-stack", "frontend", "backend", "devops", "data",
    "software", "web", "mobile", "cloud", "cyber", "machine learning",
    "ai", "qa", "quality",
    # institutional / academic keywords
    "university", "department", "faculty", "computer", "engineering",
    "science", "technology", "academy", "school",
}
_SECTION_HEADER_WORDS = {
    "profile", "summary", "objective", "about", "personal",
    "information", "contact", "details", "experience", "education",
    "skills", "projects", "languages", "interests", "references",
    "certifications", "achievements", "publications", "activities",
    "hobbies", "awards", "volunteer", "work",
}
_TRAILING_TITLE_RE = re.compile(
    r"\b(?:student|engineer|developer|intern|manager|specialist)\s*$",
    re.I,
)


def _looks_like_person_name(text: str) -> bool:
    """Return True if *text* looks like a person name."""
    text = text.strip()
    if not text:
        return False
    if _NAME_DISQUALIFY_RE.search(text):
        return False
    words = text.split()
    if not (2 <= len(words) <= 4):
        return False
    # At least one word must start with uppercase
    if not any(w[0].isupper() for w in words if w):
        return False
    # Must not look like a job title or institution
    lowered = text.lower()
    if any(hint in lowered for hint in _TITLE_HINT_WORDS):
        return False
    # Reject if ANY word is a section-header keyword
    if any(w.lower().rstrip(":") in _SECTION_HEADER_WORDS for w in words):
        return False
    # Reject lines ending with a title word (e.g. "Ali Yilmaz Student")
    if _TRAILING_TITLE_RE.search(text):
        return False
    return True


def guess_name_from_lines(lines: list[str], limit: int = 5) -> str | None:
    """Scan the first *limit* lines for a person name pattern.

    Priority: valid name → shortest → closest to top.
    Also rejects lines that look like section headers.
    """
    candidates: list[tuple[int, str]] = []
    for idx, line in enumerate((lines or [])[:limit]):
        candidate = (line or "").strip()
        if not candidate:
            continue
        if _looks_like_person_name(candidate):
            candidates.append((idx, candidate))
    if not candidates:
        return None
    # Sort: shortest first, then closest to top
    candidates.sort(key=lambda t: (len(t[1].split()), t[0]))
    return candidates[0][1]


# ── Header safety: reject header blocks without any contact signal ──
_CONTACT_SIGNAL_RE = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"        # email
    r"|(?:\(?\+?\d[\d()\-\s.]{7,}\d)"                  # phone
    r"|linkedin\.com|github\.com"                       # profile URLs
    r"|https?://",                                      # any URL
    re.IGNORECASE,
)


def _header_has_contact(lines: list[str]) -> bool:
    """Return True if at least one line contains an email, phone, or profile URL."""
    return any(_CONTACT_SIGNAL_RE.search(line) for line in lines if line)


def _extract_contact_block(
    header_lines: List[str],
    explicit_lines: List[str],
) -> tuple[str | None, List[str], List[str], List[str]]:
    lines = [line for line in header_lines + explicit_lines if line]
    name = None
    title_lines: List[str] = []
    contacts: List[str] = []
    leftovers: List[str] = []
    title_hint_words = (
        "engineer", "developer", "student", "manager", "analyst", "specialist", "consultant",
        "architect", "designer", "intern", "lead", "director", "officer", "professor",
    )

    # Language-agnostic contact-label pattern: any short label followed by a colon
    # The actual contact detection happens via email/phone/URL extraction on the value part
    _CONTACT_LABEL_RE = re.compile(
        r"^\s*[\w\s\-]{1,30}\s*:\s*",
        re.I | re.UNICODE,
    )

    # Address / location label prefixes (multilingual)
    _ADDRESS_LABEL_RE = re.compile(
        r"^\s*(?:adres|address|location|adress[ei]?|direcci[oó]n|ubicaci[oó]n"
        r"|standort|lieu|indirizzo|morada|lokasyon|konum)"
        r"\s*:\s*",
        re.I | re.UNICODE,
    )

    def _extract_email(line: str) -> str | None:
        match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", line, re.I)
        return match.group(0) if match else None

    def _extract_phone(line: str) -> str | None:
        match = re.search(r"(?:\(?\+?\d[\d()\-. ]{7,}\d)", line)
        if not match:
            return None
        val = match.group(0).strip()
        # Reject date-like matches: dd.mm.yyyy, yyyy.mm.dd, mm/dd/yyyy etc.
        if re.fullmatch(r"\d{1,4}[./]\d{1,2}[./]\d{1,4}", val):
            return None
        return val

    def _extract_url(line: str) -> str | None:
        match = re.search(r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com|[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?:/\S*)?", line, re.I)
        if not match:
            return None
        url = match.group(0).strip().rstrip(",.;")
        if url.lower().startswith(("linkedin.com", "github.com", "www.")):
            url = f"https://{url}"
        return url

    for index, line in enumerate(lines):
        # First few lines: check if it looks like a person name
        # Guard: never accept phone/email/URL as name
        if index <= 2 and name is None and _looks_like_person_name(line):
            if not re.search(r"@|https?://|\(?\+?\d[\d()\-\s.]{7,}\d", line, re.I):
                name = line
                continue

        # Detect labeled contact lines (e.g. "Phone: ...", "Email: ...")
        label_match = _CONTACT_LABEL_RE.match(line)
        if label_match:
            value_part = line[label_match.end():].strip()
            if value_part:
                email = _extract_email(value_part)
                phone = _extract_phone(value_part)
                url = _extract_url(value_part)
                if email:
                    contacts.append(email)
                    continue
                elif phone:
                    contacts.append(phone)
                    continue
                elif url:
                    contacts.append(url)
                    continue
                # Address label → strip prefix and put value in leftovers
                if _ADDRESS_LABEL_RE.match(line):
                    leftovers.append(value_part)
                    continue
                # No contact signal found — not a contact line, fall through

        tokenized = [part.strip() for part in re.split(r"\s*[|;]\s*", line) if part.strip()]
        if not tokenized:
            tokenized = [line]

        consumed_any = False
        unconsumed_tokens: List[str] = []
        for token in tokenized:
            email = _extract_email(token)
            if email:
                contacts.append(email)
                consumed_any = True
                continue
            phone = _extract_phone(token)
            if phone:
                contacts.append(phone)
                consumed_any = True
                continue
            if any(key in token.lower() for key in ("linkedin", "github", "portfolio", "http://", "https://", ".com", ".io")):
                url = _extract_url(token)
                contacts.append(url or token)
                consumed_any = True
                continue
            unconsumed_tokens.append(token)

        # For partially-consumed lines, keep unconsumed tokens as leftovers
        # (e.g. "Istanbul, Turkey" from "email | phone | Istanbul, Turkey")
        if consumed_any and unconsumed_tokens:
            leftovers.extend(unconsumed_tokens)

        if not consumed_any:
            lowered_line = line.lower()
            looks_like_title = (
                len(line.split()) <= 10
                and not re.search(r"\d|@", line)
                and any(word in lowered_line for word in title_hint_words)
            )
            if looks_like_title:
                title_lines.append(line)
            else:
                leftovers.append(line)

    deduped_contacts: List[str] = []
    seen = set()
    for value in contacts:
        key = value.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped_contacts.append(value.strip())

    deduped_titles: List[str] = []
    title_seen = set()
    for value in title_lines:
        key = value.strip().lower()
        if not key or key in title_seen:
            continue
        title_seen.add(key)
        deduped_titles.append(value.strip())

    # FIX 1: If name still empty, scan header lines for a name pattern
    if not name:
        name = guess_name_from_lines(header_lines)

    # Guard: name must never be a phone, email, or URL
    if name and re.search(r"@|https?://|\(?\+?\d[\d()\-\s.]{7,}\d", name, re.I):
        # Demote to contacts and clear name
        contacts.append(name)
        name = guess_name_from_lines(header_lines)
        if name and re.search(r"@|https?://|\(?\+?\d[\d()\-\s.]{7,}\d", name, re.I):
            name = None

    # Remove name from leftovers (it may have been added before guess_name found it)
    if name:
        name_lower = name.strip().lower()
        leftovers = [lo for lo in leftovers if lo.strip().lower() != name_lower]

    # Filter garbage leftovers (single chars, stray symbols)
    leftovers = [lo for lo in leftovers if len(lo.strip()) >= 2]

    return name, deduped_titles, deduped_contacts, leftovers


def _extract_skill_names(skill_result: dict) -> List[str]:
    if not isinstance(skill_result, dict):
        return []
    if "found" in skill_result:
        found = skill_result.get("found") or []
        return sorted(str(item).strip() for item in found if str(item).strip())

    values: List[str] = []
    for key in ("all_skills", "technical_skills", "soft_skills"):
        raw = skill_result.get(key) or []
        values.extend(str(item).strip() for item in raw if str(item).strip())
    deduped = []
    seen = set()
    for item in values:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


def _sentences_from_line(line: str) -> List[str]:
    if re.match(r"^\s*[-*•]\s*", line):
        return [re.sub(r"^\s*[-*•]\s*", "", line).strip()]
    if len(line) < 90:
        return [line]
    parts = re.split(r"(?<=[.!?])\s+", line)
    return [part.strip(" -") for part in parts if part.strip(" -")]


def _normalize_experience(lines: List[str]) -> List[str]:
    result: List[str] = []
    for line in lines:
        if not line:
            continue
        stripped = line.strip()
        if re.match(r"^\s*[-*•]\s*", stripped):
            result.append(stripped)
            continue
        if re.search(r"\b(?:19|20)\d{2}\b", stripped) or "present" in stripped.lower():
            result.append(line)
            continue
        if len(stripped.split()) <= 12:
            result.append(line)
            continue
        for sentence in _sentences_from_line(stripped):
            if sentence:
                result.append(sentence)
    return result


def _normalize_list_section(lines: List[str]) -> List[str]:
    items: List[str] = []
    for line in lines:
        if not line:
            continue
        parts = re.split(r"\s*[|,/;]\s*", line)
        if len(parts) == 1:
            parts = re.split(r"\s{2,}", line)
        for part in parts:
            cleaned = part.strip(" -*•")
            if cleaned:
                items.append(cleaned)
    deduped: List[str] = []
    seen = set()
    for item in items:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


# ── Sub-skill aware language normalizer ─────────────────────────────────
_LEVELS_PATTERN = (
    r"(A[12]|B[12]|C[12]"
    r"|native|fluent|advanced|intermediate|beginner|proficient|basic|elementary"
    r"|ana\s*dil|ileri|orta|ba[sş]lang[iı][cç]"
    r"|langue\s*maternelle|courant|avanc[eé]|interm[eé]diaire|d[eé]butant"
    r"|muttersprache|flie[ßs]end|verhandlungssicher|fortgeschritten|mittelstufe|grundkenntnisse|anf[aä]nger"
    r"|nativo|fluido|avanzado|intermedio|principiante)"
)

_SUBSKILLS_PATTERN = (
    r"(writing|reading|listening|speaking|oral|written"
    r"|yazma|okuma|dinleme|konu[sş]ma|yaz[iı]l[iı]|s[oö]zl[uü]"
    r"|[eé]crire|lire|[eé]couter|parler|[eé]crit"
    r"|schreiben|lesen|h[oö]ren|sprechen|schriftlich|m[uü]ndlich"
    r"|escritura|lectura|escucha|habla|escrito)"
)

_SUBSKILL_CEFR_RE = re.compile(
    _SUBSKILLS_PATTERN + r"\s*:?\s*" + _LEVELS_PATTERN,
    re.I,
)

# Recognises a fragment that is ONLY a sub-skill label + level
_ORPHAN_SUBSKILL_RE = re.compile(
    r"^\s*[()]*\s*" + _SUBSKILLS_PATTERN + r"\s*:?\s*" + _LEVELS_PATTERN + r"\s*[()]*\s*$",
    re.I,
)

_ORPHAN_LEVEL_RE = re.compile(
    r"^\s*\(?\s*" + _LEVELS_PATTERN + r"\s*\)?\s*$",
    re.I,
)

from utils.section_scorer import KNOWN_LANGUAGES as _KNOWN_LANGS


def _normalize_language_lines(lines: List[str]) -> List[str]:
    """Normalize language section lines, preserving CEFR details.
    Handles:
      - Sub-skills: English Writing C2 Listening C1
      - Simple levels: English C1, Almanca: B2
      - Orphaned splits: English, C1
    """
    items = []
    for line in lines:
        if not line:
            continue
        parts = re.split(r"\s*[|;/]\s*", line)
        if len(parts) == 1:
            parts = re.split(r"\s{2,}", line)
        
        # Split by comma as well, to catch lists like "English, German"
        sub_items = []
        for part in parts:
            for chunk in re.split(r"\s*,\s*", part):
                cleaned = chunk.strip(" -*•:")
                if cleaned:
                    sub_items.append(cleaned)
        items.extend(sub_items)

    # Merge orphaned items (e.g. "English" followed by "C1" or "Writing C1")
    merged: List[str] = []
    for item in items:
        if _ORPHAN_SUBSKILL_RE.match(item) or _ORPHAN_LEVEL_RE.match(item):
            if merged:
                merged[-1] = merged[-1] + ", " + item.strip()
        else:
            merged.append(item)

    result: List[str] = []
    _prefix_re = re.compile(r"^(?:foreign\s+languages?|languages?(?:\s+known)?)\s*:\s*", re.I)
    for entry in merged:
        entry = _prefix_re.sub("", entry).strip()
        if not entry:
            continue
        
        # Case 1: Sub-skill format (e.g., "English Writing C2 Speaking B2")
        pairs = _SUBSKILL_CEFR_RE.findall(entry)
        if pairs and len(pairs) >= 2:
            first_skill_match = _SUBSKILL_CEFR_RE.search(entry)
            lang_name = entry[:first_skill_match.start()].strip(" :,-–—()")
            if not lang_name:
                for token in entry.split():
                    if token.strip(" :,-()").lower() in _KNOWN_LANGS:
                        lang_name = token.strip(" :,-()")
                        break
            if lang_name:
                parts_str = [f"{skill.capitalize()}: {level.upper() if len(level) <= 2 else level.capitalize()}" for skill, level in pairs]
                result.append(f"{lang_name.capitalize()} ({', '.join(parts_str)})")
                continue
                
        # Case 2: Simple Language Level (e.g., "English C1", "Almanca: B2", "English (Native)")
        match = re.search(r"^([A-Za-z\u00C0-\u024F\u0400-\u04FF\u011E\u011F\u0130\u0131\u015E\u015F\u00C7\u00E7\u00D6\u00F6\u00DC\u00FC\s]+?)\s*[:\-–—,\s]?\s*\(?\s*" + _LEVELS_PATTERN + r"\s*\)?$", entry, re.I | re.UNICODE)
        if match:
            lang = match.group(1).strip(" :,-–—()")
            level = match.group(2).strip()
            if lang.lower() in _KNOWN_LANGS or len(lang.split()) <= 2:
                formatted_level = level.upper() if len(level) <= 2 else level.capitalize()
                result.append(f"{lang.capitalize()} ({formatted_level})")
                continue
                
        # Case 3: Fallback (keep as is)
        result.append(entry)

    # Deduplicate
    seen: set = set()
    deduped: List[str] = []
    for item in result:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(item.strip())
    return deduped


def _normalize_skill_lines(lines: List[str]) -> List[str]:
    items: List[str] = []
    for line in lines:
        if not line:
            continue
        major_parts = re.split(r"[|;/]", line)
        for part in major_parts:
            for chunk in part.split(","):
                cleaned = chunk.strip(" -*•")
                if cleaned:
                    items.append(cleaned)

    merged: List[str] = []
    index = 0
    while index < len(items):
        current = items[index]
        if current.lower() == "real" and index + 1 < len(items) and items[index + 1].lower().startswith("time"):
            merged.append(f"Real-Time {items[index + 1][4:].strip()}".strip())
            index += 2
            continue
        merged.append(current)
        index += 1

    deduped: List[str] = []
    seen = set()
    for item in merged:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


def _normalize_summary(summary_lines: List[str], fallback_lines: List[str], preferred_skills: List[str]) -> str:
    summary = " ".join(line for line in summary_lines if line).strip()
    if not summary:
        summary = " ".join(line for line in fallback_lines[:2] if line).strip()
    if not summary and preferred_skills:
        top_skills = ", ".join(preferred_skills[:6])
        summary = f"Core skills: {top_skills}."
    if len(summary) > SUMMARY_MAX_CHARS:
        summary = summary[: SUMMARY_MAX_CHARS - 3].rstrip() + "..."
    return summary


def _ordered_skills(cv_text: str, explicit_skill_lines: List[str], job_description: str) -> List[str]:
    explicit = _normalize_skill_lines(explicit_skill_lines)
    cv_skills = _extract_skill_names(extract_skills(cv_text))
    job_skills = set(skill.lower() for skill in _extract_skill_names(extract_skills(job_description)))

    combined = explicit + [skill for skill in cv_skills if skill.lower() not in {item.lower() for item in explicit}]
    matched = [skill for skill in combined if skill.lower() in job_skills]
    rest = [skill for skill in combined if skill.lower() not in job_skills]
    return matched + rest


def _extract_section_order_from_text(cv_text: str) -> List[str]:
    order: List[str] = []
    seen = set()
    for raw_line in _clean_lines(cv_text):
        canonical = _canonical_section(raw_line)
        if canonical and canonical in SECTION_ORDER and canonical not in seen:
            seen.add(canonical)
            order.append(canonical)
    for key in SECTION_ORDER:
        if key not in seen:
            order.append(key)
    return order


def _section_score(text: str) -> int:
    if not isinstance(text, str) or not text.strip():
        return 0

    # Pass 1: alias-based header matching (fast, exact)
    lowered = text.lower()
    found = set()
    for canonical, aliases in SECTION_ALIASES.items():
        if canonical == "contact":
            continue
        for alias in aliases:
            if re.search(r"\b" + re.escape(alias) + r"\b", lowered):
                found.add(canonical)
                break

    # Pass 2: block classifier fallback — detect sections by content
    if len(found) < 2:
        block_sections, _, _ = _block_detect_sections(text)
        for label in block_sections:
            if label not in ("header", "contact", "other", "noise"):
                found.add(label)

    return len(found)


def _has_sections(text: str) -> bool:
    return _section_score(text) >= 3


def _detect_fix_mode(cv_text: str, requested_mode: str = "auto") -> tuple[str, int]:
    mode = str(requested_mode or "auto").strip().lower()

    explicit_map = {
        "preserve": "preserve",
        "light_fix": "light_fix",
        "rebuild": "rebuild",
        "original": "preserve",
        "balanced": "light_fix",
        "strict": "rebuild",
    }

    score = _section_score(cv_text)
    if mode in explicit_map:
        return explicit_map[mode], score

    if score >= 4:
        return "preserve", score
    if score >= 2:
        return "light_fix", score
    return "rebuild", score


def _inject_skills_section_if_missing(
    text: str,
    job_description: str = "",
) -> tuple[str, Dict[str, List[str]], bool]:
    header_lines, sections, _ = _parse_sections(text)
    has_existing_skills = any((line or "").strip() for line in (sections.get("skills") or []))
    if has_existing_skills:
        return text, sections, False

    inferred_skills = _ordered_skills(text, [], job_description)
    if not inferred_skills:
        return text, sections, False

    output_lines: List[str] = []
    output_lines.extend(header_lines)
    if output_lines:
        output_lines.append("")

    ordered_keys = _extract_section_order_from_text(text)
    rebuilt_sections: Dict[str, List[str]] = {k: list(v or []) for k, v in sections.items()}
    rebuilt_sections["skills"] = [", ".join(inferred_skills[:20])]

    for key in ordered_keys:
        values = [value for value in (rebuilt_sections.get(key) or []) if value]
        if not values or key not in SECTION_TITLES:
            continue
        output_lines.append(SECTION_TITLES[key])
        output_lines.extend(values)
        output_lines.append("")

    rebuilt_text = "\n".join(line for line in output_lines).strip()
    _, parsed_sections, _ = _parse_sections(rebuilt_text)
    return rebuilt_text, parsed_sections, True


def _minimal_heading_rewrite(cv_text: str) -> str:
    rewritten: List[str] = []
    for line in _clean_lines(cv_text):
        canonical = _canonical_section(line)
        if canonical in SECTION_TITLES:
            rewritten.append(SECTION_TITLES[canonical])
        else:
            rewritten.append(line)
    return "\n".join(rewritten).strip()


def _build_structured_cv(
    cv_text: str,
    job_description: str = "",
    mode: str = "balanced",
) -> tuple[str, Dict[str, List[str]], List[str], List[str]]:
    if USE_PIPELINE:
        extract_structured, normalize, _get_order = _get_pipeline_agents()
        structured = extract_structured(cv_text)
        normalized = normalize(structured)
        return _pipeline_to_structured_text(
            normalized,
            job_description=job_description,
            mode=mode,
        )

    header_lines, sections, dropped_sections = _parse_sections(cv_text)
    name, title_lines, contacts, leftover_header = _extract_contact_block(header_lines, sections.get("contact", []))

    experience_raw = [line for line in sections.get("experience", []) if line]
    if mode == "safe":
        experience_lines = experience_raw
    elif mode == "strict":
        experience_lines = _normalize_experience(experience_raw)
    else:
        has_bullets = any(re.match(r"^\s*[-*•\u2013\u2014\u2023\u25aa\u25a0\uf0b7]\s+", line) for line in experience_raw)
        experience_lines = _normalize_experience(experience_raw) if (experience_raw and not has_bullets) else experience_raw
    education_lines = sections.get("education", []) or []
    certification_lines = [line for line in sections.get("certifications", []) if line]
    project_raw = [line for line in sections.get("projects", []) if line]
    if mode == "safe":
        project_lines = project_raw
    elif mode == "strict":
        project_lines = _normalize_experience(project_raw)
    else:
        has_project_bullets = any(re.match(r"^\s*[-*•\u2013\u2014\u2023\u25aa\u25a0\uf0b7]\s+", line) for line in project_raw)
        project_lines = _normalize_experience(project_raw) if (project_raw and not has_project_bullets) else project_raw
    language_lines = _normalize_list_section(sections.get("languages", []))
    skills = _ordered_skills(cv_text, sections.get("skills", []), job_description)
    summary = _normalize_summary(sections.get("summary", []), leftover_header, skills)

    output_lines: List[str] = []
    if name:
        output_lines.append(name)
    for title_line in title_lines:
        output_lines.append(title_line)
    if contacts:
        output_lines.append(" | ".join(contacts[:MAX_HEADER_CONTACTS]))

    structured_sections: Dict[str, List[str]] = {}
    if summary:
        structured_sections["summary"] = [summary]
    if experience_lines:
        structured_sections["experience"] = experience_lines
    if education_lines:
        structured_sections["education"] = education_lines
    if skills:
        original_skill_lines = [line for line in (sections.get("skills", []) or []) if line]
        if mode == "balanced":
            if original_skill_lines:
                structured_sections["skills"] = original_skill_lines
            else:
                structured_sections["skills"] = skills
        else:
            structured_sections["skills"] = [", ".join(skills[:20])]
    if certification_lines:
        structured_sections["certifications"] = certification_lines
    if project_lines:
        structured_sections["projects"] = project_lines
    if language_lines:
        structured_sections["languages"] = language_lines

    if output_lines:
        output_lines.append("")

    ordered_keys = _extract_section_order_from_text(cv_text) if mode == "balanced" else SECTION_ORDER
    for key in ordered_keys:
        values = structured_sections.get(key) or []
        if not values:
            continue
        output_lines.append(SECTION_TITLES[key])
        output_lines.extend(values)
        output_lines.append("")

    structured_text = "\n".join(line for line in output_lines).strip()
    return structured_text, structured_sections, dropped_sections, ordered_keys


def _pipeline_to_structured_text(
    normalized: Dict,
    job_description: str = "",
    mode: str = "balanced",
) -> tuple[str, Dict[str, List[str]], List[str], List[str]]:
    """Convert pipeline-normalized JSON into structured text and sections.

    Same return interface as _build_structured_cv() so downstream callers
    (keyword boost, skill injection, ATS scoring) keep working unchanged.

    Pipeline: raw → extract_structured → normalize → THIS → text
    """
    name = normalized.get("full_name", "")
    title = normalized.get("title", "")

    contacts: List[str] = []
    for field in ("email", "phone", "location", "linkedin"):
        val = (normalized.get(field) or "").strip()
        if val:
            contacts.append(val)

    summary = (normalized.get("summary") or "").strip()
    if not summary:
        skills_for_summary = [
            str(skill).strip()
            for skill in (normalized.get("skills") or normalized.get("skill") or [])
            if str(skill).strip()
        ][:6]
        education_for_summary = normalized.get("education") or []
        projects_for_summary = normalized.get("projects") or normalized.get("project") or []
        degree = ""
        if education_for_summary and isinstance(education_for_summary[0], dict):
            degree = str(education_for_summary[0].get("degree") or "").strip()
        project_names = [
            str((proj or {}).get("name") or (proj or {}).get("title") or "").strip()
            for proj in projects_for_summary
            if isinstance(proj, dict) and str((proj or {}).get("name") or (proj or {}).get("title") or "").strip()
        ][:2]
        if skills_for_summary or degree or project_names:
            subject = degree.title() if degree else "Professional"
            if project_names and skills_for_summary:
                summary = (
                    f"{subject} with project experience in {', '.join(project_names)}. "
                    f"Core skills include {', '.join(skills_for_summary)}."
                )
            elif skills_for_summary:
                summary = f"{subject} with core skills in {', '.join(skills_for_summary)}."
            elif project_names:
                summary = f"{subject} with project experience in {', '.join(project_names)}."

    # ── experience ──
    experience_lines: List[str] = []
    for exp in (normalized.get("experiences") or normalized.get("experience") or []):
        header_parts = [p for p in [
            exp.get("title", ""),
            exp.get("company", ""),
            exp.get("location", ""),
        ] if p]
        start = exp.get("start_date", "")
        end = exp.get("end_date", "")
        if start or end:
            header_parts.append(f"{start} – {end}".strip(" –"))
        if header_parts:
            experience_lines.append(" | ".join(header_parts))
        for bullet in exp.get("bullets", []):
            if bullet:
                experience_lines.append(
                    bullet if bullet.lstrip().startswith(("•", "- ", "* "))
                    else f"• {bullet}"
                )

    # ── education (GPA stays attached) ──
    education_lines: List[str] = []
    for edu in (normalized.get("education") or []):
        parts = [p for p in [
            edu.get("degree", ""),
            edu.get("field", ""),
            edu.get("school", ""),
        ] if p]
        start = edu.get("start_date", "")
        end = edu.get("end_date", "")
        if start or end:
            parts.append(f"{start} – {end}".strip(" –"))
        if parts:
            education_lines.append(" | ".join(parts))
        gpa = (edu.get("gpa") or "").strip()
        if gpa:
            education_lines.append(f"GPA: {gpa}")

    # ── skills (job-matched first) ──
    skills_flat = list(normalized.get("skills") or normalized.get("skill") or [])
    skills_cat = normalized.get("skills_categorized", {})
    if job_description and skills_flat:
        job_skills = set(
            s.lower()
            for s in _extract_skill_names(extract_skills(job_description))
        )
        matched = [s for s in skills_flat if s.lower() in job_skills]
        rest = [s for s in skills_flat if s.lower() not in job_skills]
        skills_flat = matched + rest

    skill_lines: List[str] = []
    if skills_cat and mode != "strict":
        for cat, items in skills_cat.items():
            if isinstance(items, list) and items:
                skill_lines.append(f"{cat}: {', '.join(items)}")
            elif isinstance(items, str) and items:
                skill_lines.append(f"{cat}: {items}")
    if not skill_lines and skills_flat:
        skill_lines = [", ".join(skills_flat[:20])]

    # ── projects ──
    project_lines: List[str] = []
    for proj in (normalized.get("projects") or normalized.get("project") or []):
        proj_name = proj.get("name") or proj.get("title") or ""
        if proj_name:
            project_lines.append(proj_name)
        proj_desc = proj.get("description", "")
        bullets = proj.get("bullets", [])
        has_bullets = any(b and b.strip() for b in bullets)
        # If no bullets but description exists, promote description to bullet
        if proj_desc and not has_bullets:
            project_lines.append(
                proj_desc if proj_desc.lstrip().startswith(("•", "- ", "* "))
                else f"• {proj_desc}"
            )
        else:
            if proj_desc:
                project_lines.append(proj_desc)
            for bullet in bullets:
                if bullet:
                    project_lines.append(
                        bullet if bullet.lstrip().startswith(("•", "- ", "* "))
                        else f"• {bullet}"
                    )

    # ── certifications ──
    cert_lines: List[str] = []
    for cert in (normalized.get("certifications") or normalized.get("certification") or []):
        if isinstance(cert, dict):
            cname = cert.get("name", "")
            if cname:
                cert_lines.append(cname)
        elif cert:
            cert_lines.append(str(cert))

    # ── languages ──
    language_lines = [
        str(lang)
        for lang in (normalized.get("languages") or normalized.get("language") or [])
        if lang
    ]

    # ── assemble sections ──
    structured_sections: Dict[str, List[str]] = {}
    if summary:
        structured_sections["summary"] = [summary]
    if experience_lines:
        structured_sections["experience"] = experience_lines
    if education_lines:
        structured_sections["education"] = education_lines
    if skill_lines:
        structured_sections["skills"] = skill_lines
    if cert_lines:
        structured_sections["certifications"] = cert_lines
    if project_lines:
        structured_sections["projects"] = project_lines
    if language_lines:
        structured_sections["languages"] = language_lines

    section_order = normalized.get("_section_order", SECTION_ORDER)
    dropped = normalized.get("_dropped_sections", []) or []
    title_lines = [title] if title else []

    text = _render_structured_sections(
        name, title_lines, contacts, structured_sections, section_order,
    )
    return text, structured_sections, dropped, section_order


def _render_structured_sections(
    name: str | None,
    title_lines: List[str],
    contacts: List[str],
    structured_sections: Dict[str, List[str]],
    section_order: List[str] | None = None,
) -> str:
    output_lines: List[str] = []
    if name:
        output_lines.append(name)
    for title_line in title_lines:
        if title_line:
            output_lines.append(title_line)
    if contacts:
        output_lines.append(" | ".join(contacts[:MAX_HEADER_CONTACTS]))
    if output_lines:
        output_lines.append("")

    ordered_keys = section_order or SECTION_ORDER
    for key in ordered_keys:
        values = [value for value in (structured_sections.get(key) or []) if value]
        if not values:
            continue
        output_lines.append(SECTION_TITLES.get(key, key.upper()))
        output_lines.extend(values)
        output_lines.append("")

    return "\n".join(output_lines).strip()


def _ensure_identity_header(
    text: str,
    fallback_name: str | None,
    fallback_title_lines: List[str],
    fallback_contacts: List[str],
) -> str:
    header_lines, sections, _ = _parse_sections(text)
    name, title_lines, contacts, _ = _extract_contact_block(header_lines, sections.get("contact", []))

    final_name = name or (fallback_name or "")
    final_title_lines = title_lines or (fallback_title_lines or [])
    final_contacts = contacts or (fallback_contacts or [])

    if final_name == name and final_title_lines == title_lines and final_contacts == contacts:
        return text

    lines = _clean_lines(text)
    rebuilt: List[str] = []
    if final_name:
        rebuilt.append(final_name)
    for title_line in final_title_lines:
        if title_line:
            rebuilt.append(title_line)
    if final_contacts:
        rebuilt.append(" | ".join(final_contacts[:MAX_HEADER_CONTACTS]))
    if rebuilt:
        rebuilt.append("")

    skip_header = True
    for line in lines:
        if skip_header:
            if _canonical_section(line) or _noise_section(line):
                skip_header = False
                rebuilt.append(line)
            continue
        rebuilt.append(line)

    return "\n".join(rebuilt).strip()


_BOOST_ACTION_VERBS = [
    "led", "managed", "developed", "implemented", "designed", "delivered",
    "optimized", "created", "improved", "built", "launched", "coordinated",
    "established", "streamlined", "executed", "analyzed", "achieved",
    "automated", "resolved", "maintained", "collaborated", "configured",
    "integrated", "deployed", "enhanced", "reduced", "increased",
    "spearheaded", "architected", "engineered",
]

# Full set of action verbs (from ats_service) for detection purposes
_ALL_ACTION_VERBS = set(_BOOST_ACTION_VERBS) | {
    "directed", "supervised", "oversaw", "orchestrated", "mentored", "coached",
    "exceeded", "surpassed", "earned", "won", "awarded",
    "founded", "initiated", "introduced", "pioneered",
    "upgraded", "refactored", "modernized", "revamped", "transformed", "accelerated",
    "assessed", "evaluated", "researched", "investigated", "identified",
    "diagnosed", "audited", "reviewed", "benchmarked",
    "shipped", "completed",
    "expanded", "scaled", "grew", "generated", "boosted",
    "decreased", "minimized", "eliminated", "consolidated", "cut", "saved",
    "presented", "communicated", "negotiated", "facilitated", "documented",
    "reported", "trained", "taught", "educated",
    "programmed", "migrated", "containerized", "provisioned", "instrumented",
}


def _starts_with_action_verb(line: str) -> bool:
    """Check if a bullet line already starts with a recognized action verb."""
    cleaned = re.sub(r"^[-•*]\s*", "", line).strip().lower()
    first_word = cleaned.split()[0] if cleaned.split() else ""
    for verb in _ALL_ACTION_VERBS:
        if re.match(r"\b" + re.escape(verb) + r"(?:s|ed|ing|d)?\b", first_word):
            return True
    return False


def _add_action_verb_to_bullet(line: str, used_verbs: set) -> str:
    """Prepend a diverse action verb to a bullet that lacks one."""
    cleaned = re.sub(r"^[-•*]\s*", "", line).strip()
    if not cleaned:
        return line
    # Pick a verb not recently used for diversity
    available = [v for v in _BOOST_ACTION_VERBS if v not in used_verbs]
    if not available:
        available = _BOOST_ACTION_VERBS[:10]
    verb = available[0]
    used_verbs.add(verb)
    # Capitalize verb, lowercase the original start
    first_char = cleaned[0].lower() if cleaned[0].isupper() else cleaned[0]
    return f"- {verb.capitalize()} {first_char}{cleaned[1:]}"


def _ensure_bullet_format(line: str) -> str:
    """Normalize malformed bullet markers while preserving existing bullet style."""
    stripped = line.strip()
    if stripped.startswith("• "):
        return stripped
    if stripped.startswith("* "):
        return "• " + stripped[2:]
    if stripped.startswith("-") and not stripped.startswith("- "):
        return "- " + stripped[1:].lstrip()
    return line


def _boost_keywords(
    structured_text: str,
    structured_sections: Dict[str, List[str]],
    job_description: str,
    mode: str = "balanced",
    section_order: List[str] | None = None,
) -> str:
    header_lines, parsed_sections, _ = _parse_sections(structured_text)
    name, title_lines, contacts, _ = _extract_contact_block(header_lines, parsed_sections.get("contact", []))

    cv_skills = _extract_skill_names(extract_skills(structured_text))
    job_skills = _extract_skill_names(extract_skills(job_description))
    overlaps = [skill for skill in job_skills if skill.lower() in {v.lower() for v in cv_skills}]

    boosted_sections = {key: list(values) for key, values in structured_sections.items()}

    # 1) Enrich summary with keyword overlap (idempotent — skip if already present)
    summary_lines = list(boosted_sections.get("summary", []))
    if job_description.strip() and overlaps:
        reinforcement = f"Relevant strengths include {', '.join(overlaps[:6])}."
        # Check if any "Relevant strengths include" phrase already exists
        already_has = any("relevant strengths include" in (s or "").lower() for s in summary_lines)
        allow_summary_boost = mode != "balanced" or (summary_lines and len(summary_lines[0]) < 200)
        if allow_summary_boost and not already_has:
            if summary_lines:
                summary_lines[0] = f"{summary_lines[0].rstrip('.')}. {reinforcement}".strip()
            else:
                summary_lines = [reinforcement]
    boosted_sections["summary"] = summary_lines

    # 2) Re-order skills: job-matching first
    if job_description.strip() and mode != "balanced":
        current_skills = _normalize_list_section(boosted_sections.get("skills", []))
        overlap_set = {s.lower() for s in overlaps}
        merged = overlaps + [s for s in current_skills if s.lower() not in overlap_set]
        if merged:
            boosted_sections["skills"] = [", ".join(merged[:20])]

    # 3) In strict mode only, inject action verbs for ATS lift.
    if mode == "strict":
        experience_lines = list(boosted_sections.get("experience", []))
        used_verbs: set = set()
        new_experience: List[str] = []
        for line in experience_lines:
            normalized_line = _ensure_bullet_format(line)
            if not normalized_line or not re.match(r"^\s*[-•*]\s+", normalized_line):
                new_experience.append(normalized_line)
                continue
            if _starts_with_action_verb(normalized_line):
                new_experience.append(normalized_line)
                continue
            new_experience.append(_add_action_verb_to_bullet(normalized_line, used_verbs))
        boosted_sections["experience"] = new_experience

        project_lines = list(boosted_sections.get("projects", []))
        new_projects: List[str] = []
        for line in project_lines:
            normalized_line = _ensure_bullet_format(line)
            if not normalized_line or not re.match(r"^\s*[-•*]\s+", normalized_line):
                new_projects.append(normalized_line)
                continue
            if _starts_with_action_verb(normalized_line):
                new_projects.append(normalized_line)
                continue
            new_projects.append(_add_action_verb_to_bullet(normalized_line, used_verbs))
        boosted_sections["projects"] = new_projects

        for section_key in ("experience", "projects", "certifications"):
            lines = boosted_sections.get(section_key, [])
            boosted_sections[section_key] = [_ensure_bullet_format(l) for l in lines]

    # 5) Ensure required sections exist (even if minimal)
    if not boosted_sections.get("skills"):
        if cv_skills:
            boosted_sections["skills"] = [", ".join(cv_skills[:15])]
    if not boosted_sections.get("summary"):
        top = cv_skills[:6] if cv_skills else overlaps[:6]
        if top:
            boosted_sections["summary"] = [f"Professional with expertise in {', '.join(top)}."]

    return _render_structured_sections(name, title_lines, contacts, boosted_sections, section_order=section_order)


def _split_concatenated_bullets(lines: List[str]) -> List[str]:
    """Pre-process experience lines: split bullets joined on the same line.

    PDF extractors often merge bullet points, e.g.:
      '*Analyzed pipelines * Worked on streaming'
      '•Built APIs •Deployed services'
      '– First point – Second point'
    Split these into separate lines so downstream can treat each as a bullet.
    """
    result: List[str] = []
    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue
        # Detect lines that start with a bullet marker and contain more markers mid-line
        # Markers: *, •, -, –, —, ▪, ■  (only when preceded by whitespace or sentence-end)
        if re.match(r"^\s*[*\u2022\u2023\u2013\u2014\u25aa\u25a0]", line):
            # Split on mid-line bullet markers
            parts = re.split(r"\s+(?=[*\u2022\u2023\u2013\u2014\u25aa\u25a0](?:\s|[A-Z]))", line)
            for part in parts:
                part = part.strip()
                if part:
                    result.append(part)
        elif re.match(r"^\s*-\s", line):
            # Dash-prefixed bullet: split if there are embedded dashes mid-line
            parts = re.split(r"\s+(?=-\s[A-Z])", line)
            for part in parts:
                part = part.strip()
                if part:
                    result.append(part)
        else:
            result.append(line)
    return result


def _parse_experience_entries(lines: List[str]) -> List[Dict]:
    # Pre-process: split concatenated bullets from PDF extraction
    lines = _split_concatenated_bullets(lines)
    entries: List[Dict] = []
    current: Dict | None = None

    _date_token = (
        r"(?:\d{1,2}[/.]\s*)?(?:19|20)\d{2}"
        r"|[A-Za-z\u00C0-\u024F\u0400-\u04FF]{2,12}\.?\s+(?:19|20)\d{2}"
    )
    _date_sep = r"[-\u2013\u2014]"
    _date_range_anywhere_re = re.compile(
        rf"\(?\s*(?:tarih|date|duration|period)?\s*[:：]?\s*"
        rf"(?P<start>{_date_token})\s*{_date_sep}\s*"
        rf"(?P<end>{_date_token}|present|current|ongoing|halen|devam\s+ediyor)\s*\)?",
        re.I | re.UNICODE,
    )
    _date_range_full_re = re.compile(
        rf"^\(?\s*(?P<start>{_date_token})\s*{_date_sep}\s*"
        rf"(?P<end>{_date_token}|present|current|ongoing|halen|devam\s+ediyor)\s*\)?$",
        re.I | re.UNICODE,
    )
    _date_range_reversed_re = re.compile(
        rf"^\s*(?P<end>{_date_token})\)?\s*{_date_sep}\s*\(?\s*"
        rf"(?:tarih|date|duration|period)\s*[:：]?\s*(?P<start>{_date_token})\s*$",
        re.I | re.UNICODE,
    )

    def _extract_date_range(value: str) -> tuple[str, str, str]:
        text = (value or "").strip()
        if not text:
            return "", "", ""
        match = _date_range_reversed_re.search(text)
        if not match:
            match = _date_range_anywhere_re.search(text)
        if not match:
            match = _date_range_full_re.search(text)
        if not match:
            return text, "", ""
        start = match.group("start").strip(" ()")
        end = match.group("end").strip(" ()")
        cleaned = (text[: match.start()] + " " + text[match.end():]).strip(" -\u2013\u2014|()")
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return cleaned, start, end

    def _new_entry(title: str) -> Dict:
        title, start_date, end_date = _extract_date_range(title)
        entry = {
            "title": title,
            "company": "",
            "location": "",
            "start_date": start_date,
            "end_date": end_date,
            "bullets": [],
        }
        # Auto-split "Role - Company" or "Role – Company" in title
        if " - " in title or " – " in title:
            parts = re.split(r"\s+[–-]\s+", title, maxsplit=1)
            if len(parts) == 2:
                a, b = parts[0].strip(), parts[1].strip()
                a_is_role = _looks_like_role(a)
                b_is_role = _looks_like_role(b)
                if a_is_role and not b_is_role:
                    entry["title"] = a
                    entry["company"] = b
                elif b_is_role and not a_is_role:
                    entry["title"] = b
                    entry["company"] = a
                else:
                    # Default: first=role, second=company
                    entry["title"] = a
                    entry["company"] = b
        return entry

    # Language-agnostic month: any short word (2-12 chars) of letters/accents
    # before a year.  Covers English, Turkish, German, French, Spanish, etc.
    _month_word = r"[A-Za-z\u00C0-\u024F\u0400-\u04FF]{2,12}\.?"
    year_pattern = r"(?:19|20)\d{2}"
    # Numeric date prefix: 01/2020, 2020-01, 01.2020
    _numeric_prefix = r"(?:\d{1,2}[/.]\s*)?"
    # "present" in any language: accept any single word that is NOT a year
    _present_kw = r"(?!(?:19|20)\d{2}\b)[A-Za-z\u00C0-\u024F\u0400-\u04FF]{3,}(?:\s+[A-Za-z\u00C0-\u024F]{2,})?"
    date_range_pattern = re.compile(
        rf"^(?:{_month_word}\s+|{_numeric_prefix})?{year_pattern}"
        rf"\s*(?:[-–—]|to)\s*"
        rf"(?:(?:{_month_word}\s+|{_numeric_prefix})?{year_pattern}|{_present_kw})$",
        re.I,
    )
    single_date_pattern = re.compile(
        rf"^(?:{_month_word}\s+|{_numeric_prefix})?{year_pattern}$", re.I,
    )

    def _is_date_like(value: str) -> bool:
        clean = value.strip()
        if not clean:
            return False
        _, range_start, range_end = _extract_date_range(clean)
        if range_start or range_end:
            return True
        if date_range_pattern.match(clean):
            return True
        if single_date_pattern.match(clean):
            return True
        if re.match(rf"^{year_pattern}\s*[-–—]\s*$", clean):
            return True  # open-ended: "2020 –"
        return False

    _ROLE_KEYWORDS = {
        "engineer", "developer", "manager", "analyst", "designer", "architect",
        "lead", "director", "consultant", "specialist", "coordinator",
        "administrator", "intern", "trainee", "associate", "senior", "junior",
        "principal", "staff", "head", "chief", "vp", "president", "officer",
        "scientist", "researcher", "technician", "programmer", "lecturer",
        "professor", "assistant", "executive", "founder", "co-founder",
        "cto", "ceo", "cfo", "coo", "devops", "qa", "tester",
    }

    def _looks_like_role(text: str) -> bool:
        words = set(re.split(r"[\s/,.-]+", text.lower()))
        return bool(words & _ROLE_KEYWORDS)

    def _try_split_pipe_header(line: str) -> Dict | None:
        """Try to parse pipe-delimited experience header.

        Handles both formats:
          'Company | Role | Date'  (most common)
          'Role | Company | Date'
        Uses role-keyword heuristic to decide which is which.
        """
        if "|" not in line:
            return None
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 2:
            return None

        # Separate date parts from non-date parts
        non_date_parts: List[str] = []
        start_date, end_date = "", ""
        for part in parts:
            if _is_date_like(part):
                start_date = part
            elif re.search(r"\b(?:19|20)\d{2}\b\s*(?:[-–]|to)\s*", part, re.I):
                if "–" in part:
                    start_date, end_date = [p.strip() for p in part.split("–", 1)]
                elif " - " in part:
                    start_date, end_date = [p.strip() for p in part.split(" - ", 1)]
                elif re.search(r"\bto\b", part, re.I):
                    start_date, end_date = [p.strip() for p in re.split(r"\bto\b", part, maxsplit=1, flags=re.I)]
                else:
                    start_date = part
            else:
                non_date_parts.append(part)

        # Determine title vs company from non-date parts
        title, company, location = "", "", ""
        if len(non_date_parts) >= 2:
            a, b = non_date_parts[0], non_date_parts[1]
            a_is_role = _looks_like_role(a)
            b_is_role = _looks_like_role(b)
            if b_is_role and not a_is_role:
                # "Company | Role" format
                company, title = a, b
            elif a_is_role and not b_is_role:
                # "Role | Company" format
                title, company = a, b
            else:
                # Ambiguous — default: first=company, second=title
                # (most common CV convention)
                company, title = a, b
            if len(non_date_parts) >= 3:
                location = non_date_parts[2]
        elif len(non_date_parts) == 1:
            title = non_date_parts[0]

        entry = _new_entry(title)
        entry["company"] = company
        entry["location"] = location
        entry["start_date"] = start_date
        entry["end_date"] = end_date
        return entry

    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue

        # Bullet item → add to current entry.
        # A line starting with a bullet marker (-, •, *, –, …) is a bullet
        # UNLESS it has no content after the marker, is purely a date,
        # or is a very short role-like phrase (≤3 words after marker).
        _bullet_m = re.match(r"^\s*[-*•\u2013\u2014\u2023\u25aa\u25a0\uf0b7]\s*", line)
        if _bullet_m and not _is_date_like(line):
            bullet_text = line[_bullet_m.end():].strip()
            # Only reject as "role title" if the after-marker text is very
            # short (≤3 words) AND looks like a role — longer lines are
            # descriptions that happen to mention role keywords.
            _is_short_role = (
                len(bullet_text.split()) <= 3 and _looks_like_role(bullet_text)
            )
            if bullet_text and not _is_short_role:
                if current is None:
                    current = _new_entry("Experience")
                current["bullets"].append(bullet_text)
                continue

        # Try pipe-delimited header: "Title | Company | Location | Dates"
        pipe_entry = _try_split_pipe_header(line)
        if pipe_entry:
            pipe_parts = [p.strip() for p in line.split("|") if p.strip()]
            # If current entry has title but no company, and this is a short
            # pipe line (2 parts like "Company | Dates"), treat as company+date
            # for current entry, NOT as a new entry.
            if (current and current.get("title") and not current.get("company")
                    and len(pipe_parts) <= 2):
                current["company"] = pipe_entry.get("title", "")
                current["start_date"] = pipe_entry.get("start_date", "")
                current["end_date"] = pipe_entry.get("end_date", "")
                if pipe_entry.get("company"):
                    current["location"] = pipe_entry["company"]
            else:
                if current:
                    entries.append(current)
                current = pipe_entry
            continue

        if current is None:
            current = _new_entry(line)
            continue

        cleaned_date_line, range_start, range_end = _extract_date_range(line)
        if range_start or range_end:
            if not current.get("start_date"):
                current["start_date"] = range_start
            if not current.get("end_date"):
                current["end_date"] = range_end
            if cleaned_date_line and cleaned_date_line != line and not current.get("location"):
                current["location"] = cleaned_date_line
            continue

        if (not current.get("start_date") and not current.get("end_date")) and _is_date_like(line):
            if "–" in line:
                start, end = [p.strip() for p in line.split("–", 1)]
            elif "-" in line:
                start, end = [p.strip() for p in line.split("-", 1)]
            elif "to" in line.lower():
                start, end = [p.strip() for p in re.split(r"\bto\b", line, maxsplit=1, flags=re.I)]
            else:
                start, end = line.strip(), ""
            current["start_date"] = start
            current["end_date"] = end
            continue

        if not current.get("company") and (" - " in line or " – " in line):
            parts = re.split(r"\s+[–-]\s+", line, maxsplit=1)
            current["company"] = parts[0].strip()
            if len(parts) > 1:
                current["location"] = parts[1].strip()
            continue

        if current.get("company") and current.get("title"):
            # In PDF text, experience descriptions often lose their bullet
            # marker. Long/action-like continuation lines belong to the
            # current role; short lines are more likely the next company/title.
            if len(line.split()) >= 5 or _starts_with_action_verb(line):
                current["bullets"].append(line)
                continue

        if current.get("bullets") or (current.get("company") and current.get("title")):
            entries.append(current)
            current = _new_entry(line)
            continue

        if not current.get("company"):
            current["company"] = line
        else:
            current["location"] = line

    if current:
        entries.append(current)

    return [entry for entry in entries if entry.get("title") or entry.get("bullets")]


# ── Degree detection for education parsing ──
_DEGREE_RE = re.compile(
    r"^\s*(?:"
    r"B\.?\s*S\.?c?\.?|M\.?\s*S\.?c?\.?|B\.?\s*A\.?|M\.?\s*A\.?|"
    r"B\.?\s*E(?:ng)?\.?|M\.?\s*E(?:ng)?\.?|"
    r"Ph\.?\s*D\.?|M\.?\s*B\.?\s*A\.?|"
    r"Bachelor|Master|Diploma|Associate|Doctor(?:ate)?|Certificate"
    r")(?:\s|[.,]|$)",
    re.I,
)
# Standalone degree / profession titles on their own line
_DEGREE_TITLE_RE = re.compile(
    r"\b(?:"
    # Engineering variants
    r"engineer(?:ing)?|"
    # Medicine / health
    r"medicine|medical\s+doctor|doctor\s+of\s+medicine|"
    r"nurs(?:e|ing)|pharmacy|dentistry|physiotherapy|"
    # Law
    r"law|lawyer|attorney|juris(?:prudence)?|"
    # Architecture / design
    r"architect(?:ure)?|interior\s+design|industrial\s+design|"
    # Sciences
    r"physicist?|chemist(?:ry)?|biolog(?:y|ist)|mathemati(?:cs|cian)|statistic(?:s|ian)|"
    # Social sciences / humanities
    r"psycholog(?:y|ist)|sociolog(?:y|ist)|economist?|economics|"
    r"political\s+science|international\s+relations|"
    r"philosoph(?:y|er)|histor(?:y|ian)|linguist(?:ics)?|"
    # Business / management
    r"business\s+administration|management|accounting|finance|marketing|"
    # Education
    r"teaching|pedagog(?:y|ue)|education|"
    # Arts / communication
    r"journalism|communication|public\s+relations|"
    r"graphic\s+design|fine\s+arts|"
    # IT / CS
    r"computer\s+science|information\s+(?:technology|systems)|data\s+science|"
    r"cyber\s*security|artificial\s+intelligence"
    r")\s*$",
    re.I,
)
# Turkish degree terms may appear mid-line (e.g. "Bilgisayar Mühendisliği")
_DEGREE_TR_RE = re.compile(
    r"\b(?:lisans|y[u\u00fc]ksek\s*lisans|doktora|[o\u00f6]n\s*lisans"
    r"|m[u\u00fc]hendisli[gk\u011f]\w*|b[o\u00f6]l[u\u00fc]m\w*)\b",
    re.I,
)

_PAREN_DATE_RE = re.compile(
    r"\((\d{4})\s*[-–—]\s*(\d{4}|[A-Za-z\u00C0-\u024F\u0400-\u04FF]{3,}(?:\s+[A-Za-z\u00C0-\u024F]{2,})?)\)\s*$",
    re.I,
)


def _looks_like_degree(line: str) -> bool:
    """Return True if the line looks like the start of a new education entry."""
    return (bool(_DEGREE_RE.search(line))
            or bool(_DEGREE_TR_RE.search(line))
            or bool(_DEGREE_TITLE_RE.search(line)))


def _extract_paren_dates(text: str) -> tuple:
    """Extract parenthetical dates from end of line, return (clean, start, end)."""
    m = _PAREN_DATE_RE.search(text)
    if m:
        return text[: m.start()].strip(), m.group(1), m.group(2)
    return text, "", ""


def _new_edu_entry() -> Dict:
    return {
        "degree": "",
        "school": "",
        "location": "",
        "start_date": "",
        "end_date": "",
        "gpa": "",
        "field": "",
    }


def _parse_date_range(line: str) -> tuple:
    """Parse a date range from a line, return (start, end)."""
    if "–" in line:
        s, e = [p.strip() for p in line.split("–", 1)]
    elif " - " in line:
        s, e = [p.strip() for p in line.split(" - ", 1)]
    elif re.search(r"\bto\b", line, re.I):
        s, e = [p.strip() for p in re.split(r"\bto\b", line, maxsplit=1, flags=re.I)]
    else:
        s, e = line.strip(), ""
    return s, e


def _parse_education_entries(lines: List[str]) -> List[Dict]:
    entries: List[Dict] = []
    current: Dict | None = None
    university_keywords = (
        "university", "universit",
        "institute", "enstit",
        "college",
        "school",
        "faculty", "fak\u00fclte", "fakulte",
        "academy", "akademi",
        "\u00fcniversite", "universitesi",
    )

    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue

        lowered = line.lower()

        # ── 0. If current entry is complete (school + degree + dates), flush it ──
        if (current
                and current.get("degree") and current.get("school")
                and (current.get("start_date") or current.get("end_date"))):
            # Don't flush if current school is incomplete (no university keyword)
            # and this line contains one — it's likely a continuation.
            school_low = current["school"].lower()
            if (any(kw in lowered for kw in university_keywords)
                    and not any(kw in school_low for kw in university_keywords)):
                pass  # let step 4 handle the merge
            else:
                entries.append(current)
                current = None

        # ── 1. Pipe-delimited header: "B.Sc. CS | University | 2015 - 2019" ──
        if "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                if current:
                    entries.append(current)
                current = _new_edu_entry()
                for part in parts:
                    lp = part.lower()
                    if any(kw in lp for kw in university_keywords):
                        current["school"] = part
                    elif re.search(r"(?:19|20)\d{2}\s*(?:[-–]|to)\s*", part, re.I):
                        current["start_date"], current["end_date"] = _parse_date_range(part)
                    elif re.match(r"^(?:19|20)\d{2}$", part.strip()):
                        if not current["start_date"]:
                            current["start_date"] = part.strip()
                        else:
                            current["end_date"] = part.strip()
                    elif not current["degree"]:
                        current["degree"] = part
                    elif not current["school"]:
                        current["school"] = part
                    else:
                        current["location"] = part
                continue

        # ── 2. GPA line → attach to current entry (or last entry) ──
        gpa_like = re.search(
            r"\b\d(?:\.\d{1,2})?\s*/\s*(?:4(?:\.0+)?|5(?:\.0+)?)\b", line
        )
        if "gpa" in lowered or "cgpa" in lowered or "not:" in lowered or gpa_like:
            if current:
                current["gpa"] = line
            elif entries:
                # Orphan GPA — attach to last completed entry
                entries[-1]["gpa"] = line
            continue

        # ── 3. New degree line ──
        if _looks_like_degree(line):
            deg_clean, sd, ed = _extract_paren_dates(line)
            # If current entry already has a school but no degree, fill it in
            if current and current.get("school") and not current.get("degree"):
                current["degree"] = deg_clean
                if sd:
                    current["start_date"] = sd
                if ed:
                    current["end_date"] = ed
            else:
                if current:
                    entries.append(current)
                current = _new_edu_entry()
                current["degree"] = deg_clean
                current["start_date"] = sd
                current["end_date"] = ed
            continue

        # ── 4. University/school keyword line ──
        if any(kw in lowered for kw in university_keywords):
            if current is None:
                current = _new_edu_entry()
            if current.get("school"):
                # Check if current school already has a university keyword;
                # if NOT, this line is likely a continuation of the school name
                # (e.g. "ISTANBUL HEALTH AND TECHNOLOGY" + "UNIVERSITY (İSTÜN)")
                existing_low = current["school"].lower()
                if any(kw in existing_low for kw in university_keywords):
                    # Truly a new school → start a new entry
                    entries.append(current)
                    current = _new_edu_entry()
                else:
                    # Merge continuation
                    current["school"] = current["school"] + " " + line
                    continue
            current["school"] = line
            continue

        # ── 5. First unrecognised line with no current → treat as school ──
        # (degrees and university-keyword lines are already handled above)
        if current is None:
            current = _new_edu_entry()
            current["school"] = line
            continue

        # ── 6. Date-only line ──
        if re.search(r"(?:19|20)\d{2}", line):
            current["start_date"], current["end_date"] = _parse_date_range(line)
            continue

        # ── 7. Fallback: school or extra info ──
        if not current.get("school"):
            current["school"] = line
        else:
            current["location"] = line

    if current:
        entries.append(current)

    # ── Post-process: split merged transferred lines (PDF extraction fallback) ──
    expanded: List[Dict] = []
    for entry in entries:
        degree = (entry.get("degree") or "").strip()
        transfer_match = re.match(
            r"^(.+?)\s*\(Transferred\)\s*\((.+?)\s*\((\d{4})\s*[-–]\s*(Present|\d{4})\)\)$",
            degree,
            re.I,
        )
        if transfer_match:
            old_entry = dict(entry)
            old_entry["degree"] = transfer_match.group(1).strip() + " (Transferred)"
            old_entry["start_date"] = ""
            old_entry["end_date"] = ""
            expanded.append(old_entry)
            new_entry = dict(entry)
            new_entry["degree"] = transfer_match.group(2).strip()
            new_entry["start_date"] = transfer_match.group(3).strip()
            new_entry["end_date"] = transfer_match.group(4).strip()
            expanded.append(new_entry)
        else:
            expanded.append(entry)

    for entry in expanded:
        for key in ("degree", "school", "start_date", "end_date", "gpa", "field", "location"):
            entry.setdefault(key, "")

    return expanded


def _extract_categorized_skills(lines: List[str]) -> tuple[Dict[str, List[str]], List[str]]:
    categories: Dict[str, List[str]] = {}
    uncategorized: List[str] = []

    for raw in lines or []:
        line = str(raw or "").strip()
        if not line:
            continue
        if ":" in line:
            category, values = line.split(":", 1)
            category_clean = category.strip()
            items = [item.strip(" -*•") for item in re.split(r"\s*[,;/|]\s*", values) if item.strip(" -*•")]
            if category_clean and items:
                categories.setdefault(category_clean, [])
                for item in items:
                    if item not in categories[category_clean]:
                        categories[category_clean].append(item)
                continue
        if re.match(r"^\s*[-*•]\s+", line):
            uncategorized.append(re.sub(r"^\s*[-*•]\s+", "", line).strip())
        else:
            uncategorized.extend(
                [item.strip() for item in re.split(r"\s*[,;/|]\s*", line) if item.strip()]
            )

    if uncategorized:
        dedup_uncat: List[str] = []
        seen = set()
        for item in uncategorized:
            lowered = item.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            dedup_uncat.append(item)
        if not categories:
            categories.setdefault("Technical Skills", dedup_uncat)

    flattened: List[str] = []
    seen_flat = set()
    for values in categories.values():
        for value in values:
            key = value.lower()
            if key in seen_flat:
                continue
            seen_flat.add(key)
            flattened.append(value)
    return categories, flattened


def _looks_like_description(line: str) -> bool:
    """Return True if *line* reads like a project description rather than a title."""
    # Long lines are almost always descriptions
    if len(line) > 80:
        return True
    # Sentence-ending punctuation
    stripped = line.rstrip()
    if stripped.endswith((".", "!")):
        return True
    # Majority lowercase words → sentence
    words = line.split()
    if len(words) >= 5:
        lc = sum(1 for w in words if w[:1].islower())
        if lc / len(words) > 0.5:
            return True
    return False


def _looks_like_tech_list(line: str) -> bool:
    """Return True if *line* is a comma/pipe-separated list of short tokens.

    Structural signal: 3+ short tokens separated by commas, pipes, or slashes.
    No sentence structure — just labels ("Python, React, Docker").
    """
    stripped = line.strip()
    # Must contain a delimiter
    if not re.search(r"[,|/]", stripped):
        return False
    tokens = re.split(r"\s*[,|/]\s*", stripped)
    tokens = [t.strip() for t in tokens if t.strip()]
    if len(tokens) < 3:
        return False
    # All tokens must be short (≤4 words each) — structural, not a sentence
    return all(len(t.split()) <= 4 for t in tokens)


def _parse_project_entries(lines: List[str]) -> List[Dict]:
    _TECH_HDR = re.compile(
        r"^\s*(?:used\s+technologies|tech(?:nology|nologies)?\s*(?:stack|used)?"
        r"|tools(?:\s+(?:used|&|and)\s+\w+)?"
        r"|stack|kullan[ıi]lan\s+teknolojiler"
        r"|technologies\s+used)\s*[:：\-]\s*",
        re.I,
    )
    # Labeled link lines (Link:, Website:, GitHub:, Demo:)
    _LINK_HDR = re.compile(
        r"^\s*(?:link|website|web\s*site|github|demo|url|live|repo|repository"
        r"|kaynak|site)\s*[:：]\s*",
        re.I,
    )
    _URL_LINE = re.compile(r"^\s*(?:https?://\S+|www\.\S+)\s*$", re.I)
    _BULLET_RE_PROJ = re.compile(
        r"^\s*[-*•\u2013\u2014\u2023\u25aa\u25a0►]\s+"
    )

    _PROJECT_CONTINUATION_RE = re.compile(
        r"^(?:and|or|with|to|for|in|on|of|by|as|using|between|while|through|that|which|ve|ile|i[cç]in|olarak)\b",
        re.I,
    )

    def _looks_like_project_continuation(value: str) -> bool:
        text = (value or "").strip()
        if not text or _BULLET_RE_PROJ.match(text):
            return False
        if len(text.split()) >= 6 and not text.isupper():
            return True
        return bool(_PROJECT_CONTINUATION_RE.match(text))

    entries: List[Dict] = []
    current: Dict | None = None

    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue

        # Detect "Title — tech1, tech2, tech3" or "Title | tech1, tech2"
        # Split on dash/pipe separator when the suffix is a tech list.
        # This MUST run before we assume a line is a tech-continuation of the previous project.
        _title_tech_m = re.match(
            r'^(.+?)\s*[\u2013\u2014|–—-]\s+(.+)$', line,
        )
        if _title_tech_m and _looks_like_tech_list(_title_tech_m.group(2)):
            if current is not None:
                entries.append(current)
            current = {
                "name": _title_tech_m.group(1).strip(),
                "description": _title_tech_m.group(2).strip(),
                "bullets": [],
            }
            continue

        m_bullet = _BULLET_RE_PROJ.match(line)
        if m_bullet:
            if current is None:
                current = {"name": "", "description": "", "bullets": []}
            current.setdefault("bullets", []).append(line[m_bullet.end():].strip())
            continue

        # Tech-header line → fold into current project description
        m = _TECH_HDR.match(line)
        if m:
            if current is None:
                current = {"name": "", "description": "", "bullets": []}
            after = line[m.end():].strip()
            if after:
                desc = current.get("description", "")
                current["description"] = (desc + " | " + after) if desc else after
            continue

        # Labeled link line ("Link: ...", "GitHub: ...") → fold into bullets
        m_link = _LINK_HDR.match(line)
        if m_link:
            if current is None:
                current = {"name": "", "description": "", "bullets": []}
            after = line[m_link.end():].strip() or line.strip()
            current.setdefault("bullets", []).append(after)
            continue

        # Standalone URL → fold into current project bullets
        if _URL_LINE.match(line) and current is not None:
            current.setdefault("bullets", []).append(line.strip())
            continue

        # Tech-only line (comma-separated short tokens) → fold as technologies
        if current is not None and _looks_like_tech_list(line):
            desc = current.get("description", "")
            current["description"] = (desc + " | " + line).strip(" |") if desc else line
            continue

        # Short tech continuation: if the current project description looks like
        # a comma-separated tech list and this line is a single token (1 word,
        # no bullet), treat it as continuation of the tech list.
        # Catches: "Used Technologies: HTML, CSS\nJavaScript" where JavaScript
        # overflows onto the next line.
        if (current is not None
                and not current.get("bullets")
                and len(line.split()) == 1
                and not _BULLET_RE_PROJ.match(line)
                and not re.search(r"\d{4}|https?://|@", line)):
            desc = current.get("description", "")
            if desc and re.search(r",", desc):
                # Description has commas → looks like a tech list → merge
                current["description"] = desc + ", " + line
                continue

        # Continuation after trailing comma: if the current description ends
        # with a comma (e.g. "HTML, CSS,") and this line is a short token
        # (≤3 words, no bullet prefix), treat it as description continuation.
        if (current is not None
                and current.get("description", "").rstrip().endswith(",")
                and len(line.split()) <= 3
                and not _BULLET_RE_PROJ.match(line)):
            desc = current["description"]
            current["description"] = (desc + " " + line).rstrip(",").strip()
            continue

        if current is not None and current.get("bullets") and _looks_like_project_continuation(line):
            current["bullets"][-1] = (current["bullets"][-1].rstrip() + " " + line).strip()
            continue

        # If current project exists, hasn't collected bullets yet, and this
        # line looks like a sentence/description → treat as description
        if (current is not None
                and not current.get("bullets")
                and _looks_like_description(line)):
            desc = current.get("description", "")
            current["description"] = (desc + " " + line).strip() if desc else line
            continue

        # If it didn't match any of the above, it's a new project
        if current is not None:
            entries.append(current)
        current = {"name": line, "description": "", "bullets": []}

    if current is not None:
        entries.append(current)

    # Security: cap project entry count
    if len(entries) > _MAX_PROJECT_ENTRIES:
        logger.warning("parse_projects: entries capped %d → %d",
                       len(entries), _MAX_PROJECT_ENTRIES)
        entries = entries[:_MAX_PROJECT_ENTRIES]

    return entries


def structured_text_to_builder_payload(
    cv_text: str,
    job_description: str = "",
    lang: str = "en",
) -> CVModel:
    cv_text = _guard_text(cv_text, "cv_text")

    # Pipeline: raw → extract → normalize → CVSchema → CVModel
    extract_structured, normalize, _get_order = _get_pipeline_agents()
    extracted = extract_structured(cv_text)
    normalized = normalize(extracted)

    # Build strict schema first (single source of truth)
    schema = build_schema(normalized)

    # Convert to legacy CVModel for backward compatibility
    model = schema.to_cv_model()
    model.skills = _normalize_list_section([str(skill) for skill in (model.skills or [])])
    model.ensure_skills_categorized()
    return model


def _diff_preview(before_text: str, after_text: str) -> List[str]:
    diff = difflib.unified_diff(
        before_text.splitlines(),
        after_text.splitlines(),
        fromfile="original",
        tofile="optimized",
        lineterm="",
    )
    return list(diff)[:120]


def _collect_applied_changes(
    before_ats: Dict,
    after_ats: Dict,
    dropped_sections: List[str],
    structured_sections: Dict[str, List[str]],
    used_ai: bool,
) -> List[str]:
    changes: List[str] = []

    before_content = before_ats.get("content", {}) if isinstance(before_ats, dict) else {}
    after_content = after_ats.get("content", {}) if isinstance(after_ats, dict) else {}
    before_layout = before_ats.get("layout", {}) if isinstance(before_ats, dict) else {}
    after_layout = after_ats.get("layout", {}) if isinstance(after_ats, dict) else {}

    def _score(name: str, b: float, a: float):
        if a > b:
            changes.append(f"{name} improved ({round(b,2)} → {round(a,2)})")

    _score(
        "Keyword relevance",
        float(before_content.get("keyword_score", 0) or 0),
        float(after_content.get("keyword_score", 0) or 0),
    )
    _score(
        "Action verb usage",
        float(before_content.get("action_verb_score", 0) or 0),
        float(after_content.get("action_verb_score", 0) or 0),
    )
    _score(
        "Quantified achievements",
        float(before_content.get("achievement_score", 0) or 0),
        float(after_content.get("achievement_score", 0) or 0),
    )
    _score(
        "Section completeness",
        float(before_layout.get("section_presence_score", 0) or 0),
        float(after_layout.get("section_presence_score", 0) or 0),
    )
    _score(
        "Formatting consistency",
        float(before_layout.get("formatting_score", 0) or 0),
        float(after_layout.get("formatting_score", 0) or 0),
    )

    if dropped_sections:
        changes.append(f"Removed non-ATS sections: {', '.join(dropped_sections)}")

    if structured_sections:
        changes.append(
            "Standardized ATS section structure: "
            + ", ".join(sorted(structured_sections.keys()))
        )

    if used_ai:
        changes.append("Applied AI rewrite to improve ATS wording")

    if not changes:
        changes.append("No major structural changes were required")

    return changes


def _verify_section_preservation(
    cv_text: str,
    structured_sections: Dict[str, List[str]],
) -> set:
    """Detect sections present in the original CV but missing from pipeline output.

    Returns a set of canonical section keys that were lost during processing.
    Ignores 'contact' and 'interests' which are intentionally handled separately.
    """
    _, orig_sections, _ = _parse_sections(cv_text)
    original_keys = {
        k for k, v in orig_sections.items()
        if k not in {"contact", "interests"}
        and any((line or "").strip() for line in v)
    }
    structured_keys = {k for k, v in structured_sections.items() if v}
    return original_keys - structured_keys


def _restore_lost_sections(
    cv_text: str,
    structured_sections: Dict[str, List[str]],
    section_order: List[str],
    orig_name: str | None,
    orig_title_lines: List[str],
    orig_contacts: List[str],
) -> tuple[str, Dict[str, List[str]], List[str], List[str]]:
    """Restore sections that were lost during pipeline processing.

    Parses the original CV text to recover content for any sections that exist
    in the source but are missing from the pipeline output.  Returns the
    updated (text, structured_sections, section_order, restoration_warnings).
    """
    lost = _verify_section_preservation(cv_text, structured_sections)
    if not lost:
        return (
            _render_structured_sections(
                orig_name, orig_title_lines, orig_contacts,
                structured_sections, section_order,
            ),
            structured_sections,
            section_order,
            [],
        )

    _, orig_sections, _ = _parse_sections(cv_text)
    restoration_warnings: List[str] = []

    for lost_key in lost:
        orig_lines = [line for line in orig_sections.get(lost_key, []) if (line or "").strip()]
        if orig_lines:
            structured_sections[lost_key] = orig_lines
            if lost_key not in section_order:
                section_order.append(lost_key)
            title = SECTION_TITLES.get(lost_key, lost_key.upper())
            restoration_warnings.append(
                f"{title} section was not detected by the pipeline and was restored from the original CV."
            )
            logger.info("restore_lost_section: %s (%d lines)", lost_key, len(orig_lines))

    rebuilt_text = _render_structured_sections(
        orig_name, orig_title_lines, orig_contacts,
        structured_sections, section_order,
    )
    return rebuilt_text, structured_sections, section_order, restoration_warnings


def _non_empty_section_lines(sections: Dict[str, List[str]], key: str) -> List[str]:
    return [line for line in (sections.get(key) or []) if (line or "").strip()]


def _enforce_protected_section_floor(
    cv_text: str,
    optimized_text: str,
    structured_sections: Dict[str, List[str]],
    section_order: List[str],
    orig_name: str | None,
    orig_title_lines: List[str],
    orig_contacts: List[str],
) -> tuple[str, Dict[str, List[str]], List[str], List[str]]:
    """Never let normalization shrink evidence-heavy sections.

    Parser/AI rewrites may legitimately improve wording, but they must not
    reduce projects, certifications, skills, education, or languages. If the
    optimized output has fewer non-empty lines than the source for one of
    those sections, restore the original section lines.
    """
    _, source_sections, _ = _parse_sections(cv_text)
    _, current_sections, _ = _parse_sections(optimized_text)
    restored: List[str] = []
    rebuilt_sections: Dict[str, List[str]] = {
        key: list(values or []) for key, values in structured_sections.items()
    }

    for key in PROTECTED_SECTION_KEYS:
        source_lines = _non_empty_section_lines(source_sections, key)
        current_lines = _non_empty_section_lines(current_sections, key)
        if source_lines and len(current_lines) < len(source_lines):
            rebuilt_sections[key] = source_lines
            if key not in section_order:
                section_order.append(key)
            title = SECTION_TITLES.get(key, key.upper())
            restored.append(
                f"{title} section had fewer items after optimization and was restored from the original CV."
            )

    if not restored:
        return optimized_text, structured_sections, section_order, []

    rebuilt_text = _render_structured_sections(
        orig_name,
        orig_title_lines,
        orig_contacts,
        rebuilt_sections,
        section_order,
    )
    return rebuilt_text, rebuilt_sections, section_order, restored


def auto_fix_cv_text(
    cv_text: str,
    job_description: str = "",
    lang: str = "en",
    use_ai: bool = False,
    mode: str = "safe",
) -> Dict:
    cv_text = _guard_text(cv_text, "cv_text")
    job_description = (job_description or "").strip()

    # ═══ PIPELINE FIRST: raw → extract → normalize → JSON ═══
    # This handles multi-column, broken lines, GPA, bullet separation, etc.
    # BEFORE any text-level processing. Works for ALL CV types.
    extract_fn, normalize_fn, _get_order = _get_pipeline_agents()
    extracted = extract_fn(cv_text)
    normalized = normalize_fn(extracted)
    is_multi_column = extracted.get("_multi_column_detected", False)
    _, _, raw_dropped_sections = _parse_sections(cv_text)

    from services.extraction_validator import validate_extraction
    quality = validate_extraction(cv_text, normalized)
    needs_llm_fallback = quality.get("needs_llm_fallback", False)

    # Use the strict schema as the single source of truth for downstream text
    # and PDF payload generation. The validator above intentionally sees the
    # raw normalized output so it can still trigger AI fallback on bad parses.
    clean_schema = build_schema(normalized)
    normalized = clean_schema.model_dump()

    before_ats = analyze_cv(cv_text, job_description, lang=lang)

    # ═══ MODE DETECTION ═══
    section_confidence = _section_score(cv_text)
    detected_mode, _ = _detect_fix_mode(cv_text, mode)
    if mode == "safe":
        if section_confidence >= 4:
            detected_mode = "preserve"
        elif section_confidence >= 2:
            detected_mode = "light_fix"
        else:
            detected_mode = "rebuild"

    # Pipeline mode: never preserve raw parser output.
    if USE_PIPELINE and detected_mode == "preserve":
        detected_mode = "light_fix"

    # Multi-column CVs must always go through the pipeline (never preserve raw text)
    if is_multi_column and detected_mode == "preserve":
        detected_mode = "light_fix"

    if needs_llm_fallback and detected_mode == "light_fix":
        detected_mode = "rebuild"

    # ═══ GENERATE STRUCTURED TEXT FROM PIPELINE JSON ═══
    dropped_sections: List[str] = list(raw_dropped_sections)
    skills_inferred = False
    _restore_warns: List[str] = []

    if detected_mode == "preserve":
        # Minimal rewrite: just standardize headings on original text
        optimized_text = _minimal_heading_rewrite(cv_text)
        _, parsed_secs, _ = _parse_sections(optimized_text)
        structured_sections: Dict[str, List[str]] = {
            key: [line for line in values if line]
            for key, values in parsed_secs.items()
            if key in SECTION_ORDER and any((line or "").strip() for line in values)
        }
        section_order = _extract_section_order_from_text(cv_text)
    else:
        # Use pipeline output → clean structured text
        build_mode = "balanced" if detected_mode == "light_fix" else "strict"
        optimized_text, structured_sections, dropped_sections, section_order = (
            _pipeline_to_structured_text(normalized, job_description, mode=build_mode)
        )
        dropped_sections = sorted(set(raw_dropped_sections) | set(dropped_sections))

        # ═══ SECTION PRESERVATION: restore any sections lost by the pipeline ═══
        _pipe_name = normalized.get("full_name", "")
        _pipe_title = normalized.get("title", "")
        _pipe_contacts = [v for v in [
            normalized.get("email", ""),
            normalized.get("phone", ""),
            normalized.get("location", ""),
            normalized.get("linkedin", ""),
        ] if v]
        optimized_text, structured_sections, section_order, _restore_warns = (
            _restore_lost_sections(
                cv_text, structured_sections, section_order,
                orig_name=_pipe_name,
                orig_title_lines=[_pipe_title] if _pipe_title else [],
                orig_contacts=_pipe_contacts,
            )
        )

    # ═══ KEYWORD BOOSTING ═══
    if detected_mode != "preserve" and (job_description or use_ai or detected_mode == "rebuild"):
        boost_mode = "strict" if use_ai else ("balanced" if detected_mode == "light_fix" else "strict")
        boosted_text = _boost_keywords(
            optimized_text, structured_sections, job_description,
            mode=boost_mode, section_order=section_order,
        )
        boosted_ats = analyze_cv(boosted_text, job_description, lang=lang)
        plain_ats = analyze_cv(optimized_text, job_description, lang=lang)
        if float(boosted_ats.get("overall_score", 0) or 0) >= float(
            plain_ats.get("overall_score", 0) or 0
        ):
            optimized_text = boosted_text

    # ═══ SKILLS INJECTION ═══
    optimized_text, updated_sections, skills_inferred = _inject_skills_section_if_missing(
        optimized_text, job_description=job_description,
    )
    if skills_inferred:
        structured_sections = {
            key: [line for line in values if line]
            for key, values in updated_sections.items()
            if key in SECTION_ORDER and any((line or "").strip() for line in values)
        }

    # ═══ AI REWRITE (optional) ═══
    used_ai = False
    warnings: List[str] = list(_restore_warns) if detected_mode != "preserve" else []
    best_score = float(before_ats.get("overall_score", 0) or 0)
    current_ats = analyze_cv(optimized_text, job_description, lang=lang)
    current_score = float(current_ats.get("overall_score", 0) or 0)
    if current_score >= (best_score - STRUCTURED_SCORE_TOLERANCE):
        best_score = max(best_score, current_score)

    should_run_ai = False
    if needs_llm_fallback and rewrite_service.ai_rewrite_available():
        should_run_ai = True
        warnings.append("LLM Fallback triggered by Quality Validator due to catastrophic parsing failure.")
    elif use_ai and rewrite_service.ai_rewrite_available():
        should_run_ai = True
        
    if should_run_ai:
        try:
            ai_input_text = cv_text if needs_llm_fallback else optimized_text
            candidate = rewrite_service.rewrite_cv_for_ats(
                cv_text=ai_input_text,
                job_description=job_description,
                lang=lang,
            ).strip()
            if candidate:
                candidate_ats = analyze_cv(candidate, job_description, lang=lang)
                candidate_score = float(candidate_ats.get("overall_score", 0) or 0)
                if needs_llm_fallback or candidate_score >= best_score:
                    optimized_text = candidate
                    best_score = max(best_score, candidate_score)
                    used_ai = True
                else:
                    warnings.append(f"AI rewrite skipped (Score dropped from {best_score} to {candidate_score}).")
        except Exception as exc:
            warnings.append(f"AI rewrite unavailable: {exc}")

    # ═══ IDENTITY HEADER (from pipeline — always accurate) ═══
    orig_name = normalized.get("full_name", "")
    orig_title = normalized.get("title", "")
    orig_contacts = [v for v in [
        normalized.get("email", ""),
        normalized.get("phone", ""),
        normalized.get("location", ""),
        normalized.get("linkedin", ""),
    ] if v]
    optimized_text = _ensure_identity_header(
        optimized_text,
        fallback_name=orig_name,
        fallback_title_lines=[orig_title] if orig_title else [],
        fallback_contacts=orig_contacts,
    )

    # ═══ TEXT POLISHING (typos, punctuation, Turkish chars in English CVs) ═══
    optimized_text = _polish_text(optimized_text, lang=lang)
    optimized_text, structured_sections, section_order, _floor_warns = (
        _enforce_protected_section_floor(
            cv_text,
            optimized_text,
            structured_sections,
            section_order,
            orig_name=orig_name,
            orig_title_lines=[orig_title] if orig_title else [],
            orig_contacts=orig_contacts,
        )
    )
    warnings.extend(_floor_warns)
    if _floor_warns:
        optimized_text = _polish_text(optimized_text, lang=lang)

    # ═══ FINAL SCORING ═══
    after_ats = analyze_cv(optimized_text, job_description, lang=lang)

    # Auto-fix must not ship a lower-scoring rewrite. Prefer a conservative
    # heading-only fallback, and if that still regresses, preserve the source CV.
    after_score = float(after_ats.get("overall_score", 0) or 0)
    before_score = float(before_ats.get("overall_score", 0) or 0)
    score_regression = before_score - after_score

    # Check if sections were lost in the structured output
    lost_in_structured = _verify_section_preservation(cv_text, structured_sections)

    use_fallback = score_regression > 0

    if use_fallback:
        fallback_text = _minimal_heading_rewrite(cv_text)
        fallback_text = _ensure_identity_header(
            fallback_text,
            fallback_name=orig_name,
            fallback_title_lines=[orig_title] if orig_title else [],
            fallback_contacts=orig_contacts,
        )
        fallback_text = _polish_text(fallback_text, lang=lang)
        fallback_ats = analyze_cv(fallback_text, job_description, lang=lang)
        if float(fallback_ats.get("overall_score", 0) or 0) >= before_score:
            optimized_text = fallback_text
            after_ats = fallback_ats
            if lost_in_structured:
                warnings.append(
                    f"Structured rewrite lost sections ({', '.join(sorted(lost_in_structured))}) "
                    f"and scored lower (score drop: {round(score_regression, 1)}), "
                    f"so the safer non-regression output was used."
                )
            else:
                warnings.append(
                    f"Structured rewrite scored lower than the source CV "
                    f"(score drop: {round(score_regression, 1)}), "
                    f"so the safer non-regression output was used."
                )
    # ═══ APPLIED CHANGES ═══
    if float(after_ats.get("overall_score", 0) or 0) < before_score:
        optimized_text = cv_text
        after_ats = before_ats
        _, original_sections, _ = _parse_sections(cv_text)
        structured_sections = {
            key: _non_empty_section_lines(original_sections, key)
            for key in SECTION_ORDER
            if _non_empty_section_lines(original_sections, key)
        }
        section_order = _extract_section_order_from_text(cv_text)
        warnings.append(
            "No safe auto-fix variant improved the ATS score, so the original CV text was preserved."
        )

    score_delta = round(
        float(after_ats.get("overall_score", 0)) - float(before_ats.get("overall_score", 0)),
        2,
    )

    applied_changes = _collect_applied_changes(
        before_ats=before_ats,
        after_ats=after_ats,
        dropped_sections=dropped_sections,
        structured_sections=structured_sections,
        used_ai=used_ai,
    )
    applied_changes.insert(
        0,
        f"Smart mode selected: {detected_mode} (section_score={section_confidence}).",
    )
    if skills_inferred:
        applied_changes.append("SKILLS section was missing and was inferred from CV content.")
    if use_ai and not used_ai:
        applied_changes.append(
            "Applied strict wording polish: summary, experience, and project bullets were normalized with stronger ATS action verbs where safe."
        )
    if not any(c for c in applied_changes if "Smart mode" not in c):
        applied_changes.append("Clean CV detected; kept original content unchanged.")

    # ═══ BUILDER PAYLOAD — from already-normalized pipeline data ═══
    builder_payload = {
        "full_name": normalized.get("full_name", ""),
        "title": normalized.get("title", ""),
        "email": normalized.get("email", ""),
        "phone": normalized.get("phone", ""),
        "location": normalized.get("location", ""),
        "linkedin": normalized.get("linkedin", ""),
        "summary": normalized.get("summary", ""),
        "experiences": normalized.get("experiences", []),
        "education": normalized.get("education", []),
        "skills_categorized": normalized.get("skills_categorized", {}),
        "skills": normalized.get("skills", []),
        "certifications": normalized.get("certifications", []),
        "projects": normalized.get("projects", []),
        "languages": normalized.get("languages", []),
        "job_description": job_description or "",
        "template": "classic",
        "output_format": "docx",
        "lang": lang,
    }
    builder_model = CVModel.from_mapping(builder_payload)
    builder_model.ensure_skills_categorized()

    return {
        "original_cv_text": cv_text,
        "optimized_cv_text": optimized_text,
        "before_ats": before_ats,
        "after_ats": after_ats,
        "score_delta": score_delta,
        "used_ai": used_ai,
        "dropped_sections": dropped_sections,
        "structured_sections": sorted(structured_sections.keys()),
        "detected_mode": detected_mode,
        "section_score": section_confidence,
        "skills_inferred": skills_inferred,
        "has_sections": _has_sections(cv_text),
        "warnings": warnings,
        "applied_changes": applied_changes,
        "diff_preview": _diff_preview(cv_text, optimized_text),
        "builder_payload": builder_model.model_dump(),
    }


# Semantic alias — callers can use the clearer name
normalize_cv = auto_fix_cv_text
