import logging
import os
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


MAX_INPUT_CHARS = int(os.getenv("REWRITE_MAX_INPUT_CHARS", "8000") or "8000")
MAX_OUTPUT_CHARS = int(os.getenv("REWRITE_MAX_OUTPUT_CHARS", "4000") or "4000")
MOCK_SERVICES_ON = os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes")
logger = logging.getLogger(__name__)


def _guard_text(value: str, max_chars: int, field_name: str) -> str:
    if not isinstance(value, str):
        value = str(value or "")
    value = value.strip()
    if len(value) > max_chars:
        # Hard truncate to avoid runaway prompts; caller can surface
        # a warning in the UI if needed.
        value = value[:max_chars]
    if not value:
        raise ValueError(f"{field_name} cannot be empty")
    return value


def _select_provider() -> str:
    """Return the logical provider name.

    For now this supports a built-in mock provider for local/dev. Future
    implementations can route to OpenAI, Anthropic or others without
    changing call sites.
    """

    provider = os.getenv("REWRITE_PROVIDER", "auto").strip().lower()
    if not provider:
        provider = "auto"
    if provider == "auto":
        if (not MOCK_SERVICES_ON) and os.getenv("OPENAI_API_KEY"):
            return "openai"
        return "mock"
    return provider


def _mock_generate(prompt: str, max_tokens: int = 512) -> str:
    # Deterministic and safe stub for tests and local dev.
    snippet = prompt.strip().replace("\n", " ")
    if len(snippet) > MAX_OUTPUT_CHARS:
        snippet = snippet[:MAX_OUTPUT_CHARS]
    return f"[mock-rewrite] {snippet[: max_tokens * 4]}"


def _generate(prompt: str, max_tokens: int = 512) -> str:
    provider = _select_provider()
    if provider == "mock":
        return _mock_generate(prompt, max_tokens=max_tokens)

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for rewrite provider 'openai'")
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            model = os.getenv("REWRITE_OPENAI_MODEL", "gpt-4o-mini")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise CV, ATS, and career writing assistant. "
                            "Preserve facts, never invent employers, dates, degrees, "
                            "certifications, metrics, or skills, and match the requested language."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=float(os.getenv("REWRITE_TEMPERATURE", "0.25")),
                max_tokens=max_tokens,
            )
            text = (response.choices[0].message.content or "").strip()
            if not text:
                raise RuntimeError("AI rewrite provider returned an empty response")
            return text[:MAX_OUTPUT_CHARS]
        except RuntimeError:
            raise
        except Exception as exc:
            logger.warning("OpenAI rewrite provider failed: %s", exc)
            raise RuntimeError("AI rewrite provider request failed")

    raise RuntimeError(f"AI rewrite provider '{provider}' is not configured")


def ai_rewrite_available() -> bool:
    return _select_provider() != "mock"


def generate_text(prompt: str, max_tokens: int = 512) -> str:
    prompt = _guard_text(prompt, MAX_INPUT_CHARS, "prompt")
    return _generate(prompt, max_tokens=max_tokens)


def rewrite_cv(
    cv_text: str,
    job_description: str = "",
    lang: str = "auto",
    tone: str = "professional",
) -> str:
    cv_text = _guard_text(cv_text, MAX_INPUT_CHARS, "cv_text")
    job_description = job_description or ""

    prompt = (
        f"Rewrite the following CV in a {tone} tone, optimized for ATS and the target job.\n"
        f"Language: {lang}.\n"
        f"Job description (optional): {job_description}\n\n"
        f"CV:\n{cv_text}\n"
    )
    return _generate(prompt)


def rewrite_cv_for_ats(
    cv_text: str,
    job_description: str = "",
    lang: str = "auto",
    tone: str = "professional",
) -> str:
    cv_text = _guard_text(cv_text, MAX_INPUT_CHARS, "cv_text")
    job_description = job_description or ""

    prompt = (
        f"Rewrite the following CV to improve ATS compatibility in a {tone} tone.\n"
        f"Language: {lang}.\n"
        "Rules:\n"
        "1. Preserve all factual details from the source CV.\n"
        "2. Do not invent employers, dates, metrics, certifications, degrees, or skills.\n"
        "3. Keep only ATS-relevant sections such as contact, summary, experience, education, skills, certifications, projects, and languages.\n"
        "4. Prefer standard section headings and concise bullet points.\n"
        "5. Remove clearly irrelevant sections such as references, hobbies, marital status, date of birth, and photo mentions.\n"
        f"6. Use job-description keywords only when they are already supported by the CV or clearly implied by the source text.\n"
        f"Job description (optional): {job_description}\n\n"
        f"CV:\n{cv_text}\n"
    )
    return _generate(prompt, max_tokens=1024)


def rewrite_bullets(
    bullets: List[str],
    job_description: str = "",
    lang: str = "auto",
    tone: str = "professional",
) -> List[str]:
    if not isinstance(bullets, list) or not bullets:
        raise ValueError("bullets must be a non-empty list")
    joined = "\n".join(str(b).strip() for b in bullets if str(b).strip())
    joined = _guard_text(joined, MAX_INPUT_CHARS, "bullets")
    job_description = job_description or ""

    prompt = (
        f"Rewrite the following CV bullet points in a {tone} tone, using strong action verbs and quantification where possible.\n"
        f"Language: {lang}.\n"
        f"Job description (optional): {job_description}\n\n"
        f"Bullets:\n{joined}\n"
    )
    raw = _generate(prompt)
    # In mock mode we simply return a single rewritten text; in real
    # providers this can be parsed into separate bullets.
    return [raw]


def rewrite_cover_letter(
    cv_text: str,
    job_description: str,
    lang: str = "auto",
    tone: str = "professional",
) -> str:
    cv_text = _guard_text(cv_text, MAX_INPUT_CHARS, "cv_text")
    job_description = _guard_text(job_description, MAX_INPUT_CHARS, "job_description")

    prompt = (
        f"Draft a tailored cover letter in a {tone} tone based on the CV and job description.\n"
        f"Language: {lang}.\n\n"
        f"Job description:\n{job_description}\n\n"
        f"CV:\n{cv_text}\n"
    )
    return _generate(prompt)
