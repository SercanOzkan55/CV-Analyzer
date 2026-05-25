"""CV analysis pipeline runtime."""

import hashlib
import json
import logging
import os
import re
import time

from core.runtime_bridge import main_value, redis_rate_client
from services.ats_config import get_ats_weights
from services.ats_service import analyze_cv
from services.domain_service import detect_or_create_domain, get_domain_similarity
from services.embedding_service import get_embedding as _default_get_embedding
from services.experience_service import experience_score
from services.industry_service import detect_industry_and_specialization
from services.keyword_service import compare, compute_keyword_gap, keyword_match_score
from services.language_service import (
    clean_lower,
    detect_language,
    interpret_score_localized,
    localize_risk_level,
)
from services.ml_model import predict_score as ml_predict_score
from services.model_service import predict_hire, predict_match
from services.recommendation_service import generate_recommendations
from services.scoring_service import calculate_similarity
from services.skill_service import skill_coverage_score


logger = logging.getLogger("app.pipeline")

_WORD_RE = re.compile(r"[A-Za-z\u00C0-\u024F\u0400-\u04FF]{2,}", re.UNICODE)
_WORD3_RE = re.compile(r"[A-Za-z\u00C0-\u024F\u0400-\u04FF]{3,}", re.UNICODE)

_GLOBAL_STOPWORDS = {
    # English
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "her",
    "was", "one", "our", "out", "with", "that", "this", "have", "from",
    "they", "will", "each", "make", "like", "been", "has", "its", "who",
    "did", "get", "may", "him", "his", "how", "let", "say", "she", "too",
    "use", "way", "about", "would", "there", "their", "what", "could",
    "other", "than", "then", "them", "these", "some", "which", "into",
    "over", "under", "between", "within", "without", "your", "role",
    # Turkish
    "ve", "veya", "ile", "için", "icin", "bir", "bu", "şu", "su", "da",
    "de", "mi", "mı", "mu", "mü", "olan", "olarak", "gibi", "çok", "cok",
    "daha", "en", "her", "tüm", "tum", "ise", "hem", "ya", "ki",
    # German
    "und", "oder", "mit", "für", "fur", "der", "die", "das", "ein", "eine",
    "einen", "einem", "zu", "im", "in", "von", "den", "dem", "des", "als",
    # French
    "et", "ou", "avec", "pour", "les", "des", "une", "un", "du", "de",
    "la", "le", "dans", "sur", "par", "aux", "au", "ce", "cette",
    # Spanish
    "y", "o", "con", "para", "los", "las", "una", "uno", "del", "de",
    "el", "la", "en", "por", "como", "que", "este", "esta",
    # Portuguese / Italian / Dutch
    "e", "com", "para", "os", "as", "um", "uma", "do", "da", "no", "na",
    "il", "lo", "gli", "le", "di", "per", "che", "een", "het", "van",
    "voor", "met", "op", "aan", "als",
}

_SOFT_SKILL_TERMS = {
    # English
    "leadership", "teamwork", "communication", "collaboration", "problem solving",
    "time management", "critical thinking", "adaptability", "creativity",
    "mentoring", "negotiation", "presentation", "stakeholder", "cross functional",
    "strategic", "initiative", "empathy", "conflict resolution",
    # Turkish
    "liderlik", "takım çalışması", "takim calismasi", "iletişim", "iletisim",
    "iş birliği", "is birligi", "problem çözme", "problem cozme", "zaman yönetimi",
    "zaman yonetimi", "eleştirel düşünme", "elestirel dusunme", "uyum sağlama",
    "uyum saglama", "yaratıcılık", "yaraticilik", "mentorluk", "müzakere",
    "muzakere", "sunum", "paydaş", "paydas", "stratejik", "inisiyatif", "empati",
    "çatışma çözümü", "catisma cozumu",
    # German
    "führung", "fuhrung", "teamarbeit", "kommunikation", "zusammenarbeit",
    "problemlösung", "problemlosung", "zeitmanagement", "kritisches denken",
    "anpassungsfähigkeit", "kreativität", "mentoring", "verhandlung", "präsentation",
    # French
    "leadership", "travail d'équipe", "travail equipe", "communication",
    "collaboration", "résolution de problèmes", "resolution de problemes",
    "gestion du temps", "pensée critique", "adaptabilité", "créativité",
    # Spanish
    "liderazgo", "trabajo en equipo", "comunicación", "comunicacion",
    "colaboración", "colaboracion", "resolución de problemas",
    "resolucion de problemas", "gestión del tiempo", "gestion del tiempo",
    "pensamiento crítico", "pensamiento critico", "adaptabilidad", "creatividad",
}

