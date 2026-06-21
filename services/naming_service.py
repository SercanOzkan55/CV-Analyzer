import os


def _mock_services_on() -> bool:
    return os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes")


def _get_client_and_model():
    if _mock_services_on():
        return None, None
    try:
        from services.ai_client_factory import get_ai_client_and_model

        return get_ai_client_and_model()
    except Exception:
        return None, None


def generate_primary_name(job_text):
    client, model = _get_client_and_model()
    # Allow mocking for testing without OpenAI API
    if _mock_services_on() or not client:
        return "Engineering Technology"  # Default mock primary name

    prompt = f"""
You are a strict classification engine.

Return ONLY a concise high-level industry category.
Maximum 3 words.
No explanation.
No punctuation.

Job Description:
{job_text}
"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()


def generate_specialization_name(job_text):
    client, model = _get_client_and_model()
    # Allow mocking for testing without OpenAI API
    if _mock_services_on() or not client:
        return "Software Development"  # Default mock specialization

    prompt = f"""
You are a strict job specialization classifier.

Return ONLY a concise specialization title.
Maximum 4 words.
No explanation.
No punctuation.

Job Description:
{job_text}
"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()
