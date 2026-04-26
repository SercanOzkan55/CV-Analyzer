"""Global ATS Benchmark Service.

Maintains aggregate ATS score statistics globally and per profession.
Provides percentile calculations and comparison data without exposing
individual users.
"""

import logging
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from models import ATSBenchmarkGlobal, ATSBenchmarkProfession, ATSBenchmarkScore

logger = logging.getLogger(__name__)

# ── Profession Inference ────────────────────────────────────────

# Ordered list: first match wins.  Each entry is (canonical_key, patterns).
# Patterns support English and Turkish titles. Other languages are handled
# dynamically via _MULTILANG_DICTIONARY (see Phase 1b).
_PROFESSION_RULES: list[tuple[str, list[str]]] = [
    # ── Software / IT ───────────────────────────────────
    ("software_engineer", [
        r"software\s*engineer", r"yazılım\s*müh", r"full[- ]?stack", r"front[- ]?end",
        r"back[- ]?end", r"web\s*developer", r"web\s*geliştir",
        r"mobile\s*developer", r"mobil\s*geliştir",
        r"ios\s*developer", r"android\s*developer",
        r"devops", r"sre\b", r"site\s*reliability", r"platform\s*engineer",
        r"\bswe\b", r"software\s*developer", r"programmer", r"programcı",
        r"react\b.*developer", r"node\.?js", r"python\b.*developer",
        r"java\b.*developer", r"golang", r"\bdev\b", r"cloud\s*engineer",
        r"bilgisayar\s*müh", r"bilişim\s*müh", r"sistem\s*müh",
        r"information\s*tech", r"it\s*engineer", r"it\s*specialist",
        r"bilgi\s*teknoloj", r"siber\s*güvenlik", r"cyber\s*security",
        r"network\s*engineer", r"ağ\s*müh",
    ]),
    # ── Data / AI ───────────────────────────────────────
    ("data_scientist", [
        r"data\s*scien", r"veri\s*bilim", r"machine\s*learn", r"makine\s*öğren",
        r"\bml\s*engineer", r"\bai\s*engineer", r"yapay\s*zeka",
        r"deep\s*learn", r"derin\s*öğren", r"nlp\s*engineer",
        r"data\s*engineer", r"veri\s*müh", r"big\s*data", r"büyük\s*veri",
        r"data\s*analy", r"veri\s*anali", r"business\s*intellig",
        r"\bbi\s*analy", r"quantitative", r"research\s*scien",
        r"computer\s*vision", r"bilgisayarlı\s*görü",
    ]),
    # ── Mechanical Engineering ──────────────────────────
    ("mechanical_engineer", [
        r"mechanical\s*engineer", r"makine\s*müh", r"makina\s*müh",
        r"mekatronik", r"mechatronics", r"hvac\s*engineer",
        r"thermal\s*engineer", r"termal\s*müh", r"otomotiv\s*müh",
        r"automotive\s*engineer", r"manufacturing\s*engineer",
        r"üretim\s*müh", r"kalite\s*müh", r"quality\s*engineer",
        r"maintenance\s*engineer", r"bakım\s*müh",
    ]),
    # ── Civil Engineering ───────────────────────────────
    ("civil_engineer", [
        r"civil\s*engineer", r"inşaat\s*müh", r"insaat\s*m[uü]h",
        r"structural\s*engineer", r"yapı\s*müh",
        r"geotechni", r"jeoteknik", r"şantiye\s*şef",
        r"construction\s*manager", r"site\s*engineer",
        r"urban\s*plann", r"şehir\s*planc", r"harita\s*müh",
        r"surveying", r"çevre\s*müh", r"environmental\s*engineer",
    ]),
    # ── Electrical / Electronics ────────────────────────
    ("electrical_engineer", [
        r"electri\w*\s*engineer", r"elektrik\s*müh",
        r"elektron\w*\s*engineer", r"elektronik\s*müh",
        r"embedded\s*(?:systems?\s*)?engineer", r"gömülü\s*sistem",
        r"hardware\s*engineer", r"donanım\s*müh",
        r"power\s*engineer", r"enerji\s*müh",
        r"control\s*engineer", r"kontrol\s*müh",
        r"otomasyon\s*müh", r"automation\s*engineer",
        r"telecom", r"telekom\w*\s*müh",
        r"signal\s*process", r"sinyal\s*işleme",
    ]),
    # ── Industrial Engineering ──────────────────────────
    ("industrial_engineer", [
        r"industrial\s*engineer", r"endüstri\s*müh",
        r"operations\s*research", r"yöneylem",
        r"supply\s*chain", r"tedarik\s*zincir",
        r"logistics\s*engineer", r"lojistik\s*müh",
        r"process\s*engineer", r"süreç\s*müh",
        r"lean\s*engineer", r"six\s*sigma",
    ]),
    # ── Chemical Engineering ────────────────────────────
    ("chemical_engineer", [
        r"chemical\s*engineer", r"kimya\s*müh", r"kimyager",
        r"chemist\b", r"petrole?um\s*engineer", r"petrol\s*müh",
        r"polymer", r"polimer", r"biyokimya", r"biochemi",
        r"food\s*engineer", r"gıda\s*müh",
    ]),
    # ── Architecture ────────────────────────────────────
    ("architect", [
        r"\barchitect\b", r"\bmimar\b", r"mimarlık",
        r"interior\s*design", r"iç\s*mimar", r"peyzaj",
        r"landscape\s*arch", r"building\s*design",
    ]),
    # ── Design (UX/UI/Graphic) ──────────────────────────
    ("designer", [
        r"\bux\b", r"\bui\b", r"user\s*experience", r"user\s*interface",
        r"graphic\s*design", r"grafik\s*tasarım",
        r"product\s*design", r"ürün\s*tasarım",
        r"visual\s*design", r"görsel\s*tasarım",
        r"interaction\s*design", r"web\s*design",
        r"creative\s*direct", r"yaratıcı\s*yönet",
    ]),
    # ── Product / Project Management ────────────────────
    ("product_manager", [
        r"product\s*manager", r"ürün\s*yönet",
        r"product\s*owner", r"program\s*manager",
        r"project\s*manager", r"proje\s*yönet",
        r"scrum\s*master", r"agile\s*coach",
        r"technical\s*program", r"tpm\b",
    ]),
    # ── Marketing ───────────────────────────────────────
    ("marketing", [
        r"marketing", r"pazarlama", r"growth\s*hacker",
        r"seo\b", r"sem\b", r"content\s*strat", r"içerik\s*strat",
        r"social\s*media", r"sosyal\s*medya",
        r"brand\s*manager", r"marka\s*yönet",
        r"digital\s*market", r"dijital\s*pazarlama",
        r"copywriter", r"metin\s*yazar",
    ]),
    # ── Sales ───────────────────────────────────────────
    ("sales", [
        r"\bsales\b", r"\bsatış\b", r"account\s*exec",
        r"business\s*develop", r"iş\s*geliştir",
        r"\bbdr\b", r"\bsdr\b", r"customer\s*success",
        r"müşteri\s*başarı", r"relationship\s*manager",
    ]),
    # ── Management / Leadership ─────────────────────────
    ("manager", [
        r"engineering\s*manager", r"mühendislik\s*müdür",
        r"team\s*lead", r"takım\s*lid", r"tech\s*lead",
        r"\bcto\b", r"vp\s*of\s*engineer", r"director\s*of",
        r"müdür", r"head\s*of", r"chief", r"genel\s*müdür",
        r"c-level", r"executive", r"yönetici",
        r"\bceo\b", r"\bcfo\b", r"\bcoo\b", r"general\s*manager",
    ]),
    # ── Finance / Accounting ────────────────────────────
    ("accountant", [
        r"accountant", r"muhasebe", r"accounting", r"auditor", r"denetçi",
        r"bookkeeper", r"tax\s*specialist", r"vergi\s*uzman",
        r"financial\s*analyst", r"finans\s*analist",
        r"controller", r"treasury", r"hazine",
        r"\bcpa\b", r"\bsmmm\b", r"finance\s*manager",
        r"bankacı", r"banker", r"aktüer", r"actuary",
    ]),
    # ── Human Resources ─────────────────────────────────
    ("hr", [
        r"human\s*resource", r"insan\s*kaynak",
        r"\bhr\b.*(?:manager|specialist|partner|generalist|uzman)",
        r"talent\s*acqui", r"yetenek\s*kazanım",
        r"recruiter", r"işe\s*alım", r"people\s*ops",
        r"compensation", r"ücret\s*uzman",
    ]),
    # ── Healthcare ──────────────────────────────────────
    ("healthcare", [
        r"nurse", r"hemşire", r"physician", r"doktor", r"doctor",
        r"pharmacist", r"eczacı", r"therapist", r"terapist",
        r"surgeon", r"cerrah", r"dentist", r"diş\s*hek",
        r"medical", r"tıbbi", r"clinical", r"klinik",
        r"healthcare", r"sağlık", r"fizyoterap", r"physiotherap",
        r"laborat", r"biyomed", r"biomedic",
    ]),
    # ── Law ─────────────────────────────────────────────
    ("lawyer", [
        r"\blawyer\b", r"\bavukat\b", r"\battorney\b", r"\bjurist\b",
        r"hukuk\w*", r"legal\s*counsel", r"\bnoter\b", r"\bnotary\b",
        r"savcı", r"prosecutor", r"hakim\b", r"\bjudge\b",
    ]),
    # ── Education / Academia ────────────────────────────
    ("teacher", [
        r"\bteacher\b", r"öğretmen", r"\bprofessor\b", r"profesör",
        r"öğretim\s*üye", r"öğretim\s*görev",
        r"lecturer", r"akademisyen", r"academic",
        r"eğitmen", r"instructor", r"trainer",
        r"araştırma\s*görev", r"research\s*assist",
    ]),
    # ── Student / Entry-level ───────────────────────────
    ("student", [
        r"\bstudent\b", r"\böğrenci\b", r"\bintern\b", r"\bstajyer\b",
        r"fresh\s*grad", r"new\s*grad", r"yeni\s*mezun",
        r"entry[- ]?level", r"junior\s*developer",
        r"trainee", r"apprentice", r"çırak",
        r"undergraduate", r"graduate\s*student", r"lisansüstü",
    ]),
]

