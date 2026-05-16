"""NLP-style CV section classifier.

Splits raw CV text into blocks (separated by blank lines) and classifies
each block by its *content* rather than relying on exact section-header
aliases.  This makes parsing language-agnostic: Turkish, German, French,
Canva CVs, bad-ATS PDFs, etc. all work without maintaining alias dictionaries.

Includes fuzzy/edit-distance matching so typos like "sumary", "experiance",
"eduction" are still recognised correctly.

Public API
----------
detect_sections(text)  → dict[str, list[str]]
    Returns canonical section name → list of content lines.

split_blocks(text)     → list[list[str]]
    Splits text into blocks separated by blank lines.

classify_block(lines)  → str
    Returns the best-guess canonical section name for one block.
"""

from __future__ import annotations

import difflib
import json as _json
import logging
import os
import random
import re
import time
import unicodedata
from typing import Callable, Dict, List

from utils.section_scorer import score_text as _scorer_score_text

logger = logging.getLogger("app.parser.classifier")


def _structured_log(
    _logger: logging.Logger,
    level: int,
    event: str,
    **fields: object,
) -> None:
    """Emit a structured JSON log line with standardised fields."""
    payload = {"event": event, **fields}
    _logger.log(level, _json.dumps(payload, default=str, ensure_ascii=False))

# ── Parser versioning ─────────────────────────────────────────────────────
# Allows swapping parser implementations via env var without code deploys.
# "v1" is the current production classifier.  Future versions (v2, experimental)
# can be registered in _PARSER_REGISTRY and selected at runtime.
PARSER_VERSION = os.getenv("PARSER_VERSION", "v1").strip().lower()

# Slow-CV guard: hard timeout for detect_sections
_CLASSIFIER_TIMEOUT_SECONDS = float(
    os.getenv("CLASSIFIER_TIMEOUT_SECONDS", "5") or "5"
)
_CLASSIFIER_WARN_SECONDS = float(
    os.getenv("CLASSIFIER_WARN_SECONDS", "2") or "2"
)


# ── tiny helpers ──────────────────────────────────────────────────────────

_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?"
    r"|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?"
    r"|dec(?:ember)?)"
)
# Generic month-like word: any 3-12 letter word (captures non-English months)
_MONTH_WORD = r"[A-Za-z\u00C0-\u024F\u0400-\u04FF]{3,12}\.?"
_YEAR = r"(?:19|20)\d{2}"
# Numeric date prefix: 01/2020, 2020-01, 01.2020
_NUMERIC_DATE = r"(?:\d{1,2}[/.]\s*)"
# Language-agnostic "present": any non-year word of 3+ letters (covers all languages)
_PRESENT_WORD = r"(?![12]\d{3}\b)[A-Za-z\u00C0-\u024F\u0400-\u04FF]{3,}(?:\s+[A-Za-z\u00C0-\u024F]{2,})?"
_DATE_RANGE_RE = re.compile(
    rf"(?:(?:{_MONTH}|{_MONTH_WORD})\s+|{_NUMERIC_DATE})?{_YEAR}\s*(?:[-–—]|to)\s*"
    rf"(?:(?:(?:{_MONTH}|{_MONTH_WORD})\s+|{_NUMERIC_DATE})?{_YEAR}"
    rf"|{_PRESENT_WORD})",
    re.I,
)
# Open-ended date: "2020 –" at end of line (handles any language's "present")
_OPEN_DATE_RE = re.compile(rf"{_YEAR}\s*[-–—]\s*$", re.MULTILINE)
_SINGLE_YEAR_RE = re.compile(rf"\b{_YEAR}\b")

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\+\d{1,3}[\s.-]?)?"       # optional country code: +1, +90, +44
    r"\(?\d{2,4}\)?[\s.-]?"        # area code: (555), 555, 0555
    r"\d{2,4}[\s.-]?"              # middle digits
    r"\d{2,4}"                     # last digits
    r"(?!\d)"
)
_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com|[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?:/\S*)?",
    re.I,
)

# Education indicators — international degree abbreviations + structural
_EDUCATION_KEYWORDS = re.compile(
    r"\b(?:university|institute|college|school|faculty|academy"
    r"|bachelor|master|mba|ph\.?d"
    r"|b\.?sc|m\.?sc|b\.?a|m\.?a|diploma|associate|degree"
    r"|gpa|cgpa)\b",
    re.I,
)

# Company type indicators — international legal entity suffixes
_EXPERIENCE_KEYWORDS = re.compile(
    r"\b(?:inc|ltd|llc|gmbh|corp|co\.|pvt|pty"
    r"|s\.?a\.?|s\.?l\.?|sarl|sas|s\.?r\.?l\.?|a\.?g\.?)\b",
    re.I,
)

# Project indicators — URL patterns + universal keywords
_PROJECT_KEYWORDS = re.compile(
    r"(?:github\.com|gitlab\.com|bitbucket\.org)"
    r"|\b(?:project|repository|repo"
    r"|tech\s+stack|used\s+technolog\w*|tools?\s+used|built\s+with"
    r"|personal\s+project)\b",
    re.I,
)

# Contextual project hints (sentence-level patterns)
_PROJECT_CONTEXT_RE = re.compile(
    r"\b(?:tech\s+stack|used\s+technolog\w*|tools?\s*(?:used|:)|built\s+with"
    r"|developed\s+(?:with|using)|implemented\s+(?:with|using)|stack\s*:)\b",
    re.I,
)

# Certification indicators — international cert names
_CERT_KEYWORDS = re.compile(
    r"\b(?:certified|certification|certificate|license|credential"
    r"|comptia|pmp|cissp|cka|ckad|ccna|ccnp|togaf|itil|scrum\s+master)\b",
    re.I,
)

# Well-known cert provider + title combos (each line is a cert on its own)
_CERT_PROVIDER_RE = re.compile(
    r"\b(?:aws|amazon|google\s+cloud|gcp|azure|microsoft|cisco|oracle"
    r"|red\s*hat|hashicorp|terraform|kubernetes|salesforce|comptia)\b",
    re.I,
)

# Interest / hobby indicators
_INTEREST_KEYWORDS = re.compile(
    r"\b(?:hobbies?|interests?|volunteer(?:ing)?|swimming|reading|traveling"
    r"|gaming|photography|cooking|music|sport|yoga|chess|hiking"
    r"|writing|drawing|painting|gardening|cycling|running|fishing"
    r"|camping|dancing|singing|meditation)\b",
    re.I,
)

# Language proficiency indicators — CEFR levels + universal English terms
_LANGUAGE_KEYWORDS = re.compile(
    r"\b(?:A[12]|B[12]|C[12]"
    r"|native|fluent|intermediate|beginner|proficient|basic|advanced"
    r"|elementary|upper[\s-]?intermediate"
    r"|ana\s*dil|ileri\s*d[uü]zey|orta\s*d[uü]zey"
    r"|ba[sş]lang[ıi][cç]|temel)\b",
    re.I,
)

# Structural: capitalized multi-word phrase (institution/company name in any language)
# Matches "Istanbul Technical University", "東京大学", "Société Générale" etc.
_CAPITALIZED_PHRASE_RE = re.compile(
    r"(?:[A-ZÀ-ÖØ-Þ\u0100-\u024F][\w\u00C0-\u024F'-]+(?:\s+(?:of|de|di|du|des|für|van|von|der|den|and|&|the)\s+)?){2,}",
)

# Tech/tool names — language-agnostic signal for projects/skills
_TECH_NAMES_RE = re.compile(
    r"\b(?:python|java(?:script)?|typescript|react|angular|vue|node\.?js"
    r"|django|flask|fastapi|spring|express|docker|kubernetes|aws|azure|gcp"
    r"|sql|postgresql|mysql|mongodb|redis|git|linux|html|css|c\+\+|c#|rust"
    r"|go(?:lang)?|swift|kotlin|flutter|tensorflow|pytorch|pandas|numpy"
    r"|\.net|graphql|rest(?:\s*api)?|ci/?cd|terraform|jenkins|nginx|apache"
    r"|rabbitmq|kafka|elasticsearch|sass|webpack|vite|tailwind)\b",
    re.I,
)

# Bullet line pattern (any bullet marker)
_BULLET_RE = re.compile(r"^\s*[-*\u2022\u2013\u2014\u2023\u25aa\u25a0]\s")

# Noise sections to discard (minimal set)
_NOISE_KEYWORDS = re.compile(
    r"\b(?:references|marital|nationality|photo)\b",
    re.I,
)

# Skill-style: short comma/pipe-separated items, or "Category: item, item"
_SKILL_DELIMITER_RE = re.compile(r"[,;|/]")

