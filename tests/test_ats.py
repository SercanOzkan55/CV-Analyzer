
from services import ats_service as ats


def test_analyze_cv_basic(sample_texts):
    cv, job = sample_texts
    res = ats.analyze_cv(cv, job)
    assert "overall_score" in res
    assert res["overall_score"] >= 0


def test_analyze_cv_empty_cv(sample_texts):
    _, job = sample_texts
    res = ats.analyze_cv("", job)
    assert res["content"]["keyword_score"] == 0.0
    assert res["content"]["content_score"] >= 0


def test_analyze_cv_empty_job(sample_texts):
    cv, _ = sample_texts
    res = ats.analyze_cv(cv, "")
    # When job_text is empty, keyword_score must be 0 and content_score computed from action/achievement
    assert res["content"]["keyword_score"] == 0.0
    assert res["content"]["content_score"] >= 0


def test_analyze_cv_long_cv(sample_texts):
    cv, job = sample_texts
    long_cv = cv + ("\nExperience details " * 5000)
    res = ats.analyze_cv(long_cv, job)
    # length_score should be penalized (not full 100)
    assert res["layout"]["length_score"] < 100


def test_analyze_cv_recognizes_non_english_sections_and_profiles():
    cv = """Ayse Kaya
ayse@example.com | +90 555 123 45 67 | github.com/aysekaya

Özet
Veri analisti.

Deneyim
- Geliştirdi satış raporlarını ve işlem süresini %30 azalttı.

Eğitim
İstatistik Lisans

Beceriler
Python, SQL, Power BI
"""

    res = ats.analyze_cv(cv, "Python SQL veri analisti", lang="tr")

    assert res["layout"]["contact_score"] == 100.0
    assert res["layout"]["section_presence_score"] == 100.0
    assert res["content"]["action_verb_score"] > 0
    assert res["content"]["achievement_score"] > 0


def test_analyze_cv_scores_generic_professional_profile_not_only_linkedin():
    cv = """John Doe
john@example.com | +1 555 123 4567 | github.com/johndoe

Experience
- Built APIs.

Education
BSc Computer Science

Skills
Python
"""

    res = ats.analyze_cv(cv)

    assert res["layout"]["contact_score"] == 100.0