# ── Multi-Language Translation Dictionary ───────────────────────
# Maps foreign profession words → English equivalents.
# Used in Phase 1b: translate title → re-run EN/TR regex rules.
# Adding a new language = just adding word entries here.
# Keys MUST be lowercase. Multi-word keys are supported (matched first).
_MULTILANG_PHRASES: dict[str, str] = {
    # ── Engineer variants ───────────────────────────────
    # ES
    "ingeniero mecanico": "mechanical engineer",
    "ingeniero civil": "civil engineer",
    "ingeniero electrico": "electrical engineer",
    "ingeniero electronico": "electrical engineer",
    "ingeniero industrial": "industrial engineer",
    "ingeniero quimico": "chemical engineer",
    "ingeniero de software": "software engineer",
    "ingeniero de sistemas": "software engineer",
    # FR
    "ingenieur mecanique": "mechanical engineer",
    "ingenieur civil": "civil engineer",
    "ingenieur electrique": "electrical engineer",
    "ingenieur industriel": "industrial engineer",
    "ingenieur chimique": "chemical engineer",
    "ingenieur logiciel": "software engineer",
    "ingenieur informatique": "software engineer",
    "ressources humaines": "human resources",
    # IT
    "ingegnere meccanico": "mechanical engineer",
    "ingegnere civile": "civil engineer",
    "ingegnere elettrico": "electrical engineer",
    "ingegnere elettronico": "electrical engineer",
    "ingegnere industriale": "industrial engineer",
    "ingegnere chimico": "chemical engineer",
    "ingegnere del software": "software engineer",
    "ingegnere informatico": "software engineer",
    "risorse umane": "human resources",
    "capo progetto": "project manager",
    # PT
    "engenheiro mecanico": "mechanical engineer",
    "engenheiro civil": "civil engineer",
    "engenheiro eletrico": "electrical engineer",
    "engenheiro eletronico": "electrical engineer",
    "engenheiro industrial": "industrial engineer",
    "engenheiro quimico": "chemical engineer",
    "engenheiro de software": "software engineer",
    "engenheiro de computacao": "software engineer",
    "recursos humanos": "human resources",
    "gerente de projeto": "project manager",
    "gerente de produto": "product manager",
    # DE
    "maschinenbauingenieur": "mechanical engineer",
    "bauingenieur": "civil engineer",
    "elektroingenieur": "electrical engineer",
    "industrieingenieur": "industrial engineer",
    "chemieingenieur": "chemical engineer",
    "softwareentwickler": "software developer",
    "personalwesen": "human resources",
    "personalabteilung": "human resources",
    "projektleiter": "project manager",
    "projektmanager": "project manager",
    "krankenschwester": "nurse",
    # NL
    "werktuigbouwkundig ingenieur": "mechanical engineer",
    "werktuigbouwkunde": "mechanical engineer",
    "civiel ingenieur": "civil engineer",
    "software ontwikkelaar": "software developer",
    # ES project/product
    "gerente de proyecto": "project manager",
    "gerente de producto": "product manager",
    "jefe de proyecto": "project manager",
    # FR project
    "chef de projet": "project manager",
    "chef de produit": "product manager",
    # ── RU compound phrases ─────────────────────────────
    "инженер механик": "mechanical engineer",
    "инженер-механик": "mechanical engineer",
    "инженер строитель": "civil engineer",
    "инженер-строитель": "civil engineer",
    "инженер электрик": "electrical engineer",
    "инженер-электрик": "electrical engineer",
    "инженер электроник": "electrical engineer",
    "инженер химик": "chemical engineer",
    "инженер-химик": "chemical engineer",
    "инженер промышленный": "industrial engineer",
    "менеджер проекта": "project manager",
    "руководитель проекта": "project manager",
    "менеджер продукта": "product manager",
    "управление персоналом": "human resources",
    "машиностроение": "mechanical engineering",
    # ── AR compound phrases ─────────────────────────────
    "مهندس ميكانيكي": "mechanical engineer",
    "مهندس مدني": "civil engineer",
    "مهندس كهربائي": "electrical engineer",
    "مهندس كيميائي": "chemical engineer",
    "مهندس صناعي": "industrial engineer",
    "مهندس برمجيات": "software engineer",
    "مهندس معماري": "architect",
    "مدير مشروع": "project manager",
    "موارد بشرية": "human resources",
}

