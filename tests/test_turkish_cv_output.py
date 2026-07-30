"""Turkish CVs must stay Turkish through parsing, export model and rendering.

Regression cover for a batch of defects where a Turkish CV was detected as
``tr`` but came back out with English section headings and mis-sorted skills.
"""

from schemas.cv_model import CVModel
from services.cv_autofix_service import (
    _render_structured_sections,
    get_section_title,
)
from services.section_classifier import _sniff_header


class TestExportModelKeepsLanguage:
    def test_language_survives_from_mapping(self):
        model = CVModel.from_mapping({"full_name": "Ada", "language": "tr", "skills": []})
        assert model.language == "tr"

    def test_lang_alias_is_accepted(self):
        # The autofix builder payload historically sent "lang"; a silent
        # fallback to English is what turned Turkish CVs into English ones.
        model = CVModel.from_mapping({"full_name": "Ada", "lang": "tr", "skills": []})
        assert model.language == "tr"


class TestTurkishSectionHeadings:
    def test_renderer_emits_turkish_titles(self):
        text = _render_structured_sections(
            "Ada Lovelace",
            [],
            [],
            {"summary": ["Ozet metni"], "experience": ["Bir is"]},
            lang="tr",
        )
        assert "PROFESYONEL ÖZET" in text
        assert "PROFESSIONAL SUMMARY" not in text

    def test_renderer_still_defaults_to_english(self):
        text = _render_structured_sections(
            "Ada Lovelace",
            [],
            [],
            {"summary": ["Summary text"]},
        )
        assert "PROFESSIONAL SUMMARY" in text

    def test_localized_titles_exist_for_turkish(self):
        assert get_section_title("summary", "tr") == "PROFESYONEL ÖZET"
        assert get_section_title("experience", "tr") != "EXPERIENCE"


class TestTurkishHeadingRecognition:
    def test_teknik_yetenekler_is_skills(self):
        assert _sniff_header("TEKNİK YETENEKLER") == "skills"
        assert _sniff_header("Teknik Yetenekler") == "skills"

    def test_yabanci_dil_singular_is_languages(self):
        assert _sniff_header("YABANCI DİL") == "languages"

    def test_existing_turkish_headings_unchanged(self):
        assert _sniff_header("YETENEKLER") == "skills"
        assert _sniff_header("DENEYİM") == "experience"
        assert _sniff_header("YABANCI DİLLER") == "languages"
        assert _sniff_header("TEKNİK BECERİLER") == "skills"