# Known section header aliases — BONUS signal, English only.
# Non-English headers are detected structurally (short/ALL-CAPS/Title Case)
# and classified by block content instead.
_HEADER_HINTS: Dict[str, re.Pattern] = {
    "summary": re.compile(
        r"^(?:summary|professional\s+summary|profile|about(?:\s+me)?|objective"
        r"|career\s+summary|career\s+objective|personal\s+statement"
        r"|personal\s+profile|personal\s+summary|executive\s+summary"
        r"|executive\s+profile"
        r"|personal\s+information|introduction|personal"
        # TR
        r"|[öo]zet|profil|ki[şs]isel\s+bilgiler|kariyer\s+[öo]zeti"
        # FR
        r"|r[ée]sum[ée](?:\s+professionnel)?|profil\s+professionnel"
        # DE
        r"|zusammenfassung|[üu]ber\s+mich|kurzprofil"
        # ES
        r"|resumen(?:\s+profesional)?|perfil(?:\s+profesional)?|objetivo"
        # PT
        r"|resumo(?:\s+profissional)?|objetivo\s+profissional"
        # IT
        r"|profilo\s+professionale|riepilogo|sommario"
        # NL
        r"|samenvatting|profiel|persoonlijk\s+profiel"
        # RU
        r"|резюме|профиль|о\s+себе|краткое\s+описание"
        # PL
        r"|podsumowanie(?:\s+zawodowe)?|profil\s+zawodowy|o\s+mnie"
        # SV
        r"|sammanfattning|personlig\s+profil"
        # NO/DA
        r"|sammendrag"
        # FI
        r"|yhteenveto|profiili|henkil[öo]profiili"
        # CS
        r"|shrnut[ií]|osobn[ií]\s+profil"
        # HU
        r"|[öo]sszefoglal[óo]|szem[ée]lyes\s+profil"
        # RO
        r"|rezumat|profil\s+personal|obiectiv"
        # AR
        r"|ملخص|نبذة\s+شخصية|الملف\s+الشخصي|هدف\s+وظيفي"
        # ZH
        r"|个人简介|个人概述|自我介绍|职业目标|摘要|个人总结"
        # JA
        r"|概要|自己紹介|プロフィール|職務要約"
        # KO
        r"|요약|자기소개|프로필|경력\s*요약"
        # HI
        r"|सारांश|प्रोफ़ाइल|परिचय|व्यक्तिगत\s+विवरण"
        # ID
        r"|ringkasan|tentang\s+saya|ikhtisar"
        # VI
        r"|tóm\s+tắt|hồ\s+sơ|giới\s+thiệu\s+bản\s+thân"
        # TH
        r"|สรุป|โปรไฟล์|ประวัติย่อ|เกี่ยวกับฉัน"
        r")$",
        re.I,
    ),
    "experience": re.compile(
        r"^(?:experience|work\s+experience|professional\s+experience|employment"
        r"|employment\s+history|work\s+history|work\s+background|career\s+history|professional\s+background|industrial\s+training(?:\s+attended)?|trainings?|training"
        # TR
        r"|deneyim|i[sş]\s*deneyimi|mesleki\s*deneyim"
        # FR
        r"|exp[ée]rience(?:\s+professionnelle)?|parcours\s+professionnel"
        # DE
        r"|erfahrung|berufserfahrung|beruflicher\s+werdegang"
        # ES
        r"|experiencia(?:\s+laboral|\s+profesional)?|trayectoria\s+profesional"
        # PT
        r"|experi[êe]ncia(?:\s+profissional)?|hist[óo]rico\s+profissional"
        # IT
        r"|esperienza(?:\s+lavorativa|\s+professionale)?|esperienze\s+professionali"
        # NL
        r"|ervaring|werkervaring|professionele\s+ervaring"
        # RU
        r"|опыт(?:\s+работы)?|трудовой\s+стаж|профессиональный\s+опыт"
        # PL
        r"|do[śs]wiadczenie(?:\s+zawodowe)?|historia\s+zatrudnienia"
        # SV
        r"|erfarenhet|arbetslivserfarenhet|yrkeserfarenhet"
        # NO
        r"|arbeidserfaring|yrkeserfaring"
        # DA
        r"|erhvervserfaring|arbejdserfaring"
        # FI
        r"|kokemus|ty[öo]kokemus|ty[öo]historia"
        # CS
        r"|zku[šs]enosti|pracovn[ií]\s+zku[šs]enosti"
        # HU
        r"|tapasztalat|munkatapasztalat|szakmai\s+tapasztalat"
        # RO
        r"|experien[țt][ăa](?:\s+profesional[ăa])?"
        # AR
        r"|الخبرة(?:\s+المهنية)?|الخبرات|خبرة\s+العمل"
        # ZH
        r"|工作经验|工作经历|职业经历|工作履历"
        # JA
        r"|職歴|職務経歴"
        # KO
        r"|경력|경험|직무\s*경험|업무\s*경험"
        # HI
        r"|अनुभव|कार्य\s+अनुभव|कार्यानुभव"
        # ID
        r"|pengalaman(?:\s+kerja)?|riwayat\s+pekerjaan"
        # VI
        r"|kinh\s+nghi[ệe]m(?:\s+l[àa]m\s+vi[ệe]c)?"
        # TH
        r"|ประสบการณ์(?:ทำงาน|การทำงาน)?"
        r")$",
        re.I,
    ),
    "education": re.compile(
        r"^(?:education|academic\s+background|academic\s+qualifications|educational\s+background|qualifications|academic|academics"
        # TR
        r"|e[gğ]itim|akademik\s*ge[cç]mi[sş]"
        # FR
        r"|formation|[ée]tudes|parcours\s+acad[ée]mique"
        # DE
        r"|ausbildung|bildung|studium|akademische\s+ausbildung"
        # ES
        r"|educaci[óo]n|formaci[óo]n(?:\s+acad[ée]mica)?"
        # PT
        r"|educa[çc][ãa]o|forma[çc][ãa]o(?:\s+acad[êe]mica)?"
        # IT
        r"|istruzione|formazione|percorso\s+accademico"
        # NL
        r"|opleiding|onderwijs|opleidingen"
        # RU
        r"|образование|обучение"
        # PL
        r"|wykszta[łl]cenie|edukacja"
        # SV
        r"|utbildning|akademisk\s+bakgrund"
        # NO
        r"|utdanning|utdannelse"
        # DA
        r"|uddannelse|akademisk\s+baggrund"
        # FI
        r"|koulutus|opinnot"
        # CS
        r"|vzd[ěe]l[áa]n[ií]|studium"
        # HU
        r"|v[ée]gzetts[ée]g|tanulm[áa]nyok|oktat[áa]s"
        # RO
        r"|educa[țt]ie|studii"
        # AR
        r"|التعليم|المؤهلات\s+الأكاديمية|الدراسة"
        # ZH
        r"|教育|学历|教育背景|学习经历"
        # JA
        r"|学歴"
        # KO
        r"|학력|교육"
        # HI
        r"|शिक्षा|शैक्षिक\s+योग्यता"
        # ID
        r"|pendidikan|riwayat\s+pendidikan"
        # VI
        r"|h[ọo]c\s+v[ấa]n|tr[ìi]nh\s+đ[ộo]\s+h[ọo]c\s+v[ấa]n"
        # TH
        r"|การศึกษา|ประวัติการศึกษา"
        r")$",
        re.I,
    ),
    "skills": re.compile(
        r"^(?:skills|technical\s+skills|core\s+competencies|competencies|technologies"
        r"|key\s+skills|professional\s+skills|it\s+skills|hard\s+skills|soft\s+skills|skill\s+set|skills?\s+set|skills?\s+and\s+abilities"
        # TR
        r"|beceriler|yetenekler|teknik\s*beceriler|yetkinlikler"
        # FR
        r"|comp[ée]tences(?:\s+techniques)?|aptitudes"
        # DE
        r"|f[äa]higkeiten|kenntnisse|kompetenzen|technische\s+f[äa]higkeiten"
        # ES
        r"|habilidades|competencias|habilidades\s+t[ée]cnicas"
        # PT
        r"|compet[êe]ncias|aptid[õo]es"
        # IT
        r"|competenze|abilit[àa]|competenze\s+tecniche"
        # NL
        r"|vaardigheden|competenties|technische\s+vaardigheden"
        # RU
        r"|навыки|умения|компетенции|технические\s+навыки"
        # PL
        r"|umiej[ęe]tno[śs]ci|kompetencje"
        # SV
        r"|f[äa]rdigheter|kompetenser"
        # NO
        r"|ferdigheter|kompetanser"
        # DA
        r"|f[æa]rdigheder|kompetencer"
        # FI
        r"|taidot|osaaminen"
        # CS
        r"|dovednosti|schopnosti"
        # HU
        r"|k[ée]szs[ée]gek|k[ée]pess[ée]gek|szaktud[áa]s"
        # RO
        r"|competen[țt]e|abilit[ăa][țt]i"
        # AR
        r"|المهارات(?:\s+التقنية)?|القدرات"
        # ZH
        r"|技能|专业技能|核心能力"
        # JA
        r"|スキル|技術|能力"
        # KO
        r"|기술|스킬|역량|핵심\s*역량"
        # HI
        r"|कौशल|दक्षता|तकनीकी\s+कौशल"
        # ID
        r"|keahlian|keterampilan|kemampuan"
        # VI
        r"|k[ỹy]\s+n[ăa]ng|n[ăa]ng\s+l[ựu]c"
        # TH
        r"|ทักษะ|ความสามารถ|ทักษะเทคนิค"
        r")$",
        re.I,
    ),
    "projects": re.compile(
        r"^(?:projects?|project\s+experience|personal\s+projects?|academic\s+projects?"
        r"|key\s+projects"
        # TR
        r"|projeler|ki[sş]isel\s*projeler"
        # FR
        r"|projets?|projets\s+personnels"
        # DE
        r"|projekte?"
        # ES
        r"|proyectos?"
        # PT
        r"|projetos?|projectos?"
        # IT
        r"|progetti?"
        # NL
        r"|projecten?"
        # RU
        r"|проекты?|личные\s+проекты"
        # PL/CS
        r"|projekty?"
        # SV/DA
        r"|projekter"
        # NO
        r"|prosjekter"
        # FI
        r"|projektit?"
        # HU
        r"|projektek?"
        # RO
        r"|proiecte?"
        # AR
        r"|المشاريع|مشاريع"
        # ZH
        r"|项目|项目经验|个人项目"
        # JA
        r"|プロジェクト"
        # KO
        r"|프로젝트"
        # HI
        r"|परियोजनाएं|परियोजना"
        # ID
        r"|proyek"
        # VI
        r"|d[ựu]\s+[áa]n"
        # TH
        r"|โครงการ"
        r")$",
        re.I,
    ),
    "other": re.compile(
        r"^(?:achievements|awards|volunteer|activities|other\s+activities|publications|misc|other|personal\s+details)$",
        re.I,
    ),
    "certifications": re.compile(
        r"^(?:certifications?|certificates?|licenses?|awards?(?:\s+[&and]+\s+certifications?)?"
        # TR
        r"|sertifikalar|belgeler"
        # FR
        r"|dipl[ôo]mes?"
        # DE
        r"|zertifizierungen?|zertifikate?"
        # ES
        r"|certificaciones?|certificados?"
        # PT
        r"|certifica[çc][õo]es"
        # IT
        r"|certificazioni?"
        # NL
        r"|certificeringen?|certificaten?"
        # RU
        r"|сертификаты?|дипломы?"
        # PL
        r"|certyfikaty?"
        # SV
        r"|certifieringar?"
        # NO
        r"|sertifiseringer?"
        # DA
        r"|certificeringer?"
        # FI
        r"|sertifikaatit?|todistukset?"
        # CS
        r"|certifik[áa]ty?"
        # HU
        r"|tan[úu]s[ií]tv[áa]nyok?"
        # RO
        r"|certific[ăa]ri?"
        # AR
        r"|الشهادات|شهادات"
        # ZH
        r"|证书|资格证书|认证"
        # JA
        r"|資格|認定"
        # KO
        r"|자격증|인증"
        # HI
        r"|प्रमाणपत्र"
        # ID
        r"|sertifikasi|sertifikat"
        # VI
        r"|ch[ứu]ng\s+ch[ỉi]"
        # TH
        r"|ใบรับรอง|ประกาศนียบัตร"
        r")$",
        re.I,
    ),
    "languages": re.compile(
        r"^(?:languages?|language\s+skills|foreign\s+languages"
        # TR
        r"|diller|yabanc[ıi]\s*diller"
        # FR
        r"|langues|comp[ée]tences\s+linguistiques"
        # DE
        r"|sprachen|sprachkenntnisse"
        # ES
        r"|idiomas|lenguas"
        # PT
        r"|l[íi]nguas"
        # IT
        r"|lingue|competenze\s+linguistiche"
        # NL
        r"|talen|talenkennis"
        # RU
        r"|языки|знание\s+языков|владение\s+языками"
        # PL
        r"|j[ęe]zyki(?:\s+obce)?"
        # SV/NO
        r"|spr[åa]k"
        # DA
        r"|sprog"
        # FI
        r"|kielet|kielitaito"
        # CS
        r"|jazyky|jazykov[ée]\s+znalosti"
        # HU
        r"|nyelvek|nyelvtud[áa]s|idegen\s+nyelvek"
        # RO
        r"|limbi(?:\s+str[ăa]ine)?"
        # AR
        r"|اللغات|المهارات\s+اللغوية"
        # ZH
        r"|语言|语言能力|外语"
        # JA
        r"|言語|語学"
        # KO
        r"|언어|외국어"
        # HI
        r"|भाषाएं|भाषा\s+कौशल"
        # ID
        r"|bahasa"
        # VI
        r"|ng[ôo]n\s+ng[ữu]|ngo[ạa]i\s+ng[ữu]"
        # TH
        r"|ภาษา|ทักษะทางภาษา"
        r")$",
        re.I,
    ),
    "contact": re.compile(
        r"^(?:contact|contact\s+information|communication"
        # TR
        r"|ileti[şs]im|ileti[şs]im\s+bilgileri"
        # FR
        r"|coordonn[ée]es|informations?\s+de\s+contact"
        # DE
        r"|kontakt|kontaktdaten|kontaktinformationen"
        # ES
        r"|contacto|informaci[óo]n\s+de\s+contacto|datos\s+de\s+contacto"
        # PT
        r"|conta[tc]to|informa[çc][õo]es\s+de\s+conta[tc]to"
        # IT
        r"|contatt[oi]|informazioni\s+di\s+contatto"
        # NL
        r"|contactgegevens"
        # RU
        r"|контакт(?:ы|ная\s+информация)?"
        # PL
        r"|dane\s+kontaktowe"
        # SV/NO/DA
        r"|kontakt(?:information|uppgifter|opplysninger)?"
        # FI
        r"|yhteystiedot"
        # CS
        r"|kontaktn[ií]\s+[úu]daje"
        # HU
        r"|kapcsolat|el[ée]rhet[őo]s[ée]g(?:ek)?"
        # RO
        r"|date\s+de\s+contact"
        # AR
        r"|الاتصال|التواصل|معلومات\s+الاتصال|بيانات\s+التواصل"
        # ZH
        r"|联系方式|联系信息|个人信息"
        # JA
        r"|連絡先|連絡情報"
        # KO
        r"|연락처|연락\s*정보"
        # HI
        r"|संपर्क|संपर्क\s+जानकारी"
        # ID
        r"|kontak|informasi\s+kontak"
        # VI
        r"|li[êe]n\s+h[ệe]|th[ôo]ng\s+tin\s+li[êe]n\s+h[ệe]"
        # TH
        r"|ติดต่อ|ข้อมูลติดต่อ"
        r")$",
        re.I,
    ),
    "interests": re.compile(
        r"^(?:interests?|hobbies|hobbies\s+and\s+interests|personal\s+interests?"
        # TR
        r"|ilgi\s+alanlar[ıi]|hobiler"
        # FR
        r"|centres?\s+d['']\s*int[ée]r[êe]t|loisirs|passions"
        # DE
        r"|interessen|hobbys?"
        # ES
        r"|intereses|aficiones|pasatiempos"
        # PT
        r"|interesses|passatempos"
        # IT
        r"|interessi|hobby|passioni|tempo\s+libero"
        # NL
        r"|interesses|hobby'?s"
        # RU
        r"|интересы|хобби|увлечения"
        # PL
        r"|zainteresowania"
        # SV
        r"|intressen"
        # NO/DA
        r"|interesser"
        # FI
        r"|kiinnostukset|harrastukset"
        # CS
        r"|z[áa]jmy|kon[ií][čc]ky"
        # HU
        r"|[ée]rdekl[őo]d[ée]s|hobbik?"
        # RO
        r"|interese|hobby-?uri"
        # AR
        r"|الاهتمامات|الهوايات"
        # ZH
        r"|兴趣|爱好|兴趣爱好"
        # JA
        r"|趣味|興味|関心"
        # KO
        r"|관심사|취미"
        # HI
        r"|रुचियां|शौक"
        # ID
        r"|minat|hobi"
        # VI
        r"|s[ởo]\s+th[ií]ch|đam\s+m[êe]"
        # TH
        r"|ความสนใจ|งานอดิเรก"
        r")$",
        re.I,
    ),
}


# ── block splitter ────────────────────────────────────────────────────────

def _clean_line(line: str) -> str:
    """Normalize a single line (NFC, collapse whitespace)."""
    clean = unicodedata.normalize("NFC", line)
    clean = re.sub(r"[ \t]+", " ", clean).strip()
    return clean


def split_blocks(text: str) -> List[List[str]]:
    """Split text into blocks separated by one or more blank lines.

    When a known section header (EXPERIENCE, EDUCATION, SKILLS …) appears
    on its own line *inside* an existing block, force a split there so
    that each section gets its own block.  This is critical for PDFs where
    the extractor strips blank lines between sections.

    Multi-column reconstruction is handled upstream by _extract_pdf_text
    using pdfplumber word coordinates.
    """
    blocks: List[List[str]] = []
    current: List[str] = []

    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _clean_line(raw)
        if not line:
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)

    if current:
        blocks.append(current)

    # Second pass: split any block that contains section headers mid-block.
    # Also detect merged all-caps headers (e.g. "EDUCATIONCOMMUNICATION")
    # and expand them into separate header lines.
    refined: List[List[str]] = []
    for block in blocks:
        if len(block) <= 1:
            # Even single-line blocks might be merged headers
            expanded = _try_split_merged_line(block[0]) if block else block
            if len(expanded) > 1:
                for h in expanded:
                    refined.append([h])
            else:
                refined.append(block)
            continue
        sub: List[str] = []
        for line in block:
            # Check for merged header first
            expanded = _try_split_merged_line(line)
            if len(expanded) > 1:
                # Each part becomes its own block
                if sub:
                    refined.append(sub)
                    sub = []
                for h in expanded:
                    refined.append([h])
            elif _sniff_header(line):
                if sub:
                    refined.append(sub)
                sub = [line]
            else:
                sub.append(line)
        if sub:
            refined.append(sub)

    return refined


# Multi-column text reconstruction is now handled upstream by
# _extract_pdf_text() using pdfplumber word coordinates.


# ── entry splitter inside blocks ──────────────────────────────────────────

# A line that is likely a "title line" introducing an entry: starts with
# a capitalized phrase and may contain a date somewhere on the same line.
_TITLE_WITH_DATE_RE = re.compile(
    rf"^(?![-*\u2022\u2013\u2014\u2023\u25aa\u25a0]\s)"  # not a bullet
    rf"[A-ZÀ-ÖØ-Þ\u0100-\u024F]"                        # starts uppercase
    rf".*\b{_YEAR}\b",                                     # has a year
    re.UNICODE,
)

# Year-only line: just a year with optional surrounding whitespace.
_YEAR_ONLY_LINE_RE = re.compile(rf"^\s*{_YEAR}\s*$")

# Title-like line: short (2-4 words), starts uppercase, no bullet, no
# email/URL, letters-only.  All significant words (len > 2) must start
# with an uppercase letter to qualify (strict Title Case).
_TITLE_LIKE_LINE_RE = re.compile(
    r"^(?![-*\u2022\u2013\u2014\u2023\u25aa\u25a0]\s)"   # not a bullet
    r"[A-ZÀ-ÖØ-Þ\u0100-\u024F]"                          # starts uppercase
    r"[\w\u00C0-\u024F' -]+$",                             # letters/hyphens/spaces only
    re.UNICODE,
)

# Capitalized phrase + year on the same line (e.g. "Istanbul University 2018")
_CAP_PHRASE_YEAR_RE = re.compile(
    rf"(?:[A-ZÀ-ÖØ-Þ\u0100-\u024F][\w\u00C0-\u024F'-]+\s+){{2,}}"
    rf".*\b{_YEAR}\b",
)

# Degree-like structural pattern: a short abbreviation (2-5 chars, starts
# uppercase, may contain periods) followed by a capitalized multi-word phrase.
# Examples: "BSc Istanbul Technical University", "MBA Finance".
_DEGREE_INSTITUTION_RE = re.compile(
    r"^(?:[-*\u2022\u2013\u2014\u2023\u25aa\u25a0]\s*)?"  # optional bullet
    r"[A-Z][A-Za-z.]{1,4}\s+"                              # short abbrev (2-5 chars)
    r"(?:[A-ZÀ-ÖØ-Þ\u0100-\u024F][\w\u00C0-\u024F'-]+\s*){2,}",  # capitalized phrase
    re.UNICODE,
)


def _is_strong_boundary(line: str) -> bool:
    """Date-bearing structural signals — high confidence entry boundaries.

    * Date range  (``2018 – 2020``, ``Jan 2020 – Present``)
    * Open date   (``2020 –`` at end of line)
    * Title + date (capitalized phrase containing a year)
    * Year-only   (standalone year line)
    * Capitalized phrase + year (``Istanbul University 2018``)
    """
    if _DATE_RANGE_RE.search(line):
        return True
    if _OPEN_DATE_RE.search(line):
        return True
    if _TITLE_WITH_DATE_RE.match(line):
        return True
    if _YEAR_ONLY_LINE_RE.match(line):
        return True
    if _CAP_PHRASE_YEAR_RE.match(line):
        return True
    return False


