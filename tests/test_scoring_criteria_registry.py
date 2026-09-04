import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_WORKER_DIR = PROJECT_ROOT / "local_worker"
if str(LOCAL_WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(LOCAL_WORKER_DIR))

from scoring import criteria as scoring_criteria  # noqa: E402


# education / language / recruiter_score were reserved through Phase 2/3 —
# they needed a real CV structural parser (local_worker/cv_model/, ported in
# Phase 4 from the web repo's agents/extract_agent.py + schemas/cv_model.py)
# that local_worker didn't have yet, so their `scorer` was None and their
# weight pinned at 0 everywhere. Phase 4 ported that parser and gave all 3 a
# working CVModel-based scorer, so RESERVED_CRITERIA is now empty — every
# CRITERIA key (all 12) must have a real, working scorer today.
RESERVED_KEYS = scoring_criteria.RESERVED_CRITERIA


def _sample_config():
    return {
        "required_skills": ["Python", "SQL"],
        "nice_to_have_skills": ["Docker"],
        "description": "Looking for a Senior Backend Engineer with 5+ years of Python and SQL experience.",
    }


def test_every_live_criterion_has_a_working_scorer():
    sample_cv = (
        "Jane Doe\njane@example.com\n+1 555 123 4567\n"
        "EXPERIENCE\nSenior Python Developer, Acme (2016 - 2024)\n"
        "- Built scalable APIs using Python and SQL with strong leadership and communication\n"
        "EDUCATION\nBSc Computer Science, MIT\nSKILLS\nPython, SQL, Docker, Kubernetes\n"
    )
    config = _sample_config()

    for key, meta in scoring_criteria.CRITERIA.items():
        if key in RESERVED_KEYS:
            assert meta["scorer"] is None, f"{key} is reserved and must have scorer=None"
            continue
        assert meta["scorer"] is not None, f"{key} is live and must have a working scorer"
        score = meta["scorer"](sample_cv, config)
        assert isinstance(score, (int, float)), f"{key} scorer must return a number"
        assert 0.0 <= float(score) <= 100.0, f"{key} scorer must return a 0-100 value, got {score}"


def test_no_criteria_are_reserved_anymore():
    """Phase 4 ported the CVModel structural parser education/language/
    recruiter_score needed, so nothing should be reserved (scorer=None) any
    longer — RESERVED_CRITERIA exists only as a historical, now-empty hook."""
    assert RESERVED_KEYS == ()
    for key, meta in scoring_criteria.CRITERIA.items():
        assert meta["scorer"] is not None, f"{key} must not be reserved"


def test_background_criteria_respond_to_cv_structure():
    """The 3 Phase 4 criteria must be sensitive to actual CVModel content,
    not just return a constant — feed a CV with rich education/language
    content vs. one with none and confirm the scores move."""
    rich_cv = (
        "Jane Doe\njane@example.com\n\n"
        "EXPERIENCE\nSenior Python Developer, Acme (2016 - 2024)\n"
        "- Led a team of 5 engineers\n"
        "EDUCATION\nBSc Computer Science, MIT, 2012 - 2016\n"
        "LANGUAGES\nEnglish (Native), Turkish (Fluent), German (Intermediate)\n"
    )
    bare_cv = "Some text with no structure at all, just prose about nothing in particular."
    config = _sample_config()

    education_scorer = scoring_criteria.CRITERIA["education"]["scorer"]
    language_scorer = scoring_criteria.CRITERIA["language"]["scorer"]

    assert education_scorer(rich_cv, config) > education_scorer(bare_cv, config)
    assert language_scorer(rich_cv, config) > language_scorer(bare_cv, config)


def test_background_scorer_reuses_a_passed_in_cv_model():
    """worker.py::score_cv parses CVModel once per file and passes it
    through — the scorer must use that instance rather than reparsing, so a
    caller-supplied (even inaccurate) cv_model wins over what parsing
    cv_text would have produced."""
    import cv_model as cv_model_pkg

    education_scorer = scoring_criteria.CRITERIA["education"]["scorer"]
    config = _sample_config()

    empty_model = cv_model_pkg.CVModel()
    rich_cv_text = "EDUCATION\nBSc Computer Science, MIT, 2012 - 2016\n"

    # Parsing rich_cv_text directly would produce a nonzero education score;
    # passing an explicitly empty cv_model must override that and score 0.
    assert education_scorer(rich_cv_text, config, empty_model) == 0.0
    assert education_scorer(rich_cv_text, config) > 0.0


def test_reserved_criteria_are_excluded_from_categories_but_present_in_registry():
    for key in RESERVED_KEYS:
        assert key in scoring_criteria.CRITERIA
        assert scoring_criteria.CRITERIA[key]["scorer"] is None
        assert scoring_criteria.CRITERIA[key]["default_weight"] == 0.0


@pytest.mark.parametrize("preset_name", list(scoring_criteria.PRESETS.keys()))
def test_preset_weights_sum_to_exactly_100(preset_name):
    preset = scoring_criteria.PRESETS[preset_name]
    # Every criterion key (including reserved, pinned at 0) must be present
    # so a preset is always a complete, unambiguous weight assignment.
    assert set(preset.keys()) == set(scoring_criteria.CRITERIA.keys())
    for key in RESERVED_KEYS:
        assert preset[key] == 0.0, f"{preset_name} must keep reserved criterion {key} at weight 0"
    assert sum(preset.values()) == pytest.approx(100.0)


def test_categories_have_labels_and_default_weights():
    assert set(scoring_criteria.CATEGORIES.keys()) == {
        criteria_meta["category"] for criteria_meta in scoring_criteria.CRITERIA.values()
    }
    for category_key, meta in scoring_criteria.CATEGORIES.items():
        assert meta["label"]
        assert meta["default_weight"] >= 0


def test_all_criteria_have_required_metadata_fields():
    required_fields = {"category", "label", "default_weight", "description", "scorer"}
    for key, meta in scoring_criteria.CRITERIA.items():
        assert required_fields.issubset(meta.keys()), f"{key} is missing metadata fields"
        assert meta["category"] in scoring_criteria.CATEGORIES
        assert isinstance(meta["label"], str) and meta["label"]
        assert isinstance(meta["description"], str) and meta["description"]
