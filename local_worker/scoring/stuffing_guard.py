"""Anti-gaming safeguard: detect a CV that suspiciously near-duplicates the
job description (a candidate copy-pasting the JD into their CV to game
keyword/skill matching).

This is NOT a weighted scoring criterion — it's a flag. ``detect_jd_overlap``
returns a warning string to append to ``risk_flags`` for the recruiter to
see and judge, or ``None`` when nothing suspicious is found. It must never
zero or auto-reject the score by itself (see worker.py::score_cv, which
keeps this flag out of the existing hard-reject penalty/decision path).

Kept deliberately simple and conservative (favor not flagging over
false-flagging): a tiny job_description is exempted outright, and the
thresholds are generous.
"""

import difflib
import re

JD_OVERLAP_FLAG = "⚠️ Suspicious JD overlap"  # "⚠️ Suspicious JD overlap"

# Below this length a job description is too short for a meaningful
# duplication comparison — skip the check entirely rather than risk a
# false positive on a one-line JD.
MIN_JOB_DESCRIPTION_LENGTH = 100

# A single contiguous matching block at least this long (characters) is a
# strong signal of copy-pasted text.
LONG_MATCH_THRESHOLD = 200

# Overall SequenceMatcher similarity ratio above this is a strong signal
# even without one single very long contiguous block.
SIMILARITY_RATIO_THRESHOLD = 0.5


def _normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_jd_overlap(cv_text: str, job_description: str) -> str | None:
    """Return the JD-overlap warning string if the CV suspiciously
    near-duplicates the job description, else ``None``.
    """
    jd = job_description or ""
    if len(jd) <= MIN_JOB_DESCRIPTION_LENGTH:
        return None

    cv_norm = _normalize(cv_text)
    jd_norm = _normalize(jd)
    if not cv_norm or not jd_norm:
        return None

    matcher = difflib.SequenceMatcher(None, cv_norm, jd_norm)

    match = matcher.find_longest_match(0, len(cv_norm), 0, len(jd_norm))
    if match.size >= LONG_MATCH_THRESHOLD:
        return JD_OVERLAP_FLAG

    if matcher.ratio() >= SIMILARITY_RATIO_THRESHOLD:
        return JD_OVERLAP_FLAG

    return None