_MULTILANG_WORDS: dict[str, str] = {
    # ── "engineer" in various languages ─────────────────
    "ingeniero": "engineer", "ingeniera": "engineer",     # ES
    "ingenieur": "engineer",                               # FR/NL
    "ingegnere": "engineer",                               # IT
    "engenheiro": "engineer", "engenheira": "engineer",   # PT
    "ingenieur": "engineer",                               # DE
    "inzynier": "engineer",                                # PL (inżynier after fold)
    # ── "mechanical" ────────────────────────────────────
    "mecanico": "mechanical", "mecanica": "mechanical",   # ES/PT
    "mecanique": "mechanical",                             # FR
    "meccanico": "mechanical", "meccanica": "mechanical", # IT
    "maschinenbau": "mechanical",                          # DE
    "werktuigbouw": "mechanical",                          # NL
    "mechanik": "mechanical",                              # PL
    # ── "civil" ─────────────────────────────────────────
    "civile": "civil",   # IT
    "civiel": "civil",   # NL
    "budownictwo": "civil engineering",  # PL
    "budowlany": "civil",                  # PL
    # ── "electrical/electronic" ─────────────────────────
    "electrico": "electrical", "electrica": "electrical",       # ES
    "electrique": "electrical",                                  # FR
    "elettrico": "electrical", "elettronico": "electronic",     # IT
    "eletrico": "electrical", "eletronico": "electronic",       # PT
    "elektryczny": "electrical",                                 # PL
    # ── "industrial" ────────────────────────────────────
    "industriel": "industrial", "industrielle": "industrial",   # FR
    "industriale": "industrial",                                 # IT
    "przemyslowy": "industrial",                                 # PL
    # ── "chemical" ──────────────────────────────────────
    "quimico": "chemical", "quimica": "chemical",               # ES/PT
    "chimique": "chemical",                                      # FR
    "chimico": "chemical", "chimica": "chemical",               # IT
    "chemiczny": "chemical",                                     # PL
    # ── "software" ──────────────────────────────────────
    "logiciel": "software",     # FR
    "entwickler": "developer",  # DE
    "ontwikkelaar": "developer",# NL
    "desenvolvedor": "software developer",  # PT
    "desarrollador": "software developer",  # ES
    "developpeur": "developer", # FR
    "sviluppatore": "developer",# IT
    "programist": "programmer", "programista": "programmer",  # PL
    "informaticien": "software engineer",  # FR
    "informatyk": "software engineer",     # PL
    # ── "architect" ─────────────────────────────────────
    "arquitecto": "architect", "arquitecta": "architect",       # ES
    "arquiteto": "architect", "arquiteta": "architect",         # PT
    "architecte": "architect",                                   # FR
    "architetto": "architect",                                   # IT
    "architekt": "architect",                                    # DE/PL
    # ── "lawyer / attorney" ─────────────────────────────
    "abogado": "lawyer", "abogada": "lawyer",                  # ES
    "avocat": "lawyer", "avocate": "lawyer",                   # FR
    "avvocato": "lawyer", "avvocata": "lawyer",                # IT
    "advogado": "lawyer", "advogada": "lawyer",                # PT
    "advocaat": "lawyer",                                       # NL
    "rechtsanwalt": "lawyer",                                   # DE
    "adwokat": "lawyer",                                        # PL
    # ── "teacher / professor" ───────────────────────────
    "professeur": "professor", "professeure": "professor",     # FR
    "professore": "professor", "professoressa": "professor",   # IT
    "profesor": "professor", "profesora": "professor",         # ES
    "lehrer": "teacher", "lehrerin": "teacher",                # DE
    "nauczyciel": "teacher", "nauczycielka": "teacher",        # PL
    "maestro": "teacher", "maestra": "teacher",                # ES/IT
    "dozent": "lecturer",                                       # DE
    # ── "accountant" ────────────────────────────────────
    "contador": "accountant", "contadora": "accountant",       # ES/PT
    "comptable": "accountant",                                  # FR
    "buchhalter": "accountant",                                 # DE
    "ragioniere": "accountant", "ragioniera": "accountant",    # IT
    "ksiegowy": "accountant", "ksiegowa": "accountant",        # PL
    # ── "doctor / nurse / healthcare" ───────────────────
    "medecin": "physician",                                     # FR
    "medico": "doctor",                                         # ES/IT/PT
    "arzt": "doctor", "arztin": "doctor",                      # DE
    "enfermero": "nurse", "enfermera": "nurse",                # ES
    "enfermeiro": "nurse", "enfermeira": "nurse",              # PT
    "infirmier": "nurse", "infirmiere": "nurse",               # FR
    # ── "project / product" ─────────────────────────────
    "projet": "project",     # FR
    "proyecto": "project",   # ES
    "progetto": "project",   # IT
    "projeto": "project",    # PT
    "produto": "product",    # PT
    "producto": "product",   # ES
    "produit": "product",    # FR
    "prodotto": "product",   # IT
    # ── "manager / director" ────────────────────────────
    "gerente": "manager",    # ES/PT
    "directeur": "director", # FR
    "direttore": "director", # IT
    "diretor": "director",   # PT
    "direktor": "director",  # DE
    # ── Cyrillic (RU) ──────────────────────────────────
    "инженер": "engineer",
    "программист": "programmer",
    "разработчик": "developer",
    "архитектор": "architect",
    "адвокат": "lawyer",
    "юрист": "lawyer",
    "преподаватель": "professor",
    "учитель": "teacher",
    "бухгалтер": "accountant",
    "врач": "doctor",
    "медсестра": "nurse",
    "менеджер": "manager",
    "руководитель": "director",
    "механик": "mechanical",
    "электрик": "electrical",
    # ── Arabic ──────────────────────────────────────────
    "مهندس": "engineer",
    "مبرمج": "programmer",
    "محامي": "lawyer", "محام": "lawyer",
    "محاسب": "accountant",
    "طبيب": "doctor",
    "ممرض": "nurse",
    "معلم": "teacher",
    "أستاذ": "professor",
    "مدير": "manager",
    "معمار": "architect",
    "ميكانيكي": "mechanical",
    "مدني": "civil",
    "كيميائي": "chemical",
    "صناعي": "industrial",
    "كهربائي": "electrical",
}