def _is_weak_boundary(line: str) -> bool:
    """Structural signals that MAY indicate an entry boundary but can also
    appear within a single entry.  Only used for splitting when the current
    sub-block already contains a consumed strong (date) signal.

    * Title-like line (2-4 words, strict Title Case, letters-only)
    * Degree + institution (short abbreviation + capitalized phrase)
    """
    # degree + institution
    if _DEGREE_INSTITUTION_RE.match(line):
        return True
    # title-like line (strictest check last)
    stripped = line.strip()
    words = stripped.split()
    if (2 <= len(words) <= 4
            and _TITLE_LIKE_LINE_RE.match(stripped)
            and not _EMAIL_RE.search(stripped)
            and not _URL_RE.search(stripped)
            and not _SINGLE_YEAR_RE.search(stripped)
            and all(w[0].isupper() for w in words if len(w) > 2)):
        return True
    return False


def _is_bullet_restart(line: str, prev_lines: List[str]) -> bool:
    """Detect bullet-group restart: current line is a bullet whose content
    carries a capitalized phrase or year, the preceding line was NOT a
    bullet and NOT a date line.  Signals a new entry starting with a
    bullet list (common in merged blocks)."""
    if not _BULLET_RE.match(line):
        return False
    after_bullet = re.sub(r"^\s*[-*\u2022\u2013\u2014\u2023\u25aa\u25a0]\s*", "", line)
    has_signal = bool(
        _SINGLE_YEAR_RE.search(after_bullet)
        or _CAPITALIZED_PHRASE_RE.match(after_bullet)
    )
    if not has_signal:
        return False
    if prev_lines:
        last = prev_lines[-1]
        # Mid-list: prev is also a bullet → not a restart
        if _BULLET_RE.match(last):
            return False
        # Right-after-date: prev is a strong (date) boundary → normal
        # within-entry transition, not a restart
        if _is_strong_boundary(last):
            return False
    return True


def _find_last_strong_idx(sub: List[str]) -> int:
    """Return the index of the last strong-boundary line in *sub*, or -1."""
    for i in range(len(sub) - 1, -1, -1):
        if _is_strong_boundary(sub[i]):
            return i
    return -1


def split_entries_inside_block(blocks: List[List[str]]) -> List[List[str]]:
    """Split blocks that contain multiple entries.

    Runs after ``split_blocks()`` and before classification.  The goal is
    to separate blocks where the PDF extractor merged two distinct entries
    (e.g. an education record followed by a work-experience record) into a
    single block because there was no blank line between them.

    **Structural signals only** — no CV-specific rules.

    Boundary signals are classified as **strong** (date-bearing, high
    confidence) or **weak** (structural but ambiguous):

    Strong: date range, open date, title+date, year-only, cap-phrase+year
    Weak:   title-like line, degree+institution, bullet group restart

    Gating rules:
    * Only the first strong signal in a sub-block is "consumed" (marks the
      sub as having an established entry).
    * Subsequent strong signals trigger a split, with **backtrack**: lines
      after the last strong signal in the current sub are carried over to
      the new sub (they belong to the next entry).
    * Weak signals trigger a split only *after* a strong signal has been
      consumed (the first entry is anchored by a date).
    * Safety: never split unless the current sub-block has ≥1 content line.

    Requires ≥2 total boundaries (strong+weak) AND ≥1 strong to proceed.
    """
    result: List[List[str]] = []

    for block in blocks:
        if len(block) < 3:
            result.append(block)
            continue

        # ── count boundaries; need ≥2 total AND ≥1 strong ──
        total_boundaries = 0
        strong_count = 0
        for idx, line in enumerate(block):
            if _is_strong_boundary(line):
                total_boundaries += 1
                strong_count += 1
            elif _is_weak_boundary(line):
                total_boundaries += 1
            elif idx > 0 and _is_bullet_restart(line, block[:idx]):
                total_boundaries += 1

        if total_boundaries < 2 or strong_count < 1:
            result.append(block)
            continue

        # ── walk the block with strong_seen gating ──
        sub: List[str] = []
        strong_seen = False  # a strong signal has been consumed in this sub

        for idx, line in enumerate(block):
            is_strong = _is_strong_boundary(line)
            is_weak = (_is_weak_boundary(line)
                       or (idx > 0 and _is_bullet_restart(line, block[:idx])))

            should_split = False
            if (is_strong or is_weak) and strong_seen:
                content_lines = sum(
                    1 for l in sub if l.strip() and not _sniff_header(l)
                )
                if content_lines >= 1:
                    should_split = True

            if should_split:
                if is_strong:
                    # ── backtrack: lines after the last date in sub
                    # belong to the new entry, not the old one ──
                    last_d = _find_last_strong_idx(sub)
                    if last_d >= 0 and last_d < len(sub) - 1:
                        before = sub[:last_d + 1]
                        carry = sub[last_d + 1:]
                        if before:
                            result.append(before)
                        sub = carry + [line]
                    else:
                        result.append(sub)
                        sub = [line]
                    strong_seen = True   # this strong line is consumed
                else:
                    # Weak signal split (no backtrack needed — weak signals
                    # appear at the start of a new entry, not mid-entry)
                    result.append(sub)
                    sub = [line]
                    strong_seen = False  # reset for new sub
            else:
                sub.append(line)
                if is_strong and not strong_seen:
                    strong_seen = True

        if sub:
            result.append(sub)

    return result


# ── canonical section key mapper ──────────────────────────────────────────

_CANONICAL_KEYS = [
    "summary", "experience", "education", "skills", "projects",
    "certifications", "languages", "interests", "contact", "misc",
]

# Exhaustive alias → canonical map.  Used by _canonicalize_section_key as
# first-pass exact lookup before falling back to substring matching.
_GLOBAL_ALIASES: Dict[str, str] = {
    # ── summary ──────────────────────────────────────────────────────
    "personal information": "summary", "profile": "summary",
    "about": "summary", "about me": "summary", "objective": "summary",
    "career objective": "summary", "personal": "summary",
    "personal statement": "summary", "personal profile": "summary",
    "professional summary": "summary", "executive summary": "summary",
    "executive profile": "summary", "career summary": "summary", "introduction": "summary",
    # TR
    "özet": "summary", "kişisel bilgiler": "summary",
    "kariyer özeti": "summary",
    # FR
    "résumé professionnel": "summary", "profil professionnel": "summary",
    # DE
    "zusammenfassung": "summary", "über mich": "summary", "kurzprofil": "summary",
    # ES
    "resumen profesional": "summary", "perfil profesional": "summary",
    "resumen": "summary", "perfil": "summary",
    # PT
    "resumo profissional": "summary", "perfil profissional": "summary",
    "resumo": "summary", "objetivo profissional": "summary",
    # IT
    "profilo professionale": "summary", "riepilogo": "summary", "sommario": "summary",
    # NL
    "samenvatting": "summary", "profiel": "summary", "persoonlijk profiel": "summary",
    # RU
    "резюме": "summary", "профиль": "summary", "о себе": "summary",
    "краткое описание": "summary",
    # PL
    "podsumowanie": "summary", "podsumowanie zawodowe": "summary",
    "profil zawodowy": "summary", "o mnie": "summary",
    # SV
    "sammanfattning": "summary", "personlig profil": "summary",
    # NO/DA
    "sammendrag": "summary",
    # FI
    "yhteenveto": "summary", "profiili": "summary", "henkilöprofiili": "summary",
    # CS
    "shrnutí": "summary", "osobní profil": "summary",
    # HU
    "összefoglaló": "summary", "személyes profil": "summary",
    # RO
    "rezumat": "summary", "profil personal": "summary", "obiectiv": "summary",
    # AR
    "ملخص": "summary", "نبذة شخصية": "summary", "الملف الشخصي": "summary",
    "هدف وظيفي": "summary",
    # ZH
    "个人简介": "summary", "个人概述": "summary", "自我介绍": "summary",
    "职业目标": "summary", "摘要": "summary", "个人总结": "summary",
    # JA
    "概要": "summary", "自己紹介": "summary", "プロフィール": "summary",
    "職務要約": "summary",
    # KO
    "요약": "summary", "자기소개": "summary", "프로필": "summary",
    "경력 요약": "summary",
    # HI
    "सारांश": "summary", "प्रोफ़ाइल": "summary", "परिचय": "summary",
    "व्यक्तिगत विवरण": "summary",
    # ID
    "ringkasan": "summary", "tentang saya": "summary", "ikhtisar": "summary",
    # VI
    "tóm tắt": "summary", "hồ sơ": "summary", "giới thiệu bản thân": "summary",
    # TH
    "สรุป": "summary", "โปรไฟล์": "summary", "ประวัติย่อ": "summary",

    # ── contact ──────────────────────────────────────────────────────
    "communication": "contact", "contact information": "contact",
    "contact info": "contact", "personal info": "contact",
    "details": "contact",
    # TR
    "iletişim": "contact", "iletişim bilgileri": "contact",
    # FR
    "coordonnées": "contact", "informations de contact": "contact",
    # DE
    "kontakt": "contact", "kontaktdaten": "contact",
    "kontaktinformationen": "contact",
    # ES
    "contacto": "contact", "información de contacto": "contact",
    "datos de contacto": "contact",
    # PT
    "contato": "contact", "informações de contato": "contact",
    # IT
    "contatto": "contact", "contatti": "contact",
    "informazioni di contatto": "contact",
    # NL
    "contactgegevens": "contact",
    # RU
    "контакт": "contact", "контакты": "contact",
    "контактная информация": "contact",
    # PL
    "dane kontaktowe": "contact",
    # SV
    "kontaktinformation": "contact", "kontaktuppgifter": "contact",
    # NO
    "kontaktopplysninger": "contact",
    # FI
    "yhteystiedot": "contact",
    # CS
    "kontaktní údaje": "contact",
    # HU
    "kapcsolat": "contact", "elérhetőség": "contact", "elérhetőségek": "contact",
    # RO
    "date de contact": "contact",
    # AR
    "الاتصال": "contact", "التواصل": "contact", "معلومات الاتصال": "contact",
    "بيانات التواصل": "contact",
    # ZH
    "联系方式": "contact", "联系信息": "contact",
    # JA
    "連絡先": "contact", "連絡情報": "contact",
    # KO
    "연락처": "contact", "연락 정보": "contact",
    # HI
    "संपर्क": "contact", "संपर्क जानकारी": "contact",
    # ID
    "kontak": "contact", "informasi kontak": "contact",
    # VI
    "liên hệ": "contact", "thông tin liên hệ": "contact",
    # TH
    "ติดต่อ": "contact", "ข้อมูลติดต่อ": "contact",

    # ── experience ───────────────────────────────────────────────────
    "work": "experience", "employment": "experience",
    "work experience": "experience", "professional experience": "experience",
    "career history": "experience", "work history": "experience",
    "work background": "experience",
    "employment history": "experience", "professional background": "experience",
    "training": "experience", "trainings": "experience",
    # TR
    "deneyim": "experience", "iş deneyimi": "experience",
    "mesleki deneyim": "experience",
    # FR
    "expérience": "experience", "expérience professionnelle": "experience",
    "parcours professionnel": "experience",
    # DE
    "erfahrung": "experience", "berufserfahrung": "experience",
    "beruflicher werdegang": "experience",
    # ES
    "experiencia": "experience", "experiencia laboral": "experience",
    "experiencia profesional": "experience",
    "trayectoria profesional": "experience",
    # PT
    "experiência": "experience", "experiência profissional": "experience",
    "histórico profissional": "experience",
    # IT
    "esperienza": "experience", "esperienza lavorativa": "experience",
    "esperienze professionali": "experience",
    # NL
    "ervaring": "experience", "werkervaring": "experience",
    "professionele ervaring": "experience",
    # RU
    "опыт": "experience", "опыт работы": "experience",
    "трудовой стаж": "experience", "профессиональный опыт": "experience",
    # PL
    "doświadczenie": "experience", "doświadczenie zawodowe": "experience",
    "historia zatrudnienia": "experience",
    # SV
    "erfarenhet": "experience", "arbetslivserfarenhet": "experience",
    "yrkeserfarenhet": "experience",
    # NO
    "erfaring": "experience", "arbeidserfaring": "experience",
    "yrkeserfaring": "experience",
    # DA
    "erhvervserfaring": "experience", "arbejdserfaring": "experience",
    # FI
    "kokemus": "experience", "työkokemus": "experience",
    "työhistoria": "experience",
    # CS
    "zkušenosti": "experience", "pracovní zkušenosti": "experience",
    # HU
    "tapasztalat": "experience", "munkatapasztalat": "experience",
    "szakmai tapasztalat": "experience",
    # RO
    "experiență": "experience", "experiență profesională": "experience",
    # AR
    "الخبرة": "experience", "الخبرة المهنية": "experience",
    "الخبرات": "experience", "خبرة العمل": "experience",
    # ZH
    "工作经验": "experience", "工作经历": "experience",
    "职业经历": "experience", "工作履历": "experience",
    # JA
    "職歴": "experience", "経験": "experience", "職務経歴": "experience",
    # KO
    "경력": "experience", "경험": "experience",
    "직무 경험": "experience", "업무 경험": "experience",
    # HI
    "अनुभव": "experience", "कार्य अनुभव": "experience",
    # ID
    "pengalaman": "experience", "pengalaman kerja": "experience",
    "riwayat pekerjaan": "experience",
    # VI
    "kinh nghiệm": "experience", "kinh nghiệm làm việc": "experience",
    # TH
    "ประสบการณ์": "experience", "ประสบการณ์ทำงาน": "experience",

    # ── education ────────────────────────────────────────────────────
    "academic": "education", "academics": "education",
    "qualifications": "education", "academic qualifications": "education",
    "studies": "education", "academic background": "education", "educational background": "education",
    # TR
    "eğitim": "education", "akademik geçmiş": "education",
    # FR
    "formation": "education", "études": "education",
    "parcours académique": "education",
    # DE
    "ausbildung": "education", "bildung": "education", "studium": "education",
    "akademische ausbildung": "education",
    # ES
    "educación": "education", "formación": "education",
    "formación académica": "education",
    # PT
    "educação": "education", "formação acadêmica": "education",
    # IT
    "istruzione": "education", "formazione": "education",
    # NL
    "opleiding": "education", "onderwijs": "education", "opleidingen": "education",
    # RU
    "образование": "education", "обучение": "education",
    # PL
    "wykształcenie": "education", "edukacja": "education",
    # SV
    "utbildning": "education", "akademisk bakgrund": "education",
    # NO
    "utdanning": "education", "utdannelse": "education",
    # DA
    "uddannelse": "education", "akademisk baggrund": "education",
    # FI
    "koulutus": "education", "opinnot": "education",
    # CS
    "vzdělání": "education",
    # HU
    "végzettség": "education", "tanulmányok": "education", "oktatás": "education",
    # RO
    "educație": "education", "studii": "education",
    # AR
    "التعليم": "education", "المؤهلات الأكاديمية": "education",
    "الدراسة": "education",
    # ZH
    "教育": "education", "学历": "education", "教育背景": "education",
    "学习经历": "education",
    # JA
    "学歴": "education",
    # KO
    "학력": "education", "교육": "education",
    # HI
    "शिक्षा": "education", "शैक्षिक योग्यता": "education",
    # ID
    "pendidikan": "education", "riwayat pendidikan": "education",
    # VI
    "học vấn": "education", "trình độ học vấn": "education",
    # TH
    "การศึกษา": "education", "ประวัติการศึกษา": "education",

    # ── skills ───────────────────────────────────────────────────────
    "technical skills": "skills", "core competencies": "skills", "skill set": "skills", "skills set": "skills",
    "competencies": "skills", "technologies": "skills",
    "abilities": "skills", "key skills": "skills",
    "professional skills": "skills", "it skills": "skills",
    "hard skills": "skills", "soft skills": "skills",
    # TR
    "beceriler": "skills", "yetenekler": "skills",
    "teknik beceriler": "skills", "yetkinlikler": "skills",
    # FR
    "compétences": "skills", "compétences techniques": "skills",
    "aptitudes": "skills",
    # DE
    "fähigkeiten": "skills", "kenntnisse": "skills",
    "kompetenzen": "skills", "technische fähigkeiten": "skills",
    # ES
    "habilidades": "skills", "competencias": "skills",
    "habilidades técnicas": "skills",
    # PT
    "competências": "skills", "aptidões": "skills",
    # IT
    "competenze": "skills", "abilità": "skills",
    "competenze tecniche": "skills",
    # NL
    "vaardigheden": "skills", "competenties": "skills",
    "technische vaardigheden": "skills",
    # RU
    "навыки": "skills", "умения": "skills", "компетенции": "skills",
    "технические навыки": "skills",
    # PL
    "umiejętności": "skills", "kompetencje": "skills",
    # SV
    "färdigheter": "skills", "kompetenser": "skills",
    # NO
    "ferdigheter": "skills", "kompetanser": "skills",
    # DA
    "færdigheder": "skills", "kompetencer": "skills",
    # FI
    "taidot": "skills", "osaaminen": "skills",
    # CS
    "dovednosti": "skills", "schopnosti": "skills",
    # HU
    "készségek": "skills", "képességek": "skills", "szaktudás": "skills",
    # RO
    "competențe": "skills", "abilități": "skills",
    # AR
    "المهارات": "skills", "المهارات التقنية": "skills", "القدرات": "skills",
    # ZH
    "技能": "skills", "专业技能": "skills", "核心能力": "skills",
    # JA
    "スキル": "skills", "技術": "skills", "能力": "skills",
    # KO
    "기술": "skills", "스킬": "skills", "역량": "skills", "핵심 역량": "skills",
    # HI
    "कौशल": "skills", "दक्षता": "skills", "तकनीकी कौशल": "skills",
    # ID
    "keahlian": "skills", "keterampilan": "skills", "kemampuan": "skills",
    # VI
    "kỹ năng": "skills", "năng lực": "skills",
    # TH
    "ทักษะ": "skills", "ความสามารถ": "skills",

    # ── projects ─────────────────────────────────────────────────────
    "project": "projects", "portfolio": "projects",
    "personal projects": "projects", "academic projects": "projects",
    "key projects": "projects", "project experience": "projects",
    # TR
    "projeler": "projects", "kişisel projeler": "projects",
    # FR
    "projets": "projects", "projets personnels": "projects",
    # DE
    "projekte": "projects",
    # ES
    "proyectos": "projects",
    # PT
    "projetos": "projects", "projectos": "projects",
    # IT
    "progetti": "projects",
    # NL
    "projecten": "projects",
    # RU
    "проекты": "projects", "личные проекты": "projects",
    # PL/CS
    "projekty": "projects",
    # SV/DA
    "projekter": "projects",
    # NO
    "prosjekter": "projects",
    # FI
    "projektit": "projects",
    # HU
    "projektek": "projects",
    # RO
    "proiecte": "projects",
    # AR
    "المشاريع": "projects", "مشاريع": "projects",
    # ZH
    "项目": "projects", "项目经验": "projects", "个人项目": "projects",
    # JA
    "プロジェクト": "projects",
    # KO
    "프로젝트": "projects",
    # HI
    "परियोजनाएं": "projects", "परियोजना": "projects",
    # ID
    "proyek": "projects",
    # VI
    "dự án": "projects",
    # TH
    "โครงการ": "projects",

    # ── certifications ───────────────────────────────────────────────
    "certification": "certifications", "certificates": "certifications",
    "certificate": "certifications", "licenses": "certifications",
    "awards": "certifications", "awards and certifications": "certifications",
    # TR
    "sertifikalar": "certifications", "belgeler": "certifications",
    # FR
    "diplômes": "certifications",
    # DE
    "zertifizierungen": "certifications", "zertifikate": "certifications",
    # ES
    "certificaciones": "certifications", "certificados": "certifications",
    # PT
    "certificações": "certifications",
    # IT
    "certificazioni": "certifications",
    # NL
    "certificeringen": "certifications", "certificaten": "certifications",
    # RU
    "сертификаты": "certifications", "дипломы": "certifications",
    # PL
    "certyfikaty": "certifications",
    # SV
    "certifieringar": "certifications",
    # NO
    "sertifiseringer": "certifications",
    # DA
    "certificeringer": "certifications",
    # FI
    "sertifikaatit": "certifications", "todistukset": "certifications",
    # CS
    "certifikáty": "certifications",
    # HU
    "tanúsítványok": "certifications", "minősítések": "certifications",
    # RO
    "certificări": "certifications",
    # AR
    "الشهادات": "certifications", "شهادات": "certifications",
    # ZH
    "证书": "certifications", "资格证书": "certifications", "认证": "certifications",
    # JA
    "資格": "certifications", "認定": "certifications",
    # KO
    "자격증": "certifications", "인증": "certifications",
    # HI
    "प्रमाणपत्र": "certifications",
    # ID
    "sertifikasi": "certifications", "sertifikat": "certifications",
    # VI
    "chứng chỉ": "certifications",
    # TH
    "ใบรับรอง": "certifications", "ประกาศนียบัตร": "certifications",

    # ── languages ────────────────────────────────────────────────────
    "language": "languages", "language skills": "languages",
    "foreign languages": "languages", "linguistic": "languages",
    # TR
    "diller": "languages", "yabancı diller": "languages",
    # FR
    "langues": "languages", "compétences linguistiques": "languages",
    # DE
    "sprachen": "languages", "sprachkenntnisse": "languages",
    # ES
    "idiomas": "languages", "lenguas": "languages",
    # PT
    "línguas": "languages",
    # IT
    "lingue": "languages", "competenze linguistiche": "languages",
    # NL
    "talen": "languages", "talenkennis": "languages",
    # RU
    "языки": "languages", "знание языков": "languages",
    "владение языками": "languages",
    # PL
    "języki": "languages", "języki obce": "languages",
    # SV/NO
    "språk": "languages",
    # DA
    "sprog": "languages",
    # FI
    "kielet": "languages", "kielitaito": "languages",
    # CS
    "jazyky": "languages", "jazykové znalosti": "languages",
    # HU
    "nyelvek": "languages", "nyelvtudás": "languages",
    "idegen nyelvek": "languages",
    # RO
    "limbi": "languages", "limbi străine": "languages",
    # AR
    "اللغات": "languages", "المهارات اللغوية": "languages",
    # ZH
    "语言": "languages", "语言能力": "languages", "外语": "languages",
    # JA
    "言語": "languages", "語学": "languages",
    # KO
    "언어": "languages", "외국어": "languages",
    # HI
    "भाषाएं": "languages", "भाषा कौशल": "languages",
    # ID
    "bahasa": "languages",
    # VI
    "ngôn ngữ": "languages", "ngoại ngữ": "languages",
    # TH
    "ภาษา": "languages", "ทักษะทางภาษา": "languages",

    # ── interests ────────────────────────────────────────────────────
    "interest": "interests", "hobbies": "interests",
    "personal interest": "interests", "personal interests": "interests",
    # TR
    "ilgi alanları": "interests", "hobiler": "interests",
    # FR
    "centres d'intérêt": "interests", "loisirs": "interests",
    "passions": "interests",
    # DE
    "interessen": "interests", "hobbys": "interests",
    # ES
    "intereses": "interests", "aficiones": "interests",
    "pasatiempos": "interests",
    # PT
    "interesses": "interests", "passatempos": "interests",
    # IT
    "interessi": "interests", "hobby": "interests",
    "passioni": "interests", "tempo libero": "interests",
    # NL
    "hobby's": "interests",
    # RU
    "интересы": "interests", "хобби": "interests", "увлечения": "interests",
    # PL
    "zainteresowania": "interests",
    # SV
    "intressen": "interests",
    # NO/DA
    "interesser": "interests",
    # FI
    "kiinnostukset": "interests", "harrastukset": "interests",
    # CS
    "zájmy": "interests", "koníčky": "interests",
    # HU
    "érdeklődés": "interests", "hobbik": "interests",
    # RO
    "interese": "interests", "hobby-uri": "interests",
    # AR
    "الاهتمامات": "interests", "الهوايات": "interests",
    # ZH
    "兴趣": "interests", "爱好": "interests", "兴趣爱好": "interests",
    # JA
    "趣味": "interests", "興味": "interests", "関心": "interests",
    # KO
    "관심사": "interests", "취미": "interests",
    # HI
    "रुचियां": "interests", "शौक": "interests",
    # ID
    "minat": "interests", "hobi": "interests",
    # VI
    "sở thích": "interests", "đam mê": "interests",
    # TH
    "ความสนใจ": "interests", "งานอดิเรก": "interests",
}

