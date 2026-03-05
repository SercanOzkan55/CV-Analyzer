import re

# Stop words to filter out from keyword matching (inflates scores otherwise)
STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "it", "be", "are", "was",
    "were", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "may", "might", "can", "could",
    "not", "no", "so", "if", "then", "than", "that", "this", "these",
    "those", "i", "we", "you", "he", "she", "they", "me", "us", "him",
    "her", "them", "my", "our", "your", "his", "its", "their", "what",
    "which", "who", "whom", "how", "when", "where", "why", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such",
    "only", "own", "same", "too", "very", "just", "about", "above",
    "after", "before", "between", "into", "through", "during", "out",
    "up", "down", "over", "under", "again", "further", "once", "also",
    "any", "etc", "ie", "eg", "able", "using", "work", "working",
    "including", "must", "well", "new", "use", "used", "good", "need",
    "based", "role", "team", "strong", "ensure", "within", "across",
    "years", "year", "experience", "looking", "join", "seeking",
    "responsible", "responsibilities", "required", "requirements",
    "preferred", "qualifications", "position", "company", "apply",
})


def _extract_meaningful_words(text: str) -> set:
    """Extract words filtering out stop words and very short tokens."""
    words = set(re.findall(r'\b[a-zA-Z][\w#+.-]*\b', text.lower()))
    return {w for w in words if w not in STOP_WORDS and len(w) > 1}


def _extract_phrases(text: str, max_len: int = 3) -> set:
    """Extract meaningful multi-word phrases (bigrams/trigrams) from text."""
    text = text.lower()
    words = re.findall(r'\b[a-zA-Z][\w#+.-]*\b', text)
    phrases = set()
    for n in range(2, max_len + 1):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i:i + n])
            # Only keep phrases that aren't all stop words
            non_stop = [w for w in words[i:i + n] if w not in STOP_WORDS]
            if len(non_stop) >= n - 1:
                phrases.add(phrase)
    return phrases


def keyword_match_score(cv_text: str, job_description: str) -> float:
    """
    Calculate keyword match score between CV and job description.
    Uses stop-word filtering and phrase matching for accuracy.
    """
    if not job_description or not job_description.strip():
        return 0.0

    # Single word matching (filtered)
    cv_words = _extract_meaningful_words(cv_text)
    job_words = _extract_meaningful_words(job_description)

    if not job_words:
        return 0.0

    word_matches = cv_words & job_words
    word_score = len(word_matches) / len(job_words)

    # Phrase matching (bigrams/trigrams) — rewards matching multi-word terms
    cv_phrases = _extract_phrases(cv_text)
    job_phrases = _extract_phrases(job_description)

    phrase_score = 0.0
    if job_phrases:
        phrase_matches = cv_phrases & job_phrases
        phrase_score = len(phrase_matches) / len(job_phrases)

    # Weighted combination: phrases are more meaningful than single words
    score = (0.6 * word_score + 0.4 * phrase_score) * 100

    return round(min(100.0, score), 2)