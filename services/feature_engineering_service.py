FEATURE_NAMES = [
    "semantic",
    "keyword",
    "skill",
    "experience",
    "missing_count",
    "missing_ratio",
    "semantic_skill_interaction",
    "keyword_skill_interaction",
    "balance_score",
    "bullet_score",
    "section_count",
    "section_presence_score",
    "formatting_score",
    "length_score",
    "contact_score",
    "action_verb_score",
    "achievement_score",
    "has_summary",
    "has_skills",
    "has_experience",
    "has_education",
    "has_projects",
    "domain_similarity",
    "title_match",
    "seniority_match",
    "soft_skill_score",
    "readability_score",
    "keyword_density",
    "education_quality",
]

N_FEATURES = len(FEATURE_NAMES)


def build_feature_vector(
    semantic_score,
    keyword_score,
    skill_score,
    exp_score,
    missing_skills,
    total_required_skills,
    ats_details=None,
    domain_similarity=0.0,
    title_match=0.0,
    seniority_match=0.0,
    soft_skill_score=0.0,
    readability_score=0.0,
    keyword_density=0.0,
    education_quality=0.0,
):
    # Floor values: prevent 0-scores from bad parse / empty PDF / student CV
    semantic_score = max(float(semantic_score), 5.0)
    keyword_score = max(float(keyword_score), 5.0)
    skill_score = max(float(skill_score), 5.0)
    exp_score = max(float(exp_score), 5.0)

    missing_count = len(missing_skills)

    if total_required_skills > 0:
        missing_ratio = missing_count / total_required_skills
    else:
        missing_ratio = 0

    semantic_skill_interaction = semantic_score * skill_score / 100
    keyword_skill_interaction = keyword_score * skill_score / 100
    balance_score = max(0.0, 100.0 - abs(semantic_score - skill_score))

    layout = (ats_details or {}).get("layout", {})
    content = (ats_details or {}).get("content", {})
    sections_found = layout.get("sections_found", [])

    bullet_score = float(layout.get("bullet_score", 0.0))
    section_count = int(len(sections_found))
    section_presence_score = float(layout.get("section_presence_score", 0.0))
    formatting_score = float(layout.get("formatting_score", 0.0))
    length_score = float(layout.get("length_score", 0.0))
    contact_score = float(layout.get("contact_score", 0.0))

    action_verb_score = float(content.get("action_verb_score", 0.0))
    achievement_score = float(content.get("achievement_score", 0.0))

    sections_lower = {s.lower() for s in sections_found}
    has_summary = int(any(s in sections_lower for s in ("summary", "profile", "objective")))
    has_skills = int("skills" in sections_lower)
    has_experience = int("experience" in sections_lower)
    has_education = int("education" in sections_lower)
    has_projects = int("projects" in sections_lower)

    features = [
        semantic_score,
        keyword_score,
        skill_score,
        exp_score,
        missing_count,
        missing_ratio,
        semantic_skill_interaction,
        keyword_skill_interaction,
        balance_score,
        bullet_score,
        section_count,
        section_presence_score,
        formatting_score,
        length_score,
        contact_score,
        action_verb_score,
        achievement_score,
        has_summary,
        has_skills,
        has_experience,
        has_education,
        has_projects,
        float(domain_similarity),
        float(title_match),
        float(seniority_match),
        float(soft_skill_score),
        float(readability_score),
        float(keyword_density),
        float(education_quality),
    ]
    if len(features) != N_FEATURES:
        raise ValueError(f"build_feature_vector: expected {N_FEATURES} features, got {len(features)}")
    return features