# Substring fragments → canonical key for fuzzy fallback
_FUZZY_FRAGMENTS: list[tuple[str, str]] = [
    # EN
    ("summar", "summary"), ("profile", "summary"), ("objective", "summary"),
    ("about", "summary"), ("personal info", "summary"),
    ("contact", "contact"), ("communic", "contact"), ("details", "contact"),
    ("experi", "experience"), ("employ", "experience"), ("work", "experience"),
    ("career", "experience"),
    ("educat", "education"), ("academ", "education"),
    ("studies", "education"), ("qualif", "education"),
    ("skill", "skills"), ("competen", "skills"), ("abilit", "skills"),
    ("project", "projects"), ("portfolio", "projects"),
    ("certif", "certifications"), ("licens", "certifications"),
    ("language", "languages"), ("linguist", "languages"),
    ("interest", "interests"), ("hobbi", "interests"),
    # FR
    ("résumé", "summary"), ("profil professionnel", "summary"),
    ("expérience", "experience"), ("parcours", "experience"),
    ("formation", "education"), ("études", "education"),
    ("compétence", "skills"), ("aptitude", "skills"),
    ("projet", "projects"), ("diplôme", "certifications"),
    ("langue", "languages"), ("loisir", "interests"),
    ("coordonnée", "contact"),
    # DE
    ("zusammenfassung", "summary"), ("kurzprofil", "summary"),
    ("erfahrung", "experience"), ("beruf", "experience"),
    ("ausbildung", "education"), ("bildung", "education"), ("studium", "education"),
    ("fähigkeit", "skills"), ("kenntnis", "skills"), ("kompetenz", "skills"),
    ("projekte", "projects"), ("zertifik", "certifications"),
    ("sprach", "languages"), ("kontakt", "contact"),
    # ES/PT
    ("experiencia", "experience"), ("experiência", "experience"),
    ("educación", "education"), ("educação", "education"),
    ("formación", "education"), ("formação", "education"),
    ("habilidad", "skills"), ("competência", "skills"),
    ("proyecto", "projects"), ("idioma", "languages"),
    ("certificacion", "certifications"), ("certificação", "certifications"),
    # IT
    ("esperienza", "experience"), ("istruzione", "education"),
    ("competenz", "skills"), ("progetti", "projects"),
    ("certificazion", "certifications"), ("lingu", "languages"),
    # NL
    ("ervaring", "experience"), ("opleiding", "education"),
    ("vaardighe", "skills"), ("projecten", "projects"),
    # RU
    ("опыт", "experience"), ("образован", "education"),
    ("навык", "skills"), ("умен", "skills"), ("проект", "projects"),
    ("сертификат", "certifications"), ("язык", "languages"),
    ("интерес", "interests"), ("хобби", "interests"),
    ("резюме", "summary"), ("профил", "summary"),
    # PL
    ("doświadczeni", "experience"), ("wykształceni", "education"),
    ("umiejętnoś", "skills"), ("zainteresowania", "interests"),
    # SV/NO/DA
    ("erfarenhet", "experience"), ("utbildning", "education"),
    ("utdanning", "education"), ("uddannelse", "education"),
    ("färdighet", "skills"), ("ferdighet", "skills"),
    # FI
    ("kokemus", "experience"), ("koulutus", "education"),
    ("taido", "skills"), ("osaaminen", "skills"),
    # CS/HU/RO
    ("zkušenost", "experience"), ("tapasztalat", "experience"),
    ("vzdělán", "education"), ("végzettség", "education"),
    ("dovednost", "skills"), ("készség", "skills"),
    # AR
    ("الخبر", "experience"), ("التعليم", "education"),
    ("المهار", "skills"), ("المشاريع", "projects"),
    ("الشهاد", "certifications"), ("اللغ", "languages"),
    ("الاهتمام", "interests"), ("ملخص", "summary"),
    # ZH
    ("经验", "experience"), ("经历", "experience"),
    ("教育", "education"), ("学历", "education"),
    ("技能", "skills"), ("项目", "projects"),
    ("证书", "certifications"), ("语言", "languages"),
    ("兴趣", "interests"), ("简介", "summary"),
    # JA
    ("職歴", "experience"), ("学歴", "education"),
    ("スキル", "skills"), ("プロジェクト", "projects"),
    ("資格", "certifications"), ("言語", "languages"),
    ("趣味", "interests"), ("概要", "summary"),
    # KO
    ("경력", "experience"), ("학력", "education"),
    ("기술", "skills"), ("프로젝트", "projects"),
    ("자격증", "certifications"), ("언어", "languages"),
    ("취미", "interests"), ("요약", "summary"),
    # HI
    ("अनुभव", "experience"), ("शिक्षा", "education"),
    ("कौशल", "skills"), ("परियोजना", "projects"),
    ("प्रमाणपत्र", "certifications"), ("भाषा", "languages"),
    ("रुचि", "interests"), ("सारांश", "summary"),
    # ID
    ("pengalaman", "experience"), ("pendidikan", "education"),
    ("keahlian", "skills"), ("keterampilan", "skills"),
    ("proyek", "projects"), ("sertifikas", "certifications"),
    ("ringkasan", "summary"),
    # VI
    ("kinh nghiệm", "experience"), ("học vấn", "education"),
    ("kỹ năng", "skills"), ("dự án", "projects"),
    ("chứng chỉ", "certifications"), ("ngôn ngữ", "languages"),
    ("tóm tắt", "summary"),
    # TH
    ("ประสบการณ์", "experience"), ("การศึกษา", "education"),
    ("ทักษะ", "skills"), ("โครงการ", "projects"),
    ("ใบรับรอง", "certifications"), ("ภาษา", "languages"),
    ("ความสนใจ", "interests"), ("สรุป", "summary"),
]


# ── Pre-indexed alias lookup by first character (Task 8) ──────────────
_ALIAS_BY_FIRST: Dict[str, list[str]] = {}
for _alias_key in list(_CANONICAL_KEYS) + list(_GLOBAL_ALIASES.keys()):
    if _alias_key:
        _ALIAS_BY_FIRST.setdefault(_alias_key[0], []).append(_alias_key)


def _fuzzy_match_alias(key: str, cutoff: float = 0.82) -> str | None:
    """Use edit-distance matching to find the closest known alias.

    Returns the canonical section name if a close match is found with
    similarity >= *cutoff*, else None.  Only fuzzy-matches keys with
    length >= 4 to avoid false positives on short words.
    Uses a pre-indexed lookup by first character for performance.
    """
    if len(key) < 4:
        return None
    # Narrow candidates by first character for performance
    first = key[0] if key else ""
    candidates = _ALIAS_BY_FIRST.get(first, [])
    if not candidates:
        # Fall back to full list if no first-char bucket
        candidates = list(_CANONICAL_KEYS) + list(_GLOBAL_ALIASES.keys())
    matches = difflib.get_close_matches(key, candidates, n=1, cutoff=cutoff)
    if not matches:
        return None
    best = matches[0]
    if best in _CANONICAL_KEYS:
        return best
    return _GLOBAL_ALIASES.get(best)


