"""Reset all users to free plan."""

import os

os.environ["DATABASE_URL"] = "postgresql://postgres:Sercan16187341966@db.oanidolrgdukiqxvvbzd.supabase.co:5432/postgres"

from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as conn:
    r = conn.execute(text("UPDATE app_users SET plan_type = 'free' WHERE plan_type != 'free'"))
    conn.commit()
    print(f"{r.rowcount} users reset to free")
