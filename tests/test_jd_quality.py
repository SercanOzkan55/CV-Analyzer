import main as main_module


def test_invalid_job_description_disables_match_score():
    quality = main_module._assess_job_description_quality("zfvsgfdsf", [])

    assert quality["status"] == "invalid"
    assert quality["valid"] is False


def test_short_real_job_description_is_weak_not_invalid():
    quality = main_module._assess_job_description_quality("backend developer", [])

    assert quality["status"] == "weak"
    assert quality["valid"] is True


def test_detailed_job_description_is_ok():
    jd = (
        "Backend developer responsible for Python APIs, SQL database design, "
        "Docker deployments, testing, performance monitoring, and cross-functional "
        "collaboration with product and frontend teams."
    )

    quality = main_module._assess_job_description_quality(jd, ["python", "sql", "docker"])

    assert quality["status"] == "ok"
    assert quality["valid"] is True