# Sort phrase keys by length (longest first) for greedy matching
_PHRASE_KEYS_SORTED = sorted(_MULTILANG_PHRASES.keys(), key=len, reverse=True)
_WORD_KEYS_SORTED = sorted(_MULTILANG_WORDS.keys(), key=len, reverse=True)


def _translate_to_english(text: str) -> str:
    """Translate foreign profession words to English using the dictionary.

    First tries multi-word phrases (longest match first), then single words.
    Operates on ASCII-folded lowercase text for accent-insensitive matching.
    """
    # ASCII-fold for matching
    folded = text.translate(_TR_MAP)
    folded = unicodedata.normalize("NFKD", folded)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = folded.lower()

    # Phase A: phrase replacement (longest first)
    for phrase in _PHRASE_KEYS_SORTED:
        if phrase in folded:
            folded = folded.replace(phrase, _MULTILANG_PHRASES[phrase])

    # Phase B: whole-word replacement (avoid partial matches inside already-translated words)
    for word in _WORD_KEYS_SORTED:
        if word in folded:
            # Use regex word-boundary to avoid replacing substrings
            folded = re.sub(r'(?<!\w)' + re.escape(word) + r'(?!\w)', _MULTILANG_WORDS[word], folded)

    return folded

_SKILL_PROFESSION_MAP: dict[str, str] = {
    "react": "software_engineer", "angular": "software_engineer",
    "vue": "software_engineer", "django": "software_engineer",
    "flask": "software_engineer", "spring": "software_engineer",
    "kubernetes": "software_engineer", "docker": "software_engineer",
    "terraform": "software_engineer", "aws": "software_engineer",
    "tensorflow": "data_scientist", "pytorch": "data_scientist",
    "pandas": "data_scientist", "scikit-learn": "data_scientist",
    "tableau": "data_scientist", "power bi": "data_scientist",
    "figma": "designer", "sketch": "designer", "adobe xd": "designer",
    "photoshop": "designer", "illustrator": "designer",
    "jira": "product_manager", "confluence": "product_manager",
    "google analytics": "marketing", "hubspot": "marketing",
    "salesforce": "sales",
    "quickbooks": "accountant", "sap": "accountant",
    "solidworks": "mechanical_engineer", "autocad": "civil_engineer",
    "catia": "mechanical_engineer", "ansys": "mechanical_engineer",
    "revit": "architect", "sketchup": "architect",
    "matlab": "electrical_engineer", "simulink": "electrical_engineer",
    "plc": "electrical_engineer", "scada": "electrical_engineer",
    "arena simulation": "industrial_engineer",
    "aspen": "chemical_engineer", "hysys": "chemical_engineer",
}