def canonicalize_section_key(raw: str) -> str:
    """Map *raw* section label to a canonical key.

    Strategy — score-based selection (highest wins):
      +3  exact alias match
      +2  substring fragment match
      +2  edit-distance fuzzy match (len >= 4)
    If nothing matches, return original (never drop).
    """
    if not raw:
        return raw
    key = re.sub(r"[^\w\s]|[\d_]", " ", raw.lower(), flags=re.UNICODE).strip()
    key = re.sub(r"\s+", " ", key)

    # Already canonical?
    if key in _CANONICAL_KEYS:
        return key

    best_score = 0
    best_canonical = key  # fallback = original

    # Exact alias → score 3
    mapped = _GLOBAL_ALIASES.get(key)
    if mapped:
        best_score, best_canonical = 3, mapped

    # Substring fragment → score 2 (only if not already beaten)
    if best_score < 2:
        for fragment, canonical in _FUZZY_FRAGMENTS:
            if fragment in key:
                best_score, best_canonical = 2, canonical
                break

    # Edit-distance fuzzy → score 2 (only if nothing yet)
    if best_score < 2:
        fuzzy = _fuzzy_match_alias(key)
        if fuzzy:
            best_score, best_canonical = 2, fuzzy

    return best_canonical


# ── header sniff ──────────────────────────────────────────────────────────

# Contact-line guard for _sniff_header: lines matching these patterns must
# never be treated as section headers.
_CONTACT_LINE_RE = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
    r"|(?:\(?\+?\d[\d()\-\s.]{7,}\d)"
    r"|https?://"
    r"|linkedin\.com|github\.com"
    r"|\b(?:birth|dob|doğum|geboren|date\s+of\s+birth)\b",
    re.I,
)

# ALL-CAPS words that are safe to accept as section headers even
# without matching _HEADER_HINTS.  Very conservative list.
_ALLCAPS_SECTION_WORDS = frozenset({
    # EN
    "experience", "education", "skills", "projects", "certifications",
    "languages", "summary", "profile", "objective", "employment",
    "qualifications", "competencies", "technologies", "certificates",
    "communication", "professional", "technical", "personal", "academic",
    "interests", "hobbies", "references", "contact", "activities",
    "publications", "awards", "achievements", "volunteer", "about",
    "work", "portfolio",
    # TR
    "deneyim", "eğitim", "beceriler", "projeler", "sertifikalar",
    "diller", "özet", "profil", "yetenekler", "yetkinlikler",
    "iletişim", "ilgi", "alanları", "referanslar", "hobiler",
    # FR
    "expérience", "formation", "études", "compétences", "projets",
    "certifications", "langues", "loisirs", "coordonnées", "diplômes",
    # DE
    "erfahrung", "berufserfahrung", "ausbildung", "bildung", "studium",
    "fähigkeiten", "kenntnisse", "kompetenzen", "projekte",
    "zertifizierungen", "zertifikate", "sprachen", "kontakt",
    "interessen", "hobbys", "zusammenfassung",
    # ES
    "experiencia", "educación", "formación", "habilidades",
    "competencias", "proyectos", "certificaciones", "idiomas",
    "intereses", "aficiones", "contacto", "resumen", "perfil",
    # PT
    "experiência", "educação", "formação", "habilidades",
    "competências", "projetos", "certificações", "interesses",
    "contato", "resumo",
    # IT
    "esperienza", "istruzione", "formazione", "competenze",
    "abilità", "progetti", "certificazioni", "lingue",
    "interessi", "contatto", "contatti", "riepilogo", "sommario",
    # NL
    "ervaring", "werkervaring", "opleiding", "onderwijs",
    "vaardigheden", "competenties", "projecten", "certificeringen",
    "talen", "contactgegevens", "samenvatting", "profiel",
    # RU
    "опыт", "образование", "навыки", "умения", "компетенции",
    "проекты", "сертификаты", "языки", "контакт", "контакты",
    "интересы", "хобби", "резюме", "профиль",
    # PL
    "doświadczenie", "wykształcenie", "edukacja", "umiejętności",
    "kompetencje", "projekty", "certyfikaty", "języki",
    "zainteresowania", "podsumowanie",
    # SV
    "erfarenhet", "utbildning", "färdigheter", "kompetenser",
    "sammanfattning", "intressen",
    # NO
    "erfaring", "utdanning", "ferdigheter", "kompetanser",
    "sammendrag", "interesser",
    # DA
    "uddannelse", "færdigheder", "kompetencer",
    # FI
    "kokemus", "työkokemus", "koulutus", "taidot", "osaaminen",
    "projektit", "kielet", "yhteystiedot", "yhteenveto",
    "kiinnostukset", "harrastukset",
    # CS
    "zkušenosti", "vzdělání", "dovednosti", "schopnosti",
    "certifikáty", "jazyky", "zájmy", "shrnutí",
    # HU
    "tapasztalat", "végzettség", "tanulmányok", "készségek",
    "képességek", "projektek", "tanúsítványok", "nyelvek",
    "kapcsolat", "összefoglaló", "érdeklődés",
    # RO
    "experiență", "educație", "studii", "competențe", "abilități",
    "proiecte", "certificări", "limbi", "interese", "rezumat",
    # AR
    "الخبرة", "التعليم", "المهارات", "المشاريع", "الشهادات",
    "اللغات", "الاتصال", "التواصل", "الاهتمامات", "الهوايات", "ملخص",
    # ZH
    "工作经验", "教育", "技能", "项目", "证书", "语言",
    "联系方式", "兴趣", "个人简介", "学历",
    # JA
    "職歴", "学歴", "スキル", "プロジェクト", "資格",
    "言語", "連絡先", "趣味", "概要",
    # KO
    "경력", "학력", "기술", "스킬", "프로젝트",
    "자격증", "언어", "연락처", "취미", "요약",
    # HI
    "अनुभव", "शिक्षा", "कौशल", "परियोजनाएं", "प्रमाणपत्र",
    "भाषाएं", "संपर्क", "रुचियां", "सारांश",
    # ID
    "pengalaman", "pendidikan", "keahlian", "keterampilan",
    "proyek", "sertifikasi", "sertifikat", "bahasa",
    "kontak", "ringkasan", "minat",
    # VI
    "kinh nghiệm", "học vấn", "kỹ năng", "dự án",
    "chứng chỉ", "ngôn ngữ", "liên hệ", "sở thích", "tóm tắt",
    # TH
    "ประสบการณ์", "การศึกษา", "ทักษะ", "โครงการ",
    "ใบรับรอง", "ภาษา", "ติดต่อ", "ความสนใจ", "สรุป",
})


def _sniff_header(line: str) -> str | None:
    """If *line* looks like a standalone section header, return the canonical name."""
    stripped = line.strip()
    if not stripped:
        return None
    # Lines starting with bullet markers are never section headers
    if re.match(r'^\s*[-*•‣–—▪■]\s', stripped):
        return None

    # ── Contact-line guard: email / phone / URL / birth-date lines are NEVER headers ──
    if _CONTACT_LINE_RE.search(stripped):
        return None

    # ── Key-Value guard: Lines with "Key : Value" are rarely standalone headers ──
    if ":" in stripped:
        parts = stripped.split(":", 1)
        if len(parts[1].strip().split()) >= 1 and not parts[0].strip().isupper():
            return None

    # Normalize for matching: remove punctuation, collapse whitespace
    # Unicode-aware: keep all letters from any script
    normalized = re.sub(r"[^\w\s]|[\d_]", " ", stripped, flags=re.UNICODE).strip()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized or len(normalized.split()) > 4:
        return None

    # 1) Check against known header hints (regex patterns)
    for canonical, pattern in _HEADER_HINTS.items():
        if pattern.match(normalized):
            return canonical

    # 2) Noise headers
    if _NOISE_KEYWORDS.search(normalized):
        return "noise"

    # 3) Title Case check: "Education", "Experience", "Skills", etc.
    #    Single word that matches a known hint when lowered
    if len(normalized.split()) <= 2:
        lowered = normalized.lower()
        for canonical, pattern in _HEADER_HINTS.items():
            if pattern.match(lowered):
                return canonical

    # 4) ALL-CAPS line → only accept if it matches a known hint or is in
    #    the conservative _ALLCAPS_SECTION_WORDS set.  Unknown ALL-CAPS
    #    words (city names, person names) are NOT section headers.
    if stripped.isupper() and len(stripped) < 40 and len(stripped.split()) <= 4:
        if len(stripped) >= 3 and not re.search(r"\d|@|https?://|\.com", stripped, re.I):
            low = stripped.lower()
            for canonical, pattern in _HEADER_HINTS.items():
                if pattern.match(low):
                    return canonical
            # Only accept known section words, reject everything else
            low_words = low.split()
            if all(w in _ALLCAPS_SECTION_WORDS for w in low_words):
                return low

    # 5) Title Case short line (1-3 words, starts with uppercase, no digits/URLs)
    #    Only return canonical names from _HEADER_HINTS — never return
    #    arbitrary Title Case words (they could be person/company names).
    words = stripped.split()
    if (1 <= len(words) <= 3
        and stripped[0].isupper()
        and not re.search(r"\d|@|https?://|\.com|\.io", stripped, re.I)
        and all(w[0].isupper() for w in words if len(w) > 2)):
        lowered_all = " ".join(w.lower() for w in words)
        for canonical, pattern in _HEADER_HINTS.items():
            if pattern.match(lowered_all):
                return canonical

    # 6) Fuzzy/edit-distance fallback for typos (e.g. "SUMARY", "Experiance")
    #    Only triggered for short lines (≤3 words) that look like headers.
    if len(normalized.split()) <= 3:
        fuzzy = _fuzzy_match_alias(normalized.lower(), cutoff=0.82)
        if fuzzy:
            return fuzzy

    return None


# ── headerless detection helpers ──────────────────────────────────────────

def _is_title_like(line: str) -> bool:
    """Return True if *line* looks like a short title (not a date/URL/email)."""
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return False
    words = stripped.split()
    if not (1 <= len(words) <= 8):
        return False
    if _DATE_RANGE_RE.search(stripped) or _EMAIL_RE.search(stripped):
        return False
    if re.search(r"https?://", stripped, re.I):
        return False
    return stripped[0].isupper() or stripped[0].isdigit()


def _detect_headerless_project(
    lines: List[str], text: str, text_raw: str,
    has_tech: bool, has_url: bool, bullet_count: int,
) -> bool:
    """Detect project blocks without explicit section headers.

    Fires when a title-like line co-occurs with tech keywords and either
    a URL or contextual phrases like 'used technologies' / 'tech stack'.
    """
    has_context = bool(_PROJECT_CONTEXT_RE.search(text))
    has_title = any(_is_title_like(l) for l in lines[:3])
    # title + tech + (URL or context)
    if has_title and has_tech and (has_url or has_context):
        return True
    # context keywords alone + (tech or bullets)
    if has_context and (has_tech or bullet_count >= 1):
        return True
    # URL + tech + title
    if has_url and has_tech and has_title:
        return True
    return False


def _detect_headerless_education(lines: List[str], text: str) -> bool:
    """Detect education blocks: >=2 of {degree, institution, year}."""
    has_degree = bool(re.search(
        r"\b(?:b\.?s\.?c?|m\.?s\.?c?|b\.?a|m\.?a|ph\.?d|m\.?b\.?a"
        r"|bachelor|master|diploma|associate|degree)\b",
        text, re.I,
    ))
    has_institution = bool(re.search(
        r"\b(?:university|institute|college|school|faculty|academy)\b",
        text, re.I,
    ))
    has_year = bool(_SINGLE_YEAR_RE.search(text))
    return sum([has_degree, has_institution, has_year]) >= 2


def _detect_headerless_interests(
    lines: List[str], text: str,
    has_tech: bool, has_url: bool,
) -> bool:
    """Detect interest/hobby blocks: short lines, no tech/date/URL, human words."""
    if has_tech or has_url:
        return False
    if bool(_DATE_RANGE_RE.search(text)):
        return False
    if len(_SINGLE_YEAR_RE.findall(text)) >= 2:
        return False
    if len(lines) > 6:
        return False
    avg_words = sum(len(l.split()) for l in lines) / max(len(lines), 1)
    if avg_words > 8:
        return False
    return bool(_INTEREST_KEYWORDS.search(text))


def _detect_headerless_skills(lines: List[str], text: str, has_tech: bool) -> bool:
    """Detect skills blocks: comma-separated tech tokens or dense tech names."""
    if bool(_DATE_RANGE_RE.search(text)) or bool(_EMAIL_RE.search(text)):
        return False
    if bool(_EDUCATION_KEYWORDS.search(text)):
        return False
    delimiter_count = sum(len(_SKILL_DELIMITER_RE.findall(l)) for l in lines)
    avg_words = sum(len(l.split()) for l in lines) / max(len(lines), 1)
    # Comma-separated tokens with tech names
    if has_tech and delimiter_count >= 3 and avg_words <= 6:
        return True
    # Dense tech names in short block
    tech_hits = len(_TECH_NAMES_RE.findall(text))
    if tech_hits >= 3 and len(lines) <= 5:
        return True
    return False


def _scorer_fallback(text: str) -> str | None:
    """Use section_scorer as last resort before misc.

    *text* should be the original-case text (not lowered) since the
    scorer applies its own case handling internally.
    Returns a section name if confident, otherwise None.
    """
    scores = _scorer_score_text(text)
    if scores.is_confident(min_score=0.40, min_margin=0.10):
        best = scores.best()
        # contact has a high false-positive rate; skip it
        if best != "contact":
            return best
    return None


# ── block classifier ─────────────────────────────────────────────────────

