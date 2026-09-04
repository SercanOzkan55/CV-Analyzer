"""Keyword-match criterion (ported from services/keyword_service.py).

Only ``keyword_match_score`` and the private helpers it needs are ported.
The source file's semantic-similarity fallback (an ``except`` block that
imports ``services.embedding_service`` and calls OpenAI-backed embeddings)
is intentionally **not** ported — the Local Worker is fully offline with
zero network dependency, so that code path is dead weight here, not a
safe no-op to keep around.
"""

import os
import re
import difflib

# Stop words to filter out from keyword matching (inflates scores otherwise)
STOP_WORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
        "by", "from", "as", "is", "it", "be", "are", "was", "were", "been", "being", "have",
        "has", "had", "do", "does", "did", "will", "would", "shall", "should", "may", "might",
        "can", "could", "not", "no", "so", "if", "then", "than", "that", "this", "these",
        "those", "i", "we", "you", "he", "she", "they", "me", "us", "him", "her", "them",
        "my", "our", "your", "his", "its", "their", "what", "which", "who", "whom", "how",
        "when", "where", "why", "all", "each", "every", "both", "few", "more", "most",
        "other", "some", "such", "only", "own", "same", "too", "very", "just", "about",
        "above", "after", "before", "between", "into", "through", "during", "out", "up",
        "down", "over", "under", "again", "further", "once", "also", "any", "etc", "ie",
        "eg", "able", "using", "work", "working", "including", "must", "well", "new", "use",
        "used", "good", "need", "based", "role", "team", "strong", "ensure", "within",
        "across", "years", "year", "experience", "looking", "join", "seeking", "responsible",
        "responsibilities", "required", "requirements", "preferred", "qualifications",
        "position", "company", "apply",
        # ── TR common stop words ──
        "ve", "ile", "bir", "bu", "için", "da", "de", "den", "olan", "olarak", "gibi",
        "daha", "çok", "her", "hem", "ya", "veya", "ama", "ancak", "ise",
        # ── FR common stop words ──
        "le", "la", "les", "un", "une", "des", "du", "et", "en", "est", "que", "qui",
        "dans", "pour", "pas", "sur", "avec", "ce", "il", "elle", "nous", "vous", "sont",
        "aux", "par", "au", "plus", "ou", "ont", "son", "ses", "mais", "comme", "tout",
        "faire", "été", "dit", "même", "entre", "après", "aussi",
        # ── DE common stop words ──
        "der", "die", "das", "ein", "eine", "und", "ist", "ich", "nicht", "sie", "es",
        "wir", "mir", "mit", "sich", "auf", "dem", "den", "hat", "auch", "noch", "nach",
        "bei", "aus", "wenn", "nur", "als", "um", "wie", "man", "aber", "dann", "sein",
        "schon", "hier", "zum", "zur", "vom", "über", "vor", "unter", "durch", "oder",
        "ohne", "bis", "gegen", "seit", "zwischen",
        # ── ES common stop words ──
        "el", "los", "del", "al", "es", "que", "en", "por", "con", "una", "se", "no",
        "lo", "más", "las", "como", "pero", "sus", "ser", "ya", "fue", "sin", "sobre",
        "entre", "cuando", "muy", "donde", "hay", "desde", "todo", "esta", "hasta", "porque",
    }
)

# ── TF-IDF: Common JD filler words ──────────────────────────────────
COMMON_JD_FILLER = frozenset(
    {
        "skills", "knowledge", "ability", "proficiency", "familiarity", "understanding",
        "background", "expertise", "competency", "develop", "developing", "development",
        "developer", "build", "building", "create", "creating", "implement", "design",
        "designing", "manage", "managing", "management", "lead", "leading", "leadership",
        "support", "supporting", "maintain", "maintaining", "maintenance", "collaborate",
        "collaboration", "communicate", "communication", "analyze", "analysis", "analytical",
        "evaluate", "evaluation", "improve", "improving", "improvement", "optimize",
        "optimization", "deliver", "delivering", "delivery", "project", "projects",
        "product", "products", "business", "client", "clients", "customer", "customers",
        "stakeholder", "stakeholders", "process", "processes", "system", "systems",
        "environment", "platform", "solution", "solutions", "strategy", "strategic",
        "planning", "plan", "report", "reporting", "documentation", "document", "training",
        "mentor", "mentoring", "performance", "quality", "standard", "standards", "senior",
        "junior", "mid", "level", "minimum", "preferred", "desired", "ideal", "opportunity",
        "candidate", "applicant", "salary", "benefits", "remote", "hybrid", "onsite", "full",
        "time", "part", "contract", "permanent", "degree", "bachelor", "master", "phd",
        "certification", "excellent", "proven", "demonstrated", "hands", "relevant",
        "related", "similar", "equivalent", "fast", "paced", "dynamic", "agile", "problem",
        "solving", "critical", "thinking", "detail", "oriented", "self", "motivated",
        "passionate", "driven", "proactive",
    }
)


