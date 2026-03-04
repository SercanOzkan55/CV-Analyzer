# Docker secrets usage example for production
# Place this file as 'docker-secrets.md' in your repo for reference

## 1. Create secret files (one per secret)
# Example: openai_api_key.txt, db_url.txt, jwt_secret.txt

## 2. Add secrets to Docker
# docker secret create openai_api_key openai_api_key.txt
# docker secret create db_url db_url.txt
# docker secret create jwt_secret jwt_secret.txt

## 3. Reference secrets in docker-compose.yml
services:
  app:
    image: your-app-image
    secrets:
      - openai_api_key
      - db_url
      - jwt_secret
    environment:
      OPENAI_API_KEY_FILE: /run/secrets/openai_api_key
      DATABASE_URL_FILE: /run/secrets/db_url
      SUPABASE_JWT_SECRET_FILE: /run/secrets/jwt_secret
    # ...other config...

secrets:
  openai_api_key:
    file: ./openai_api_key.txt
  db_url:
    file: ./db_url.txt
  jwt_secret:
    file: ./jwt_secret.txt

## 4. Read secrets in Python
import os

def read_secret(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return None

OPENAI_API_KEY = read_secret(os.getenv("OPENAI_API_KEY_FILE", ".env"))
DATABASE_URL = read_secret(os.getenv("DATABASE_URL_FILE", ".env"))
SUPABASE_JWT_SECRET = read_secret(os.getenv("SUPABASE_JWT_SECRET_FILE", ".env"))

# Use these variables in your app config
