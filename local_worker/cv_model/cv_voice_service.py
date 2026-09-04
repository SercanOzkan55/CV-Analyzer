"""Language-aware resume voice analysis and conservative rewriting.

Parsing must preserve what the candidate wrote.  This module is therefore
used by scoring and Auto-Fix/export only; extraction code must not call it.

Turkish CV bullets use third-person singular action verbs (``analiz etti``),
while English CV bullets conventionally omit the subject (``Analyzed``).
"""

from __future__ import annotations

import re
from typing import Any


_TR_WORD_RE = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşüÂâÎîÛû]+")
_TR_CLAUSE_WORD_RE = re.compile(
    r"(?P<word>[A-Za-zÇĞİÖŞÜçğıöşüÂâÎîÛû]+)"
    r"(?=\s*(?:[,;:.!?]|\b(?:ve|ancak|fakat|ayrıca|sonra|ardından)\b|$))",
    re.IGNORECASE,
)

# Common nouns and technical terms that resemble Turkish first-person verb
# endings.  Boundary-based matching plus this list keeps the rewrite safe.
_TR_NON_VERBS = {
    "adım",
    "bakım",
    "başarım",
    "benim",
    "bilim",
    "bilişim",
    "bildirim",
    "birim",
    "birikim",
    "bölüm",
    "çizim",
    "dağıtım",
    "değişim",
    "deneyim",
    "donanım",
    "durum",
    "eğitim",
    "erişim",
    "gelişim",
    "girişim",
    "iletim",
    "indirim",
    "katılım",
    "konum",
    "kullanım",
    "kurulum",
    "kurum",
    "öğretim",
    "seçim",
    "sunum",
    "sürüm",
    "takım",
    "tanım",
    "tasarım",
    "teknik",
    "toplum",
    "uyum",
    "üretim",
    "verim",
    "yazılım",
    "yardım",
    "yatırım",
    "yönetim",
    "çözüm",
}

_TR_SUFFIXES: tuple[tuple[str, str], ...] = (
    # Past tense: geliştirdim -> geliştirdi, bulundum -> bulundu.
    ("dım", "dı"),
    ("dim", "di"),
    ("dum", "du"),
    ("düm", "dü"),
    ("tım", "tı"),
    ("tim", "ti"),
    ("tum", "tu"),
    ("tüm", "tü"),
    # Present continuous.
    ("ıyorum", "ıyor"),
    ("iyorum", "iyor"),
    ("uyorum", "uyor"),
    ("üyorum", "üyor"),
    # Evidential past.
    ("mışım", "mış"),
    ("mişim", "miş"),
    ("muşum", "muş"),
    ("müşüm", "müş"),
    # Future and necessity.
    ("acağım", "acak"),
    ("eceğim", "ecek"),
    ("malıyım", "malı"),
    ("meliyim", "meli"),
    # Ability.
    ("abilirim", "abilir"),
    ("ebilirim", "ebilir"),
    # Copular adjective/noun form: deneyimliyim -> deneyimli.
    ("yım", ""),
    ("yim", ""),
    ("yum", ""),
    ("yüm", ""),
)

_TR_FIRST_PERSON_PRONOUN_RE = re.compile(r"\b(?:ben|benim|bana|bende|benden|biz|bizim|bize|bizde|bizden)\b", re.I)
_EN_FIRST_PERSON_PRONOUN_RE = re.compile(r"\b(?:I|me|my|mine|we|us|our|ours)\b", re.I)


def _language_code(lang: str) -> str:
    return (lang or "en").strip().lower().split("-", 1)[0].split("_", 1)[0]


def _content_without_bullet(line: str) -> str:
    return re.sub(r"^\s*(?:[-*•▪◦◆▸►–—]|\d+[.)])\s*", "", line).strip()


def _is_heading(line: str) -> bool:
    content = _content_without_bullet(line)
    words = _TR_WORD_RE.findall(content)
    return bool(words and len(words) <= 6 and content == content.upper())


