import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# convert to psycopg2-friendly URL
clean_url = DATABASE_URL
if clean_url.startswith("postgresql+psycopg2://"):
    clean_url = clean_url.replace("postgresql+psycopg2://", "postgresql://", 1)
conn = psycopg2.connect(clean_url)
conn.autocommit = True
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS industries (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    centroid VECTOR(1536),
    sample_count INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    raw_text TEXT,
    embedding VECTOR(1536),
    industry_id INT REFERENCES industries(id),
    created_at TIMESTAMP DEFAULT NOW()
);
""")

print("Database setup completed successfully.")

cur.close()
conn.close()

# Create SQLAlchemy models (User, Analysis, etc.)
from database import engine
from models import Base

# ------------------------------------------------------------------
# Historical note:
# Early development relied on dropping and recreating all ORM tables on
# each invocation. That made schema tweaks easy but obliterated any
# stored data and bypassed our new migration system. Since we now use
# Alembic, we should avoid destructive operations.
#
# The first Alembic revision simply stamps the existing schema. It is
# intentionally a no-op so that applying migrations against an existing
# database doesn't inadvertently delete the legacy industry/job tables
# which are still managed via raw SQL elsewhere in this script.
#
# This helper remains a convenience for bootstrapping a fresh database
# during development. It will *create* any missing ORM tables but will
# never drop anything. For production and continuous deployment,
# always run `alembic upgrade head` instead of this script.
# ------------------------------------------------------------------

# non-destructive table creation
Base.metadata.create_all(bind=engine)
print("SQLAlchemy models created (create_all) successfully.")