# ── Title Normalization ─────────────────────────────────────────

# Turkish → ASCII mapping for normalization
_TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")

# Noise words to strip when building a canonical profession key
_NOISE_WORDS = {
    "senior", "junior", "lead", "staff", "principal", "chief",
    "kıdemli", "kidemli", "baş", "uzman", "specialist",
    "associate", "assistant", "yardımcı", "head", "of", "the",
    "bir", "ve", "and", "in", "at", "ile",
    "sr", "jr", "i", "ii", "iii", "iv", "1", "2", "3",
}

# Minimum similarity ratio to consider two profession keys as the same
_SIMILARITY_THRESHOLD = 0.78


def _normalize_title(raw: str) -> str:
    """Normalize a job title: lowercase, strip noise, ASCII-fold, underscores."""
    text = raw.strip().lower()
    # Turkish chars → ASCII
    text = text.translate(_TR_MAP)
    # Remove accents/diacritics for other languages
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Keep only alphanumeric + spaces
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # Remove noise words
    words = [w for w in text.split() if w not in _NOISE_WORDS and len(w) > 1]
    return "_".join(words) if words else ""


def _title_similarity(a: str, b: str) -> float:
    """Return similarity ratio (0.0–1.0) between two normalized keys."""
    return SequenceMatcher(None, a, b).ratio()


