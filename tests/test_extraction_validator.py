"""Tests for services/extraction_validator.py — experience fragmentation gate."""

from services.extraction_validator import (
    validate_extraction,
    _looks_fragmented_title,
    _check_experience_fragmentation,
)


class TestFragmentedTitle:
    def test_real_role_titles_are_not_fragments(self):
        for title in [
            "Software Engineer, Acme Corp",
            "Pharmacy Intern, CVS Health",
            "Senior Data Analyst",
            "Microbiology Clinical Affairs Intern, Beckman Coulter",
        ]:
            assert _looks_fragmented_title(title) is False

    def test_fragments_are_detected(self):
        for title in [
            "2015.",  # bare date
            "(HNUU)",  # parenthetical fragment
            "BUT",  # ALL-CAPS stray word
            "KEY RESPONSIBILITIES",  # leaked section header
            "& provides",  # conjunction-led wrap
            "such as memos, reports",  # mid-sentence wrap
            "support & screening, record maintain",  # lowercase wrap
            "",  # empty
        ]:
            assert _looks_fragmented_title(title) is True


def _exp(title, bullets=0):
    return {"title": title, "company": "", "bullets": ["x"] * bullets}


class TestExperienceFragmentation:
    def test_clean_experience_list_passes(self):
        entries = [
            _exp("Software Engineer, Acme", 3),
            _exp("Pharmacy Intern, CVS Health", 4),
            _exp("Salesperson, Macy's", 3),
            _exp("Research Assistant, MIT", 2),
        ]
        assert _check_experience_fragmentation({"experiences": entries}) == []

    def test_few_entries_never_flagged(self):
        # Below the n>=4 floor we never flag (avoids false positives).
        entries = [_exp("2015.", 0), _exp("(HNUU)", 0)]
        assert _check_experience_fragmentation({"experiences": entries}) == []

    def test_fragment_dominated_list_is_flagged(self):
        entries = [
            _exp("2015.", 1),
            _exp("(HNUU)", 0),
            _exp("BUT", 1),
            _exp("Engineer, Reliance", 1),
        ]
        issues = _check_experience_fragmentation({"experiences": entries})
        assert any("fragmented" in i for i in issues)

    def test_oversplit_low_bullet_list_is_flagged(self):
        # Many entries with almost no bullets → shredded table/structure.
        entries = [_exp("Designation: Draughtsman", 1)] + [_exp("Detail line %d" % i, 0) for i in range(9)]
        issues = _check_experience_fragmentation({"experiences": entries})
        assert any("oversplit" in i for i in issues)

    def test_validate_extraction_sets_fallback_on_garbage(self):
        normalized = {
            "full_name": "Rizwan Haque",
            "email": "rizwan@example.com",
            "experiences": [
                _exp("2015.", 1),
                _exp("(HNUU)", 0),
                _exp("PLATFORMER", 0),
                _exp("BUT", 1),
                _exp("Jamnagar", 0),
            ],
        }
        result = validate_extraction("Rizwan Haque rizwan@example.com ... experience", normalized)
        assert result["needs_llm_fallback"] is True
        assert any("experience_garbage" in h for h in result["hard_fails"])