def _case_aware_replacement(source: str, replacement: str) -> str:
    if not replacement:
        return ""
    if source.isupper():
        return replacement.upper()
    if source[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _rewrite_turkish_word(word: str, *, allow_plural: bool = False) -> str:
    lowered = word.lower()
    if lowered in _TR_NON_VERBS or len(lowered) < 5:
        return word

    for suffix, replacement in sorted(_TR_SUFFIXES, key=lambda item: len(item[0]), reverse=True):
        if lowered.endswith(suffix) and len(lowered) > len(suffix) + 1:
            if suffix in {"yım", "yim", "yum", "yüm"} and not lowered[: -len(suffix)].endswith(
                ("lı", "li", "lu", "lü")
            ):
                continue
            converted = word[: -len(suffix)] + replacement
            return _case_aware_replacement(word, converted)

    # First-person plural is changed only when an explicit "biz" subject was
    # present.  This avoids treating words such as "teknik" as verbs.
    if allow_plural:
        for suffix, replacement in (
            ("dık", "dı"),
            ("dik", "di"),
            ("duk", "du"),
            ("dük", "dü"),
            ("tık", "tı"),
            ("tik", "ti"),
            ("tuk", "tu"),
            ("tük", "tü"),
        ):
            if lowered.endswith(suffix) and len(lowered) > len(suffix) + 1:
                converted = word[: -len(suffix)] + replacement
                return _case_aware_replacement(word, converted)
    return word


def _turkish_suffix_matches(text: str) -> list[str]:
    matches: list[str] = []
    for line in text.splitlines() or [text]:
        if _is_heading(line):
            continue
        has_biz = bool(re.search(r"\bbiz\b", line, re.I))
        for match in _TR_CLAUSE_WORD_RE.finditer(line):
            word = match.group("word")
            if _rewrite_turkish_word(word, allow_plural=has_biz) != word:
                matches.append(word)
    return matches


def _narrative_line_count(text: str) -> int:
    return max(
        1,
        sum(
            1
            for line in text.splitlines()
            if not _is_heading(line) and len(_TR_WORD_RE.findall(_content_without_bullet(line))) >= 4
        ),
    )


def analyze_resume_voice(text: str, lang: str = "en") -> dict[str, Any]:
    """Return a 0-100 resume-voice score and detected first-person markers."""
    source = text or ""
    language = _language_code(lang)
    if language == "tr":
        matches = [m.group(0) for m in _TR_FIRST_PERSON_PRONOUN_RE.finditer(source)]
        matches.extend(_turkish_suffix_matches(source))
    else:
        matches = [m.group(0) for m in _EN_FIRST_PERSON_PRONOUN_RE.finditer(source)]

    issue_count = len(matches)
    narrative_lines = _narrative_line_count(source)
    issue_ratio = min(1.0, issue_count / narrative_lines)
    penalty = min(75.0, issue_count * 8.0 + issue_ratio * 25.0)
    score = round(max(0.0, 100.0 - penalty), 2)
    return {
        "score": score,
        "first_person_count": issue_count,
        "matches": matches[:10],
        "language": language,
    }


def _rewrite_english_line(line: str) -> str:
    # Preserve indentation/bullet prefix while normalizing only a leading
    # first-person construction. Internal pronouns are reported but not
    # rewritten because doing so safely requires wider sentence context.
    match = re.match(r"^(?P<prefix>\s*(?:[-*•▪◦◆▸►–—]|\d+[.)])?\s*)(?P<body>.*)$", line)
    if not match:
        return line
    prefix, body = match.group("prefix"), match.group("body")
    original = body
    body = re.sub(r"^(?:I|We)\s+(?:have|had)\s+", "", body, flags=re.I)
    body = re.sub(r"^(?:I|We)\s+(?:am|are|was|were)\s+", "", body, flags=re.I)
    body = re.sub(r"^(?:I|We)\s+", "", body, flags=re.I)
    body = re.sub(r"^My\s+responsibilities\b", "Responsibilities", body, flags=re.I)
    body = re.sub(r"^My\s+role\b", "Role", body, flags=re.I)
    if body != original and body:
        body = body[:1].upper() + body[1:]
    return prefix + body


def _rewrite_turkish_line(line: str) -> str:
    if _is_heading(line):
        return line
    has_biz = bool(re.search(r"\bbiz\b", line, re.I))
    # Remove an explicit subject only at the start of a sentence/bullet.
    rewritten = re.sub(
        r"^(?P<prefix>\s*(?:[-*•▪◦◆▸►–—]|\d+[.)])?\s*)(?:Ben|Biz)\s*,?\s*",
        lambda m: m.group("prefix"),
        line,
        flags=re.I,
    )

    def replace(match: re.Match[str]) -> str:
        return _rewrite_turkish_word(match.group("word"), allow_plural=has_biz)

    return _TR_CLAUSE_WORD_RE.sub(replace, rewritten)


def rewrite_resume_voice(text: str, lang: str = "en") -> str:
    """Conservatively normalize first-person CV prose for the given language."""
    if not text:
        return text
    language = _language_code(lang)
    rewrite_line = _rewrite_turkish_line if language == "tr" else _rewrite_english_line
    return "\n".join(rewrite_line(line) for line in text.split("\n"))
