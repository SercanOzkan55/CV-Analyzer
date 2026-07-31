"""Turkish CVs must stay Turkish through parsing, export model and rendering.

Regression cover for a batch of defects where a Turkish CV was detected as
``tr`` but came back out with English section headings and mis-sorted skills.
"""

from unittest.mock import patch

from pypdf import PdfReader

from agents.extract_agent import extract_structured
from renderers.pdf_renderer import render_pdf
from schemas.cv_model import CVModel
from services.cv_autofix_service import (
    _parse_sections,
    _render_structured_sections,
    auto_fix_cv_text,
    get_section_title,
)
from services.section_classifier import _sniff_header

TURKISH_CV_WITH_CATEGORIZED_SKILLS = """Ada Yılmaz
İstanbul, Türkiye | ada@example.com

ÖZET
Backend geliştirme ve gerçek zamanlı sistemler üzerinde deneyimli bir yazılım mühendisidir.

DENEYİM
Yazılım Mühendisi | Örnek Teknoloji
Ocak 2024 – Devam ediyor
• Güvenilir servisler ve veri işleme hatları geliştirdi.

TEKNİK YETENEKLER
Diller: | Python, Java, C#, SQL
Frontend: | React, Vite, HTML, CSS

Backend: | FastAPI, REST API'ler, Celery, JWT kimlik doğrulama
Veritabanları: | PostgreSQL, Redis, SQLite
AI / LLM: | OpenAI, RAG mimarileri, embedding'ler, prompt
mühendisliği
Araç & Platform: Git, Docker, AWS S3
Kavramlar: | Veri Yapıları, Algoritmalar, OOP, Gerçek Zamanlı Sistemler,
Ölçeklenebilir Sistemler
Protokoller: | TCP, RTP, RTSP, HTTP/REST

SERTİFİKALAR
AWS Cloud Technical Essentials | edX | Nisan 2026

EĞİTİM
Bilgisayar Mühendisliği (Lisans) | Örnek Üniversitesi | 2022 – Devam ediyor

YABANCI DİL
İngilizce: Konuşma B1 | Yazma B2 | Teknik Okuma B2
"""


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

    def test_deterministic_parser_keeps_diller_sublabel_inside_skills(self):
        _, sections, _ = _parse_sections(TURKISH_CV_WITH_CATEGORIZED_SKILLS)

        assert "Diller: | Python, Java, C#, SQL" in sections["skills"]
        assert "Backend: | FastAPI, REST API'ler, Celery, JWT kimlik doğrulama" in sections["skills"]
        assert not any(line.startswith("Backend:") for line in sections["languages"])

    def test_page_break_skill_continuation_is_not_duplicated_into_summary(self):
        extracted = extract_structured(TURKISH_CV_WITH_CATEGORIZED_SKILLS)

        assert "Backend: |" not in extracted["summary"]
        assert "Veritabanları: |" not in extracted["summary"]
        assert "Backend" in extracted["skills_categorized"]
        assert "Veritabanları" in extracted["skills_categorized"]


@patch("services.cv_autofix_service.analyze_cv")
def test_auto_language_preserves_turkish_headings_and_all_skill_categories(mock_analyze):
    mock_analyze.return_value = {
        "overall_score": 80,
        "section_status": {"skills": "pass", "experience": "pass", "education": "pass"},
    }

    result = auto_fix_cv_text(
        TURKISH_CV_WITH_CATEGORIZED_SKILLS,
        lang="auto",
        use_ai=False,
        mode="strict",
    )

    assert result["source_language"] == "tr"
    assert result["requested_language"] == "auto"
    assert result["output_language"] == "tr"
    assert result["translation_requested"] is False
    assert "PROFESYONEL ÖZET" in result["optimized_cv_text"]
    assert "PROFESSIONAL SUMMARY" not in result["optimized_cv_text"]
    assert "DENEYİM" in result["optimized_cv_text"]
    assert "SERTİFİKALAR" in result["optimized_cv_text"]
    assert "DİLLER" in result["optimized_cv_text"]

    payload = result["builder_payload"]
    assert payload["language"] == "tr"
    assert payload["section_titles"]["skills"] == "TEKNİK YETENEKLER"
    assert not payload["summary"].startswith("PROFESYONEL ÖZET")
    assert list(payload["skills_categorized"]) == [
        "Diller",
        "Frontend",
        "Backend",
        "Veritabanları",
        "AI / LLM",
        "Araç & Platform",
        "Kavramlar",
        "Protokoller",
    ]
    assert "FastAPI" in payload["skills_categorized"]["Backend"]
    assert "PostgreSQL" in payload["skills_categorized"]["Veritabanları"]

    rendered = render_pdf(CVModel.from_mapping(payload), template="classic")
    rendered_text = "\n".join((page.extract_text() or "") for page in PdfReader(rendered).pages)
    assert "TEKNİK YETENEKLER" in rendered_text
    assert "Backend:" in rendered_text
    assert "Veritabanları:" in rendered_text
    assert "Protokoller:" in rendered_text
    assert "PROFESYONEL ÖZET" not in rendered_text
