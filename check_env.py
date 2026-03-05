from pathlib import Path

content = Path(".env").read_text()
print(f"File size: {len(content)} chars")
print(f"First 300 chars:\n{content[:300]}\n")
print(f"Has newlines: {chr(10) in content}")
print(f'Has SUPABASE_JWT_SECRET: {"SUPABASE_JWT_SECRET" in content}')

if "SUPABASE_JWT_SECRET" in content:
    idx = content.find("SUPABASE_JWT_SECRET")
    print(f"\nSUPABASE_JWT_SECRET found at position {idx}")
    print(f"Content around it:\n{content[idx:idx+100]}")
