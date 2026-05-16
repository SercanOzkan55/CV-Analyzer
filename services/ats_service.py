"""ATS Text Analysis — detailed section-level CV feedback.

This module operates on **raw text** (not CVModel) and provides:
  - Section-by-section scores with pass/warning/fail status
  - Localized recommendations (EN/TR)
  - Industry tips and next-step planning

For the authoritative numeric scorer (CVModel-based), use
``ats_scoring.score_cv()`` instead.
"""
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


def _has_project_based_experience(cv_text: str) -> bool:
    """Treat substantial project sections as experience for student/entry CVs."""
    text_lower = cv_text.lower()
    has_projects = bool(re.search(r"\b(?:projects?|key projects|projeler)\b", text_lower))
    if not has_projects:
        return False
    has_project_work = bool(
        re.search(
            r"\b(?:developed|implemented|designed|built|created|used|applied|managed|"
            r"geliştirdi|uyguladı|tasarladı)\b",
            text_lower,
        )
    )
    has_entry_context = bool(
        re.search(
            r"\b(?:student|intern|junior|entry[-\s]?level|graduate|computer engineer|"
            r"bachelor|university|öğrenci|stajyer|mezun|üniversite)\b",
            text_lower,
        )
    )
    return has_project_work and has_entry_context


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

# Multilingual action verbs — keyed by language code
ACTION_VERBS_I18N: dict[str, list[str]] = {
    "tr": [
        "yönetti", "liderlik etti", "koordine etti", "geliştirdi", "oluşturdu",
        "tasarladı", "uyguladı", "başlattı", "iyileştirdi", "optimize etti",
        "analiz etti", "değerlendirdi", "araştırdı", "teslim etti", "çözdü",
        "artırdı", "azalttı", "eğitti", "sundu", "otomatize etti",
        "entegre etti", "yeniden yapılandırdı", "denetledi", "planladı",
    ],
    "fr": [
        "dirigé", "géré", "coordonné", "développé", "créé", "conçu",
        "mis en œuvre", "lancé", "amélioré", "optimisé", "analysé",
        "évalué", "livré", "résolu", "augmenté", "réduit", "formé",
        "présenté", "automatisé", "intégré", "restructuré", "supervisé",
        "planifié", "négocié", "collaboré", "documenté",
    ],
    "de": [
        "geleitet", "geführt", "koordiniert", "entwickelt", "erstellt",
        "entworfen", "implementiert", "gestartet", "verbessert", "optimiert",
        "analysiert", "bewertet", "geliefert", "gelöst", "gesteigert",
        "reduziert", "geschult", "präsentiert", "automatisiert", "integriert",
        "umstrukturiert", "überwacht", "geplant", "verhandelt",
    ],
    "es": [
        "dirigió", "gestionó", "coordinó", "desarrolló", "creó", "diseñó",
        "implementó", "lanzó", "mejoró", "optimizó", "analizó", "evaluó",
        "entregó", "resolvió", "aumentó", "redujo", "capacitó", "presentó",
        "automatizó", "integró", "reestructuró", "supervisó", "planificó",
        "negoció", "colaboró", "documentó",
    ],
    "pt": [
        "liderou", "gerenciou", "coordenou", "desenvolveu", "criou",
        "projetou", "implementou", "lançou", "melhorou", "otimizou",
        "analisou", "avaliou", "entregou", "resolveu", "aumentou",
        "reduziu", "treinou", "apresentou", "automatizou", "integrou",
        "reestruturou", "supervisionou", "planejou", "negociou",
    ],
    "it": [
        "diretto", "gestito", "coordinato", "sviluppato", "creato",
        "progettato", "implementato", "lanciato", "migliorato", "ottimizzato",
        "analizzato", "valutato", "consegnato", "risolto", "aumentato",
        "ridotto", "formato", "presentato", "automatizzato", "integrato",
        "ristrutturato", "supervisionato", "pianificato", "negoziato",
    ],
    "nl": [
        "geleid", "beheerd", "gecoördineerd", "ontwikkeld", "gecreëerd",
        "ontworpen", "geïmplementeerd", "gelanceerd", "verbeterd",
        "geoptimaliseerd", "geanalyseerd", "beoordeeld", "opgeleverd",
        "opgelost", "verhoogd", "verlaagd", "getraind", "gepresenteerd",
        "geautomatiseerd", "geïntegreerd", "geherstructureerd",
    ],
    "ru": [
        "руководил", "управлял", "координировал", "разработал", "создал",
        "спроектировал", "внедрил", "запустил", "улучшил", "оптимизировал",
        "проанализировал", "оценил", "доставил", "решил", "увеличил",
        "сократил", "обучил", "презентовал", "автоматизировал",
        "интегрировал", "реструктуризировал", "контролировал",
    ],
    "pl": [
        "kierował", "zarządzał", "koordynował", "opracował", "stworzył",
        "zaprojektował", "wdrożył", "uruchomił", "usprawnił", "zoptymalizował",
        "przeanalizował", "ocenił", "dostarczył", "rozwiązał", "zwiększył",
        "zmniejszył", "przeszkolił", "zaprezentował", "zautomatyzował",
    ],
    "sv": [
        "ledde", "hanterade", "koordinerade", "utvecklade", "skapade",
        "designade", "implementerade", "lanserade", "förbättrade",
        "optimerade", "analyserade", "utvärderade", "levererade",
        "löste", "ökade", "minskade", "utbildade", "presenterade",
    ],
    "no": [
        "ledet", "administrerte", "koordinerte", "utviklet", "opprettet",
        "designet", "implementerte", "lanserte", "forbedret",
        "optimaliserte", "analyserte", "evaluerte", "leverte",
        "løste", "økte", "reduserte", "trente", "presenterte",
    ],
    "da": [
        "ledte", "styrede", "koordinerede", "udviklede", "skabte",
        "designede", "implementerede", "lancerede", "forbedrede",
        "optimerede", "analyserede", "evaluerede", "leverede",
        "løste", "øgede", "reducerede", "uddannede", "præsenterede",
    ],
    "fi": [
        "johti", "hallinnoi", "koordinoi", "kehitti", "loi",
        "suunnitteli", "toteutti", "käynnisti", "paransi", "optimoi",
        "analysoi", "arvioi", "toimitti", "ratkaisi", "kasvatti",
        "vähensi", "koulutti", "esitti", "automatisoi",
    ],
    "cs": [
        "vedl", "řídil", "koordinoval", "vyvinul", "vytvořil",
        "navrhl", "implementoval", "spustil", "vylepšil", "optimalizoval",
        "analyzoval", "vyhodnotil", "dodal", "vyřešil", "zvýšil",
        "snížil", "vyškolil", "prezentoval", "automatizoval",
    ],
    "hu": [
        "vezette", "irányította", "koordinálta", "fejlesztette", "létrehozta",
        "tervezte", "megvalósította", "elindította", "javította",
        "optimalizálta", "elemezte", "értékelte", "szállította",
        "megoldotta", "növelte", "csökkentette", "képezte", "bemutatta",
    ],
    "ro": [
        "condus", "gestionat", "coordonat", "dezvoltat", "creat",
        "proiectat", "implementat", "lansat", "îmbunătățit", "optimizat",
        "analizat", "evaluat", "livrat", "rezolvat", "crescut",
        "redus", "instruit", "prezentat", "automatizat",
    ],
    "ar": [
        "قاد", "أدار", "نسق", "طور", "أنشأ", "صمم",
        "نفذ", "أطلق", "حسن", "حلل", "قيم",
        "سلم", "حل", "زاد", "قلل", "درب", "قدم",
    ],
    "zh": [
        "领导", "管理", "协调", "开发", "创建", "设计",
        "实施", "启动", "改进", "优化", "分析", "评估",
        "交付", "解决", "提升", "降低", "培训", "展示",
        "自动化", "集成", "重构", "监督", "规划",
    ],
    "ja": [
        "主導", "管理", "調整", "開発", "構築", "設計",
        "実装", "立ち上げ", "改善", "最適化", "分析", "評価",
        "提供", "解決", "向上", "削減", "教育", "発表",
        "自動化", "統合", "リファクタリング",
    ],
    "ko": [
        "리드", "관리", "조정", "개발", "구축", "설계",
        "구현", "출시", "개선", "최적화", "분석", "평가",
        "전달", "해결", "증가", "감소", "교육", "발표",
        "자동화", "통합", "주도",
    ],
    "hi": [
        "नेतृत्व किया", "प्रबंधन किया", "समन्वय किया", "विकसित किया",
        "बनाया", "डिज़ाइन किया", "लागू किया", "शुरू किया",
        "सुधार किया", "अनुकूलित किया", "विश्लेषण किया", "मूल्यांकन किया",
        "वितरित किया", "हल किया", "बढ़ाया", "कम किया", "प्रशिक्षित किया",
    ],
    "id": [
        "memimpin", "mengelola", "mengkoordinasi", "mengembangkan",
        "membuat", "merancang", "mengimplementasi", "meluncurkan",
        "meningkatkan", "mengoptimalkan", "menganalisis", "mengevaluasi",
        "menyampaikan", "menyelesaikan", "melatih", "mempresentasikan",
    ],
    "vi": [
        "lãnh đạo", "quản lý", "điều phối", "phát triển",
        "tạo", "thiết kế", "triển khai", "khởi động",
        "cải thiện", "tối ưu hóa", "phân tích", "đánh giá",
        "giao", "giải quyết", "tăng", "giảm", "đào tạo",
    ],
    "th": [
        "นำ", "บริหาร", "ประสานงาน", "พัฒนา", "สร้าง",
        "ออกแบบ", "ดำเนินการ", "เปิดตัว", "ปรับปรุง",
        "เพิ่มประสิทธิภาพ", "วิเคราะห์", "ประเมิน", "ส่งมอบ",
        "แก้ไข", "เพิ่ม", "ลด", "ฝึกอบรม", "นำเสนอ",
    ],
}


