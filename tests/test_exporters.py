import pytest
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse
from utils.csv_exporter import (
    generate_csv_download,
    get_temp_download as get_csv_temp_download,
    cleanup_expired_downloads as cleanup_csv,
    _temp_downloads as csv_store
)
from utils.json_exporter import (
    generate_json_download,
    get_temp_download as get_json_temp_download,
    cleanup_expired_downloads as cleanup_json,
    _temp_downloads as json_store
)

def _download_parts(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    download_id = parsed.path.split("/")[-1]
    token = parse_qs(parsed.query).get("token", [""])[0]
    return download_id, token

@pytest.fixture(autouse=True)
def clear_stores():
    csv_store.clear()
    json_store.clear()
    yield
    csv_store.clear()
    json_store.clear()

def test_csv_exporter():
    results = [
        {
            "filename": "cv1.pdf",
            "status": "success",
            "final_score": 85.0,
            "ats_score": 90.0,
            "skills_match": ["Python", "Go"],
            "experience_match": 5,
            "education_match": 4,
            "processed_at": "2026-05-17T12:00:00"
        }
    ]
    
    # 1. Test generation
    url = generate_csv_download(results, 101, owner_organization_id=7, owner_subscription_id=11)
    assert url.startswith("/api/v1/downloads/csv_")
    
    download_id, token = _download_parts(url)
    assert token
    assert download_id in csv_store
    assert csv_store[download_id]["owner_organization_id"] == 7
    assert csv_store[download_id]["owner_subscription_id"] == 11
    
    # 2. Test retrieval (active)
    download = get_csv_temp_download(download_id)
    assert download is not None
    assert download["content_type"] == "text/csv"
    assert "cv1.pdf" in download["content"]
    assert "Python; Go" in download["content"]
    
    # 3. Test retrieval (missing)
    assert get_csv_temp_download("missing_id") is None
    
    # 4. Test retrieval (expired)
    csv_store[download_id]["expires_at"] = datetime.utcnow() - timedelta(minutes=1)
    assert get_csv_temp_download(download_id) is None
    assert download_id not in csv_store
    
    # 5. Test cleanup
    url2 = generate_csv_download(results, 101)
    id2, token2 = _download_parts(url2)
    assert token2
    csv_store[id2]["expires_at"] = datetime.utcnow() - timedelta(minutes=1)
    
    deleted = cleanup_csv()
    assert deleted == 1
    assert id2 not in csv_store

def test_json_exporter():
    results = [
        {
            "filename": "cv1.pdf",
            "status": "success",
            "final_score": 85.0,
            "ats_score": 90.0
        }
    ]
    
    # 1. Test generation
    url = generate_json_download(results, 102, owner_organization_id=8, owner_subscription_id=12)
    assert url.startswith("/api/v1/downloads/json_")
    
    download_id, token = _download_parts(url)
    assert token
    assert download_id in json_store
    assert json_store[download_id]["owner_organization_id"] == 8
    assert json_store[download_id]["owner_subscription_id"] == 12
    
    # 2. Test retrieval (active)
    download = get_json_temp_download(download_id)
    assert download is not None
    assert download["content_type"] == "application/json"
    assert "cv1.pdf" in download["content"]
    assert '"job_id": 102' in download["content"]
    
    # 3. Test retrieval (missing)
    assert get_json_temp_download("missing_id") is None
    
    # 4. Test retrieval (expired)
    json_store[download_id]["expires_at"] = datetime.utcnow() - timedelta(minutes=1)
    assert get_json_temp_download(download_id) is None
    assert download_id not in json_store
    
    # 5. Test cleanup
    url2 = generate_json_download(results, 102)
    id2, token2 = _download_parts(url2)
    assert token2
    json_store[id2]["expires_at"] = datetime.utcnow() - timedelta(minutes=1)
    
    deleted = cleanup_json()
    assert deleted == 1
    assert id2 not in json_store
