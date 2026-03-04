from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_industry_name(job_text):

    prompt = f"""
    You are an expert in job market classification.

    Analyze the following job description and generate a concise,
    professional industry name (max 4 words).

    Examples:
    - Java Backend Development
    - Mechanical Engineering
    - Data Science
    - Embedded Systems Engineering
    - Cloud Infrastructure Engineering

    Job Description:
    {job_text}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You classify job descriptions into industry names."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    industry_name = response.choices[0].message.content.strip()
    return industry_name