def get_action_verbs(lang: str = "en") -> list[str]:
    """Return action verbs for the given language, with EN as fallback."""
    if lang == "en" or lang not in ACTION_VERBS_I18N:
        return ACTION_VERBS
    return ACTION_VERBS + ACTION_VERBS_I18N[lang]

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
    github = re.search(r"github\.com/[A-Za-z0-9_-]+", text.lower())
    portfolio = re.search(r"(?:portfolio|website|blog)\s*[:.]?\s*(?:https?://)?[\w\.-]+\.\w{2,}", text.lower())

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

    # Compact header bonus: contacts in first 5 lines = better ATS parsing
    first_lines = "\n".join(text.split("\n")[:5])
    contacts_in_header = sum([
        bool(re.search(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}", first_lines)),
        bool(re.search(r"(\+?\d[\d\s\-()]{6,}\d)", first_lines)),
    ])
    if contacts_in_header >= 2:
        score += 10

    # Pipe-separated single-line contact format bonus (ATS-optimised)
    if re.search(r".+\|.+\|.+", first_lines):
        score += 5

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

    # 6) Standardised heading bonus — ALL CAPS standard headings score better.
    #    Real ATS parsers recognise these more reliably.
    standard_headings = [
        "PROFESSIONAL SUMMARY", "EXPERIENCE", "EDUCATION", "SKILLS",
        "PROJECTS", "CERTIFICATIONS", "LANGUAGES",
    ]
    std_count = sum(1 for h in standard_headings if h in cv_text)
    if std_count >= 4:
        score = min(100.0, score + 8.0)
    elif std_count >= 3:
        score = min(100.0, score + 5.0)

    # 7) Compact contact header bonus (name + contacts in first 3 lines)
    first_lines = non_empty_lines[:3]
    contact_in_header = sum(
        1 for l in first_lines
        if re.search(r"[@|]", l) or re.search(r"\+?\d[\d\s\-]{7,}", l)
    )
    if contact_in_header >= 1:
        score = min(100.0, score + 3.0)

    return max(0.0, score)


def _summary_score(cv_text: str) -> float:
    """Score the professional summary / profile section."""
    text_lower = cv_text.lower()
    has_summary = bool(
        re.search(r"\b(?:summary|profile|objective|professional\s+summary|about\s+me|özet|profil)\b", text_lower)
    )
    if not has_summary:
        return 30.0

    # Try to extract summary text (text between summary header and next section)
    summary_match = re.search(
        r"(?:summary|profile|objective|professional\s+summary|about\s+me|özet|profil)\s*\n([\s\S]{10,500}?)(?:\n\s*(?:experience|education|skills|projects|work)\b|\Z)",
        text_lower,
    )
    if not summary_match:
        return 55.0

    summary_text = summary_match.group(1).strip()
    score = 50.0

    word_count = len(summary_text.split())
    if 20 <= word_count <= 80:
        score += 20.0
    elif 10 <= word_count < 20:
        score += 10.0

    # Contains keywords / action verbs
    action_count = sum(1 for v in ACTION_VERBS[:20] if re.search(r"\b" + re.escape(v), summary_text))
    if action_count >= 3:
        score += 15.0
    elif action_count >= 1:
        score += 8.0

    # Contains quantification
    quant = sum(1 for p in QUANTIFICATION_PATTERNS if re.findall(p, summary_text))
    if quant >= 1:
        score += 15.0

    return min(100.0, score)


def _skills_section_score(cv_text: str, job_text: str = "") -> float:
    """Score the skills section quality."""
    text_lower = cv_text.lower()
    has_skills = bool(
        re.search(r"\b(?:skills|technical\s+skills|core\s+competencies|competencies|beceriler|yetenekler)\b", text_lower)
    )
    if not has_skills:
        return 25.0

    score = 50.0

    # Count skill-like items (comma/pipe separated or bullet listed)
    skill_lines = re.findall(r"(?:skills|competencies|beceriler)[\s\S]{0,50}\n([\s\S]{10,1000}?)(?:\n\s*(?:experience|education|projects|certifications)\b|\Z)", text_lower)
    skill_text = skill_lines[0] if skill_lines else ""

    if skill_text:
        # Count individual skills (comma, pipe, bullet separated)
        items = re.split(r"[,|•\-\n]+", skill_text)
        items = [i.strip() for i in items if len(i.strip()) > 1]
        skill_count = len(items)

        if skill_count >= 10:
            score += 25.0
        elif skill_count >= 6:
            score += 18.0
        elif skill_count >= 3:
            score += 10.0

        # Are skills categorized?
        categories = re.findall(r"\b(?:languages?|frameworks?|databases?|tools?|platforms?|devops|cloud|frontend|backend|programming)\b", skill_text)
        if len(set(categories)) >= 2:
            score += 15.0

    # Keyword overlap with job description
    if job_text:
        from .keyword_service import keyword_match_score
        skill_keyword = keyword_match_score(skill_text or cv_text, job_text)
        score += min(20.0, skill_keyword * 0.2)

    return min(100.0, score)


def _work_experience_score(cv_text: str) -> float:
    """Score work experience section quality (structure, bullets, metrics)."""
    text_lower = cv_text.lower()
    has_exp = bool(
        re.search(r"\b(?:experience|work\s+experience|professional\s+experience|employment|deneyim|iş\s+deneyimi)\b", text_lower)
    )
    if not has_exp:
        if not _has_project_based_experience(cv_text):
            return 20.0
        # Student and entry-level CVs often carry practical work under
        # Projects. Score that as project-based experience without requiring
        # the CV to invent a formal work-history section.
        score = 45.0
        bullets = len(re.findall(r"(^|\n)\s*(\-|\*|â€¢|•)\s+", cv_text))
        if bullets >= 6:
            score += 12.0
        elif bullets >= 3:
            score += 8.0
        action_count = sum(
            1
            for v in ACTION_VERBS
            if re.search(r"\b" + re.escape(v) + r"(?:s|ed|ing|d)?\b", text_lower)
        )
        if action_count >= 5:
            score += 12.0
        elif action_count >= 2:
            score += 8.0
        return min(70.0, score)

    score = 45.0

    # Count experience entries (date range patterns)
    date_ranges = re.findall(
        r"((?:19|20)\d{2})\s*(?:[-–—]|to)\s*((?:19|20)\d{2}|present|current|now|günümüz|halen|devam)",
        text_lower,
    )
    entry_count = len(date_ranges)
    if entry_count >= 3:
        score += 15.0
    elif entry_count >= 2:
        score += 10.0
    elif entry_count >= 1:
        score += 5.0

    # Bullet points in experience section
    bullets = len(re.findall(r"(^|\n)\s*(\-|\*|•)\s+", cv_text))
    if bullets >= 8:
        score += 15.0
    elif bullets >= 4:
        score += 10.0
    elif bullets >= 2:
        score += 5.0

    # Action verbs
    action_count = sum(1 for v in ACTION_VERBS if re.search(r"\b" + re.escape(v) + r"(?:s|ed|ing|d)?\b", text_lower))
    if action_count >= 8:
        score += 15.0
    elif action_count >= 4:
        score += 10.0
    elif action_count >= 2:
        score += 5.0

    # Quantified achievements in experience
    quant_hits = 0
    for pattern in QUANTIFICATION_PATTERNS:
        quant_hits += len(re.findall(pattern, cv_text))
    if quant_hits >= 4:
        score += 20.0
    elif quant_hits >= 2:
        score += 12.0
    elif quant_hits >= 1:
        score += 6.0

    return min(100.0, score)


def _education_score(cv_text: str) -> float:
    """Score education section presence and quality."""
    text_lower = cv_text.lower()
    has_edu = bool(
        re.search(r"\b(?:education|academic|eğitim|öğrenim|university|üniversite)\b", text_lower)
    )
    if not has_edu:
        return 20.0

    score = 45.0

    # Degree keywords
    degree_keywords = [
        "bachelor", "master", "phd", "mba", "associate", "diploma",
        "b.s.", "b.a.", "m.s.", "m.a.", "b.sc", "m.sc",
        "lisans", "yüksek lisans", "doktora", "mühendislik",
    ]
    degree_found = sum(1 for d in degree_keywords if d in text_lower)
    if degree_found >= 1:
        score += 15.0

    # Institution name present
    institution_patterns = [
        r"\b(?:university|college|institute|school|akademi|üniversite)\b",
    ]
    if any(re.search(p, text_lower) for p in institution_patterns):
        score += 10.0

    # Dates present
    if re.search(r"((?:19|20)\d{2})", text_lower):
        score += 10.0

    # GPA present
    if re.search(r"\b(?:gpa|grade|not\s*ortalaması)\b", text_lower):
        score += 10.0

    # Field of study
    if re.search(r"\b(?:computer|software|engineering|science|business|management|bilgisayar|yazılım|mühendislik)\b", text_lower):
        score += 10.0

    return min(100.0, score)


def _get_section_status(score: float) -> str:
    """Return pass/warning/fail based on score."""
    if score >= 70:
        return "pass"
    elif score >= 50:
        return "warning"
    return "fail"


def _get_section_message(section: str, score: float, lang: str = "en") -> dict:
    """Return a bilingual status message dict for a section."""
    status = _get_section_status(score)
    messages = _SECTION_MESSAGES.get(section, {}).get(status, {})
    return {"en": messages.get("en", ""), "tr": messages.get("tr", messages.get("en", ""))}


_SECTION_MESSAGES = {
    "education": {
        "pass": {
            "en": "Education section is clear with degree, institution, dates, and GPA. Shows strong academic performance.",
            "tr": "Eğitim bölümü derece, kurum, tarihler ve GPA ile net. Güçlü akademik performans gösteriyor.",
        },
        "warning": {
            "en": "Education section exists but could be improved with more details.",
            "tr": "Eğitim bölümü mevcut ama daha fazla detayla geliştirilebilir.",
        },
        "fail": {
            "en": "Education section is missing or incomplete. Add degree, institution, and dates.",
            "tr": "Eğitim bölümü eksik veya tamamlanmamış. Derece, kurum ve tarih ekleyin.",
        },
    },
    "formatting": {
        "pass": {
            "en": "Formatting is clean with consistent visual hierarchy and good readability.",
            "tr": "Biçimlendirme tutarlı görsel hiyerarşi ve iyi okunabilirlik ile temiz.",
        },
        "warning": {
            "en": "Overall formatting is clean but could be improved for better visual hierarchy and consistency.",
            "tr": "Genel biçimlendirme temiz ama daha iyi görsel hiyerarşi ve tutarlılık için geliştirilebilir.",
        },
        "fail": {
            "en": "Formatting has significant inconsistencies that may confuse ATS systems.",
            "tr": "Biçimlendirmede ATS sistemlerini karıştırabilecek önemli tutarsızlıklar var.",
        },
    },
    "contact": {
        "pass": {
            "en": "Contact information is complete and includes phone, email, location, and GitHub link.",
            "tr": "İletişim bilgileri eksiksiz; telefon, e-posta, konum ve GitHub bağlantısı içeriyor.",
        },
        "warning": {
            "en": "Contact information is present but missing some elements (LinkedIn, phone, or location).",
            "tr": "İletişim bilgileri mevcut ama bazı ögeler eksik (LinkedIn, telefon veya konum).",
        },
        "fail": {
            "en": "Contact information is missing or very incomplete. Add email, phone, and location.",
            "tr": "İletişim bilgileri eksik veya çok yetersiz. E-posta, telefon ve konum ekleyin.",
        },
    },
    "skills": {
        "pass": {
            "en": "Skills are relevant and categorized, but could be expanded with proficiency levels or additional tools.",
            "tr": "Beceriler alakalı ve kategorize edilmiş, yeterlilik düzeyleri veya ek araçlarla genişletilebilir.",
        },
        "warning": {
            "en": "Skills section exists but lacks organization or relevance to the target role.",
            "tr": "Beceri bölümü mevcut ama organizasyon veya hedef rolle ilgisi eksik.",
        },
        "fail": {
            "en": "Skills section is missing or very limited. Add a categorized skills section.",
            "tr": "Beceri bölümü eksik veya çok sınırlı. Kategorize edilmiş bir beceri bölümü ekleyin.",
        },
    },
    "experience": {
        "pass": {
            "en": "Work experience is well described with technical details and measurable achievements.",
            "tr": "İş deneyimi teknik detaylar ve ölçülebilir başarılarla iyi tanımlanmış.",
        },
        "warning": {
            "en": "Work experience section exists but could benefit from more metrics and action verbs.",
            "tr": "İş deneyimi bölümü mevcut ama daha fazla metrik ve eylem fiilleriyle geliştirebilir.",
        },
        "fail": {
            "en": "Work experience section is missing or lacks detail. Add roles with bullets and metrics.",
            "tr": "İş deneyimi bölümü eksik veya detaysız. Maddeler ve metriklerle roller ekleyin.",
        },
    },
    "ats_compatibility": {
        "pass": {
            "en": "Resume is mostly ATS-friendly with clear section headings and keywords.",
            "tr": "CV çoğunlukla ATS uyumlu, net bölüm başlıkları ve anahtar kelimeler içeriyor.",
        },
        "warning": {
            "en": "Resume has some ATS compatibility issues that should be addressed.",
            "tr": "CV'de ele alınması gereken bazı ATS uyumluluk sorunları var.",
        },
        "fail": {
            "en": "Resume has significant ATS compatibility issues. Restructure for better parsing.",
            "tr": "CV'de önemli ATS uyumluluk sorunları var. Daha iyi ayrıştırma için yeniden yapılandırın.",
        },
    },
    "keywords": {
        "pass": {
            "en": "Good keyword coverage with relevant terms from the job description.",
            "tr": "İş tanımından ilgili terimlerle iyi anahtar kelime kapsamı.",
        },
        "warning": {
            "en": "Some keywords from the job description are missing. Incorporate more relevant terms.",
            "tr": "İş tanımındaki bazı anahtar kelimeler eksik. Daha fazla ilgili terim ekleyin.",
        },
        "fail": {
            "en": "Very low keyword match with the job description. Tailor your CV to the target role.",
            "tr": "İş tanımıyla çok düşük anahtar kelime eşleşmesi. CV'nizi hedef role göre özelleştirin.",
        },
    },
    "summary": {
        "pass": {
            "en": "Professional summary is clear and effectively highlights career goals and key skills.",
            "tr": "Profesyonel özet net ve kariyer hedeflerini ve temel becerileri etkili bir şekilde vurguluyor.",
        },
        "warning": {
            "en": "Professional summary exists but could be more targeted and impactful.",
            "tr": "Profesyonel özet mevcut ama daha hedefli ve etkili olabilir.",
        },
        "fail": {
            "en": "Professional summary is missing or too vague. Add a 2-3 sentence targeted summary.",
            "tr": "Profesyonel özet eksik veya çok belirsiz. 2-3 cümlelik hedefli bir özet ekleyin.",
        },
    },
}


_SECTION_RECOMMENDATIONS = {
    "education": {
        "en": [
            "Add expected graduation date for current degree.",
            "Include relevant coursework or academic projects if space allows.",
            "Add GPA if it strengthens your application.",
        ],
        "tr": [
            "Mevcut derece için beklenen mezuniyet tarihini ekleyin.",
            "Alan izin veriyorsa ilgili dersleri veya akademik projeleri ekleyin.",
            "Başvurunuzu güçlendiriyorsa GPA ekleyin.",
        ],
    },
    "formatting": {
        "en": [
            "Use consistent bullet point styles and indentation.",
            "Ensure uniform spacing between sections.",
            "Consider using bold or italics consistently for section headers and job titles.",
        ],
        "tr": [
            "Tutarlı madde işareti stilleri ve girinti kullanın.",
            "Bölümler arasında düzgün boşluk bırakın.",
            "Bölüm başlıkları ve iş unvanları için tutarlı kalın veya italik kullanmayı düşünün.",
        ],
    },
    "contact": {
        "en": [
            "Add LinkedIn profile if available.",
            "Format phone number in international format consistently.",
            "Include a professional portfolio or GitHub link if relevant.",
        ],
        "tr": [
            "Varsa LinkedIn profili ekleyin.",
            "Telefon numarasını tutarlı bir şekilde uluslararası formatta yazın.",
            "İlgiliyse profesyonel portfolyo veya GitHub bağlantısı ekleyin.",
        ],
    },
    "skills": {
        "en": [
            "Add proficiency levels (e.g., proficient, familiar) for each skill.",
            "Include any relevant frameworks, libraries, or software tools used.",
            "Categorize skills into logical groups (Languages, Frameworks, Tools, etc.).",
        ],
        "tr": [
            "Her beceri için yeterlilik düzeyleri ekleyin (ör. ileri, orta, başlangıç).",
            "Kullanılan ilgili framework, kütüphane veya yazılım araçlarını ekleyin.",
            "Becerileri mantıklı gruplara ayırın (Diller, Framework'ler, Araçlar, vb.).",
        ],
    },
    "experience": {
        "en": [
            "Add specific achievements or results with metrics if possible.",
            "Clarify if internship was full-time or part-time.",
            "Include any teamwork or leadership experiences.",
            "Start each bullet with a strong action verb.",
        ],
        "tr": [
            "Mümkünse metriklerle belirli başarılar veya sonuçlar ekleyin.",
            "Stajın tam zamanlı mı yarı zamanlı mı olduğunu belirtin.",
            "Takım çalışması veya liderlik deneyimlerini ekleyin.",
            "Her maddeyi güçlü bir eylem fiili ile başlatın.",
        ],
    },
    "ats_compatibility": {
        "en": [
            "Avoid special characters or unusual symbols that may confuse ATS.",
            "Use standard fonts and avoid graphics or tables.",
            "Keep section headings standard (Experience, Education, Skills).",
        ],
        "tr": [
            "ATS'yi karıştırabilecek özel karakterler veya olağandışı sembollerden kaçının.",
            "Standart yazı tipleri kullanın ve grafikler veya tablolardan kaçının.",
            "Bölüm başlıklarını standart tutun (Deneyim, Eğitim, Beceriler).",
        ],
    },
    "keywords": {
        "en": [
            "Mirror key terms from the job description in your CV.",
            "Include both acronyms and full forms of technical terms.",
            "Naturally weave keywords into experience bullets, not just the skills section.",
        ],
        "tr": [
            "İş tanımındaki ana terimleri CV'nizde yansıtın.",
            "Teknik terimlerin hem kısaltmalarını hem tam hallerini ekleyin.",
            "Anahtar kelimeleri sadece beceri bölümüne değil, deneyim maddelerine de doğal şekilde ekleyin.",
        ],
    },
    "summary": {
        "en": [
            "Expand professional summary to clearly state career goals and key skills.",
            "Tailor the summary to the specific job you are applying for.",
            "Include 1-2 quantifiable highlights in the summary.",
        ],
        "tr": [
            "Profesyonel özeti kariyer hedeflerinizi ve temel becerilerinizi net olarak belirtecek şekilde genişletin.",
            "Özeti başvurduğunuz iş için özelleştirin.",
            "Özete 1-2 ölçülebilir vurgu ekleyin.",
        ],
    },
}


def _get_section_recommendations(section: str, score: float, lang: str = "en") -> list:
    """Get bilingual recommendations for a section based on score."""
    if score >= 90:
        return []
    recs = _SECTION_RECOMMENDATIONS.get(section, {})
    en_items = recs.get("en", [])
    tr_items = recs.get("tr", en_items)
    limit = 2 if score >= 70 else 3
    return [{"en": en_items[i], "tr": tr_items[i] if i < len(tr_items) else en_items[i]} for i in range(min(limit, len(en_items)))]


def compute_final_score(
    keyword: float,
    section: float,
    exp: float,
    skills: float,
    layout: float,
    contact: float,
    ml_score: float,
    ml_confidence: float | None = None,
    debug: bool = False,
) -> float:
    """Compute final ATS score using rule-based weights + ML blend.

    The split between rule-based and ML is controlled by the
    MODEL_WEIGHT / ATS_WEIGHT env vars (defaults 0.25 / 0.75).
    When keyword is 0 (no job description) its weight is redistributed.

    **Safeguards:** Each score input is validated and clamped to [0, 100].
    None values fall back to a conservative default (60.0) and emit a
    warning log so integration bugs surface quickly in production.
    """
    import os
    import logging as _logging
    _log = _logging.getLogger(__name__)

    # ── Input validation / safeguard ────────────────────────────────
    _DEFAULT = 60.0  # conservative fallback for missing scores
    _inputs = {"keyword": keyword, "section": section, "exp": exp,
               "skills": skills, "layout": layout, "contact": contact}
    _overrides = []
    _input_warnings = []
    for _name, _val in _inputs.items():
        if _val is None:
            _overrides.append(_name)
            _input_warnings.append(f"missing_{_name}_score")
            _inputs[_name] = _DEFAULT
        else:
            try:
                _inputs[_name] = max(0.0, min(100.0, float(_val)))
            except (TypeError, ValueError):
                _overrides.append(_name)
                _input_warnings.append(f"invalid_{_name}_score")
                _inputs[_name] = _DEFAULT
    if _overrides:
        _log.warning(
            "compute_final_score: missing/invalid inputs defaulted to %.0f: %s",
            _DEFAULT, _overrides,
        )
    # Score confidence: 1.0 when all inputs valid, drops per defaulted input
    _score_confidence = round(max(0.0, 1.0 - len(_overrides) * 0.12), 2)

    keyword = _inputs["keyword"]
    section = _inputs["section"]
    exp = _inputs["exp"]
    skills = _inputs["skills"]
    layout = _inputs["layout"]
    contact = _inputs["contact"]

    ats_w = float(os.getenv("ATS_WEIGHT", 0.75))
    ml_w = float(os.getenv("MODEL_WEIGHT", 0.25))
    total = ats_w + ml_w or 1.0
    ats_w, ml_w = ats_w / total, ml_w / total  # normalise to 1.0

    # Safety overrides: if ML signal is untrusted or wildly different from
    # the rule-based score, prefer the rule-based score for stability.
    ml_conf_threshold = float(os.getenv("ML_CONFIDENCE_THRESHOLD", 0.6))
    ml_discrepancy_max = float(os.getenv("ML_DISCREPANCY_MAX", 20.0))

    # When keyword is effectively 0 (no job desc), redistribute weight
    if keyword < 1.0:
        rule_score = (
            section * 0.25
            + exp * 0.25
            + skills * 0.20
            + layout * 0.18
            + contact * 0.12
        )
    else:
        rule_score = (
            keyword * 0.20
            + section * 0.18
            + exp * 0.22
            + skills * 0.15
            + layout * 0.15
            + contact * 0.10
        )
    # Decide whether to use ML blend or override with rule_score
    use_ml = True
    ml_reason = None
    try:
        ml_val = float(ml_score)
    except Exception:
        ml_val = float(0.0)
        use_ml = False
        ml_reason = "ml_not_numeric"

    if ml_confidence is not None and float(ml_confidence) < ml_conf_threshold:
        use_ml = False
        ml_reason = "low_confidence"

    if use_ml and abs(rule_score - ml_val) > ml_discrepancy_max:
        use_ml = False
        ml_reason = "large_discrepancy"

    if not use_ml:
        final = round(max(0.0, min(100.0, rule_score)), 2)
        if debug:
            return {
                "final": final,
                "rule_score": round(rule_score, 2),
                "ml_score": round(float(ml_val), 2),
                "ats_weight": round(ats_w, 3),
                "model_weight": 0.0,
                "ml_overridden": True,
                "ml_override_reason": ml_reason,
                "score_confidence": _score_confidence,
                "input_warnings": _input_warnings,
            }
        return final

    final = rule_score * ats_w + ml_val * ml_w
    final = round(max(0.0, min(100.0, final)), 2)
    if debug:
        return {
            "final": final,
            "rule_score": round(rule_score, 2),
            "ml_score": round(float(ml_val), 2),
            "ats_weight": round(ats_w, 3),
            "model_weight": round(ml_w, 3),
            "ml_overridden": False,
            "score_confidence": _score_confidence,
            "input_warnings": _input_warnings,
        }
    return final


def analyze_cv(cv_text: str, job_text: str = "", lang: str = "en") -> Dict:
    """
    Returns a dictionary with detailed ATS compatibility scores and suggestions.

    - content_score: how well the words/keywords/achievements align with `job_text`
    - layout_score: structural & formatting heuristics (sections, contact, bullets, length)
    - overall_score: weighted combination
    - section_scores: per-section detailed scoring with status and recommendations
    - suggestions: actionable items to improve ATS compatibility
    """

    # Content related
    keyword_score = 0.0
    if job_text and job_text.strip():
        keyword_score = keyword_match_score(cv_text, job_text)
    else:
        keyword_score = 0.0

    # Spam / density penalty (prevent copy-paste job descriptions)
    penalty = _keyword_density_penalty(cv_text, job_text)

    action_score = _action_verb_score(cv_text)

    # Quantified achievements: percentages, dollar amounts, large numbers
    quant_hits = 0
    for pattern in QUANTIFICATION_PATTERNS:
        quant_hits += len(re.findall(pattern, cv_text))
    quant_hits += len(
        re.findall(
            r"\b\d+\s+(?:users|clients|customers|projects|team members|employees|servers|applications|features|releases|deployments|endpoints|repositories|databases|microservices)\b",
            cv_text.lower(),
        )
    )
    achievement_score = float(min(100.0, quant_hits * 12))

    # Layout / structure
    sections_found = _find_sections(cv_text)
    required_found = [
        s
        for s in MIN_REQUIRED_SECTIONS
        if re.search(r"\b" + re.escape(s) + r"\b", cv_text.lower())
    ]
    if "experience" not in required_found and _has_project_based_experience(cv_text):
        required_found.append("experience")
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

    # Section order bonus
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

    # Content scoring
    if job_text and job_text.strip():
        content_score = (
            (0.6 * keyword_score) + (0.2 * action_score) + (0.2 * achievement_score)
        )
        content_score += penalty
    else:
        content_score = (0.5 * action_score) + (0.5 * achievement_score)

    content_score = max(0.0, min(100.0, content_score))

    # Formatting consistency score
    formatting_score = _formatting_consistency_score(cv_text)

    # ── Section-level detailed scores ────────────────────────────────
    edu_score = _education_score(cv_text)
    summary_score = _summary_score(cv_text)
    skills_score = _skills_section_score(cv_text, job_text)
    work_exp_score = _work_experience_score(cv_text)

    # ATS compatibility composite
    ats_compat_score = round(
        0.30 * section_presence_score
        + 0.25 * formatting_score
        + 0.20 * bullet_score
        + 0.15 * length_score
        + 0.10 * (100.0 if order_ok and found_any else 60.0),
        2,
    )

    # ── Rule-based overall score (real ATS simulation) ───────────────
    # When no job description is provided, keyword_score is 0 which
    # would unfairly penalise the overall score.  Redistribute its
    # weight to the other components so that standalone CV analysis
    # produces realistic scores.
    # More components = more sensitivity to structural improvements.
    if job_text and job_text.strip():
        rule_overall = (
            keyword_score * 0.15
            + section_presence_score * 0.15
            + work_exp_score * 0.15
            + skills_score * 0.12
            + formatting_score * 0.13
            + contact_score * 0.10
            + summary_score * 0.08
            + edu_score * 0.07
            + bullet_score * 0.05
        )
    else:
        rule_overall = (
            section_presence_score * 0.20
            + work_exp_score * 0.17
            + skills_score * 0.14
            + formatting_score * 0.16
            + contact_score * 0.12
            + summary_score * 0.08
            + edu_score * 0.07
            + bullet_score * 0.06
        )
    rule_overall = max(0.0, min(100.0, rule_overall))
    overall = round(rule_overall, 2)

    # ── Build section scores for frontend ────────────────────────────
    section_scores = [
        {
            "name": "education",
            "icon": "🎓",
            "label": {"en": "Education", "tr": "Eğitim"},
            "score": round(edu_score, 0),
            "status": _get_section_status(edu_score),
            "message": _get_section_message("education", edu_score, lang),
            "recommendations": _get_section_recommendations("education", edu_score, lang),
        },
        {
            "name": "formatting",
            "icon": "✨",
            "label": {"en": "Formatting", "tr": "Biçimlendirme"},
            "score": round(formatting_score, 0),
            "status": _get_section_status(formatting_score),
            "message": _get_section_message("formatting", formatting_score, lang),
            "recommendations": _get_section_recommendations("formatting", formatting_score, lang),
        },
        {
            "name": "contact",
            "icon": "📇",
            "label": {"en": "Contact Information", "tr": "İletişim Bilgileri"},
            "score": round(contact_score, 0),
            "status": _get_section_status(contact_score),
            "message": _get_section_message("contact", contact_score, lang),
            "recommendations": _get_section_recommendations("contact", contact_score, lang),
        },
        {
            "name": "skills",
            "icon": "⚡",
            "label": {"en": "Skills Section", "tr": "Beceriler Bölümü"},
            "score": round(skills_score, 0),
            "status": _get_section_status(skills_score),
            "message": _get_section_message("skills", skills_score, lang),
            "recommendations": _get_section_recommendations("skills", skills_score, lang),
        },
        {
            "name": "experience",
            "icon": "💼",
            "label": {"en": "Work Experience", "tr": "İş Deneyimi"},
            "score": round(work_exp_score, 0),
            "status": _get_section_status(work_exp_score),
            "message": _get_section_message("experience", work_exp_score, lang),
            "recommendations": _get_section_recommendations("experience", work_exp_score, lang),
        },
        {
            "name": "ats_compatibility",
            "icon": "🤖",
            "label": {"en": "ATS Compatibility", "tr": "ATS Uyumluluğu"},
            "score": round(ats_compat_score, 0),
            "status": _get_section_status(ats_compat_score),
            "message": _get_section_message("ats_compatibility", ats_compat_score, lang),
            "recommendations": _get_section_recommendations("ats_compatibility", ats_compat_score, lang),
        },
        {
            "name": "summary",
            "icon": "📝",
            "label": {"en": "Professional Summary", "tr": "Profesyonel Özet"},
            "score": round(summary_score, 0),
            "status": _get_section_status(summary_score),
            "message": _get_section_message("summary", summary_score, lang),
            "recommendations": _get_section_recommendations("summary", summary_score, lang),
        },
    ]

    # Only include keywords section when a job description is provided
    if job_text and job_text.strip():
        section_scores.insert(-1, {
            "name": "keywords",
            "icon": "🔍",
            "label": {"en": "Keywords", "tr": "Anahtar Kelimeler"},
            "score": round(keyword_score, 0),
            "status": _get_section_status(keyword_score),
            "message": _get_section_message("keywords", keyword_score, lang),
            "recommendations": _get_section_recommendations("keywords", keyword_score, lang),
        })

    # Aggregate counts
    passed_count = sum(1 for s in section_scores if s["status"] == "pass")
    warning_count = sum(1 for s in section_scores if s["status"] == "warning")
    fail_count = sum(1 for s in section_scores if s["status"] == "fail")

    # ── Priority recommendations ─────────────────────────────────────
    high_priority = []
    medium_priority = []
    low_priority = []

    if summary_score < 70:
        high_priority.append({"en": "Expand professional summary to clearly state career goals and key skills.", "tr": "Profesyonel özeti kariyer hedeflerini ve temel becerileri net olarak belirtecek şekilde genişletin."})
    if achievement_score < 40:
        high_priority.append({"en": "Add quantifiable achievements or impact metrics in internship experience.", "tr": "Staj deneyimine ölçülebilir başarılar veya etki metrikleri ekleyin."})
    if formatting_score < 80:
        high_priority.append({"en": "Improve formatting consistency for better readability and ATS compatibility.", "tr": "Daha iyi okunabilirlik ve ATS uyumluluğu için biçimlendirme tutarlılığını iyileştirin."})

    if edu_score < 90:
        medium_priority.append({"en": "Include expected graduation date in education section.", "tr": "Eğitim bölümüne beklenen mezuniyet tarihini ekleyin."})
    if skills_score < 85:
        medium_priority.append({"en": "Add proficiency levels for technical skills.", "tr": "Teknik beceriler için yeterlilik düzeyleri ekleyin."})
    if keyword_score < 70 and job_text:
        medium_priority.append({"en": "Incorporate keywords from targeted job descriptions into resume content.", "tr": "Hedeflenen iş tanımlarının anahtar kelimelerini CV içeriğine ekleyin."})

    if contact_score < 100:
        low_priority.append({"en": "Add LinkedIn profile link.", "tr": "LinkedIn profil bağlantısı ekleyin."})
    low_priority.append({"en": "Include soft skills or extracurricular activities if relevant.", "tr": "İlgiliyse sosyal becerileri veya ders dışı etkinlikleri ekleyin."})
    low_priority.append({"en": "Use consistent formatting for dates.", "tr": "Tarihler için tutarlı biçimlendirme kullanın."})

    # ── Industry-specific tips ───────────────────────────────────────
    industry_tips = _generate_industry_tips(cv_text, job_text, lang)

    # ── Next steps ───────────────────────────────────────────────────
    next_steps = _generate_next_steps(
        summary_score, edu_score, formatting_score, work_exp_score,
        skills_score, keyword_score, contact_score, lang
    )

    # ── Old-style suggestions (backward compat) ─────────────────────
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
        "section_scores": section_scores,
        "passed_checks": passed_count,
        "warning_checks": warning_count,
        "failed_checks": fail_count,
        "priority_recommendations": {
            "high": high_priority,
            "medium": medium_priority,
            "low": low_priority,
        },
        "industry_tips": industry_tips,
        "next_steps": next_steps,
        "overall_score": overall,
        "suggestions": suggestions,
    }

    return result


