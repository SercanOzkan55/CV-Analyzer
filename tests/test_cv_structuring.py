"""Phase 4 tests — CV -> structured CVModel parser port.

Covers:
  * the ported extract_agent/normalize_agent chain (local_worker/cv_model/)
    produces non-empty education/languages/experiences for a complete CV
  * a drift guard comparing the ported copy's output against the original
    web-repo agents/extract_agent.py for the same input text (the two are
    separate, unlinked files by necessity — local_worker ships standalone —
    so nothing else would catch silent divergence between them)
  * graceful degradation: malformed/garbage CV text must not raise, and
    must still produce a valid (low) score from the 3 Background criteria
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_WORKER_DIR = PROJECT_ROOT / "local_worker"
if str(LOCAL_WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(LOCAL_WORKER_DIR))
# Appended (not inserted at 0) so it never shadows local_worker's own
# flat-style imports (e.g. "import worker", "import cv_model") for modules
# that happen to share a name with something at the repo root.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import cv_model  # noqa: E402
import worker as worker_module  # noqa: E402
from scoring.education_language import education_score, language_score  # noqa: E402
from scoring.recruiter_score import recruiter_score  # noqa: E402


SAMPLE_CV_TEXT = """Jane Doe
Senior Backend Engineer
jane.doe@example.com | +1 555 123 4567 | Istanbul, Turkey

SUMMARY
Experienced backend engineer with 6 years building scalable APIs in Python and Go, leading teams and mentoring junior engineers.

EXPERIENCE
Senior Backend Engineer | Acme Corp | Jan 2020 - Present
- Led migration of monolith to microservices, reducing latency by 40 percent
- Built REST APIs used by 2 million daily users
- Mentored 3 junior engineers

Backend Engineer | Beta Inc | Jun 2016 - Dec 2019
- Developed payment processing service in Python
- Improved test coverage from 40 percent to 85 percent

EDUCATION
BSc Computer Science | Istanbul Technical University | 2012 - 2016
GPA: 3.6/4.0

SKILLS
Python, Go, Docker, Kubernetes, PostgreSQL, AWS, Redis, Kafka

