import os

file_path = r"c:\Users\ASUS\Desktop\cv-analyzer\services\rewrite_service.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update _generate and ai_rewrite_available
target_1 = """def _generate(prompt: str, max_tokens: int = 512) -> str:
    provider = _select_provider()
    if provider == "mock":
        return _mock_generate(prompt, max_tokens=max_tokens)

    api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        return _mock_generate(prompt, max_tokens=max_tokens)

    try:
        from openai import OpenAI
    except Exception:
        return _mock_generate(prompt, max_tokens=max_tokens)

    model = str(os.getenv("REWRITE_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    base_url = os.getenv("OPENAI_API_BASE")
    timeout_seconds = float(os.getenv("REWRITE_TIMEOUT_SECONDS", "25") or "25")
    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=max_tokens,
            timeout=timeout_seconds,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        raise RuntimeError(f"AI provider error: {exc}")


def ai_rewrite_available() -> bool:
    provider = _select_provider()
    if provider == "mock":
        return False
    if provider in {"openai", "openai-compatible"}:
        return bool(str(os.getenv("OPENAI_API_KEY", "")).strip())
    return False"""

replacement_1 = """def _generate(prompt: str, max_tokens: int = 512) -> str:
    from services.ai_client_factory import get_ai_client_and_model
    client, model = get_ai_client_and_model()
    if not client:
        return _mock_generate(prompt, max_tokens=max_tokens)

    timeout_seconds = float(os.getenv("REWRITE_TIMEOUT_SECONDS", "25") or "25")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=max_tokens,
            timeout=timeout_seconds,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        raise RuntimeError(f"AI provider error: {exc}")


def ai_rewrite_available() -> bool:
    from services.ai_client_factory import get_ai_client_and_model
    client, _ = get_ai_client_and_model()
    return client is not None"""

# 2. Update ai_review_cv_payload client creation
target_2 = """    source_payload = dict(payload)
    if _select_provider() == "mock":
        return source_payload

    api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        return source_payload

    try:
        from openai import OpenAI
    except Exception:
        return source_payload

    model = str(os.getenv("AI_FINAL_REVIEW_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    timeout_seconds = float(os.getenv("AI_FINAL_REVIEW_TIMEOUT_SECONDS", "20") or "20")
    client = OpenAI(api_key=api_key)"""

replacement_2 = """    source_payload = dict(payload)
    from services.ai_client_factory import get_ai_client_and_model
    client, default_model = get_ai_client_and_model()
    if not client:
        return source_payload

    model = str(os.getenv("AI_FINAL_REVIEW_MODEL", "")).strip() or default_model
    timeout_seconds = float(os.getenv("AI_FINAL_REVIEW_TIMEOUT_SECONDS", "20") or "20")"""

# 3. Update suggest_summaries client creation
target_3 = """    provider = _select_provider()
    if provider == "mock":
        return _mock_suggest_summaries(summary, job_description, lang, count)

    api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        return _mock_suggest_summaries(summary, job_description, lang, count)

    try:
        from openai import OpenAI
    except Exception:
        return _mock_suggest_summaries(summary, job_description, lang, count)

    model = str(os.getenv("AI_SUGGEST_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    timeout_seconds = float(os.getenv("AI_SUGGEST_TIMEOUT_SECONDS", "15") or "15")
    client = OpenAI(api_key=api_key)"""

replacement_3 = """    from services.ai_client_factory import get_ai_client_and_model
    client, default_model = get_ai_client_and_model()
    if not client:
        return _mock_suggest_summaries(summary, job_description, lang, count)

    model = str(os.getenv("AI_SUGGEST_MODEL", "")).strip() or default_model
    timeout_seconds = float(os.getenv("AI_SUGGEST_TIMEOUT_SECONDS", "15") or "15")"""

# 4. Update generate_interview_questions check
target_4 = """    provider = _select_provider()
    if provider == "mock" or not str(os.getenv("OPENAI_API_KEY", "")).strip():
        return _mock_interview_questions(cv_text, job_description, lang, normalized_mode, count)"""

replacement_4 = """    if not ai_rewrite_available():
        return _mock_interview_questions(cv_text, job_description, lang, normalized_mode, count)"""

# 5. Update evaluate_interview_answer check
target_5 = """    provider = _select_provider()
    if provider == "mock" or not str(os.getenv("OPENAI_API_KEY", "")).strip():
        return _mock_evaluate_answer(question, answer, lang)"""

replacement_5 = """    if not ai_rewrite_available():
        return _mock_evaluate_answer(question, answer, lang)"""

# Perform replacements
checks = [
    (target_1, replacement_1, "1. _generate"),
    (target_2, replacement_2, "2. ai_review_cv_payload"),
    (target_3, replacement_3, "3. suggest_summaries"),
    (target_4, replacement_4, "4. generate_interview_questions"),
    (target_5, replacement_5, "5. evaluate_interview_answer"),
]

modified = content
for target, replacement, desc in checks:
    # Normalize line endings to avoid platform mismatch
    target_norm = target.replace("\r\n", "\n")
    modified_norm = modified.replace("\r\n", "\n")
    
    if target_norm in modified_norm:
        modified_norm = modified_norm.replace(target_norm, replacement.replace("\r\n", "\n"))
        modified = modified_norm
        print(f"SUCCESS: Applied {desc}")
    else:
        print(f"FAILED: Could not find match for {desc}")

with open(file_path, 'w', encoding='utf-8', newline='') as f:
    f.write(modified)