def _find_similar_profession(
    candidate_key: str,
    existing_keys: list[str],
) -> str | None:
    """Find the most similar existing profession key above threshold."""
    best_key = None
    best_score = 0.0
    for existing in existing_keys:
        score = _title_similarity(candidate_key, existing)
        if score > best_score:
            best_score = score
            best_key = existing
    if best_score >= _SIMILARITY_THRESHOLD and best_key:
        return best_key
    return None


# All known canonical keys (from rules) — used as base for similarity checks
_KNOWN_PROFESSION_KEYS = [key for key, _ in _PROFESSION_RULES] + ["general"]


def infer_profession(
    job_title: str | None = None,
    experience_titles: list[str] | None = None,
    skills: list[str] | None = None,
    db: Session | None = None,
) -> str:
    """Infer profession group from job title, experience, and skills.

    Returns a canonical profession key (e.g. ``software_engineer``).

    Three-phase matching:
    1. Regex rules (fast, covers known professions in TR + EN)
    2. Skill-based voting (fallback for rule misses)
    3. Dynamic similarity matching — normalizes the title, checks against
       existing profession keys (rules + DB). If similar enough, maps to
       existing. If genuinely new and clean, creates a new key.
       Falls back to ``"general"`` only when title is empty/noise.
    """
    # Build a combined text blob for matching
    parts: list[str] = []
    if job_title:
        parts.append(job_title)
    for t in (experience_titles or []):
        parts.append(t)
    raw = " ".join(parts)
    # Fix Turkish İ/ı before lowering: İ.lower() produces i+combining_dot which
    # breaks regex; ı (dotless) won't match patterns that use regular 'i'.
    raw = raw.replace("\u0130", "I").replace("\u0131", "i")
    combined = raw.lower()

    # Phase 1: regex rules (TR + EN, fast)
    for profession, patterns in _PROFESSION_RULES:
        for pat in patterns:
            if re.search(pat, combined, re.IGNORECASE):
                return profession

    # Phase 1b: translate foreign title → English, then re-run rules
    # Also handles ASCII-folded input (e.g. "insaat muhendisi")
    translated = _translate_to_english(combined)
    if translated != combined:
        for profession, patterns in _PROFESSION_RULES:
            for pat in patterns:
                if re.search(pat, translated, re.IGNORECASE):
                    return profession

    # Phase 1c: retry with fully ASCII-folded text AND patterns
    # (catches cases like "insaat muhendisi" → civil_engineer via TR patterns)
    def _ascii_fold(text: str) -> str:
        t = text.translate(_TR_MAP)
        t = unicodedata.normalize("NFKD", t)
        return "".join(c for c in t if not unicodedata.combining(c))

    combined_ascii = _ascii_fold(combined)
    for profession, patterns in _PROFESSION_RULES:
        for pat in patterns:
            folded_pat = _ascii_fold(pat)
            if re.search(folded_pat, combined_ascii, re.IGNORECASE):
                return profession

    # Phase 2: skill-based voting
    skill_votes: dict[str, int] = {}
    for skill in (skills or []):
        key = skill.strip().lower()
        prof = _SKILL_PROFESSION_MAP.get(key)
        if prof:
            skill_votes[prof] = skill_votes.get(prof, 0) + 1
    if skill_votes:
        return max(skill_votes, key=skill_votes.get)

    # Phase 3: dynamic similarity matching
    # Try to derive a profession from the strongest title signal
    best_title = (job_title or "").strip()
    if not best_title and experience_titles:
        best_title = experience_titles[0]
    if not best_title:
        return "general"

    candidate_key = _normalize_title(best_title)
    if not candidate_key or len(candidate_key) < 3:
        return "general"

    # Collect all known keys: static rules + dynamic DB entries
    all_keys = list(_KNOWN_PROFESSION_KEYS)
    if db is not None:
        try:
            db_profs = [
                r[0] for r in
                db.query(ATSBenchmarkProfession.profession).all()
            ]
            for k in db_profs:
                if k not in all_keys:
                    all_keys.append(k)
        except Exception:
            pass

    # Check similarity against all known keys
    match = _find_similar_profession(candidate_key, all_keys)
    if match:
        logger.info("profession_similarity_match: '%s' → '%s'", candidate_key, match)
        return match

    # Truly new profession — register with normalized key
    logger.info("profession_new_dynamic: '%s' (from '%s')", candidate_key, best_title)
    return candidate_key