def _classify_content(lines: List[str], text: str, text_raw: str) -> str:
    """Content-only block classification using structural patterns.

    Uses structure + signals, not language dictionaries:
    - Education: year range + capitalized phrase + no url/email
    - Experience: year range + multiple lines / bullets
    - Contact: email / phone / url patterns
    - Skills: short comma/bullet-separated items
    - Languages: CEFR levels (A1-C2) + native/fluent/advanced
    - Projects: url/github + tech names + action verbs
    """

    # ── Security: cap regex input length ──
    if len(text) > _MAX_REGEX_INPUT:
        logger.warning("classify: regex input truncated %d → %d", len(text), _MAX_REGEX_INPUT)
        text = text[:_MAX_REGEX_INPUT]
    if len(text_raw) > _MAX_REGEX_INPUT:
        text_raw = text_raw[:_MAX_REGEX_INPUT]

    has_education_signal = bool(_EDUCATION_KEYWORDS.search(text))
    has_email = bool(_EMAIL_RE.search(text_raw))
    has_url = bool(re.search(r"https?://|github\.com|gitlab\.com|linkedin\.com", text_raw, re.I))
    bullet_count = sum(1 for line in lines if _BULLET_RE.match(line))

    # ── Date-bearing blocks → experience or education ──
    has_dates = bool(_DATE_RANGE_RE.search(text)) or bool(_OPEN_DATE_RE.search(text))
    has_years = len(_SINGLE_YEAR_RE.findall(text)) >= 2
    if has_dates or has_years:
        edu_score = len(_EDUCATION_KEYWORDS.findall(text))
        exp_score = len(_EXPERIENCE_KEYWORDS.findall(text))
        if _CERT_KEYWORDS.search(text) and edu_score == 0 and exp_score == 0:
            return "certifications"
        has_gpa = bool(re.search(r"\bgpa|cgpa\b", text, re.I))
        has_degree = bool(re.search(
            r"\b(?:b\.?s\.?c?|m\.?s\.?c?|b\.?a|m\.?a|ph\.?d|m\.?b\.?a|bachelor|master|diploma|associate|degree)\b",
            text, re.I,
        ))
        # Education: degree/institution/GPA takes priority over experience
        # when there are no bullets (education blocks rarely have bullets).
        if edu_score > 0 or has_gpa or has_degree:
            # Guard: if there are many bullets, this is experience
            # that mentions a degree incidentally.
            if bullet_count >= 3 and exp_score > edu_score:
                return "experience"
            return "education"

        # Education structural fallback: year range + capitalized phrase + no url/email
        has_cap_phrase = bool(_CAPITALIZED_PHRASE_RE.search(text_raw))
        if has_cap_phrase and not has_email and not has_url and len(lines) <= 5:
            # Short block with dates and a capitalized institution-like name
            if bullet_count == 0 and exp_score == 0:
                return "education"

        # Experience: year range + multiple lines or bullets
        if len(lines) >= 3 or bullet_count >= 1:
            return "experience"
        if exp_score > 0:
            return "experience"

        # Default: short date block without other signals → education
        if len(lines) <= 3:
            return "education"
        return "experience"

    # ── Contact: email / phone / url even without label ──
    contact_signals = 0
    has_phone = False
    for line in lines:
        if _EMAIL_RE.search(line):
            contact_signals += 1
        if _PHONE_RE.search(line):
            contact_signals += 1
            has_phone = True
        url_match = _URL_RE.search(line)
        if url_match and not _EDUCATION_KEYWORDS.search(line):
            url_text = url_match.group(0).lower()
            if any(k in url_text for k in ("linkedin", "github", "http", "/")):
                contact_signals += 1
    if not has_education_signal:
        if (has_email or has_phone) and contact_signals >= 1:
            return "contact"
        if contact_signals >= 2:
            return "contact"

    # ── Certifications ──
    if _CERT_KEYWORDS.search(text):
        return "certifications"

    # ── Projects: url/github + tech names, or action verbs + tech ──
    has_tech = bool(_TECH_NAMES_RE.search(text))
    has_project_url = bool(_PROJECT_KEYWORDS.search(text))
    if has_project_url and (has_tech or bullet_count >= 1 or len(lines) >= 2):
        return "projects"
    if has_tech and has_url and bullet_count >= 1:
        return "projects"

    # ── Languages: CEFR levels or proficiency words ──
    lang_matches = len(_LANGUAGE_KEYWORDS.findall(text))
    if lang_matches >= 2 and len(lines) <= 8:
        return "languages"
    # Single CEFR level in a very short block (1-3 lines) → languages
    if lang_matches >= 1 and len(lines) <= 3 and not has_tech:
        return "languages"

    # ── Skills: short items, comma/bullet separated ──
    delimiter_count = sum(len(_SKILL_DELIMITER_RE.findall(line)) for line in lines)
    avg_words = sum(len(line.split()) for line in lines) / max(len(lines), 1)
    has_colon = any(":" in line for line in lines)
    if not has_education_signal and not has_project_url:
        if has_colon and delimiter_count >= 2:
            return "skills"
        if delimiter_count >= 3 and avg_words <= 8:
            return "skills"
        # Bullet list of short items → skills
        if bullet_count >= 2 and avg_words <= 5:
            return "skills"

    # ── Summary: long prose ──
    total_chars = sum(len(line) for line in lines)
    if total_chars > 80 and bullet_count <= 1 and avg_words > 5:
        return "summary"

    # ── Experience: bullet-heavy ──
    if bullet_count >= 3:
        return "experience"

    # ── Headerless fallbacks (misc must be last) ──
    if _detect_headerless_interests(lines, text, has_tech, has_url):
        return "interests"
    if _detect_headerless_project(lines, text, text_raw, has_tech, has_url, bullet_count):
        return "projects"
    if _detect_headerless_education(lines, text):
        return "education"
    if _detect_headerless_skills(lines, text, has_tech):
        return "skills"

    # Section scorer as last resort
    _fb = _scorer_fallback(text_raw)
    if _fb:
        return _fb

    return "other"


def classify_block(lines: List[str], *, layout_type: str = "single_column") -> str:
    """Classify a block of lines into a canonical CV section.

    Parameters
    ----------
    lines : list of str
        Block of text lines to classify.
    layout_type : str
        Structural layout hint from ``layout_analyzer`` (e.g.
        ``"single_column"`` or ``"two_column"``).  Used to adjust
        classification confidence but never overrides explicit headers.

    Priority:
    1. If the first line is a known section header → use it as strong signal.
    2. Content-based heuristics (dates, keywords, structure).
    """
    if not lines:
        return "other"

    # 1) Check if first line is a section header
    header_hint = _sniff_header(lines[0])
    if header_hint:
        # Recognized canonical name or "noise" → return directly
        if header_hint in _CANONICAL_KEYS or header_hint == "noise":
            return header_hint
        # Unrecognized header (non-English): classify by block content
        content_lines = lines[1:]
        if not content_lines:
            return "other"  # bare header, resolved by detect_sections
        text = " ".join(content_lines).lower()
        text_raw = " ".join(content_lines)
        return _classify_content(content_lines, text, text_raw)

    text = " ".join(lines).lower()
    text_raw = " ".join(lines)

    # 2) Noise detection
    if _NOISE_KEYWORDS.search(text):
        return "noise"

    has_education_signal = bool(_EDUCATION_KEYWORDS.search(text))
    has_email = bool(_EMAIL_RE.search(text_raw))
    has_url_any = bool(re.search(r"https?://|github\.com|gitlab\.com|linkedin\.com", text_raw, re.I))
    bullet_count = sum(1 for line in lines if _BULLET_RE.match(line))
    has_tech = bool(_TECH_NAMES_RE.search(text))

    # 3) Has date ranges → experience or education (check BEFORE contact
    #    to avoid date ranges like "2019-2022" matching as phone numbers)
    has_dates = bool(_DATE_RANGE_RE.search(text))
    has_years = len(_SINGLE_YEAR_RE.findall(text)) >= 2

    if has_dates or has_years:
        edu_score = len(_EDUCATION_KEYWORDS.findall(text))
        exp_score = len(_EXPERIENCE_KEYWORDS.findall(text))

        # Certification with dates
        if _CERT_KEYWORDS.search(text) and edu_score == 0 and exp_score == 0:
            return "certifications"

        # Strong education signals: GPA, degree abbreviations, university names
        has_gpa = bool(re.search(r"\bgpa|cgpa\b", text, re.I))
        has_degree = bool(re.search(
            r"\b(?:b\.?s\.?c?|m\.?s\.?c?|b\.?a|m\.?a|ph\.?d|m\.?b\.?a|bachelor|master|diploma|associate|degree)\b",
            text, re.I,
        ))

        # Education: degree/institution/GPA wins over experience when no
        # heavy bullet usage (education blocks rarely have bullets).
        if edu_score > exp_score:
            if bullet_count >= 3 and exp_score > 0:
                return "experience"  # many bullets + company suffix → experience
            return "education"
        if (has_gpa or has_degree) and edu_score >= 1:
            if bullet_count >= 3 and exp_score > 0:
                return "experience"
            return "education"
        # degree + institution (no header) → education, unless bullet-heavy
        if has_degree and bool(_EDUCATION_KEYWORDS.search(text)) and bullet_count <= 1:
            return "education"

        # Education structural fallback: year range + capitalized phrase + no url/email
        has_cap_phrase = bool(_CAPITALIZED_PHRASE_RE.search(text_raw))
        if has_cap_phrase and not has_email and not has_url_any and len(lines) <= 5:
            if bullet_count == 0 and exp_score == 0:
                return "education"

        if exp_score > 0:
            return "experience"

        # Experience: year range + multiple lines or bullets
        if bullet_count >= 1 or len(lines) >= 4:
            return "experience"

        # Default for date-containing blocks: short → education, long → experience
        if len(lines) <= 4:
            return "education"
        return "experience"

    # 4) Contact block — emails, phones, urls (after date check)
    contact_signals = 0
    has_phone = False
    for line in lines:
        if _EMAIL_RE.search(line):
            contact_signals += 1
        if _PHONE_RE.search(line):
            contact_signals += 1
            has_phone = True
        url_match = _URL_RE.search(line)
        if url_match and not _EDUCATION_KEYWORDS.search(line):
            url_text = url_match.group(0).lower()
            if any(k in url_text for k in ("linkedin", "github", "http", "/")):
                contact_signals += 1
    if not has_education_signal:
        if (has_email or has_phone) and contact_signals >= 1:
            return "contact"
        if contact_signals >= 2:
            return "contact"

    # 5) Certifications (no dates needed)
    if _CERT_KEYWORDS.search(text):
        return "certifications"

    # 5b) Short block where most lines mention cert providers → certifications
    if len(lines) <= 5:
        delimiter_count_early = sum(len(_SKILL_DELIMITER_RE.findall(l)) for l in lines)
        provider_lines = sum(1 for l in lines if _CERT_PROVIDER_RE.search(l))
        if (provider_lines >= len(lines) * 0.5 and provider_lines >= 1
                and not has_education_signal and delimiter_count_early < 3):
            return "certifications"

    # 6) Projects: url/github + tech names, or action verbs + tech + url
    has_proj_signal = bool(_PROJECT_KEYWORDS.search(text))
    if has_proj_signal and (has_tech or bullet_count >= 1 or len(lines) >= 3):
        return "projects"
    if has_tech and has_url_any and bullet_count >= 1:
        return "projects"

    # 7) Languages
    lang_matches = len(_LANGUAGE_KEYWORDS.findall(text))
    if lang_matches >= 2 and len(lines) <= 8:
        return "languages"
    if lang_matches >= 1 and len(lines) <= 3 and not has_tech:
        return "languages"

    # 8) Skills — short items, comma/bullet separated
    delimiter_count = sum(len(_SKILL_DELIMITER_RE.findall(line)) for line in lines)
    avg_words = sum(len(line.split()) for line in lines) / max(len(lines), 1)
    has_colon = any(":" in line for line in lines)
    has_date_signal = bool(_DATE_RANGE_RE.search(text)) or len(_SINGLE_YEAR_RE.findall(text)) >= 2

    skills_blocked = has_education_signal or has_proj_signal or has_date_signal

    # Experience with bullets takes priority over skills when lines are long
    if bullet_count >= 3 and avg_words >= 5:
        return "experience"

    if not skills_blocked:
        if has_colon and delimiter_count >= 2:
            return "skills"
        if delimiter_count >= 3 and avg_words <= 8:
            return "skills"
        if len(lines) <= 4 and delimiter_count >= 2 and avg_words <= 6:
            return "skills"
        # Bullet list of short items → skills
        if bullet_count >= 2 and avg_words <= 5:
            return "skills"

    # URL-heavy blocks without other signals → misc
    if has_url_any and not has_education_signal and not has_proj_signal:
        return "other"

    # 9) Summary — longer prose block with few bullets
    total_chars = sum(len(line) for line in lines)
    if total_chars > 80 and bullet_count <= 1 and avg_words > 5:
        return "summary"

    # 10) Experience with bullets (no dates, but bullet-heavy)
    if bullet_count >= 3:
        return "experience"

    # 11) Very short block at start → could be header/contact
    if len(lines) <= 2 and total_chars < 80:
        if _EDUCATION_KEYWORDS.search(text) or re.search(r"\bgpa|cgpa\b", text, re.I):
            return "education"
        if re.search(r"\b\d\.\d{1,2}\s*/\s*[45]\.\d{1,2}\b", text):
            return "education"
        return "header"

    # 11b) Short block with GPA or education keywords
    if len(lines) <= 4 and total_chars < 200:
        if re.search(r"\bgpa|cgpa\b", text, re.I):
            return "education"
        if _EDUCATION_KEYWORDS.search(text):
            return "education"

    # 12) Headerless fallbacks — misc must be last
    if _detect_headerless_interests(lines, text, has_tech, has_url_any):
        return "interests"
    if _detect_headerless_project(lines, text, text_raw, has_tech, has_url_any, bullet_count):
        return "projects"
    if _detect_headerless_education(lines, text):
        return "education"
    if _detect_headerless_skills(lines, text, has_tech):
        return "skills"

    # 13) Section scorer as last resort before other
    _fb = _scorer_fallback(text_raw)
    if _fb:
        return _fb

    return "other"


# ── validation layer ──────────────────────────────────────────────────────

def _validate_section(
    label: str, *, lines: List[str], text: str, text_raw: str,
    has_header: bool = False,
) -> str:
    """Validate that a content-based section label has sufficient signals.

    When *has_header* is True the block had an explicit section header;
    validation is relaxed (one signal is enough) but never skipped entirely
    for safety.  Without a header, multiple signals are required.

    Returns *label* when confident, or ``"other"`` when validation fails.
    """
    # Labels that don't need validation
    if label in ("other", "header", "noise", "summary", "certifications", "interests"):
        return label

    has_dates = bool(_DATE_RANGE_RE.search(text)) or bool(_OPEN_DATE_RE.search(text))
    has_years = len(_SINGLE_YEAR_RE.findall(text)) >= 2
    has_date_signal = has_dates or has_years
    bullet_count = sum(1 for line in lines if _BULLET_RE.match(line))
    has_email = bool(_EMAIL_RE.search(text_raw))
    has_phone = bool(_PHONE_RE.search(text_raw))
    has_url = bool(
        re.search(r"https?://|github\.com|gitlab\.com|linkedin\.com", text_raw, re.I)
    )
    has_tech = bool(_TECH_NAMES_RE.search(text))
    avg_words = sum(len(line.split()) for line in lines) / max(len(lines), 1)

    if label == "education":
        has_institution = bool(_EDUCATION_KEYWORDS.search(text))
        has_degree = bool(re.search(
            r"\b(?:b\.?s\.?c?|m\.?s\.?c?|b\.?a|m\.?a|ph\.?d|m\.?b\.?a"
            r"|bachelor|master|diploma|associate|degree)\b",
            text, re.I,
        ))
        has_gpa = bool(re.search(r"\bgpa|cgpa\b", text, re.I))
        has_cap_phrase = bool(_CAPITALIZED_PHRASE_RE.search(text_raw))
        if has_header:
            # Header present → one supporting signal is enough
            if not any([has_date_signal, has_institution, has_degree,
                        has_gpa, has_cap_phrase]):
                return "other"
        else:
            # No header → need ≥2 corroborating signals
            signals = sum([has_date_signal, has_institution, has_degree,
                           has_gpa, has_cap_phrase])
            if signals < 2:
                return "other"

    elif label == "experience":
        # Guard: degree + institution + no bullets → this is education, not experience
        has_degree_v = bool(re.search(
            r"\b(?:b\.?s\.?c?|m\.?s\.?c?|b\.?a|m\.?a|ph\.?d|m\.?b\.?a"
            r"|bachelor|master|diploma|associate|degree)\b",
            text, re.I,
        ))
        has_institution_v = bool(_EDUCATION_KEYWORDS.search(text))
        if has_degree_v and has_institution_v and bullet_count <= 1:
            return "education"

        if has_header:
            # Header present → date OR bullets is enough
            if not has_date_signal and bullet_count == 0:
                return "other"
        else:
            # No header: dates need multiline/bullets, no dates need ≥3 bullets
            if has_date_signal:
                if len(lines) < 3 and bullet_count == 0:
                    return "other"
            else:
                if bullet_count < 3:
                    return "other"

    elif label == "projects":
        has_proj_signal = has_url or has_tech or bool(_PROJECT_KEYWORDS.search(text))
        has_content = bullet_count >= 1 or len(lines) >= 2
        if has_header:
            if not has_proj_signal and not has_content:
                return "other"
        else:
            if not has_proj_signal or not has_content:
                return "other"

    elif label == "skills":
        # Block dates and urls — but allow long comma-separated lines
        if has_date_signal or has_url:
            return "other"
        # A line with commas is a skill list even if word count is high
        has_comma_list = any(
            len(_SKILL_DELIMITER_RE.findall(line)) >= 2 for line in lines
        )
        if not has_comma_list:
            has_long_sentence = any(len(line.split()) > 12 for line in lines)
            if has_long_sentence:
                return "other"
            if avg_words > 10:
                return "other"

    elif label == "languages":
        lang_matches = len(_LANGUAGE_KEYWORDS.findall(text))
        if len(lines) > 8:
            return "other"
        # With header: short block is enough, no CEFR required
        if not has_header and lang_matches < 1:
            return "other"

    elif label == "contact":
        if not (has_email or has_phone or has_url):
            return "other"

    return label


