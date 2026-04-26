import os
import re
import difflib

# Stop words to filter out from keyword matching (inflates scores otherwise)
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "it",
        "be",
        "are",
        "was",
        "were",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "can",
        "could",
        "not",
        "no",
        "so",
        "if",
        "then",
        "than",
        "that",
        "this",
        "these",
        "those",
        "i",
        "we",
        "you",
        "he",
        "she",
        "they",
        "me",
        "us",
        "him",
        "her",
        "them",
        "my",
        "our",
        "your",
        "his",
        "its",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "how",
        "when",
        "where",
        "why",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "only",
        "own",
        "same",
        "too",
        "very",
        "just",
        "about",
        "above",
        "after",
        "before",
        "between",
        "into",
        "through",
        "during",
        "out",
        "up",
        "down",
        "over",
        "under",
        "again",
        "further",
        "once",
        "also",
        "any",
        "etc",
        "ie",
        "eg",
        "able",
        "using",
        "work",
        "working",
        "including",
        "must",
        "well",
        "new",
        "use",
        "used",
        "good",
        "need",
        "based",
        "role",
        "team",
        "strong",
        "ensure",
        "within",
        "across",
        "years",
        "year",
        "experience",
        "looking",
        "join",
        "seeking",
        "responsible",
        "responsibilities",
        "required",
        "requirements",
        "preferred",
        "qualifications",
        "position",
        "company",
        "apply",
        # ── TR common stop words ──
        "ve", "ile", "bir", "bu", "için", "da", "de", "den",
        "olan", "olarak", "gibi", "daha", "çok", "her", "hem",
        "ya", "veya", "ama", "ancak", "ise", "olan", "olan",
        # ── FR common stop words ──
        "le", "la", "les", "un", "une", "des", "du", "de",
        "et", "en", "est", "que", "qui", "dans", "pour",
        "pas", "sur", "avec", "ce", "il", "elle", "nous",
        "vous", "sont", "aux", "par", "au", "plus", "ou",
        "ont", "son", "ses", "mais", "comme", "tout", "faire",
        "été", "dit", "même", "entre", "après", "aussi",
        # ── DE common stop words ──
        "der", "die", "das", "ein", "eine", "und", "ist",
        "ich", "nicht", "sie", "es", "wir", "mir", "mit",
        "sich", "auf", "dem", "den", "hat", "auch", "noch",
        "nach", "bei", "aus", "wenn", "nur", "als", "um",
        "wie", "man", "aber", "dann", "sein", "schon", "hier",
        "zum", "zur", "vom", "über", "vor", "unter", "durch",
        "oder", "ohne", "bis", "gegen", "seit", "zwischen",
        # ── ES common stop words ──
        "el", "los", "del", "al", "es", "que", "en",
        "por", "con", "una", "se", "no", "lo", "más",
        "las", "como", "pero", "sus", "ser", "ya", "fue",
        "sin", "sobre", "entre", "cuando", "muy", "donde",
        "hay", "desde", "todo", "esta", "hasta", "porque",
        # ── PT common stop words ──
        "os", "das", "dos", "não", "uma", "como", "mais",
        "mas", "seu", "sua", "seus", "suas", "nos", "nas",
        "pelo", "pela", "pelos", "pelas", "tem", "pode",
        "são", "está", "foi", "ser", "ter", "isso", "esse",
        "essa", "esta", "esses", "estas", "aqui", "ali",
        # ── IT common stop words ──
        "il", "gli", "lo", "della", "delle", "dello",
        "dei", "degli", "che", "non", "una", "per",
        "con", "sono", "nel", "nella", "nei", "nelle",
        "dal", "dalla", "dai", "dalle", "sul", "sulla",
        "sui", "sulle", "tra", "fra", "ma", "anche",
        "come", "più", "ancora", "già", "poi",
        # ── NL common stop words ──
        "het", "een", "van", "op", "dat", "niet",
        "met", "ook", "zijn", "wordt", "naar", "bij",
        "nog", "wel", "maar", "als", "dan", "wat",
        "hier", "daar", "dit", "deze", "die", "hun",
        # ── PL common stop words ──
        "nie", "tak", "jest", "się", "jak", "ale",
        "już", "czy", "tylko", "ten", "tego", "tym",
        "tej", "tych", "przez", "przy", "czyli", "gdzie",
        "więc", "jeszcze", "oraz", "może",
        # ── SV common stop words ──
        "och", "att", "det", "som", "för", "med",
        "har", "till", "av", "var", "den", "kan",
        "ska", "inte", "ett", "men", "hans", "sin",
        # ── ID common stop words ──
        "dan", "yang", "ini", "itu", "dengan", "untuk",
        "dari", "pada", "adalah", "akan", "tidak", "juga",
        "telah", "oleh", "ke", "sudah", "dapat", "saya",
        # ── VI common stop words ──
        "và", "của", "là", "cho", "các", "được",
        "trong", "có", "để", "này", "đã",
        "những", "một", "về", "với", "từ",
    }
)

