import os
import sys
from urllib.parse import urlparse

# ensure project root is on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from database import Base, engine

# Destructive reset is deliberately impossible against production or any
# remote database. Both checks are required so an accidentally loaded .env
# cannot turn a local maintenance command into a production incident.
environment = os.getenv("ENV", "development").strip().lower()
database_url = str(engine.url)
parsed = urlparse(database_url)
hostname = (parsed.hostname or "").lower()
local_hosts = {"", "localhost", "127.0.0.1", "::1", "db", "postgres", "testdb"}

if environment in {"production", "prod"}:
    raise SystemExit("Refusing to drop tables: ENV is production.")
if not database_url.startswith("sqlite") and hostname not in local_hosts:
    raise SystemExit(f"Refusing to drop tables on remote database host: {hostname or '<unknown>'}.")
if os.getenv("ALLOW_DESTRUCTIVE_DB_RESET") != "1":
    raise SystemExit(
        "Refusing to drop tables without ALLOW_DESTRUCTIVE_DB_RESET=1. "
        "Use only with a disposable local development/test database."
    )

Base.metadata.drop_all(bind=engine)
print("All tables dropped")
