from services.language_service import (
    FALLBACK_LANG,
    NEUTRAL_LANG,
    contains_mojibake,
    detect_language,
    get_ats_suggestion,
    get_recommendation,
    interpret_score_localized,
    localize_risk_level,
    normalize_language,
    resolve_output_language,
)


def test_short_or_empty_text_is_neutral_not_english():
    assert detect_language("") == NEUTRAL_LANG
    assert detect_language("short text") == NEUTRAL_LANG


def test_auto_and_unknown_languages_have_safe_output_fallback():
    assert normalize_language("auto", "") == NEUTRAL_LANG
    assert normalize_language("xx") == NEUTRAL_LANG
    assert resolve_output_language("xx") == FALLBACK_LANG


def test_localized_strings_do_not_return_mojibake():
    strings = [
        interpret_score_localized(90, "tr"),
        localize_risk_level("High Risk", "tr"),
        get_recommendation("all_good", "tr"),
        get_ats_suggestion("keyword_low", "tr"),
        get_recommendation("all_good", "de"),
        get_ats_suggestion("keyword_low", "ja"),
    ]

    assert all(value for value in strings)
    assert not any(contains_mojibake(value) for value in strings)


def test_recommendation_skill_placeholder_survives_language_fallback():
    assert "Kubernetes" in get_recommendation("add_skill", "auto", "Kubernetes")