def _idf_weight(word: str) -> float:
    """Return an IDF-like weight for a keyword.

    - Common JD filler words -> 0.3 (low signal)
    - Normal domain words -> 1.0 (standard)
    - Technical terms with special chars (#, +, digits) -> 1.5 (high signal)
    """
    w = word.lower()
    if w in COMMON_JD_FILLER:
        return 0.3
    if re.search(r"[#+\d.]", w):
        return 1.5
    return 1.0


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    s = text.lower()
    s = s.replace("/", " ").replace("\\", " ")
    s = re.sub(r"[-_]+", " ", s)
    s = re.sub(r"[^\w\s#+.]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_meaningful_words(text: str) -> set:
    """Extract words filtering out stop words and very short tokens."""
    if not text:
        return set()

    text = _normalize_text(text)
    words = set(re.findall(r"\b\w[\w#+.]*\b", text, re.UNICODE))

    out: set[str] = set()
    for w in words:
        if w in STOP_WORDS or len(w) <= 1:
            continue
        if w == "oop":
            out.add("object-oriented")
            out.add("object oriented")
        elif w == "js":
            out.add("javascript")
        else:
            out.add(w)

    return out


def _extract_phrases(text: str, max_len: int = 3) -> set:
    """Extract meaningful multi-word phrases (bigrams/trigrams) from text."""
    text = _normalize_text(text)
    words = re.findall(r"\b\w[\w#+.]*\b", text, re.UNICODE)
    phrases = set()
    for n in range(2, max_len + 1):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i : i + n])
            non_stop = [w for w in words[i : i + n] if w not in STOP_WORDS]
            if len(non_stop) >= n - 1:
                phrases.add(phrase)
    return phrases


def _best_fuzzy_match(target: str, candidates: set, cutoff: float) -> str | None:
    if not candidates:
        return None
    try:
        matches = difflib.get_close_matches(target, list(candidates), n=1, cutoff=cutoff)
        return matches[0] if matches else None
    except Exception:
        return None


def keyword_match_score(cv_text: str, job_description: str) -> float:
    """Calculate keyword match score between CV and job description.

    Uses stop-word filtering and phrase matching for accuracy, with
    TF-IDF-like weighting (JD filler words count less than technical
    terms) and adaptive word/phrase weighting for long job descriptions.
    """
    if not job_description or not job_description.strip():
        return 0.0

    cv_words = _extract_meaningful_words(cv_text)
    job_words = _extract_meaningful_words(job_description)

    if not job_words:
        return 0.0

    fuzzy_cutoff = float(os.getenv("FUZZY_MATCH_THRESHOLD", 0.8))
    matched: set[str] = set()
    for jw in job_words:
        if jw in cv_words:
            matched.add(jw)
            continue
        fm = _best_fuzzy_match(jw, cv_words, fuzzy_cutoff)
        if fm:
            matched.add(jw)

    idf_enabled = os.getenv("TFIDF_ENABLED", "1") != "0"
    if idf_enabled:
        total_weight = 0.0
        matched_weight = 0.0
        for jw in job_words:
            w = _idf_weight(jw)
            total_weight += w
            if jw in matched:
                matched_weight += w
        word_score = matched_weight / total_weight if total_weight > 0 else 0.0
    else:
        word_score = len(matched) / len(job_words)

    cv_phrases = _extract_phrases(cv_text)
    job_phrases = _extract_phrases(job_description)

    max_phrases = int(os.getenv("MAX_JD_PHRASES", 30))
    if len(job_phrases) > max_phrases:
        job_phrases = set(sorted(job_phrases, key=lambda phrase: (-len(phrase), phrase))[:max_phrases])

    phrase_matches = set()
    phrase_cutoff = float(os.getenv("PHRASE_FUZZY_THRESHOLD", 0.75))
    if job_phrases:
        for jp in job_phrases:
            if jp in cv_phrases:
                phrase_matches.add(jp)
                continue
            for cp in cv_phrases:
                try:
                    ratio = difflib.SequenceMatcher(None, jp, cp).ratio()
                except Exception:
                    ratio = 0.0
                if ratio >= phrase_cutoff:
                    phrase_matches.add(jp)
                    break

        phrase_score = len(phrase_matches) / len(job_phrases)
    else:
        phrase_score = 0.0

    jd_word_count = len(job_words)
    if jd_word_count <= 20:
        word_weight, phrase_weight = 0.60, 0.40
    elif jd_word_count >= 50:
        word_weight, phrase_weight = 0.80, 0.20
    else:
        ratio = (jd_word_count - 20) / 30.0
        word_weight = 0.60 + ratio * 0.20
        phrase_weight = 0.40 - ratio * 0.20

    score = (word_weight * word_score + phrase_weight * phrase_score) * 100

    return round(min(100.0, score), 2)
