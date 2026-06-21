import os

file_path = r"c:\Users\ASUS\Desktop\cv-analyzer\services\cv_builder_service.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target_1 = """_OPENAI_KEY = os.getenv("OPENAI_API_KEY")

def _get_openai_client():
    if MOCK_SERVICES_ON or not _OPENAI_KEY:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=_OPENAI_KEY)
    except Exception:
        return None"""

replacement_1 = """def _get_openai_client_and_model():
    if MOCK_SERVICES_ON:
        return None, None
    try:
        from services.ai_client_factory import get_ai_client_and_model
        return get_ai_client_and_model()
    except Exception:
        return None, None"""

target_2 = """    client = _get_openai_client()
    if not client:
        return _mock_enhance(cv_data, job_description, lang)"""

replacement_2 = """    client, model = _get_openai_client_and_model()
    if not client:
        return _mock_enhance(cv_data, job_description, lang)"""

target_3 = """                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.4,
                    max_tokens=3000,
                    timeout=_AI_TIMEOUT_SECONDS,
                )"""

replacement_3 = """                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.4,
                    max_tokens=3000,
                    timeout=_AI_TIMEOUT_SECONDS,
                )"""

modified = content.replace("\r\n", "\n")
target_1_norm = target_1.replace("\r\n", "\n")
target_2_norm = target_2.replace("\r\n", "\n")
target_3_norm = target_3.replace("\r\n", "\n")

if target_1_norm in modified:
    modified = modified.replace(target_1_norm, replacement_1.replace("\r\n", "\n"))
    print("SUCCESS: target_1 replaced")
else:
    print("FAILED: target_1 not found")

if target_2_norm in modified:
    modified = modified.replace(target_2_norm, replacement_2.replace("\r\n", "\n"))
    print("SUCCESS: target_2 replaced")
else:
    print("FAILED: target_2 not found")

if target_3_norm in modified:
    modified = modified.replace(target_3_norm, replacement_3.replace("\r\n", "\n"))
    print("SUCCESS: target_3 replaced")
else:
    print("FAILED: target_3 not found")

with open(file_path, "w", encoding="utf-8", newline="") as f:
    f.write(modified)