# ── Aggregate Helpers ───────────────────────────────────────────

def _compute_median(scores: list[float]) -> float:
    if not scores:
        return 0.0
    s = sorted(scores)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return round(s[mid], 2)
    return round((s[mid - 1] + s[mid]) / 2, 2)


def _compute_percentile(score: float, scores: list[float]) -> int:
    """Return the percentile rank of *score* within *scores* (0–100)."""
    if not scores:
        return 50
    below = sum(1 for s in scores if s < score)
    return min(100, max(0, round(below / len(scores) * 100)))


def _compute_top_10_pct(scores: list[float]) -> float:
    if not scores:
        return 0.0
    s = sorted(scores)
    idx = max(0, int(len(s) * 0.9))
    return round(s[min(idx, len(s) - 1)], 2)


def _rank_label(percentile: int) -> str:
    if percentile >= 90:
        return "Top 10%"
    if percentile >= 75:
        return "Top 25%"
    if percentile >= 50:
        return "Above Average"
    if percentile >= 25:
        return "Average"
    return "Below Average"


def _profession_display(profession: str) -> str:
    if profession == "general":
        return "Other / General"
    # Dynamic keys are already snake_case — prettify
    return profession.replace("_", " ").title()


# ── DB-aware infer helper (passes db session) ──────────────────

def infer_profession_with_db(
    db: Session,
    job_title: str | None = None,
    experience_titles: list[str] | None = None,
    skills: list[str] | None = None,
) -> str:
    """Convenience wrapper that passes db for dynamic similarity matching."""
    return infer_profession(job_title, experience_titles, skills, db=db)


# ── Core API ────────────────────────────────────────────────────

def record_ats_score(
    db: Session,
    ats_score: float,
    profession: str,
) -> None:
    """Record a new ATS score and update all aggregates.

    Called after every successful CV analysis.
    """
    if ats_score is None or ats_score < 0:
        return

    profession = profession or "general"

    # 1. Insert individual score record (anonymised — no user id)
    db.add(ATSBenchmarkScore(ats_score=ats_score, profession=profession))

    # 2. Update global aggregate
    _update_global_aggregate(db, ats_score)

    # 3. Update profession aggregate
    _update_profession_aggregate(db, profession, ats_score)

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to record ATS benchmark score")


def _update_global_aggregate(db: Session, new_score: float) -> None:
    row = db.query(ATSBenchmarkGlobal).filter(ATSBenchmarkGlobal.id == 1).first()
    if not row:
        row = ATSBenchmarkGlobal(id=1, total_cvs=0, sum_ats=0.0, avg_ats=0.0, median_ats=0.0)
        db.add(row)
        db.flush()

    row.total_cvs += 1
    row.sum_ats += new_score
    row.avg_ats = round(row.sum_ats / row.total_cvs, 2)
    row.updated_at = datetime.utcnow()

    # Recompute median from stored scores (sampled for perf)
    all_scores = [
        r[0] for r in db.query(ATSBenchmarkScore.ats_score)
        .order_by(ATSBenchmarkScore.ats_score)
        .limit(50000)
        .all()
    ]
    row.median_ats = _compute_median(all_scores)


