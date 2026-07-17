"""Reset all users to free plan."""

import os

from sqlalchemy import create_engine, text

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL must be set before running reset_plans.py")

engine = create_engine(database_url)
with engine.connect() as conn:
    r = conn.execute(text("UPDATE app_users SET plan_type = 'free' WHERE plan_type != 'free'"))
    conn.commit()
    print(f"{r.rowcount} users reset to free")
