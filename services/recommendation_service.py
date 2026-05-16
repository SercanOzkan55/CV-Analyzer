from .language_service import get_recommendation


def generate_recommendations(missing_skills, semantic_score, keyword_score, lang="en"):
    """
    Generate prioritized, multi-dimensional recommendations.
    Returns up to 5 recommendations covering all weak areas.
    """
    recommendations = []

    # Semantic alignment problem
    if semantic_score < 40:
        recommendations.append(get_recommendation("semantic_low", lang))

    # Missing skills (show top 3)
    if missing_skills:
        for skill in missing_skills[:3]:
            recommendations.append(get_recommendation("add_skill", lang, skill))

    # Keyword matching problem
    if keyword_score < 50:
        recommendations.append(get_recommendation("keyword_low", lang))

    # If everything looks good
    if not recommendations:
        recommendations.append(get_recommendation("all_good", lang))

    # Cap at 5 to avoid overwhelming
    return recommendations[:5]