# ── TF-IDF: Common JD filler words ──────────────────────────────────
# These words appear in nearly every job description and carry very
# little signal about the actual role. They get LOW IDF weight (0.3).
# Technical/domain terms not in this set get HIGH weight (1.0–1.5).
COMMON_JD_FILLER = frozenset({
    "skills", "knowledge", "ability", "proficiency", "familiarity",
    "understanding", "background", "expertise", "competency",
    "develop", "developing", "development", "developer",
    "build", "building", "create", "creating", "implement",
    "design", "designing", "manage", "managing", "management",
    "lead", "leading", "leadership", "support", "supporting",
    "maintain", "maintaining", "maintenance",
    "collaborate", "collaboration", "communicate", "communication",
    "analyze", "analysis", "analytical", "evaluate", "evaluation",
    "improve", "improving", "improvement", "optimize", "optimization",
    "deliver", "delivering", "delivery",
    "project", "projects", "product", "products",
    "business", "client", "clients", "customer", "customers",
    "stakeholder", "stakeholders",
    "process", "processes", "system", "systems",
    "environment", "platform", "solution", "solutions",
    "strategy", "strategic", "planning", "plan",
    "report", "reporting", "documentation", "document",
    "training", "mentor", "mentoring",
    "performance", "quality", "standard", "standards",
    "senior", "junior", "mid", "level",
    "minimum", "preferred", "desired", "ideal",
    "opportunity", "candidate", "applicant",
    "salary", "benefits", "remote", "hybrid", "onsite",
    "full", "time", "part", "contract", "permanent",
    "degree", "bachelor", "master", "phd", "certification",
    "excellent", "proven", "demonstrated", "hands",
    "relevant", "related", "similar", "equivalent",
    "fast", "paced", "dynamic", "agile",
    "problem", "solving", "critical", "thinking",
    "detail", "oriented", "self", "motivated",
    "passionate", "driven", "proactive",
})


def _idf_weight(word: str) -> float:
    """Return an IDF-like weight for a keyword.

    - Common JD filler words → 0.3 (low signal)
    - Normal domain words → 1.0 (standard)
    - Technical terms with special chars (#, +, digits) → 1.5 (high signal)
      Examples: c#, c++, python3, node.js, h2o
    """
    w = word.lower()
    if w in COMMON_JD_FILLER:
        return 0.3
    # Technical terms: contain digits, #, + or . (like "c#", "node.js", "python3")
    if re.search(r"[#+\d.]", w):
        return 1.5
    return 1.0


def _extract_meaningful_words(text: str) -> set:
    """Extract words filtering out stop words and very short tokens.

    Performs light normalization so that common separators ("-", "/") and
    case differences don't cause missed matches. Also adds small expansions
    (e.g. `oop` -> `object-oriented`) to improve coverage.
    """
    if not text:
        return set()

    # Normalize: lowercase, replace separators with spaces, collapse punctuation
    text = _normalize_text(text)

    # Keep # and + and . inside tokens; hyphens/underscores already replaced
    words = set(re.findall(r"\b\w[\w#+.]*\b", text, re.UNICODE))

    out: set[str] = set()
    for w in words:
        if w in STOP_WORDS or len(w) <= 1:
            continue
        # Small expansions / synonym handling
        if w == "oop":
            out.add("object-oriented")
            out.add("object oriented")
        elif w == "js":
            out.add("javascript")
        else:
            out.add(w)

    return out


def _token_freq(text: str) -> dict[str, int]:
    text = _normalize_text(str(text or ""))
    tokens = re.findall(r"\b\w[\w#+.]*\b", text, re.UNICODE)
    freq: dict[str, int] = {}
    for token in tokens:
        if token in STOP_WORDS or len(token) <= 1:
            continue
        freq[token] = freq.get(token, 0) + 1
    return freq