def _generate_industry_tips(cv_text: str, job_text: str, lang: str = "en") -> list:
    """Generate bilingual industry-specific tips based on CV and job description content."""
    text = (cv_text + " " + (job_text or "")).lower()

    tech_keywords = ["software", "developer", "engineer", "programming", "api", "cloud", "devops", "database", "yazılım", "geliştirici", "mühendis"]
    is_tech = any(kw in text for kw in tech_keywords)

    if is_tech:
        en_tips = [
            "Highlight experience with real-time systems and streaming protocols as these are niche and valuable skills.",
            "Emphasize programming skills with examples from projects and internship.",
            "Consider contributing to open source or personal projects to strengthen portfolio.",
            "Prepare to discuss latency optimization and protocol knowledge in interviews.",
            "Quantify performance improvements (e.g., reduced latency by X%, improved throughput by Y%).",
        ]
        tr_tips = [
            "Gerçek zamanlı sistemler ve akış protokolleri deneyimini vurgulayın, bunlar niş ve değerli becerilerdir.",
            "Proje ve stajlardan örneklerle programlama becerilerini vurgulayın.",
            "Portföyünüzü güçlendirmek için açık kaynak veya kişisel projelere katkıda bulunmayı düşünün.",
            "Mülakatlarda gecikme optimizasyonu ve protokol bilgisini tartışmaya hazır olun.",
            "Performans iyileştirmelerini sayılarla ifade edin (ör. gecikme %X azaldı, verim %Y arttı).",
        ]
    else:
        en_tips = [
            "Tailor your CV summary to each application for maximum relevance.",
            "Use industry-standard terminology consistently throughout.",
            "Highlight measurable impact in every role.",
            "Consider adding relevant certifications to strengthen your profile.",
        ]
        tr_tips = [
            "CV özetinizi her başvuru için maksimum uygunluk sağlamak üzere özelleştirin.",
            "Sektör standardı terminolojiyi tutarlı bir şekilde kullanın.",
            "Her rolde ölçülebilir etkiyi vurgulayın.",
            "Profilinizi güçlendirmek için ilgili sertifikalar eklemeyi düşünün.",
        ]

    return [{"en": en_tips[i], "tr": tr_tips[i]} for i in range(min(4, len(en_tips)))]


