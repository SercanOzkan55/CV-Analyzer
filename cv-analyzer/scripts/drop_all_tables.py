import os, sys
# ensure project root is on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from database import engine, Base

# WARNING: This will drop ALL tables in the configured database.
# Only run on development/test databases!

Base.metadata.drop_all(bind=engine)
print("All tables dropped")