"""Unit tests for services/experience_service.py"""
import pytest
from services.experience_service import extract_years, experience_score


# ── extract_years ────────────────────────────────────────────

class TestExtractYears:
    def test_direct_pattern_years(self):
        assert extract_years("5+ years of experience") == 5

    def test_direct_pattern_yrs(self):
        assert extract_years("3 yrs in software") == 3

    def test_direct_pattern_turkish(self):
        assert extract_years("10 yıl deneyim") == 10

    def test_picks_max_from_multiple(self):
        assert extract_years("3 years Python, 5 years Java") == 5

    def test_date_range_calculation(self):
        years = extract_years("2018 - 2022")
        assert years == 4

    def test_present_keyword(self):
        from datetime import datetime
        years = extract_years("2020 - present")
        expected = datetime.now().year - 2020
        assert years == expected

    def test_merged_overlapping_ranges(self):
        # Two overlapping periods shouldn't double-count
        text = "2015 - 2020 at Company A, 2018 - 2022 at Company B"
        years = extract_years(text)
        assert years == 7  # 2015-2022

    def test_no_experience_returns_zero(self):
        assert extract_years("Hello world, no dates here") == 0

    def test_turkish_present_keyword(self):
        from datetime import datetime
        years = extract_years("2019 - halen")
        expected = datetime.now().year - 2019
        assert years == expected

    def test_dash_variants(self):
        # en-dash and em-dash should work too
        assert extract_years("2018 – 2022") == 4
        assert extract_years("2018 — 2022") == 4

    def test_to_keyword(self):
        assert extract_years("2018 to 2022") == 4


# ── experience_score ─────────────────────────────────────────

class TestExperienceScore:
    def test_meets_requirement(self):
        cv = "I have 5 years of experience in Python"
        jd = "Requires 3 years of experience"
        assert experience_score(cv, jd) == 100.0

    def test_exceeds_requirement(self):
        cv = "10 years senior developer"
        jd = "5 years required"
        assert experience_score(cv, jd) == 100.0

    def test_under_requirement_gets_penalty(self):
        cv = "2 years of experience"
        jd = "5 years required"
        score = experience_score(cv, jd)
        assert 20 <= score < 100

    def test_no_job_requirement_with_experience(self):
        cv = "10 years of experience"
        jd = "Looking for a Python developer"
        assert experience_score(cv, jd) == 100.0

    def test_no_job_requirement_no_experience(self):
        cv = "Fresh graduate"
        jd = "Looking for a Python developer"
        assert experience_score(cv, jd) == 50.0

    def test_zero_cv_experience_against_requirement(self):
        cv = "Recent grad, no work history"
        jd = "5 years required"
        score = experience_score(cv, jd)
        assert score == 20.0  # minimum penalty floor