# ── Confidence scoring ────────────────────────────────────────────────────

# Base confidence thresholds — per layout_type from layout_analyzer.
_CONFIDENCE_THRESHOLDS: dict[str, float] = {
    "default": 0.40,
    "sidebar": 0.35,
    "academic": 0.45,
    "developer": 0.35,
    "skills_heavy": 0.30,
    "no_header": 0.40,
    "ats_clean": 0.40,
}

_W_HEADER   = 0.35
_W_DATE     = 0.15
_W_KEYWORDS = 0.20
_W_BULLETS  = 0.10
_W_URL      = 0.05
_W_LENGTH   = 0.15


def _compute_confidence(
    label: str, *, lines: List[str], text: str, text_raw: str,
    has_header: bool = False,
) -> float:
    """Compute confidence score (0.0–1.0) for a section classification.

    Uses six signals: header, date, keywords, bullets, url, length.
    Each signal contributes a weighted score based on whether it supports
    the given label.
    """
    if label in ("other", "header", "noise"):
        return 0.0

    score = 0.0

    # ── Signal extraction ──
    has_dates = bool(_DATE_RANGE_RE.search(text)) or bool(_OPEN_DATE_RE.search(text))
    has_years = len(_SINGLE_YEAR_RE.findall(text)) >= 2
    has_date_signal = has_dates or has_years
    bullet_count = sum(1 for ln in lines if _BULLET_RE.match(ln))
    has_email = bool(_EMAIL_RE.search(text_raw))
    has_phone = bool(_PHONE_RE.search(text_raw))
    has_url = bool(
        re.search(r"https?://|github\.com|gitlab\.com|linkedin\.com", text_raw, re.I)
    )
    has_tech = bool(_TECH_NAMES_RE.search(text))
    avg_words = sum(len(ln.split()) for ln in lines) / max(len(lines), 1)
    n_lines = len(lines)
    delimiter_count = sum(len(_SKILL_DELIMITER_RE.findall(ln)) for ln in lines)

    # ── header signal ──
    if has_header:
        score += _W_HEADER

    # ── Per-section signal evaluation ──
    if label == "education":
        if has_date_signal:
            score += _W_DATE
        has_edu_kw = bool(_EDUCATION_KEYWORDS.search(text))
        has_degree = bool(re.search(
            r"\b(?:b\.?s\.?c?|m\.?s\.?c?|b\.?a|m\.?a|ph\.?d|m\.?b\.?a"
            r"|bachelor|master|diploma|associate|degree)\b", text, re.I,
        ))
        has_gpa = bool(re.search(r"\bgpa|cgpa\b", text, re.I))
        if has_edu_kw or has_degree or has_gpa:
            score += _W_KEYWORDS
        if bullet_count <= 2:
            score += _W_BULLETS
        if not has_url and not has_email:
            score += _W_URL
        if n_lines <= 6:
            score += _W_LENGTH

    elif label == "experience":
        if has_date_signal:
            score += _W_DATE
        has_exp_kw = bool(_EXPERIENCE_KEYWORDS.search(text))
        if has_exp_kw or bullet_count >= 1:
            score += _W_KEYWORDS
        if bullet_count >= 2:
            score += _W_BULLETS
        if not has_url:
            score += _W_URL
        if n_lines >= 3:
            score += _W_LENGTH

    elif label == "skills":
        if not has_date_signal:
            score += _W_DATE
        if has_tech or delimiter_count >= 2:
            score += _W_KEYWORDS
        if avg_words <= 6:
            score += _W_BULLETS
        if not has_url:
            score += _W_URL
        if n_lines <= 8 and avg_words <= 8:
            score += _W_LENGTH

    elif label == "projects":
        score += _W_DATE * 0.5
        if has_tech or bool(_PROJECT_KEYWORDS.search(text)):
            score += _W_KEYWORDS
        if bullet_count >= 1:
            score += _W_BULLETS
        if has_url:
            score += _W_URL
        if n_lines >= 2:
            score += _W_LENGTH

    elif label == "languages":
        if not has_date_signal:
            score += _W_DATE
        lang_matches = len(_LANGUAGE_KEYWORDS.findall(text))
        if lang_matches >= 1:
            score += _W_KEYWORDS
        if bullet_count <= 2:
            score += _W_BULLETS
        if not has_url:
            score += _W_URL
        if n_lines <= 5:
            score += _W_LENGTH

    elif label == "contact":
        if not has_date_signal:
            score += _W_DATE
        contact_signals = sum([has_email, has_phone, has_url])
        if contact_signals >= 1:
            score += _W_KEYWORDS
        if contact_signals >= 2:
            score += _W_URL
        if bullet_count == 0:
            score += _W_BULLETS
        if n_lines <= 5:
            score += _W_LENGTH

    elif label == "certifications":
        score += _W_DATE * 0.5
        if _CERT_KEYWORDS.search(text):
            score += _W_KEYWORDS
        if bullet_count <= 2:
            score += _W_BULLETS
        score += _W_URL * 0.5
        if n_lines <= 8:
            score += _W_LENGTH

    elif label == "summary":
        if not has_date_signal:
            score += _W_DATE
        total_chars = sum(len(ln) for ln in lines)
        if total_chars > 80:
            score += _W_KEYWORDS
        if bullet_count <= 1:
            score += _W_BULLETS
        if not has_url:
            score += _W_URL
        if avg_words > 5:
            score += _W_LENGTH

    elif label == "interests":
        if not has_date_signal:
            score += _W_DATE
        score += _W_KEYWORDS * 0.5
        if n_lines <= 5:
            score += _W_LENGTH
        score += _W_URL * 0.5
        score += _W_BULLETS * 0.5

    return min(score, 1.0)


# ── Multi-section scoring ─────────────────────────────────────────────────────

_SCORED_SECTIONS = [
    "education", "experience", "projects", "skills",
    "languages", "contact", "summary", "certifications", "interests",
]

_CLOSE_MARGIN = 0.10


def _score_all_sections(
    *, lines: List[str], text: str, text_raw: str, has_header: bool = False,
) -> Dict[str, float]:
    """Score a block against every candidate section.

    Extracts signals once, then evaluates each section.
    Returns section name → score (0.0–1.0).
    """
    scores: Dict[str, float] = {}

    # ── shared signal extraction ──
    has_dates = bool(_DATE_RANGE_RE.search(text)) or bool(_OPEN_DATE_RE.search(text))
    has_years = len(_SINGLE_YEAR_RE.findall(text)) >= 2
    has_date_signal = has_dates or has_years
    bullet_count = sum(1 for ln in lines if _BULLET_RE.match(ln))
    has_email = bool(_EMAIL_RE.search(text_raw))
    has_phone = bool(_PHONE_RE.search(text_raw))
    has_url = bool(
        re.search(r"https?://|github\.com|gitlab\.com|linkedin\.com", text_raw, re.I)
    )
    has_tech = bool(_TECH_NAMES_RE.search(text))
    avg_words = sum(len(ln.split()) for ln in lines) / max(len(lines), 1)
    n_lines = len(lines)
    delimiter_count = sum(len(_SKILL_DELIMITER_RE.findall(ln)) for ln in lines)
    total_chars = sum(len(ln) for ln in lines)
    lang_matches = len(_LANGUAGE_KEYWORDS.findall(text))
    has_edu_kw = bool(_EDUCATION_KEYWORDS.search(text))
    has_degree = bool(re.search(
        r"\b(?:b\.?s\.?c?|m\.?s\.?c?|b\.?a|m\.?a|ph\.?d|m\.?b\.?a"
        r"|bachelor|master|diploma|associate|degree)\b", text, re.I,
    ))
    has_gpa = bool(re.search(r"\bgpa|cgpa\b", text, re.I))
    has_exp_kw = bool(_EXPERIENCE_KEYWORDS.search(text))
    has_cert_kw = bool(_CERT_KEYWORDS.search(text))
    has_proj_kw = bool(_PROJECT_KEYWORDS.search(text))
    contact_signals = sum([has_email, has_phone, has_url])

    hdr = _W_HEADER if has_header else 0.0

    # ── education ──
    s = hdr
    if has_date_signal:
        s += _W_DATE
    if has_edu_kw or has_degree or has_gpa:
        s += _W_KEYWORDS
    if bullet_count <= 2:
        s += _W_BULLETS
    if not has_url and not has_email:
        s += _W_URL
    if n_lines <= 6:
        s += _W_LENGTH
    scores["education"] = min(s, 1.0)

    # ── experience ──
    s = hdr
    if has_date_signal:
        s += _W_DATE
    if has_exp_kw or bullet_count >= 1:
        s += _W_KEYWORDS
    if bullet_count >= 2:
        s += _W_BULLETS
    if not has_url:
        s += _W_URL
    if n_lines >= 3:
        s += _W_LENGTH
    scores["experience"] = min(s, 1.0)

    # ── projects ──
    s = hdr + _W_DATE * 0.5
    if has_tech or has_proj_kw:
        s += _W_KEYWORDS
    if bullet_count >= 1:
        s += _W_BULLETS
    if has_url:
        s += _W_URL
    if n_lines >= 2:
        s += _W_LENGTH
    scores["projects"] = min(s, 1.0)

    # ── skills ──
    s = hdr
    if not has_date_signal:
        s += _W_DATE
    if has_tech or delimiter_count >= 2:
        s += _W_KEYWORDS
    if avg_words <= 6:
        s += _W_BULLETS
    if not has_url:
        s += _W_URL
    if n_lines <= 8 and avg_words <= 8:
        s += _W_LENGTH
    scores["skills"] = min(s, 1.0)

    # ── languages ──
    s = hdr
    if not has_date_signal:
        s += _W_DATE
    if lang_matches >= 1:
        s += _W_KEYWORDS
    if bullet_count <= 2:
        s += _W_BULLETS
    if not has_url:
        s += _W_URL
    if n_lines <= 5:
        s += _W_LENGTH
    scores["languages"] = min(s, 1.0)

    # ── contact ──
    s = hdr
    if not has_date_signal:
        s += _W_DATE
    if contact_signals >= 1:
        s += _W_KEYWORDS
    if contact_signals >= 2:
        s += _W_URL
    if bullet_count == 0:
        s += _W_BULLETS
    if n_lines <= 5:
        s += _W_LENGTH
    scores["contact"] = min(s, 1.0)

    # ── summary ──
    s = hdr
    if not has_date_signal:
        s += _W_DATE
    if total_chars > 80:
        s += _W_KEYWORDS
    if bullet_count <= 1:
        s += _W_BULLETS
    if not has_url:
        s += _W_URL
    if avg_words > 5:
        s += _W_LENGTH
    scores["summary"] = min(s, 1.0)

    # ── certifications ──
    s = hdr + _W_DATE * 0.5
    if has_cert_kw:
        s += _W_KEYWORDS
    if bullet_count <= 2:
        s += _W_BULLETS
    s += _W_URL * 0.5
    if n_lines <= 8:
        s += _W_LENGTH
    scores["certifications"] = min(s, 1.0)

    # ── interests ──
    s = hdr
    if not has_date_signal:
        s += _W_DATE
    s += _W_KEYWORDS * 0.5
    if n_lines <= 5:
        s += _W_LENGTH
    s += _W_URL * 0.5
    s += _W_BULLETS * 0.5
    scores["interests"] = min(s, 1.0)

    return scores


def _pick_best_section(
    scores: Dict[str, float],
    active_section: str | None,
    initial_label: str | None = None,
    proximity: int | None = None,
) -> tuple[str, float]:
    """Pick the highest-scoring section.

    * If *initial_label* (from classify_block) scored within *_CLOSE_MARGIN*
      of the top scorer, prefer it — it already passed content heuristics.
    * If *active_section* scored within margin of the top scorer,
      prefer it for continuity.  When *proximity* is 1 (block immediately
      follows a header), use a wider margin so the header context wins
      over ambiguous content scores.
    """
    if not scores:
        return ("other", 0.0)

    best_label = max(scores, key=lambda k: scores[k])
    best_score = scores[best_label]

    # Prefer initial_label when it's competitive
    if (initial_label
            and initial_label in scores
            and best_score - scores[initial_label] <= _CLOSE_MARGIN):
        best_label = initial_label
        best_score = scores[initial_label]

    # Prefer active section for continuity when scores are close.
    # Use wider margin for blocks immediately adjacent to a header.
    margin = _CLOSE_MARGIN
    if proximity is not None and proximity <= 2:
        margin = 0.20
    if (active_section
            and active_section in scores
            and best_score - scores[active_section] <= margin):
        return (active_section, scores[active_section])

    return (best_label, best_score)


# ── header normalisation ──────────────────────────────────────────────────────

_MERGED_SPLIT_RE = re.compile(r'(?<=[a-z])(?=[A-Z])')

# Known section words used to split merged all-caps headers
_KNOWN_WORDS = sorted([
    "EXPERIENCE", "EDUCATION", "SKILLS", "PROJECTS", "CERTIFICATIONS",
    "LANGUAGES", "SUMMARY", "PROFILE", "OBJECTIVE", "EMPLOYMENT",
    "QUALIFICATIONS", "COMPETENCIES", "TECHNOLOGIES", "CERTIFICATES",
    "COMMUNICATION", "PROFESSIONAL", "TECHNICAL", "PERSONAL", "ACADEMIC",
    "INTEREST", "INTERESTS", "HOBBIES", "REFERENCES", "CONTACT",
    "VOLUNTEER", "AWARDS", "ACHIEVEMENTS", "ACTIVITIES", "PUBLICATIONS",
    "ABOUT", "WORK",
], key=len, reverse=True)  # longest first for greedy match


def _try_split_merged_line(line: str) -> list[str]:
    """If *line* is a merged all-caps or CamelCase header, return individual parts.

    Returns a list with >1 elements only when multiple known section words
    are found and each part is itself a recognisable header.
    """
    stripped = line.strip()
    # Must have no spaces and be long enough to contain 2 headers
    if ' ' in stripped or len(stripped) < 10:
        return [line]
    # All-caps: try known-word split
    if stripped == stripped.upper():
        parts = []
        remaining = stripped
        while remaining:
            matched = False
            for word in _KNOWN_WORDS:
                if remaining.upper().startswith(word):
                    parts.append(remaining[:len(word)])
                    remaining = remaining[len(word):]
                    matched = True
                    break
            if not matched:
                break
        if len(parts) > 1 and not remaining:
            return parts
    # Mixed case: split on case transitions
    else:
        parts = _MERGED_SPLIT_RE.split(stripped)
        if len(parts) > 1 and all(_sniff_header(p) for p in parts):
            return parts
    return [line]