def _generate_next_steps(
    summary_score: float, edu_score: float, formatting_score: float,
    exp_score: float, skills_score: float, keyword_score: float,
    contact_score: float, lang: str = "en",
) -> list:
    """Generate ordered bilingual next steps based on weakest areas."""
    en_steps = [
        (summary_score, "Add a professional summary or objective at the top to better capture attention and clarify career goals."),
        (60.0, "Include dates for projects or specify if they were part of coursework or personal initiatives to provide timeline context."),
        (formatting_score, "Improve formatting consistency, such as alignment and spacing, to enhance readability and professional appearance."),
        (exp_score, "Add more quantifiable achievements or metrics in the experience section to demonstrate impact."),
        (edu_score, "Include relevant coursework or certifications to strengthen the education section."),
        (skills_score, "Consider adding a section for soft skills or extracurricular activities if relevant to the role."),
        (70.0, "Clarify language proficiency levels using a standard framework (e.g., CEFR) and consider adding certifications if available."),
    ]
    tr_steps = [
        (summary_score, "Dikkat çekmek ve kariyer hedeflerini netleştirmek için üst kısma profesyonel bir özet veya hedef ekleyin."),
        (60.0, "Projeler için tarihler ekleyin veya ders çalışması ya da kişisel girişimlerin parçası olup olmadığını belirtin."),
        (formatting_score, "Okunabilirliği ve profesyonel görünümü artırmak için hizalama ve boşluk gibi biçimlendirme tutarlılığını iyileştirin."),
        (exp_score, "Etkiyi göstermek için deneyim bölümüne daha fazla ölçülebilir başarı veya metrik ekleyin."),
        (edu_score, "Eğitim bölümünü güçlendirmek için ilgili dersleri veya sertifikaları ekleyin."),
        (skills_score, "Rolle ilgiliyse sosyal beceriler veya ders dışı etkinlikler için bir bölüm eklemeyi düşünün."),
        (70.0, "Dil yeterlilik düzeylerini standart bir çerçeve kullanarak netleştirin (ör. CEFR) ve varsa sertifika eklemeyi düşünün."),
    ]
    # Sort by score ascending (worst areas first)
    indices = sorted(range(len(en_steps)), key=lambda i: en_steps[i][0])
    return [{"en": en_steps[i][1], "tr": tr_steps[i][1]} for i in indices[:7]]