def _update_profession_aggregate(db: Session, profession: str, new_score: float) -> None:
    row = (
        db.query(ATSBenchmarkProfession)
        .filter(ATSBenchmarkProfession.profession == profession)
        .first()
    )
    if not row:
        row = ATSBenchmarkProfession(
            profession=profession, total_cvs=0,
            sum_ats=0.0, avg_ats=0.0, median_ats=0.0, top_10_pct=0.0,
        )
        db.add(row)
        db.flush()

    row.total_cvs += 1
    row.sum_ats += new_score
    row.avg_ats = round(row.sum_ats / row.total_cvs, 2)
    row.updated_at = datetime.utcnow()

    # Recompute median & top 10% for this profession
    prof_scores = [
        r[0] for r in db.query(ATSBenchmarkScore.ats_score)
        .filter(ATSBenchmarkScore.profession == profession)
        .order_by(ATSBenchmarkScore.ats_score)
        .limit(50000)
        .all()
    ]
    row.median_ats = _compute_median(prof_scores)
    row.top_10_pct = _compute_top_10_pct(prof_scores)


def get_benchmark_comparison(
    db: Session,
    ats_score: float,
    profession: str,
) -> dict:
    """Build the benchmark comparison payload for a single CV.

    Returns the response structure described in the feature spec.
    """
    profession = profession or "general"

    # Global stats
    g_row = db.query(ATSBenchmarkGlobal).filter(ATSBenchmarkGlobal.id == 1).first()
    global_avg = g_row.avg_ats if g_row else 0.0
    global_median = g_row.median_ats if g_row else 0.0
    total_cvs = g_row.total_cvs if g_row else 0

    # Profession stats
    p_row = (
        db.query(ATSBenchmarkProfession)
        .filter(ATSBenchmarkProfession.profession == profession)
        .first()
    )
    prof_avg = p_row.avg_ats if p_row else global_avg
    prof_median = p_row.median_ats if p_row else global_median
    prof_top10 = p_row.top_10_pct if p_row else 0.0
    prof_total = p_row.total_cvs if p_row else 0

    # Percentile within profession (or global if profession has too few)
    target_table = ATSBenchmarkScore.profession == profession
    if prof_total < 10:
        target_table = True  # use all scores
    peer_scores = [
        r[0] for r in db.query(ATSBenchmarkScore.ats_score)
        .filter(target_table)
        .limit(50000)
        .all()
    ]
    percentile = _compute_percentile(ats_score, peer_scores) if peer_scores else 50

    vs_global = round(ats_score - global_avg, 1)
    vs_profession = round(ats_score - prof_avg, 1)

    return {
        "user_score": round(ats_score, 1),
        "global": {
            "avg": global_avg,
            "median": global_median,
            "total_cvs": total_cvs,
            "delta": f"{'+' if vs_global >= 0 else ''}{vs_global}",
        },
        "profession": {
            "name": profession,
            "display_name": _profession_display(profession),
            "avg": prof_avg,
            "median": prof_median,
            "top_10_percent": prof_top10,
            "total_cvs": prof_total,
            "delta": f"{'+' if vs_profession >= 0 else ''}{vs_profession}",
        },
        "percentile": percentile,
        "rank_label": _rank_label(percentile),
        "rank_description": (
            f"You are in the top {100 - percentile}% of "
            f"{_profession_display(profession)}s"
            if percentile >= 50
            else f"You are in the {_rank_label(percentile).lower()} range among "
                 f"{_profession_display(profession)}s"
        ) if profession != "general" else (
            f"You are in the top {100 - percentile}% of all CVs"
            if percentile >= 50
            else f"You are in the {_rank_label(percentile).lower()} range among all CVs"
        ),
    }


def get_global_stats(db: Session) -> dict:
    """Return global-only benchmark stats (for public API / dashboard)."""
    g = db.query(ATSBenchmarkGlobal).filter(ATSBenchmarkGlobal.id == 1).first()
    if not g or g.total_cvs == 0:
        return {"total_cvs": 0, "avg": 0, "median": 0}
    return {
        "total_cvs": g.total_cvs,
        "avg": g.avg_ats,
        "median": g.median_ats,
    }


def get_profession_stats(db: Session) -> list[dict]:
    """Return stats for all profession groups."""
    rows = (
        db.query(ATSBenchmarkProfession)
        .filter(ATSBenchmarkProfession.total_cvs >= 1)
        .order_by(ATSBenchmarkProfession.total_cvs.desc())
        .all()
    )
    return [
        {
            "profession": r.profession,
            "display_name": _profession_display(r.profession),
            "total_cvs": r.total_cvs,
            "avg": r.avg_ats,
            "median": r.median_ats,
            "top_10_percent": r.top_10_pct,
        }
        for r in rows
    ]
