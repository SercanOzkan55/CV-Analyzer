import os

file_path = r"c:\Users\ASUS\Desktop\cv-analyzer\services\domain_service.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target_1 = """_OPENAI_KEY = os.getenv("OPENAI_API_KEY")

if not _OPENAI_KEY:
    client = None  # Will be checked in functions
else:
    client = OpenAI(api_key=_OPENAI_KEY)"""

replacement_1 = """def _get_client_and_model():
    if _mock_services_on():
        return None, None
    try:
        from services.ai_client_factory import get_ai_client_and_model
        return get_ai_client_and_model()
    except Exception:
        return None, None"""

target_2 = """def classify_domain_llm(job_text):
    # Allow mocking for testing without OpenAI API
    if _mock_services_on() or not client:
        return "Engineering & Technology"  # Default mock domain"""

replacement_2 = """def classify_domain_llm(job_text):
    client, model = _get_client_and_model()
    # Allow mocking for testing without OpenAI API
    if _mock_services_on() or not client:
        return "Engineering & Technology"  # Default mock domain"""

target_3 = """    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )"""

replacement_3 = """    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
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
