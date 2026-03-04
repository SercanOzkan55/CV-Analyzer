import sys
import types
import importlib
import os

# ensure project root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# --- Create stub modules before importing main ---
# Stub services.model_service
model_mod = types.ModuleType("services.model_service")
def predict_match(features):
    return 80.0, 90.0, "Low Risk", {"note": "stub"}
model_mod.predict_match = predict_match
sys.modules["services.model_service"] = model_mod

# Stub services.embedding_service
embed_mod = types.ModuleType("services.embedding_service")
def get_embedding(text):
    # return fixed small vector
    return [0.01] * 1536
embed_mod.get_embedding = get_embedding
sys.modules["services.embedding_service"] = embed_mod

# Stub services.domain_service
domain_mod = types.ModuleType("services.domain_service")
def detect_or_create_domain(job_text, embedding=None):
    return {"domain_id": 1, "domain_name": "Other"}
def get_domain_similarity(domain_id, embedding):
    return 0.0
domain_mod.detect_or_create_domain = detect_or_create_domain
domain_mod.get_domain_similarity = get_domain_similarity
sys.modules["services.domain_service"] = domain_mod

# Stub services.industry_service
ind_mod = types.ModuleType("services.industry_service")
def detect_industry_and_specialization(job_text, embedding=None):
    return {"industry_id": 1, "industry_name": "Other", "specialization_id": 1, "specialization_name": "General"}
ind_mod.detect_industry_and_specialization = detect_industry_and_specialization
sys.modules["services.industry_service"] = ind_mod

# Stub database and models to avoid DB dependency
db_mod = types.ModuleType("database")
class DummySession:
    def __init__(self):
        pass
    def add(self, _):
        pass
    def commit(self):
        pass
    def refresh(self, _):
        pass
    def rollback(self):
        pass
    def close(self):
        pass
    def query(self, *a, **k):
        class Q:
            def order_by(self, *a, **k):
                class R:
                    def all(self):
                        return []
                return R()
        return Q()


db_mod.engine = object()
from types import SimpleNamespace

def SessionLocal():
    return DummySession()

db_mod.SessionLocal = SessionLocal
sys.modules["database"] = db_mod

# Stub models.Analysis
models_mod = types.ModuleType("models")
class Analysis:
    class metadata:
        @staticmethod
        def create_all(bind=None):
            return None

    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            setattr(self, k, v)
    # provide a dummy Column-like attribute used in queries
    class _Id:
        @staticmethod
        def desc():
            return None

    id = _Id()
models_mod.Analysis = Analysis
sys.modules["models"] = models_mod

# Stub slowapi to avoid decorator issues during tests
slowapi_mod = types.ModuleType("slowapi")
class DummyLimiter:
    def __init__(self, *a, **k):
        pass
    def limit(self, *args, **kwargs):
        def _decorator(f):
            return f
        return _decorator
slowapi_mod.Limiter = DummyLimiter
util_mod = types.ModuleType("slowapi.util")
def get_remote_address(request=None):
    return "test-client"
util_mod.get_remote_address = get_remote_address
sys.modules["slowapi"] = slowapi_mod
sys.modules["slowapi.util"] = util_mod

# Now import the modules we will test
import services.ats_service as ats
print("Running ATS unit test (analyze_cv)...")
cv = "John Doe\nExperience: Managed a team that increased revenue by 20%\nSkills: Python, SQL\nContact: john@example.com"
job = "Looking for a software engineer with experience in Python and SQL. Increase revenue and manage team."
res = ats.analyze_cv(cv, job)
print("ATS result:", res)

# Import main after stubbing required services
import importlib
main = importlib.import_module('main')

# Monkeypatch PDF reader used by main
class DummyPage:
    def extract_text(self):
        return "Managed projects and increased revenue by 20%"
class DummyPdfReader:
    def __init__(self, stream):
        self.pages = [DummyPage()]

main.PyPDF2.PdfReader = DummyPdfReader

# B) Pipeline integration (run_pipeline)
print('\nRunning pipeline integration test (run_pipeline)...')
result = main.run_pipeline(cv, job)
print('Pipeline result keys:', list(result.keys()))
print('Final score:', result.get('final_score'))

# C) HTTP endpoint tests using TestClient
print('\nRunning HTTP endpoint tests...')
from fastapi.testclient import TestClient
client = TestClient(main.app)

# /analyze
resp = client.post('/analyze', json={'cv_text': cv, 'job_description': job})
print('/analyze status', resp.status_code)
print('/analyze json keys', list(resp.json().keys()) if resp.status_code==200 else resp.text)

# /analyze-pdf (multipart) - send minimal pdf bytes
pdf_bytes = b"%PDF-1.4\n%EOF\n"
files = {'file': ('test.pdf', pdf_bytes, 'application/pdf')}
resp2 = client.post('/analyze-pdf', files=files, data={'job_description': job})
print('/analyze-pdf status', resp2.status_code)
print('/analyze-pdf json keys', list(resp2.json().keys()) if resp2.status_code==200 else resp2.text)

# /history
resp3 = client.get('/history')
print('/history status', resp3.status_code)
print('/history json', resp3.json() if resp3.status_code==200 else resp3.text)

print('\nAll tests completed.')
