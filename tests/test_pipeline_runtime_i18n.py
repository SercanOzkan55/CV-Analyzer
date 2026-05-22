from services.pipeline_runtime import _detect_seniority, build_features


def _features(cv_text: str, job_description: str = "") -> list[float]:
    return build_features(
        semantic=70,
        keyword=70,
        skill=70,
        exp=70,
        missing_skills=[],
        domain_similarity=70,
        ats_score=70,
        ats_details={},
        title_match=70,
        seniority_match=70,
        cv_text=cv_text,
        job_description=job_description,
    )


def test_readability_counts_latin_extended_words():
    features = _features(
        "Türkçe iletişim becerileri güçlü, çözüm odaklı mühendislik deneyimi.",
        "Mühendislik deneyimi ve iletişim beklenir.",
    )
    assert features[26] > 0


def test_keyword_density_filters_turkish_stopwords():
    features = _features(
        "ve ile için bir ve ile için bir",
        "ve ile için bir",
    )
    assert features[27] == 0


def test_soft_skill_score_detects_turkish_terms():
    features = _features(
        "Liderlik, takım çalışması, iletişim ve problem çözme konularında güçlü.",
        "Takım çalışması ve iletişim önemlidir.",
    )
    assert features[25] > 0


def test_seniority_detection_supports_major_european_titles():
    assert _detect_seniority("Praktikant Softwareentwicklung") == "intern"
    assert _detect_seniority("Becario de ingeniería") == "intern"
    assert _detect_seniority("Leiter Engineering") in {"senior", "manager"}
    assert _detect_seniority("Gerente de producto") == "manager"


def test_education_quality_supports_global_degree_terms():
    assert _features("Abitur Gymnasium", "")[28] == 20
    assert _features("Licenciatura en Informática", "")[28] == 60
    assert _features("Laurea magistrale in Ingegneria", "")[28] == 80
    assert _features("Doctorado en Ciencias", "")[28] == 100