_EDUCATION_LEVEL_PATTERNS = (
    (100.0, r"\b(ph\.?d|doctorate|doctoral|doctorado|doctorat|doktor|doktora|promotion)\b"),
    (80.0, r"\b(master|msc|m\.sc|m\.a\.|mba|magistrale|maestr[ií]a|ma[îi]trise|yüksek\s*lisans|yuksek\s*lisans|mast[eè]re|magister)\b"),
    (60.0, r"\b(bachelor|bsc|b\.sc|b\.a\.|licenciatura|licence|laurea|lisans|undergraduate|grado|studium)\b"),
    (40.0, r"\b(associate|ön\s*lisans|on\s*lisans|diploma|berufsabschluss|technicien|t[eé]cnico)\b"),
    (20.0, r"\b(high\s*school|lise|certificate|certificat|certificado|zertifikat|abitur|gymnasium|baccalaur[eé]at|bachillerato)\b"),
)


def _phrase_pattern(term: str) -> str:
    return r"(?<!\w)" + re.escape(clean_lower(term)).replace(r"\ ", r"\s+") + r"(?!\w)"


def _word_tokens(text: str, min_len: int = 2) -> list[str]:
    pattern = _WORD3_RE if min_len >= 3 else _WORD_RE
    return pattern.findall(clean_lower(text or ""))


def _contains_soft_skill(text: str, term: str) -> bool:
    return bool(re.search(_phrase_pattern(term), text))


def _get_embedding(text: str):
    # Tests monkeypatch main.get_embedding; keep that hook centralized here.
    return main_value("get_embedding", _default_get_embedding)(text)


def _fallback_domain_data() -> dict:
    return {"domain_id": 1, "domain_name": "Other"}


def _fallback_industry_data(domain_id: int = 1) -> dict:
    return {
        "domain_id": domain_id,
        "industry_id": 1,
        "industry_name": "Other",
        "specialization_id": 1,
        "specialization_name": "General",
    }


def interpret_score(score):
    if score > 75:
        return "High Match"
    elif score > 50:
        return "Moderate Match"
    return "Low Match"


