import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def redacted(url: str):
    if not url:
        return None
    # hide credentials
    try:
        parts = url.split("@")
        if len(parts) == 2:
            return "***@" + parts[1]
    except Exception:
        pass
    return url


def main():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    print("DATABASE_URL:", redacted(url))
    if not url:
        print("NO_DATABASE_URL")
        return 2
    url = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    engine = create_engine(url)
    with engine.connect() as conn:
        try:
            r = conn.execute(text("SELECT extname FROM pg_extension WHERE extname='vector';"))
            rows = r.fetchall()
            print("PGVECTOR:", "INSTALLED" if rows else "MISSING")
        except Exception as e:
            print("PGVECTOR_CHECK_ERROR", e)

        try:
            r = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='candidates';"))
            cols = [row[0] for row in r.fetchall()]
            print("CANDIDATES_TABLE_EXISTS:", bool(cols))
            if cols:
                print("CANDIDATES_COLUMNS:", cols)
        except Exception as e:
            print("CANDIDATES_TABLE_CHECK_ERROR", e)

        try:
            r = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='jobs';"))
            cols = [row[0] for row in r.fetchall()]
            print("JOBS_TABLE_EXISTS:", bool(cols))
            if cols:
                print("JOBS_COLUMNS_SAMPLE:", [c for c in cols if "embedding" in c])
        except Exception as e:
            print("JOBS_TABLE_CHECK_ERROR", e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
