def generate_recommendations(missing_skills, semantic_score, keyword_score):

    recommendations = []

    # Öncelik 1: Semantic çok düşükse
    if semantic_score < 40:
        recommendations.append(
            "Your CV structure does not align well with this job description. Rewrite your experience section using similar terminology."
        )
        return recommendations

    # Öncelik 2: Teknik skill eksikliği
    if missing_skills:
        top_skills = missing_skills[:2]
        for skill in top_skills:
            recommendations.append(
                f"Add measurable project experience demonstrating {skill}."
            )
        return recommendations

    # Öncelik 3: Keyword problemi
    if keyword_score < 50:
        recommendations.append(
            "Improve keyword matching by explicitly mentioning required technologies."
        )
        return recommendations

    # Eğer her şey iyiyse
    recommendations.append(
        "Your CV is generally aligned. Focus on adding quantified achievements."
    )

    return recommendations