def build_features(
    semantic, keyword, skill, exp, missing_skills, domain_similarity, ats_score,
    ats_details=None, title_match=0.0, seniority_match=0.0,
    cv_text="", job_description="",
):
    # Floor values: prevent 0-scores from bad parse / empty PDF / student CV
    semantic = max(float(semantic), 5.0)
    keyword = max(float(keyword), 5.0)
    skill = max(float(skill), 5.0)
    exp = max(float(exp), 5.0)

    missing_count = len(missing_skills)
    total_required_skills = missing_count + max(1, int(skill / 20))

    missing_ratio = missing_count / total_required_skills

    semantic_skill_interaction = float(semantic * skill / 100)
    keyword_skill_interaction = float(keyword * skill / 100)

    # balance_score approximates how balanced semantic vs skill coverage is
    balance_score = float(max(0.0, 100.0 - abs(float(semantic) - float(skill))))

    # ATS layout features (from ats_details if available)
    layout = (ats_details or {}).get("layout", {})
    content = (ats_details or {}).get("content", {})
    sections_found = layout.get("sections_found", [])

    bullet_score = float(layout.get("bullet_score", 0.0))
    section_count = int(len(sections_found))
    section_presence_score = float(layout.get("section_presence_score", 0.0))
    formatting_score = float(layout.get("formatting_score", 0.0))
    length_score = float(layout.get("length_score", 0.0))
    contact_score = float(layout.get("contact_score", 0.0))

    # ATS content features
    action_verb_score = float(content.get("action_verb_score", 0.0))
    achievement_score = float(content.get("achievement_score", 0.0))

    # Section presence flags
    sections_lower = {s.lower() for s in sections_found}
    has_summary = int(any(s in sections_lower for s in ("summary", "profile", "objective")))
    has_skills = int("skills" in sections_lower)
    has_experience = int("experience" in sections_lower)
    has_education = int("education" in sections_lower)
    has_projects = int("projects" in sections_lower)

    # ── New features (v2.1) ──────────────────────────────────────────────

    # Soft skill detection: leadership, teamwork, communication keywords
    _SOFT_SKILL_PATTERNS = [
        r"\bleadership\b", r"\bteamwork\b", r"\bcommunication\b",
        r"\bcollaboration\b", r"\bproblem.solving\b", r"\btime.management\b",
        r"\bcritical.thinking\b", r"\badaptability\b", r"\bcreativity\b",
        r"\bmentoring\b", r"\bnegotiation\b", r"\bpresentation\b",
        r"\bstakeholder\b", r"\bcross.functional\b", r"\bstrategic\b",
        r"\binitiative\b", r"\bempathy\b", r"\bconflict.resolution\b",
    ]
    _cv_lower = clean_lower(cv_text or "")
    _soft_hits = sum(1 for term in _SOFT_SKILL_TERMS if _contains_soft_skill(_cv_lower, term))
    soft_skill_score = min(100.0, (_soft_hits / max(len(_SOFT_SKILL_TERMS), 1)) * 300)

    # Readability: vocabulary richness (unique words / total words)
    _words = _word_tokens(_cv_lower, min_len=2)
    _total_words = max(len(_words), 1)
    _unique_words = len(set(_words))
    readability_score = min(100.0, (_unique_words / _total_words) * 130)

    # Keyword density: how well matched keywords spread across the text
    _jd_words = set(_word_tokens(job_description, min_len=3))
    _stop = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "her",
             "was", "one", "our", "out", "with", "that", "this", "have", "from",
             "they", "will", "each", "make", "like", "been", "has", "its", "who",
             "did", "get", "may", "him", "his", "how", "its", "let", "say", "she",
             "too", "use", "way", "about", "would", "there", "their", "what",
             "could", "other", "than", "then", "them", "these", "some", "which"}
    _jd_kw = _jd_words - _GLOBAL_STOPWORDS
    if _jd_kw and _total_words > 0:
        _kw_found = sum(1 for w in _words if w in _jd_kw)
        keyword_density = min(100.0, (_kw_found / _total_words) * 500)
    else:
        keyword_density = 0.0

    # Education quality: degree level detection
    _edu_score = 0.0
    if re.search(r"\b(ph\.?d|doctorate|doktora)\b", _cv_lower):
        _edu_score = 100.0
    elif re.search(r"\b(master|msc|m\.sc|m\.a\.|mba|yüksek\s*lisans)\b", _cv_lower):
        _edu_score = 80.0
    elif re.search(r"\b(bachelor|bsc|b\.sc|b\.a\.|lisans|undergraduate)\b", _cv_lower):
        _edu_score = 60.0
    elif re.search(r"\b(associate|ön\s*lisans|diploma)\b", _cv_lower):
        _edu_score = 40.0
    elif re.search(r"\b(high\s*school|lise|certificate)\b", _cv_lower):
        _edu_score = 20.0
    for score, pattern in _EDUCATION_LEVEL_PATTERNS:
        if re.search(pattern, _cv_lower):
            _edu_score = max(_edu_score, score)
            break

    features = [
        float(semantic),
        float(keyword),
        float(skill),
        float(exp),
        int(missing_count),
        float(missing_ratio),
        semantic_skill_interaction,
        keyword_skill_interaction,
        balance_score,
        bullet_score,
        section_count,
        section_presence_score,
        formatting_score,
        length_score,
        contact_score,
        action_verb_score,
        achievement_score,
        has_summary,
        has_skills,
        has_experience,
        has_education,
        has_projects,
        float(domain_similarity),
        float(title_match),
        float(seniority_match),
        float(soft_skill_score),
        float(readability_score),
        float(keyword_density),
        float(_edu_score),
    ]
    if len(features) != 29:
        raise ValueError(f"build_features: expected 29 features, got {len(features)}")
    return features


ANALYSIS_SCORE_VERSION = os.getenv("ANALYSIS_SCORE_VERSION", "v3-jd-quality")
ANALYSIS_CACHE_TTL = int(os.getenv("ANALYSIS_CACHE_TTL", "86400"))
_analysis_mem_cache: dict[str, tuple[float, dict]] = {}


