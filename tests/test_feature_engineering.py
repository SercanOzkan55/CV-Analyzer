"""Tests for services/feature_engineering_service.py."""

import pytest
from services.feature_engineering_service import build_feature_vector, FEATURE_NAMES, N_FEATURES


class TestBuildFeatureVector:
    def _base_args(self, **overrides):
        defaults = dict(
            semantic_score=70,
            keyword_score=60,
            skill_score=65,
            exp_score=50,
            missing_skills=["python", "sql"],
            total_required_skills=10,
        )
        defaults.update(overrides)
        return defaults

    def test_returns_correct_length(self):
        vec = build_feature_vector(**self._base_args())
        assert len(vec) == N_FEATURES

    def test_floor_values_applied(self):
        vec = build_feature_vector(**self._base_args(semantic_score=0, keyword_score=0, skill_score=0, exp_score=0))
        # First 4 features are the score values, each floored to 5.0
        assert vec[0] == 5.0  # semantic
        assert vec[1] == 5.0  # keyword
        assert vec[2] == 5.0  # skill
        assert vec[3] == 5.0  # experience

    def test_missing_ratio_calculation(self):
        vec = build_feature_vector(**self._base_args(missing_skills=["a", "b"], total_required_skills=4))
        assert vec[5] == 0.5  # missing_ratio = 2/4

    def test_missing_ratio_zero_when_no_required(self):
        vec = build_feature_vector(**self._base_args(missing_skills=[], total_required_skills=0))
        assert vec[5] == 0.0

    def test_interaction_features(self):
        vec = build_feature_vector(**self._base_args(semantic_score=80, skill_score=60))
        semantic_skill = 80.0 * 60.0 / 100
        assert abs(vec[6] - semantic_skill) < 0.01

    def test_balance_score(self):
        vec = build_feature_vector(**self._base_args(semantic_score=70, skill_score=70))
        assert vec[8] == 100.0  # perfect balance

    def test_ats_details_layout(self):
        ats_details = {
            "layout": {
                "bullet_score": 85.0,
                "sections_found": ["Summary", "Experience", "Education"],
                "section_presence_score": 70.0,
                "formatting_score": 80.0,
                "length_score": 60.0,
                "contact_score": 90.0,
            },
            "content": {
                "action_verb_score": 75.0,
                "achievement_score": 65.0,
            },
        }
        vec = build_feature_vector(**self._base_args(), ats_details=ats_details)
        assert vec[9] == 85.0  # bullet_score
        assert vec[10] == 3  # section_count
        assert vec[15] == 75.0  # action_verb_score

    def test_section_presence_flags(self):
        ats_details = {
            "layout": {"sections_found": ["summary", "skills", "experience", "education", "projects"]},
            "content": {},
        }
        vec = build_feature_vector(**self._base_args(), ats_details=ats_details)
        assert vec[17] == 1  # has_summary
        assert vec[18] == 1  # has_skills
        assert vec[19] == 1  # has_experience
        assert vec[20] == 1  # has_education
        assert vec[21] == 1  # has_projects

    def test_extra_params_passed_through(self):
        vec = build_feature_vector(
            **self._base_args(),
            domain_similarity=0.8,
            title_match=0.9,
            seniority_match=0.7,
            soft_skill_score=60.0,
            readability_score=75.0,
            keyword_density=0.05,
            education_quality=80.0,
        )
        assert vec[22] == 0.8  # domain_similarity
        assert vec[23] == 0.9  # title_match
        assert vec[28] == 80.0  # education_quality

    def test_feature_names_count_matches(self):
        assert len(FEATURE_NAMES) == N_FEATURES
