import os

from openai import OpenAI

# Initialize OpenAI client conditionally
MOCK_SERVICES_ON = os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes")
_OPENAI_KEY = os.getenv("OPENAI_API_KEY")

if MOCK_SERVICES_ON or not _OPENAI_KEY:
    client = None  # Will be checked in functions
else:
    client = OpenAI(api_key=_OPENAI_KEY)


def generate_primary_name(job_text):
    # Allow mocking for testing without OpenAI API
    if MOCK_SERVICES_ON or not client:
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
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()


def generate_specialization_name(job_text):
    # Allow mocking for testing without OpenAI API
    if MOCK_SERVICES_ON or not client:
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
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()
