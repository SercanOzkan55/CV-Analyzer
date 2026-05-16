"""Unit tests for services/ats_scoring.py"""
import pytest
from schemas.cv_model import CVModel, Experience, Education, Project, Certification
from services.ats_scoring import score_cv, ScoreResult


def _make_model(**overrides) -> CVModel:
    """Build a CVModel with sensible defaults for testing."""
    defaults = dict(
        full_name="John Doe",
        title="Software Engineer",
        email="john@example.com",
        phone="+1234567890",
        summary="Experienced software engineer with 5 years in Python and cloud technologies.",
        experiences=[
            Experience(
                title="Senior Developer",
                company="TechCorp",
                start_date="2020",
                end_date="2024",
                bullets=[
                    "Developed REST APIs serving 10M requests/day",
                    "Led team of 5 engineers on microservices migration",
                    "Reduced deployment time by 60% using CI/CD pipelines",
                    "Mentored junior developers on best practices",
                ],
            ),
            Experience(
                title="Developer",
                company="StartupXYZ",
                start_date="2018",
                end_date="2020",
                bullets=[
                    "Built React frontend with TypeScript",
                    "Implemented OAuth2 authentication system",
                ],
            ),
        ],
        education=[
            Education(
                degree="B.Sc. Computer Science",
                school="MIT",
                start_date="2014",
                end_date="2018",
                field="Computer Science",
            ),
        ],
        skills=["Python", "Django", "PostgreSQL", "Docker", "AWS", "React"],
        skills_categorized={
            "Backend": ["Python", "Django", "FastAPI"],
            "DevOps": ["Docker", "AWS", "Kubernetes"],
        },
        languages=["English", "Turkish"],
        projects=[
            Project(name="OpenSourceLib", description="ML library", bullets=["1k stars"]),
        ],
        certifications=[
            Certification(name="AWS Solutions Architect", issuer="Amazon"),
        ],
    )
    defaults.update(overrides)
    return CVModel(**defaults)


class TestScoreCV:
    def test_returns_score_result(self):
        model = _make_model()
        result = score_cv(model)
        assert isinstance(result, ScoreResult)

    def test_overall_in_range(self):
        model = _make_model()
        result = score_cv(model)
        assert 0 <= result.overall <= 100

    def test_all_categories_in_range(self):
        model = _make_model()
        result = score_cv(model)
        for field in ["structure", "keywords", "experience", "education",
                      "languages", "ats", "length", "soft_skills"]:
            score = getattr(result, field)
            assert 0 <= score <= 100, f"{field} out of range: {score}"

    def test_complete_cv_scores_high(self):
        model = _make_model()
        result = score_cv(model)
        assert result.overall >= 60
        assert result.structure >= 80

    def test_empty_cv_scores_low(self):
        model = CVModel()
        result = score_cv(model)
        assert result.overall < 30
        assert result.structure == 0

    def test_experience_count_affects_score(self):
        no_exp = _make_model(experiences=[])
        with_exp = _make_model()
        r1 = score_cv(no_exp)
        r2 = score_cv(with_exp)
        assert r2.experience > r1.experience

    def test_skills_affect_keywords_score(self):
        no_skills = _make_model(skills=[], skills_categorized={})
        with_skills = _make_model()
        r1 = score_cv(no_skills)
        r2 = score_cv(with_skills)
        assert r2.keywords > r1.keywords

    def test_education_scoring(self):
        no_edu = _make_model(education=[])
        with_edu = _make_model()
        r1 = score_cv(no_edu)
        r2 = score_cv(with_edu)
        assert r1.education == 0
        assert r2.education > 50

    def test_language_scoring(self):
        no_lang = _make_model(languages=[])
        one_lang = _make_model(languages=["English"])
        two_lang = _make_model(languages=["English", "Turkish"])
        three_lang = _make_model(languages=["English", "Turkish", "French"])
        assert score_cv(no_lang).languages == 0
        assert score_cv(one_lang).languages == 50
        assert score_cv(two_lang).languages == 75
        assert score_cv(three_lang).languages == 100

    def test_short_cv_penalized_on_length(self):
        short = _make_model(
            summary="Hi",
            experiences=[],
            skills=[],
            skills_categorized={},
            projects=[],
            certifications=[],
            languages=[],
        )
        result = score_cv(short)
        assert result.length < 50

    def test_soft_skills_detected(self):
        model = _make_model(
            summary="Strong leadership and communication skills. "
                    "Excellent teamwork and problem-solving abilities. "
                    "Experienced in mentoring and stakeholder management.",
        )
        result = score_cv(model)
        assert result.soft_skills >= 50

    def test_no_soft_skills_scores_zero(self):
        model = _make_model(
            summary="Python developer.",
            experiences=[
                Experience(title="Dev", company="X", bullets=["Wrote code"]),
            ],
        )
        result = score_cv(model)
        assert result.soft_skills <= 25