LANGUAGES
English (Fluent), Turkish (Native)
"""


def test_extract_structured_populates_core_sections_for_a_complete_cv():
    structured = cv_model.extract_structured(SAMPLE_CV_TEXT)
    assert structured["full_name"]
    assert structured["experiences"], "expected at least one experience entry"
    assert structured["education"], "expected at least one education entry"
    assert structured["languages"], "expected at least one language entry"


def test_normalize_preserves_core_sections():
    structured = cv_model.extract_structured(SAMPLE_CV_TEXT)
    normalized = cv_model.normalize(structured)
    assert normalized.get("experiences")
    assert normalized.get("education")
    assert normalized.get("languages")
    assert normalized.get("_normalized") is True


def test_parse_cv_model_builds_a_valid_cvmodel_for_a_complete_cv():
    model = cv_model.parse_cv_model(SAMPLE_CV_TEXT)
    assert isinstance(model, cv_model.CVModel)
    assert model.full_name
    assert len(model.experiences) >= 1
    assert len(model.education) >= 1
    assert len(model.languages) >= 1
    assert model.email == "jane.doe@example.com"


def test_parse_cv_model_from_real_pdf_sample_never_crashes():
    """sample_cvs/general_resume.pdf is a minimal placeholder fixture (its
    extracted text is a single unbroken line — "Sample CV John Doe Software
    Engineer ... Experience Education Skills Certifications" — with none of
    the line breaks a section classifier needs), not a realistic multi-
    section resume. It can't exercise structural extraction, but it's a
    real PDF-extraction code path worth a smoke test: parsing must still
    complete without raising and return a well-formed (if mostly empty)
    CVModel rather than crashing on unusual whitespace/layout."""
    pdf_path = PROJECT_ROOT / "sample_cvs" / "general_resume.pdf"
    if not pdf_path.exists():
        pytest.skip("sample_cvs/general_resume.pdf not present")
    data = pdf_path.read_bytes()
    text = worker_module.extract_text(data, "pdf", pdf_path.name)

    model = cv_model.parse_cv_model(text)  # must not raise

    assert isinstance(model, cv_model.CVModel)
    # The extracted text's content should show up somewhere in the model
    # (here, the whole line lands in summary) — confirms this wasn't
    # silently dropped, even though it couldn't be bucketed into sections.
    assert model.summary or model.experiences or model.education or model.skills


def test_malformed_cv_text_degrades_gracefully_instead_of_crashing():
    garbage = "###@@@ !!! \x00\x01\x02 asdkfj asldkfj \n\n\n ??!! %%%^^^ 12345 67890"

    model = cv_model.parse_cv_model(garbage)  # must not raise

    assert isinstance(model, cv_model.CVModel)
    assert model.education == []
    assert model.languages == []

    # Downstream scoring must also degrade gracefully: a low, valid 0-100
    # score, never an exception.
    assert education_score(model) == 0.0
    assert language_score(model) == 0.0
    assert 0.0 <= recruiter_score(model) <= 100.0


@pytest.mark.parametrize("value", ["", None])
def test_empty_or_missing_cv_text_never_raises(value):
    model = cv_model.parse_cv_model(value)
    assert isinstance(model, cv_model.CVModel)
    assert model.education == []
    assert model.languages == []
    assert model.experiences == []


def test_score_cv_end_to_end_scores_background_criteria_without_crashing():
    """worker.py::score_cv is the real integration point: it must build the
    CVModel once, score all 3 Background criteria through it, and never
    raise — even when scoring_weights explicitly activates them."""
    config = {
        "required_skills": ["Python"],
        "nice_to_have_skills": [],
        "description": "Backend role requiring Python.",
        "scoring_weights": {"education": 5.0, "language": 5.0, "recruiter_score": 5.0},
    }
    result = worker_module.score_cv(SAMPLE_CV_TEXT, config)
    breakdown = result["score_breakdown"]
    assert breakdown["education"] > 0.0
    assert breakdown["language"] > 0.0
    assert breakdown["recruiter_score"] > 0.0

    # And the same call on garbage text must not crash, degrading to 0s.
    garbage_result = worker_module.score_cv("###@@@ garbage text !!! 12345", config)
    garbage_breakdown = garbage_result["score_breakdown"]
    assert garbage_breakdown["education"] == 0.0
    assert garbage_breakdown["language"] == 0.0


# ── Drift guard: ported copy vs. original web-repo module ──────────────


def test_ported_extract_agent_matches_original_web_extract_agent():
    """Guards against silent drift between the web repo's
    agents/extract_agent.py and this ported, unlinked copy at
    local_worker/cv_model/extract_agent.py. The two are separate files by
    necessity (local_worker ships standalone, without the web repo present
    alongside it), so nothing else enforces they stay in sync."""
    from agents.extract_agent import extract_structured as original_extract_structured

    original = original_extract_structured(SAMPLE_CV_TEXT)
    ported = cv_model.extract_structured(SAMPLE_CV_TEXT)

    assert original["full_name"] == ported["full_name"]
    assert original["email"] == ported["email"]
    assert original["phone"] == ported["phone"]
    assert len(original["experiences"]) == len(ported["experiences"])
    assert len(original["education"]) == len(ported["education"])
    assert len(original["languages"]) == len(ported["languages"])
    assert set(original["skills"]) == set(ported["skills"])


def test_ported_normalize_agent_matches_original_web_normalize_agent():
    """Same drift guard, one stage further down the pipeline."""
    from agents.extract_agent import extract_structured as original_extract_structured
    from agents.normalize_agent import normalize as original_normalize

    original_structured = original_extract_structured(SAMPLE_CV_TEXT)
    original_normalized = original_normalize(original_structured)

    ported_structured = cv_model.extract_structured(SAMPLE_CV_TEXT)
    ported_normalized = cv_model.normalize(ported_structured)

    assert len(original_normalized.get("experiences") or []) == len(ported_normalized.get("experiences") or [])
    assert len(original_normalized.get("education") or []) == len(ported_normalized.get("education") or [])
    assert len(original_normalized.get("languages") or []) == len(ported_normalized.get("languages") or [])
    assert set(original_normalized.get("skills") or []) == set(ported_normalized.get("skills") or [])
