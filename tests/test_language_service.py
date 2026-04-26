"""Unit tests for services/language_service.py"""
import pytest
from services.language_service import (
    detect_language,
    interpret_score_localized,
    localize_risk_level,
    get_recommendation,
    get_ats_suggestion,
)


# ── detect_language ──────────────────────────────────────────

class TestDetectLanguage:
    def test_english_text(self):
        text = "I am an experienced software developer with strong Python skills. " * 5
        assert detect_language(text) == "en"

    def test_turkish_text(self):
        text = "Deneyimli bir yazılım geliştiriciyim ve Python becerilerim güçlü. " * 5
        assert detect_language(text) == "tr"

    def test_short_text_defaults_to_en(self):
        assert detect_language("Hi") == "en"

    def test_empty_text_defaults_to_en(self):
        assert detect_language("") == "en"

    def test_none_like_input(self):
        assert detect_language("   ") == "en"


# ── interpret_score_localized ────────────────────────────────

class TestInterpretScoreLocalized:
    def test_high_score_english(self):
        assert interpret_score_localized(90) == "Strong Match"

    def test_moderate_score_english(self):
        assert interpret_score_localized(60) == "Moderate Match"

    def test_low_score_english(self):
        assert interpret_score_localized(30) == "Weak Match"

    def test_turkish_localization(self):
        assert interpret_score_localized(90, "tr") == "Güçlü Eşleşme"
        assert interpret_score_localized(60, "tr") == "Orta Eşleşme"
        assert interpret_score_localized(30, "tr") == "Zayıf Eşleşme"

    def test_unsupported_lang_falls_back_to_en(self):
        result = interpret_score_localized(90, "xx")
        assert result == "Strong Match"

    def test_boundary_values(self):
        assert interpret_score_localized(75) == "Moderate Match"
        assert interpret_score_localized(76) == "Strong Match"
        assert interpret_score_localized(50) == "Weak Match"
        assert interpret_score_localized(51) == "Moderate Match"


# ── localize_risk_level ──────────────────────────────────────

class TestLocalizeRiskLevel:
    def test_low_risk_en(self):
        assert localize_risk_level("Low Risk") == "Low Risk"

    def test_medium_risk_tr(self):
        assert localize_risk_level("Medium Risk", "tr") == "Orta Risk"

    def test_high_risk_fr(self):
        assert localize_risk_level("High Risk", "fr") == "Risque Élevé"

    def test_unknown_risk_falls_back(self):
        result = localize_risk_level("Unknown Risk")
        assert result  # should return something from fallback


# ── get_recommendation ───────────────────────────────────────

class TestGetRecommendation:
    def test_semantic_low_en(self):
        rec = get_recommendation("semantic_low")
        assert "structure" in rec.lower() or "align" in rec.lower() or "rewrite" in rec.lower()

    def test_add_skill_with_format(self):
        rec = get_recommendation("add_skill", skill="Docker")
        assert "Docker" in rec

    def test_all_good(self):
        rec = get_recommendation("all_good")
        assert rec  # non-empty string

    def test_turkish_locale(self):
        rec = get_recommendation("semantic_low", lang="tr")
        assert rec  # non-empty
        assert rec != get_recommendation("semantic_low", lang="en")


# ── get_ats_suggestion ───────────────────────────────────────

class TestGetAtsSuggestion:
    def test_keyword_low(self):
        sug = get_ats_suggestion("keyword_low")
        assert sug  # non-empty

    def test_turkish_locale(self):
        sug = get_ats_suggestion("keyword_low", lang="tr")
        assert sug
