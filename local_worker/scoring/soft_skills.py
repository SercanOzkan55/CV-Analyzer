"""Soft-skills criterion, ported from services/pipeline_runtime.py.

Ports ``_SOFT_SKILL_TERMS`` (~line 218-309) and the phrase-matching logic
around it (``_contains_soft_skill`` / ``_phrase_pattern``, ~line 326-336),
plus the combining formula used in ``build_features`` (~line 444-446):
``min(100, (hits / len(terms)) * 300)`` — i.e. finding a third of the
terms already saturates the score at 100.
"""

import re

_SOFT_SKILL_TERMS = {
    # English
    "leadership", "teamwork", "communication", "collaboration", "problem solving",
    "time management", "critical thinking", "adaptability", "creativity", "mentoring",
    "negotiation", "presentation", "stakeholder", "cross functional", "strategic",
    "initiative", "empathy", "conflict resolution",
    # Turkish
    "liderlik", "takım çalışması", "takim calismasi", "iletişim", "iletisim",
    "iş birliği", "is birligi", "problem çözme", "problem cozme", "zaman yönetimi",
    "zaman yonetimi", "eleştirel düşünme", "elestirel dusunme", "uyum sağlama",
    "uyum saglama", "yaratıcılık", "yaraticilik", "mentorluk", "müzakere", "muzakere",
    "sunum", "paydaş", "paydas", "stratejik", "inisiyatif", "empati",
    "çatışma çözümü", "catisma cozumu",
    # German
    "führung", "fuhrung", "teamarbeit", "kommunikation", "zusammenarbeit",
    "problemlösung", "problemlosung", "zeitmanagement", "kritisches denken",
    "anpassungsfähigkeit", "kreativität", "verhandlung", "präsentation",
    # French
    "travail d'équipe", "travail equipe", "résolution de problèmes",
    "resolution de problemes", "gestion du temps", "pensée critique", "adaptabilité",
    "créativité",
    # Spanish
    "liderazgo", "trabajo en equipo", "comunicación", "comunicacion", "colaboración",
    "colaboracion", "resolución de problemas", "resolucion de problemas",
    "gestión del tiempo", "gestion del tiempo", "pensamiento crítico",
    "pensamiento critico", "adaptabilidad", "creatividad",
}


def clean_lower(text: str) -> str:
    """Locale-independent lowercasing (mirrors language_service.clean_lower)."""
    if not text:
        return ""
    text = text.replace("İ", "i")
    lowered = text.lower()
    lowered = lowered.replace("i̇", "i").replace("i̇", "i")
    return lowered


def _phrase_pattern(term: str) -> str:
    return r"(?<!\w)" + re.escape(clean_lower(term)).replace(r"\ ", r"\s+") + r"(?!\w)"


def _contains_soft_skill(text: str, term: str) -> bool:
    return bool(re.search(_phrase_pattern(term), text))


def soft_skills_score(cv_text: str) -> float:
    """Score 0-100 based on how many distinct soft-skill terms appear in the CV."""
    cv_lower = clean_lower(cv_text or "")
    hits = sum(1 for term in _SOFT_SKILL_TERMS if _contains_soft_skill(cv_lower, term))
    score = min(100.0, (hits / max(len(_SOFT_SKILL_TERMS), 1)) * 300)
    return round(score, 2)