def _stable_hash(text: str) -> str:
    if not isinstance(text, str):
        text = str(text or "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_job_title_from_jd(job_description: str) -> str | None:
    """Extract a compact job title candidate from JD text.

    Uses the first non-empty line and trims common separators.
    """
    if not isinstance(job_description, str):
        return None
    lines = [ln.strip() for ln in job_description.splitlines() if ln.strip()]
    if not lines:
        return None
    first = lines[0]
    for sep in ("|", "-", "("):
        if sep in first:
            first = first.split(sep, 1)[0].strip()
    if not first:
        return None
    return first[:120]


def _extract_probable_job_title(text: str) -> str:
    source = str(text or "")
    patterns = [
        r"\b(?:hiring|looking for|seeking|position|role)\s+(?:a|an)?\s*([A-Za-z][A-Za-z0-9\-\s]{3,60})",
        r"\b([A-Za-z][A-Za-z0-9\-\s]{3,60})\s+(?:position|role)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, source, flags=re.I)
        if match:
            title = re.sub(r"\s+", " ", match.group(1)).strip(" -:;,.\t\n")
            if title:
                return title
    return ""


def _title_match_score(cv_text: str, job_description: str) -> float:
    title = _extract_probable_job_title(job_description)
    if not title:
        return 50.0
    normalized_title = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    normalized_cv = re.sub(r"[^a-z0-9]+", " ", str(cv_text or "").lower())
    if normalized_title and normalized_title in normalized_cv:
        return 100.0
    title_tokens = {tok for tok in normalized_title.split() if len(tok) > 2}
    if not title_tokens:
        return 50.0
    cv_tokens = set(normalized_cv.split())
    overlap = len(title_tokens & cv_tokens)
    return round((overlap / max(1, len(title_tokens))) * 100.0, 2)


def _detect_seniority(text: str) -> str:
    lowered = clean_lower(text or "")
    senior_patterns = {
        "intern": ["intern", "internship", "trainee", "stajyer", "praktikant", "stagiaire", "pasante", "becario", "tirocinante", "practicante"],
        "junior": ["junior", "entry level", "entry-level", "associate", "júnior", "juniorentwickler", "débutant", "debutant", "principiante"],
        "mid": ["mid", "mid level", "mid-level", "intermediate", "regular", "mittelstufe", "confirmé", "confirme", "intermedio"],
        "senior": ["senior", "lead", "principal", "staff", "experienced", "kıdemli", "kidemli", "leiter", "chef", "responsable", "principal", "avanzado"],
        "manager": ["manager", "head", "director", "vp", "chief", "yönetici", "yonetici", "müdür", "mudur", "leiter", "geschäftsführer", "chef", "directeur", "gerente", "jefe", "diretor"],
    }
    for level, patterns in senior_patterns.items():
        for pattern in patterns:
            if re.search(r"\b" + re.escape(pattern) + r"\b", lowered):
                return level
    return "unknown"


def _seniority_match_score(cv_text: str, job_description: str) -> float:
    jd_level = _detect_seniority(job_description)
    cv_level = _detect_seniority(cv_text)
    if jd_level == "unknown" or cv_level == "unknown":
        return 60.0
    if jd_level == cv_level:
        return 100.0

    rank = {"intern": 1, "junior": 2, "mid": 3, "senior": 4, "manager": 5}
    distance = abs(rank.get(jd_level, 3) - rank.get(cv_level, 3))
    if distance == 1:
        return 75.0
    if distance == 2:
        return 55.0
    return 35.0


def _assess_job_description_quality(job_description: str, jd_skills: list | None = None) -> dict:
    text = str(job_description or "").strip()
    if not text:
        return {"status": "missing", "valid": False, "reason": "empty", "word_count": 0}

    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿÇĞİÖŞÜçğıöşü0-9+#.]{2,}", text)
    alpha_tokens = [tok for tok in tokens if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿÇĞİÖŞÜçğıöşü]", tok)]
    word_count = len(tokens)
    lower = text.lower()
    has_skill = bool(jd_skills)
    role_terms = {
        "developer", "engineer", "analyst", "manager", "designer", "intern", "specialist",
        "consultant", "assistant", "coordinator", "architect", "technician", "administrator",
        "backend", "frontend", "fullstack", "full-stack", "software", "data", "devops",
        "qa", "tester", "sales", "marketing", "teacher", "nurse", "accountant", "product",
        "recruiter", "junior", "senior", "lead", "mühendis", "muhendis", "geliştirici",
        "gelistirici", "uzman", "stajyer", "analist", "tasarımcı", "tasarimci", "yönetici",
        "yonetici", "öğretmen", "ogretmen", "hemşire", "hemsire", "satış", "satis",
    }
    has_role = any(re.search(rf"\b{re.escape(term)}\b", lower) for term in role_terms)
    vowel_re = re.compile(r"[aeiouıöüAEIOUİÖÜ]")
    meaningful_alpha = [
        tok for tok in alpha_tokens
        if vowel_re.search(tok) or tok.lower() in {"qa", "hr", "ui", "ux", "c++", "c#"}
    ]

    if not has_skill and not has_role:
        if word_count < 4:
            return {
                "status": "invalid",
                "valid": False,
                "reason": "too_short_without_role_or_skill",
                "word_count": word_count,
            }
        if alpha_tokens and not meaningful_alpha:
            return {
                "status": "invalid",
                "valid": False,
                "reason": "gibberish_like_text",
                "word_count": word_count,
            }

    if word_count < 15:
        return {
            "status": "weak",
            "valid": True,
            "reason": "too_short_for_reliable_matching",
            "word_count": word_count,
        }

    return {"status": "ok", "valid": True, "reason": "ok", "word_count": word_count}


def _build_match_score_v2(result: dict, keyword_gap_v2: dict) -> dict:
    keyword_coverage = float(keyword_gap_v2.get("keyword_coverage_pct", 0.0) or 0.0)
    experience_match = float(result.get("experience_score", 0.0) or 0.0)
    title_match = float(result.get("title_match", 0.0) or 0.0)
    seniority_match = float(result.get("seniority_match", 0.0) or 0.0)

    weighted = (
        keyword_coverage * 0.35
        + experience_match * 0.30
        + title_match * 0.20
        + seniority_match * 0.15
    )
    overall = round(min(100.0, max(0.0, weighted)), 2)

    weak_notes = []
    if keyword_coverage < 50:
        weak_notes.append("Low keyword coverage")
    if seniority_match < 60:
        weak_notes.append("Seniority mismatch")
    if experience_match < 60:
        weak_notes.append("Experience evidence is weak")
    if title_match < 60:
        weak_notes.append("Title alignment is weak")

    return {
        "match_score": overall,
        "keyword_coverage_pct": round(keyword_coverage, 2),
        "experience_match": round(experience_match, 2),
        "title_match": round(title_match, 2),
        "seniority_match": round(seniority_match, 2),
        "missing_skills": result.get("missing_skills") or [],
        "missing_keywords": keyword_gap_v2.get("missing_keywords") or [],
        "extra_skills": result.get("extra_skills") or [],
        "strong_keywords": keyword_gap_v2.get("strong_keywords") or [],
        "weak_keywords": keyword_gap_v2.get("weak_keywords") or [],
        "weak_signals": weak_notes,
    }


def run_pipeline(cv_text: str, job_description: str, lang: str = ""):
    # Basic input guards
    if not isinstance(cv_text, str):
        cv_text = ""
    if not isinstance(job_description, str):
        job_description = ""

    forced_lang = (lang or "").strip().lower()
    lang_detection_fallback = False

    # Detect languages independently and prefer job-description language for output,
    # unless the client explicitly requests a language.
    cv_lang = detect_language(cv_text)
    jd_lang = detect_language(job_description)
    if forced_lang:
        detected_lang = forced_lang
    elif jd_lang and jd_lang != "en":
        detected_lang = jd_lang
    elif cv_lang:
        detected_lang = cv_lang
    else:
        detected_lang = "en"
        lang_detection_fallback = True

    # Truncate extremely large inputs to avoid resource exhaustion
    MAX_CV_LEN = 200_000
    MAX_JOB_LEN = 100_000
    if len(cv_text) > MAX_CV_LEN:
        cv_text = cv_text[:MAX_CV_LEN]
    if len(job_description) > MAX_JOB_LEN:
        job_description = job_description[:MAX_JOB_LEN]

    # Analysis result cache (Redis-backed when available).
    cache_key = None
    try:
        cv_hash = _stable_hash(cv_text)
        job_hash = _stable_hash(job_description)
        # Cache is language-aware to avoid returning English content on non-English UI.
        cache_key = f"analysis:{ANALYSIS_SCORE_VERSION}:{detected_lang}:{cv_hash}:{job_hash}"
    except Exception:
        cache_key = None

    # 1) Fast in-memory cache (works even when Redis is down)
    if cache_key:
        cached_entry = _analysis_mem_cache.get(cache_key)
        if cached_entry:
            cached_at, cached_result = cached_entry
            if (time.time() - cached_at) <= ANALYSIS_CACHE_TTL:
                return cached_result
            _analysis_mem_cache.pop(cache_key, None)

    # 2) Redis-backed cache
    redis_rate = redis_rate_client()
    if cache_key and redis_rate is not None:
        try:
            cached = redis_rate.get(cache_key)
        except Exception:
            cached = None
        if cached:
            try:
                decoded = json.loads(cached)
                _analysis_mem_cache[cache_key] = (time.time(), decoded)
                return decoded
            except Exception:
                # Ignore cache decode errors and continue with fresh pipeline
                pass

    _has_jd = bool(job_description and job_description.strip())
    cv_embedding = None
    job_embedding = None
    if _has_jd:
        cv_embedding = _get_embedding(cv_text)
        job_embedding = _get_embedding(job_description)

    # If embeddings fail, fall back to conservative defaults and mark
    warnings: list[str] = []
    embedding_failed = False
    if _has_jd and (not cv_embedding or not job_embedding):
        semantic_score = 0.0
        embedding_failed = True
        warnings.append(
            "Semantic analysis unavailable (embedding service offline). "
            "Scores are based on keyword matching only."
        )
    else:
        try:
            semantic_score = calculate_similarity(cv_embedding, job_embedding) * 100 if (_has_jd and cv_embedding and job_embedding) else 0.0
        except Exception:
            semantic_score = 0.0
    keyword_score = keyword_match_score(cv_text, job_description)

    skill_score, missing_skills = skill_coverage_score(cv_text, job_description)

    # Also extract detected skills from the CV for display
    from services.skill_service import extract_skills

    cv_skill_data = extract_skills(cv_text)
    detected_skills = sorted(cv_skill_data.get("found", set()))

    # Instrument skill detection for debugging. This emits a structured log
    # containing detected skills, missing skills and a short CV snippet when
    # either the score is zero or `SKILL_DEBUG` environment flag is enabled.
    try:
        SKILL_DEBUG = os.getenv("SKILL_DEBUG", "").lower() in ("1", "true", "yes")
        if SKILL_DEBUG or float(skill_score) == 0.0:
            snippet = (cv_text or "")[:1000].replace("\n", " ")
            logger.info(
                "skill_debug",
                extra={
                    "skill_score": skill_score,
                    "missing_skills": missing_skills,
                    "detected_skills": detected_skills,
                    "cv_text_snippet": snippet,
                },
            )
    except Exception:
        logger.exception("Failed to emit skill debug log")

    exp_score = experience_score(cv_text, job_description)

    # DOMAIN / INDUSTRY: only run embedding-backed classification when a real JD
    # and a job embedding are available. This avoids extra OpenAI retries when
    # embeddings are disabled, rate-limited, or unnecessary for CV-only scoring.
    if _has_jd and job_embedding:
        domain_data = detect_or_create_domain(job_description, job_embedding)
        domain_similarity = get_domain_similarity(domain_data["domain_id"], job_embedding)
        industry_data = detect_industry_and_specialization(job_description, job_embedding)
    else:
        domain_data = _fallback_domain_data()
        domain_similarity = 0.0
        industry_data = _fallback_industry_data(domain_data["domain_id"])

    # ATS DETAILS (detailed breakdown)
    ats_details = analyze_cv(cv_text, job_description, lang=detected_lang)
    ats_score = ats_details.get("overall_score", 0)

    # Keyword gap analysis for explainability
    keyword_gap = compute_keyword_gap(cv_text, job_description)
    keyword_gap_v2 = compare(cv_text, job_description)

    jd_skill_data = extract_skills(job_description)
    jd_skills = sorted(jd_skill_data.get("found", set()))
    jd_skill_set = {str(s).strip().lower() for s in jd_skills if str(s).strip()}
    jd_quality = _assess_job_description_quality(job_description, jd_skills)
    extra_skills = sorted([skill for skill in detected_skills if skill.lower() not in jd_skill_set])[:25]

    title_match = _title_match_score(cv_text, job_description)
    seniority_match = _seniority_match_score(cv_text, job_description)

    # FEATURES
    features = build_features(
        semantic_score,
        keyword_score,
        skill_score,
        exp_score,
        missing_skills,
        domain_similarity,
        ats_score,
        ats_details=ats_details,
        title_match=title_match,
        seniority_match=seniority_match,
        cv_text=cv_text,
        job_description=job_description,
    )

    try:
        prediction, confidence, risk_level, explanation = predict_match(features)
    except Exception as e:
        # If model runner failed, log and return conservative defaults
        print("Model prediction error:", str(e))
        prediction, confidence, risk_level, explanation = (
            50.0,
            50.0,
            "High Risk",
            {"error": str(e)},
        )

    # Direct ML score from singleton model (fast, no subprocess)
    try:
        ml_score = ml_predict_score(features)
    except Exception:
        ml_score = prediction * 100  # fallback to worker prediction (convert 0-1 to 0-100)

    # Hire classification model
    try:
        hire_decision, hire_probability = predict_hire(features)
    except Exception:
        hire_decision, hire_probability = False, 0.5

    recommendations = generate_recommendations(
        missing_skills, semantic_score, keyword_score, lang=detected_lang
    )

    content_score = float(ats_details.get("content", {}).get("content_score", 0.0))
    layout_score = float(ats_details.get("layout", {}).get("layout_score", 0.0))
    formatting_score_val = float(ats_details.get("layout", {}).get("formatting_score", 0.0))
    contact_score_val = float(ats_details.get("layout", {}).get("contact_score", 0.0))
    section_presence_val = float(ats_details.get("layout", {}).get("section_presence_score", 0.0))

    # Final score: rule-based 70% + ML 30% (real ATS simulation)
    # When no job description is provided, use ATS overall_score directly
    # since keyword/skill/semantic scores are meaningless without a JD target.
    from services.ats_service import compute_final_score
    breakdown = None
    if not _has_jd:
        final_score = round(float(ats_score), 2)
    else:
        # Request a debug breakdown from compute_final_score so we can
        # expose rule vs ML contributions for diagnostics.
        # Pass ML prediction confidence (if available) so ATS can decide
        # whether to trust the ML signal or prefer the rule-based score.
        ml_conf = None
        try:
            ml_conf = float(confidence) / 100.0 if confidence is not None else None
        except Exception:
            ml_conf = None

        breakdown = compute_final_score(
            keyword=keyword_score,
            section=section_presence_val,
            exp=exp_score,
            skills=skill_score,
            layout=formatting_score_val,
            contact=contact_score_val,
            ml_score=ml_score,
            ml_confidence=ml_conf,
            debug=True,
        )
        # `breakdown` is a dict with keys: final, rule_score, ml_score, ats_weight, model_weight
        final_score = round(float(breakdown.get("final", 0.0)), 2)
        # Propagate score confidence & input warnings from safeguard layer
        _sc = breakdown.get("score_confidence", 1.0)
        if _sc < 1.0:
            warnings.append(
                f"Score confidence reduced to {_sc} due to missing inputs: "
                + ", ".join(breakdown.get("input_warnings", []))
            )

    # ── ML Calibrator (optional blend) ────────────────────────────
    ml_calibration = None
    if bool(job_description and job_description.strip()):
        try:
            from services.ml_calibrator import predict_calibrated_score, blend_with_rule_score
            ml_pred = predict_calibrated_score(
                keyword_score=keyword_score,
                skill_score=skill_score,
                ats_score=ats_score,
                content_score=content_score,
                layout_score=layout_score,
                missing_count=len(missing_skills),
                cv_length=len(cv_text or ""),
                jd_length=len(job_description or ""),
            )
            if ml_pred is not None:
                final_score, ml_calibration = blend_with_rule_score(
                    rule_score=final_score,
                    ml_result=ml_pred,
                )
        except Exception:
            pass  # ML calibrator unavailable — use rule-based score

    interpretation = interpret_score_localized(final_score, detected_lang)

    # Localize risk level
    risk_level = localize_risk_level(risk_level, detected_lang)

    # If embeddings failed for this request, apply a conservative cap. The cap
    # remains configurable, but defaults to 40 so semantic outages cannot inflate
    # match scores.
    if embedding_failed:
        cap_val = os.getenv("EMBEDDING_CAP", "40")
        if cap_val:
            try:
                cap_num = float(cap_val)
                capped = min(final_score, cap_num)
                if capped != final_score:
                    final_score = capped
                    interpretation = interpret_score_localized(final_score, detected_lang)
            except Exception:
                # If env var is malformed, skip capping but note warning
                warnings.append("Embedding cap configured but invalid; skipping cap.")
        else:
            # No cap configured: keep final_score as computed, but warn
            warnings.append(
                "Embeddings unavailable; semantic signals disabled for this analysis."
            )

    if _has_jd and jd_quality.get("status") == "invalid":
        final_score = 0.0
        confidence = min(float(confidence or 0.0), 30.0)
        risk_level = localize_risk_level("High Risk", detected_lang)
        warnings.append(
            "Job description appears invalid or meaningless; match score is disabled until a real job description is provided."
        )
        if isinstance(breakdown, dict):
            breakdown["jd_quality_override"] = "invalid"
            breakdown["final"] = 0.0
    elif _has_jd and jd_quality.get("status") == "weak":
        weak_cap = float(os.getenv("WEAK_JD_MATCH_CAP", "45") or "45")
        if final_score > weak_cap:
            final_score = round(weak_cap, 2)
            warnings.append(
                "Job description is too short for reliable matching; match score was capped. Add responsibilities, required skills, seniority, and role context."
            )
            if isinstance(breakdown, dict):
                breakdown["jd_quality_override"] = "weak_cap"
                breakdown["final"] = final_score

    interpretation = interpret_score_localized(final_score, detected_lang)

    # ATS config-based composite score
    ats_weights = get_ats_weights()
    score_breakdown = {
        "skills": round(float(skill_score), 2),
        "keywords": round(float(keyword_score), 2),
        "format": float(ats_details["layout"].get("formatting_score", 0.0)),
        "experience": round(float(exp_score), 2),
    }
    total_w = sum(ats_weights.values()) or 1.0
    ats_weighted_score = 0.0
    for key, value in score_breakdown.items():
        w = float(ats_weights.get(key, 0.0))
        ats_weighted_score += value * w
    ats_weighted_score = round(float(ats_weighted_score / total_w), 2)

    # ── Score Decomposition ──────────────────────────────────────────
    # Separate "CV quality" (structural) from "job match" (relevance).
    # This prevents misleading UX where a chef's CV scores 71 against a dev JD
    # because the CV is well-structured, even though relevance is near zero.
    if _has_jd:
        # Job match: keyword + skill + semantic + seniority (content relevance)
        _job_match = round(min(100.0, max(0.0,
            keyword_score * 0.35
            + skill_score * 0.25
            + semantic_score * 0.25
            + seniority_match * 0.15
        )), 2)
        # ATS quality: structural quality independent of JD
        _ats_quality = round(min(100.0, max(0.0, float(ats_score))), 2)
        # Interpretation text
        if _job_match >= 70:
            _decomp_text = "Strong match for this role"
        elif _job_match >= 40:
            _decomp_text = "Partial match — some skills align"
        else:
            _decomp_text = "CV is well-structured but not aligned with this role"
        if jd_quality.get("status") == "invalid":
            _job_match = 0.0
            _decomp_text = "Job description is invalid - enter a real role description to calculate match"
    else:
        _job_match = 0.0
        _ats_quality = round(min(100.0, max(0.0, float(ats_score))), 2)
        _decomp_text = "No job description provided — showing CV quality only"

    score_decomposition = {
        "overall_score": final_score,
        "ats_quality": _ats_quality,
        "job_match": _job_match,
        "interpretation": _decomp_text,
    }

    result = {
        "semantic_score": round(semantic_score, 2),
        "keyword_score": keyword_score,
        "skill_score": skill_score,
        "experience_score": exp_score,
        "ats_score": ats_score,
        "ml_score": ml_score,
        "soft_skills_score": round(features[25], 2),
        "content_score": round(content_score, 2),
        "layout_score": round(layout_score, 2),
        "ats": ats_details,
        "domain_similarity": round(domain_similarity, 2),
        "detected_skills": detected_skills,
        "job_skills": jd_skills,
        "missing_skills": missing_skills,
        "extra_skills": extra_skills,
        "keyword_gap": keyword_gap,
        "keyword_gap_v2": keyword_gap_v2,
        "title_match": title_match,
        "seniority_match": seniority_match,
        "final_score": final_score,
        "interpretation": interpretation,
        "confidence": float(confidence),
        "risk_level": risk_level,
        "hire_decision": hire_decision,
        "hire_probability": hire_probability,
        "detected_language": detected_lang,
        "explanation": explanation,
        "recommendations": recommendations,
        "domain": domain_data,
        "industry": industry_data,
        "specialization": {
            "id": industry_data["specialization_id"],
            "name": industry_data["specialization_name"],
        },
        "score_breakdown": score_breakdown,
        "final_score_breakdown": breakdown,
        "ats_weights": ats_weights,
        "ats_weighted_score": ats_weighted_score,
        "embedding_available": not embedding_failed,
        "score_decomposition": score_decomposition,
        "ml_calibration": ml_calibration,
        "job_description_quality": jd_quality,
        "score_version": ANALYSIS_SCORE_VERSION,
    }

    # ── Score Suggestions (actionable improvement tips) ────────────
    if _has_jd and jd_quality.get("status") != "invalid":
        from services.ats_service import generate_score_suggestions
        result["score_suggestions"] = generate_score_suggestions(
            missing_skills=missing_skills,
            keyword_gap=keyword_gap,
            keyword_score=keyword_score,
            skill_score=skill_score,
            final_score=final_score,
            total_jd_skills=len(jd_skills),
            lang=detected_lang,
        )
    else:
        result["score_suggestions"] = []

    # Language detection fallback warning
    if lang_detection_fallback:
        warnings.append(
            "Language could not be confidently detected; defaulting to English. "
            "You can set the 'lang' parameter explicitly for better results."
        )

    # Job description quality warning
    jd_stripped = (job_description or "").strip()
    if jd_stripped and len(jd_stripped.split()) < 15:
        warnings.append(
            "Job description is very short (fewer than 15 words). "
            "A detailed job description improves matching accuracy."
        )

    if warnings:
        result["warnings"] = warnings

    result["match_score_v2"] = _build_match_score_v2(result, keyword_gap_v2)
    if _has_jd and jd_quality.get("status") == "invalid":
        result["match_score_v2"]["match_score"] = 0.0
        result["match_score_v2"]["weak_signals"] = list(result["match_score_v2"].get("weak_signals") or []) + [
            "Invalid job description"
        ]
    elif _has_jd and jd_quality.get("status") == "weak":
        result["match_score_v2"]["match_score"] = min(
            float(result["match_score_v2"].get("match_score") or 0.0),
            float(final_score),
        )

    # Store analysis result in Redis cache for subsequent identical requests.
    if cache_key:
        _analysis_mem_cache[cache_key] = (time.time(), result)

    redis_rate = redis_rate_client()
    if cache_key and redis_rate is not None:
        try:
            redis_rate.setex(cache_key, ANALYSIS_CACHE_TTL, json.dumps(result))
        except Exception:
            pass

    return result

# =====================================================
# TEXT ANALYZE
# =====================================================


# Analysis routes moved to routes/analysis.py


# Dashboard, favorites, sharing, benchmark, and usage routes moved to routes/dashboard.py


# User data, retention, reminder, and specialization routes moved to routes/user_data.py


