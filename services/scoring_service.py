from sklearn.metrics.pairwise import cosine_similarity


def calculate_similarity(vec1, vec2):
    similarity = cosine_similarity([vec1], [vec2])
    return float(similarity[0][0])
