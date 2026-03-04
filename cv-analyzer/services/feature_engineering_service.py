def build_feature_vector(
    semantic_score,
    keyword_score,
    skill_score,
    exp_score,
    missing_skills,
    total_required_skills
):
    missing_count = len(missing_skills)

    if total_required_skills > 0:
        missing_ratio = missing_count / total_required_skills
    else:
        missing_ratio = 0

    semantic_skill_interaction = semantic_score * skill_score / 100
    keyword_skill_interaction = keyword_score * skill_score / 100
    balance_score = abs(semantic_score - skill_score)

    return [
        semantic_score,
        keyword_score,
        skill_score,
        exp_score,
        missing_count,
        missing_ratio,
        semantic_skill_interaction,
        keyword_skill_interaction,
        balance_score
    ]