def _split_merged_allcaps(text: str) -> str:
    """Try to split an all-caps merged string using known section words."""
    remaining = text
    parts: list[str] = []
    while remaining:
        matched = False
        for word in _KNOWN_WORDS:
            if remaining.upper().startswith(word):
                parts.append(remaining[:len(word)])
                remaining = remaining[len(word):]
                matched = True
                break
        if not matched:
            parts.append(remaining)
            break
    return ' '.join(parts) if len(parts) > 1 else text


def _normalize_header(raw: str) -> str:
    """Clean a raw header string for display.

    * strip whitespace
    * remove trailing colon / colon-space
    * split merged CamelCase/UPPERCASEUPPERCASE words
    * preserve original case
    """
    t = raw.strip()
    # remove trailing colon (possibly with space before it)
    t = re.sub(r'\s*:\s*$', '', t)
    # split merged uppercase words: "EDUCATIONCOMMUNICATION" → "EDUCATION COMMUNICATION"
    if ' ' not in t and len(t) > 14 and t == t.upper():
        t = _split_merged_allcaps(t)
    # split mixed case merged words: "EducationCommunication"
    elif ' ' not in t and len(t) > 14:
        t = _MERGED_SPLIT_RE.sub(' ', t)
    return t


# ── main entry point ──────────────────────────────────────────────────────

_SAFE_MODE = os.getenv("SAFE_MODE", "").lower() in ("1", "true", "yes")
_MAX_INPUT_CHARS = 50_000 if _SAFE_MODE else 100_000
_MAX_INPUT_LINES = 500 if _SAFE_MODE else 1_000
_MAX_BLOCKS = 1_000 if _SAFE_MODE else 2_000
_MAX_WORDS_PER_LINE = 200       # truncate absurdly long lines
_MAX_REGEX_INPUT = 10_000      # max chars fed to any single regex call
_MAX_SECTIONS = 20             # max distinct section keys in output


def detect_sections(
    text: str,
    *,
    layout_type: str = "default",
) -> tuple[Dict[str, List[str]], Dict[str, str], Dict[str, str]]:
    """Parse CV text into canonical sections using block-based classification.

    Parameters
    ----------
    text : str
        Raw (linearized) CV text.
    layout_type : str
        Structural layout hint from ``layout_analyzer``.  Forwarded to
        ``classify_block`` so it can adjust confidence.

    Returns a tuple of:
        sections: dict like {"experience": [...], "education": [...], ...}
        section_headers: dict like {"experience": "DENEYİM", "education": "EĞİTİM", ...}
        section_sources: dict like {"experience": "header", "skills": "score", ...}
            Records how each section was established:
            "header"   – explicit section header in the CV
            "score"    – multi-section scoring picked this section
            "fallback" – inherited from nearby header or scorer fallback

    The section_headers dict preserves original header text from the CV so
    the renderer can use it directly (language-independent).

    Blocks classified as "noise" are silently dropped.
    Blocks classified as "other" are appended to "header".
    """
    _t0 = time.perf_counter()
    # Performance guard: truncate oversized input
    if len(text) > _MAX_INPUT_CHARS:
        text = text[:_MAX_INPUT_CHARS]
    lines_list = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(lines_list) > _MAX_INPUT_LINES:
        lines_list = lines_list[:_MAX_INPUT_LINES]
        text = "\n".join(lines_list)

    blocks = split_blocks(text)
    blocks = split_entries_inside_block(blocks)
    if len(blocks) > _MAX_BLOCKS:
        blocks = blocks[:_MAX_BLOCKS]
    # Truncate absurdly long lines inside blocks
    for _blk in blocks:
        for _i, _ln in enumerate(_blk):
            _words = _ln.split()
            if len(_words) > _MAX_WORDS_PER_LINE:
                _blk[_i] = " ".join(_words[:_MAX_WORDS_PER_LINE])
    sections: Dict[str, List[str]] = {}
    section_headers: Dict[str, str] = {}
    section_sources: Dict[str, str] = {}  # key → "header" | "score" | "fallback"

    # Map non-canonical labels to canonical section names
    _LABEL_ALIASES: Dict[str, str] = {
        "profile": "summary", "about": "summary", "about me": "summary",
        "objective": "summary", "personal": "summary", "introduction": "summary",
        "personal statement": "summary", "personal profile": "summary",
        "professional summary": "summary", "executive summary": "summary",
        "executive profile": "summary", "career summary": "summary", "career objective": "summary",
        "personal information": "summary",
        "work": "experience", "employment": "experience", "work experience": "experience",
        "professional experience": "experience", "career history": "experience",
        "work history": "experience", "work background": "experience",
        "employment history": "experience", "training": "experience", "trainings": "experience",
        "academic": "education", "academics": "education", "qualifications": "education",
        "academic qualifications": "education", "educational background": "education",
        "technical skills": "skills", "core competencies": "skills", "skill set": "skills", "skills set": "skills",
        "competencies": "skills", "technologies": "skills",
        "project": "projects",
        "certification": "certifications", "certificates": "certifications",
        "certificate": "certifications", "licenses": "certifications",
        "language": "languages",
        "communication": "contact", "contact information": "contact",
        "interest": "interests", "interests": "interests",
        "personal interest": "interests", "personal interests": "interests",
        "hobbies": "interests",
        "volunteer": "misc", "awards": "misc", "achievements": "misc",
        "publications": "misc", "activities": "misc",
        "other activities": "misc", "other": "misc",
    }

    # Pre-process: tag each block with its header hint and content lines
    tagged: list[tuple[str, str | None, list[str], list[str]]] = []
    for block in blocks:
        label = classify_block(block, layout_type=layout_type)
        if label == "noise":
            continue
        header_hint = _sniff_header(block[0]) if block else None
        content_lines = block[1:] if header_hint else block

        # Validate classifications.  Blocks with an explicit canonical
        # header get relaxed validation (has_header=True); blocks with
        # no header get strict multi-signal validation.
        if label not in ("noise", "header", "other"):
            has_hdr = header_hint is not None and (
                header_hint in _CANONICAL_KEYS or header_hint == "noise"
            )
            v_lines = content_lines or block
            v_text = " ".join(v_lines).lower()
            v_text_raw = " ".join(v_lines)
            label = _validate_section(
                label, lines=v_lines, text=v_text, text_raw=v_text_raw,
                has_header=has_hdr,
            )

        tagged.append((label, header_hint, content_lines, block))

    # ── Slow-CV guard: check elapsed time after classification ──
    _elapsed_classify = time.perf_counter() - _t0
    if _elapsed_classify > _CLASSIFIER_TIMEOUT_SECONDS:
        logger.warning(
            "detect_sections TIMEOUT: classification took %.2fs (limit %.1fs), "
            "returning partial results from %d tagged blocks",
            _elapsed_classify, _CLASSIFIER_TIMEOUT_SECONDS, len(tagged),
        )
        # Build sections from what we have so far and return early
        for _label, _hdr, _clines, _blk in tagged:
            _label = _LABEL_ALIASES.get(_label, _label)
            _label = canonicalize_section_key(_label)
            sections.setdefault(_label, [])
            sections[_label].extend(_clines)
        return sections, section_headers, section_sources
    if _elapsed_classify > _CLASSIFIER_WARN_SECONDS:
        logger.warning(
            "detect_sections SLOW: classification took %.2fs (warn threshold %.1fs)",
            _elapsed_classify, _CLASSIFIER_WARN_SECONDS,
        )

    # Layout-dependent confidence threshold
    _conf_threshold = _CONFIDENCE_THRESHOLDS.get(layout_type, 0.40)

    active_section = None  # last section established by a header
    active_section_idx = -1  # block index where active_section was set

    for i, (label, header_hint, content_lines, block) in enumerate(tagged):
        # Skip header-only blocks (no real content after the header line)
        # that appear in runs — typical of sidebar layout labels.
        has_content = any(line.strip() for line in content_lines)
        if header_hint and not has_content:
            # Check if next block is also a bare header
            next_is_header = (
                i + 1 < len(tagged)
                and tagged[i + 1][1] is not None
                and not any(l.strip() for l in tagged[i + 1][2])
            )
            # Or previous block was a bare header
            prev_is_header = (
                i > 0
                and tagged[i - 1][1] is not None
                and not any(l.strip() for l in tagged[i - 1][2])
            )
            if next_is_header or prev_is_header:
                continue  # sidebar label — skip entirely

        # Resolve label to canonical name
        label = _LABEL_ALIASES.get(label, label)
        label = canonicalize_section_key(label)
        if header_hint:
            header_hint = _LABEL_ALIASES.get(header_hint, header_hint)
            header_hint = canonicalize_section_key(header_hint)

        # Store header text under canonical key (label), not raw header text
        header_key = header_hint if header_hint in _CANONICAL_KEYS else label
        if header_hint and header_key not in section_headers:
            section_headers[header_key] = _normalize_header(block[0])

        # ── Multi-section scoring ──
        c_lines = content_lines or block
        c_text = " ".join(c_lines).lower()
        c_text_raw = " ".join(c_lines)
        has_hdr_flag = header_hint is not None and (
            header_hint in _CANONICAL_KEYS or header_hint == "noise"
        )

        if header_hint:
            # Header blocks definitively establish the section.
            # Use header_hint (not label) so validation downgrades don't
            # poison the active section for following blocks.
            active_section = header_hint if header_hint in _CANONICAL_KEYS else label
            label = active_section
            active_section_idx = i
            _source = "header"
        else:
            # No header: score all candidate sections and pick best
            all_scores = _score_all_sections(
                lines=c_lines, text=c_text, text_raw=c_text_raw,
                has_header=has_hdr_flag,
            )
            nearby_active = (
                active_section
                if active_section and (i - active_section_idx) <= 5
                else None
            )
            # Pass proximity so _pick_best_section can use a wider
            # margin for blocks right next to their section header.
            proximity = (i - active_section_idx) if active_section else None
            scored_label, scored_score = _pick_best_section(
                all_scores, nearby_active, initial_label=label,
                proximity=proximity,
            )
            if scored_score >= _conf_threshold:
                label = scored_label
                _source = "score"
            elif nearby_active:
                label = nearby_active
                _source = "fallback"
            else:
                _source = "fallback"

        # "other" and "header" go to header bucket only when no active section
        # or when active section is far away.
        if label in ("other", "header"):
            # Try section scorer on content-only text (headerless blocks only;
            # blocks with an explicit header already have a trusted active_section).
            if not header_hint:
                _fb = _scorer_fallback(c_text_raw)
                if _fb:
                    label = _fb
                    _source = "fallback"
            if label in ("other", "header"):
                if active_section and (i - active_section_idx) <= 5:
                    label = active_section
                    _source = "fallback"
                else:
                    label = "header"

        # ── Orphan block detection ──
        # Block far from any section header with real prose → summary
        if label == "header":
            orphan_chars = sum(len(ln) for ln in c_lines)
            orphan_words = sum(len(ln.split()) for ln in c_lines)
            if orphan_chars >= 40 and orphan_words >= 8:
                label = "summary"
                _source = "fallback"

        # Record strongest source for this section key
        # Priority: header > score > fallback
        _SOURCE_RANK = {"header": 3, "score": 2, "fallback": 1}
        if label not in ("other", "header", "noise"):
            existing_source = section_sources.get(label)
            if (existing_source is None
                    or _SOURCE_RANK.get(_source, 0) > _SOURCE_RANK.get(existing_source, 0)):
                section_sources[label] = _source

        sections.setdefault(label, [])
        sections[label].extend(content_lines)

    _elapsed = time.perf_counter() - _t0
    logger.info(
        "detect_sections: %.3fs | blocks=%d | sections=%s",
        _elapsed,
        len(blocks),
        {k: len(v) for k, v in sections.items()},
    )
    _structured_log(
        logger, logging.INFO, "detect_sections",
        latency=round(_elapsed, 3),
        blocks=len(blocks),
        sections={k: len(v) for k, v in sections.items()},
        version=PARSER_VERSION,
    )

    # ── Security: cap distinct section count ──
    if len(sections) > _MAX_SECTIONS:
        logger.warning("detect_sections: section count capped %d → %d",
                       len(sections), _MAX_SECTIONS)
        # Keep sections with most lines; drop smallest
        sorted_keys = sorted(sections.keys(), key=lambda k: len(sections[k]), reverse=True)
        for extra_key in sorted_keys[_MAX_SECTIONS:]:
            sections.pop(extra_key, None)
            section_headers.pop(extra_key, None)
            section_sources.pop(extra_key, None)

    return sections, section_headers, section_sources


# ── Parser version registry ───────────────────────────────────────────────
# Maps version tags to parser functions.  ``get_parser()`` returns the
# active implementation selected by ``PARSER_VERSION`` env var.

def _detect_sections_v1(
    text: str,
    *,
    layout_type: str = "default",
) -> tuple[Dict[str, List[str]], Dict[str, str], Dict[str, str]]:
    """Alias for the current production classifier (v1)."""
    return detect_sections(text, layout_type=layout_type)


# Placeholder for future parser versions.
# To add v2: implement ``_detect_sections_v2`` with the same signature and
# register it below.  Then set ``PARSER_VERSION=v2`` in env.

_PARSER_REGISTRY: Dict[str, Callable] = {
    "v1": _detect_sections_v1,
    # "v2": _detect_sections_v2,
    # "experimental": _detect_sections_experimental,
}


# ── Canary / gradual rollout ──────────────────────────────────────────────
# PARSER_CANARY_VERSION: parser version to canary (e.g. "v2")
# PARSER_CANARY_PERCENT: percentage of requests routed to canary (0-100)
# NOTE: random.randint is seeded per-process.  In a multi-worker cluster
# each worker independently decides canary routing.  Over many requests
# the aggregate ratio converges to the configured percentage.
_CANARY_VERSION = os.getenv("PARSER_CANARY_VERSION", "").strip().lower()
_CANARY_PERCENT = max(0, min(100, int(os.getenv("PARSER_CANARY_PERCENT", "0") or "0")))


def get_parser():
    """Return the parser function for the configured ``PARSER_VERSION``.

    When canary rollout is configured (``PARSER_CANARY_VERSION`` +
    ``PARSER_CANARY_PERCENT``), a percentage of calls are routed to the
    canary version while the rest use the primary ``PARSER_VERSION``.

    Falls back to v1 if the requested version is unknown.
    """
    # Canary check
    if _CANARY_VERSION and _CANARY_PERCENT > 0:
        if random.randint(1, 100) <= _CANARY_PERCENT:
            canary_fn = _PARSER_REGISTRY.get(_CANARY_VERSION)
            if canary_fn is not None:
                logger.info(
                    "Canary routing: using %s (%d%% rollout)",
                    _CANARY_VERSION, _CANARY_PERCENT,
                )
                return canary_fn
            logger.warning(
                "Canary version %r not in registry, falling back to primary",
                _CANARY_VERSION,
            )

    fn = _PARSER_REGISTRY.get(PARSER_VERSION)
    if fn is None:
        logger.warning(
            "Unknown PARSER_VERSION=%r, falling back to v1", PARSER_VERSION,
        )
        fn = _PARSER_REGISTRY["v1"]
    return fn