def generate_score_suggestions(
    missing_skills: list,
    keyword_gap: dict,
    keyword_score: float,
    skill_score: float,
    final_score: float,
    total_jd_skills: int = 0,
    lang: str = "en",
) -> list:
    """Generate actionable suggestions with estimated point impact.

    Returns a list of dicts:
      [{"action": "Add Docker experience", "impact": 6.2, "category": "skill"}, ...]

    Impact estimation logic:
      - Each missing skill ≈ (skill_weight_in_final / total_jd_skills) * 100
      - Keyword gap items get a smaller weight since they're individual terms
      - Capped at top 8 suggestions, sorted by highest impact
    """
    suggestions = []

    # -- Skill-based suggestions (higher impact) --
    if total_jd_skills > 0 and missing_skills:
        # skill_score contributes ~15% to final_score via compute_final_score
        # Each missing skill represents 1/total_jd_skills of that 15%
        per_skill_impact = round(15.0 / max(total_jd_skills, 1), 2)
        # Cap per-skill impact to reasonable range
        per_skill_impact = max(1.0, min(per_skill_impact, 8.0))

        for skill in missing_skills[:10]:
            skill_name = str(skill).strip()
            if not skill_name:
                continue
            if lang == "tr":
                action = f"{skill_name} deneyimi ekleyin"
            else:
                action = f"Add {skill_name} experience"
            suggestions.append({
                "action": action,
                "impact": per_skill_impact,
                "category": "skill",
                "skill": skill_name,
            })

    # -- Keyword-based suggestions (medium impact) --
    kw_missing = keyword_gap.get("missing_keywords", []) if keyword_gap else []
    if kw_missing:
        # Keywords contribute ~15% to final via keyword_score weight
        total_kw = keyword_gap.get("total_jd_keywords", len(kw_missing))
        per_kw_impact = round(15.0 / max(total_kw, 1), 2)
        per_kw_impact = max(0.5, min(per_kw_impact, 4.0))

        # Only add keywords not already in skills
        skill_lower = {str(s).lower() for s in (missing_skills or [])}
        for kw in kw_missing[:8]:
            kw_name = str(kw).strip()
            if not kw_name or kw_name.lower() in skill_lower:
                continue
            if lang == "tr":
                action = f"CV'nizde '{kw_name}' ifadesini kullanın"
            else:
                action = f"Mention '{kw_name}' in your CV"
            suggestions.append({
                "action": action,
                "impact": per_kw_impact,
                "category": "keyword",
                "skill": kw_name,
            })

    # -- ATS formatting suggestions (fixed impact estimates) --
    if final_score < 70:
        ats_suggestions = []
        if lang == "tr":
            ats_suggestions = [
                {"action": "Ölçülebilir başarılar ekleyin (ör: '%25 artış sağladı')", "impact": 3.0, "category": "format"},
                {"action": "Madde işaretleri kullanın (uzun paragraflar yerine)", "impact": 2.0, "category": "format"},
            ]
        else:
            ats_suggestions = [
                {"action": "Add quantified achievements (e.g., 'Increased revenue by 25%')", "impact": 3.0, "category": "format"},
                {"action": "Use bullet points instead of long paragraphs", "impact": 2.0, "category": "format"},
            ]
        suggestions.extend(ats_suggestions)

    # Sort by impact descending, take top 8
    suggestions.sort(key=lambda x: x["impact"], reverse=True)
    return suggestions[:8]
