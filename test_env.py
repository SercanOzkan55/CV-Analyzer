import os

from dotenv import load_dotenv

load_dotenv()

print("Environment variables:")
print(f"MOCK_SERVICES: '{os.getenv('MOCK_SERVICES')}'")
print(f"SUPABASE_URL: '{os.getenv('SUPABASE_URL')}'")
print(f"DATABASE_URL: '{os.getenv('DATABASE_URL')}'")

# Test the condition that should enable mock mode
mock_on = os.getenv("MOCK_SERVICES", "").lower() in ("1", "true", "yes")
print(f"Mock mode enabled: {mock_on}")