def _extract_phrases(text: str, max_len: int = 3) -> set:
    """Extract meaningful multi-word phrases (bigrams/trigrams) from text."""
    text = _normalize_text(text)
    words = re.findall(r"\b\w[\w#+.]*\b", text, re.UNICODE)
    phrases = set()
    for n in range(2, max_len + 1):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i : i + n])
            # Only keep phrases that aren't all stop words
            non_stop = [w for w in words[i : i + n] if w not in STOP_WORDS]
            if len(non_stop) >= n - 1:
                phrases.add(phrase)
    return phrases


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    s = text.lower()
    # Replace common separators that break tokens (keep #, +, .)
    s = s.replace("/", " ").replace("\\", " ")
    s = re.sub(r"[-_]+", " ", s)
    # Remove any stray punctuation except word chars, whitespace, #, +, .
    s = re.sub(r"[^\w\s#+.]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _best_fuzzy_match(target: str, candidates: set, cutoff: float) -> str | None:
    if not candidates:
        return None
    try:
        matches = difflib.get_close_matches(target, list(candidates), n=1, cutoff=cutoff)
        return matches[0] if matches else None
    except Exception:
        return None


def compute_keyword_gap(cv_text: str, job_description: str) -> dict:
    """Return which job keywords/phrases are missing from the CV.

    This uses the same tokenization and stop-word filtering as
    `keyword_match_score` so that the gap aligns with the score.
    """

    if not job_description or not job_description.strip():
        return {"missing_words": [], "missing_phrases": []}

    cv_words = _extract_meaningful_words(cv_text)
    job_words = _extract_meaningful_words(job_description)

    # Simple exact-miss list
    missing_words = sorted(w for w in job_words if w not in cv_words)

    # Attempt fuzzy promotion of near-misses so suggestions are actionable
    fuzzy_cutoff = float(os.getenv("FUZZY_MATCH_THRESHOLD", 0.8))
    adjusted_missing: list[str] = []
    for w in missing_words:
        if _best_fuzzy_match(w, cv_words, fuzzy_cutoff):
            # treat as weak match (skip from missing list)
            continue
        adjusted_missing.append(w)

    cv_phrases = _extract_phrases(cv_text)
    job_phrases = _extract_phrases(job_description)
    missing_phrases = sorted(p for p in job_phrases if p not in cv_phrases)

    return {
        "missing_words": adjusted_missing,
        "missing_phrases": missing_phrases,
    }


def compare(cv_text: str, job_description: str) -> dict:
    """Keyword gap detector v2 used by match-score and UI explainability.

    Returns:
      - missing_keywords: required keywords in JD absent in CV
      - weak_keywords: present but low-frequency in CV
      - strong_keywords: present and repeated in CV
      - suggested_keywords: shortlist to improve ATS score
      - extra_keywords: CV keywords not present in JD
      - keyword_coverage_pct: percentage of JD keywords covered by CV
    """

    if not str(job_description or "").strip():
        return {
            "missing_keywords": [],
            "weak_keywords": [],
            "strong_keywords": [],
            "suggested_keywords": [],
            "extra_keywords": [],
            "keyword_coverage_pct": 0.0,
        }

    cv_words = _extract_meaningful_words(cv_text)
    job_words = _extract_meaningful_words(job_description)
    cv_freq = _token_freq(cv_text)

    if not job_words:
        return {
            "missing_keywords": [],
            "weak_keywords": [],
            "strong_keywords": [],
            "suggested_keywords": [],
            "extra_keywords": sorted(cv_words)[:25],
            "keyword_coverage_pct": 0.0,
        }

    strong_keywords: list[str] = []
    weak_keywords: list[str] = []
    missing_keywords: list[str] = []

    for keyword in sorted(job_words):
        if keyword not in cv_words:
            missing_keywords.append(keyword)
            continue
        count = int(cv_freq.get(keyword, 0))
        if count >= 2:
            strong_keywords.append(keyword)
        else:
            weak_keywords.append(keyword)

    covered = len(job_words) - len(missing_keywords)
    coverage = round((covered / max(1, len(job_words))) * 100.0, 2)

    extra_keywords = sorted([w for w in cv_words if w not in job_words])

    # Fuzzy-match some of the missing keywords - treat them as weak signals
    fuzzy_cutoff = float(os.getenv("FUZZY_MATCH_THRESHOLD", 0.8))
    final_missing: list[str] = []
    for kw in missing_keywords:
        match = _best_fuzzy_match(kw, cv_words, fuzzy_cutoff)
        if match:
            weak_keywords.append(kw)
        else:
            final_missing.append(kw)
    missing_keywords = final_missing

    suggested_keywords = []
    for item in missing_keywords:
        suggested_keywords.append(item)
        if len(suggested_keywords) >= 15:
            break
    if len(suggested_keywords) < 15:
        for item in weak_keywords:
            suggested_keywords.append(item)
            if len(suggested_keywords) >= 15:
                break

    return {
        "missing_keywords": missing_keywords,
        "weak_keywords": weak_keywords,
        "strong_keywords": strong_keywords,
        "suggested_keywords": suggested_keywords,
        "extra_keywords": extra_keywords[:25],
        "keyword_coverage_pct": coverage,
    }


def keyword_match_score(cv_text: str, job_description: str) -> float:
    """
    Calculate keyword match score between CV and job description.
    Uses stop-word filtering and phrase matching for accuracy.

    Adaptive weighting: when the JD is long (many unique words), the phrase
    component's denominator grows disproportionately, penalizing candidates
    unfairly.  We shift weight from phrases to words for long JDs to counter
    this bias.

    Phrase cap: JD phrases are capped at MAX_PHRASES (configurable via env
    ``MAX_JD_PHRASES``) to bound computation and prevent dilution.
    """
    if not job_description or not job_description.strip():
        return 0.0

    # Single word matching (filtered) with fuzzy fallback
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
        # fuzzy token-level matches
        fm = _best_fuzzy_match(jw, cv_words, fuzzy_cutoff)
        if fm:
            matched.add(jw)

    # ── TF-IDF weighted scoring ──────────────────────────────────────
    # Instead of simple count ratio (matched/total), weight each keyword
    # by its specificity. Common JD filler words get LOW weight, while
    # domain-specific technical terms get HIGH weight.
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

    # Phrase matching (bigrams/trigrams) — rewards matching multi-word terms
    cv_phrases = _extract_phrases(cv_text)
    job_phrases = _extract_phrases(job_description)

    # Cap JD phrases to prevent denominator inflation on long JDs
    max_phrases = int(os.getenv("MAX_JD_PHRASES", 30))
    if len(job_phrases) > max_phrases:
        # Keep the most distinctive phrases (shortest = most specific)
        job_phrases = set(sorted(job_phrases, key=len)[:max_phrases])

    phrase_matches = set()
    phrase_cutoff = float(os.getenv("PHRASE_FUZZY_THRESHOLD", 0.75))
    if job_phrases:
        for jp in job_phrases:
            if jp in cv_phrases:
                phrase_matches.add(jp)
                continue
            # fuzzy compare against CV phrases
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

    # Adaptive weighting: shift weight from phrases to words for long JDs
    # Short JDs (<= 20 unique words): 60/40 word/phrase
    # Long JDs (>= 50 unique words): 80/20 word/phrase
    jd_word_count = len(job_words)
    if jd_word_count <= 20:
        word_weight, phrase_weight = 0.60, 0.40
    elif jd_word_count >= 50:
        word_weight, phrase_weight = 0.80, 0.20
    else:
        # Linear interpolation between 60/40 and 80/20
        ratio = (jd_word_count - 20) / 30.0
        word_weight = 0.60 + ratio * 0.20
        phrase_weight = 0.40 - ratio * 0.20

    score = (word_weight * word_score + phrase_weight * phrase_score) * 100

    # ── Semantic similarity (fallback-only mode) ────────────────────
    # Semantic is used ONLY when keyword score is low (< 40).
    # When keywords match well, semantic adds noise (double counting risk).
    # When keywords are weak, semantic rescues "same meaning, different words".
    _sem_threshold = float(os.getenv("SEMANTIC_FALLBACK_THRESHOLD", 40))
    _sem_enabled = os.getenv("SEMANTIC_BLEND_WEIGHT", "0.3") != "0"
    if _sem_enabled and score < _sem_threshold:
        try:
            from services.embedding_service import get_embedding, calculate_similarity
            cv_emb = get_embedding(cv_text)
            jd_emb = get_embedding(job_description)
            if cv_emb and jd_emb:
                sem_score = calculate_similarity(cv_emb, jd_emb) * 100
                # 50/50 blend when keyword is weak — semantic is a rescue signal
                score = 0.5 * score + 0.5 * sem_score
        except Exception:
            pass  # Embeddings unavailable — use pure keyword score

    return round(min(100.0, score), 2)
