import os

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_primary_name(job_text):

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
