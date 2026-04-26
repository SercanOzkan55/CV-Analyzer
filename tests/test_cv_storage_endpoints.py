"""Tests for CV storage endpoints: upload, upload-optimized, download, delete."""

import pytest
from unittest.mock import patch, MagicMock
import main as main_module


@pytest.fixture(autouse=True)
def _storage_env(monkeypatch):
    """Keep storage tests isolated from external services."""
    monkeypatch.setattr(main_module, "redis_rate", None)
    monkeypatch.setattr(main_module, "CLAMAV_ENABLED", False)


class TestUploadCV:
    @patch("services.storage_service.upload_original_cv", return_value="user_test-user-123/original/abcdef01.pdf")
    @patch("security.file_guard.validate_file_upload")
    @patch("security.s3_guard.enforce_user_cv_limit")
    @patch("security.rate_limit.check_upload_rate")
    def test_upload_success(self, mock_rate, mock_limit, mock_validate, mock_upload, client):
        files = {"file": ("my_cv.pdf", b"%PDF-1.4\n%EOF\n", "application/pdf")}
        resp = client.post("/api/v1/cv/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert "key" in data
        assert data["filename"] == "my_cv.pdf"
        assert data["size"] > 0

    @patch("security.rate_limit.check_upload_rate", side_effect=ValueError("Rate limit exceeded"))
    def test_upload_rate_limited(self, mock_rate, client):
        files = {"file": ("cv.pdf", b"%PDF-1.4\n%EOF\n", "application/pdf")}
        resp = client.post("/api/v1/cv/upload", files=files)
        assert resp.status_code == 429

    @patch("security.rate_limit.check_upload_rate")
    @patch("security.s3_guard.enforce_user_cv_limit", side_effect=ValueError("CV limit reached"))
    def test_upload_cv_limit(self, mock_limit, mock_rate, client):
        files = {"file": ("cv.pdf", b"%PDF-1.4\n%EOF\n", "application/pdf")}
        resp = client.post("/api/v1/cv/upload", files=files)
        assert resp.status_code == 400

    @patch("security.rate_limit.check_upload_rate")
    @patch("security.s3_guard.enforce_user_cv_limit")
    @patch("security.file_guard.validate_file_upload", side_effect=ValueError("Unsupported format"))
    def test_upload_bad_file_type(self, mock_validate, mock_limit, mock_rate, client):
        files = {"file": ("virus.exe", b"MZ\x90", "application/x-msdownload")}
        resp = client.post("/api/v1/cv/upload", files=files)
        assert resp.status_code == 400


class TestUploadOptimizedCV:
    @patch("services.storage_service.upload_optimized_cv", return_value="user_test-user-123/optimized/abcdef01.pdf")
    @patch("security.file_guard.validate_file_upload")
    @patch("security.s3_guard.enforce_user_cv_limit")
    @patch("security.rate_limit.check_upload_rate")
    def test_upload_optimized_success(self, mock_rate, mock_limit, mock_validate, mock_upload, client):
        files = {"file": ("optimized.pdf", b"%PDF-1.4\n%EOF\n", "application/pdf")}
        resp = client.post("/api/v1/cv/upload-optimized", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert "key" in data


class TestDownloadCV:
    @patch("services.storage_service.exists", return_value=True)
    @patch("services.storage_service.get_download_url", return_value="https://s3.example.com/signed-url")
    @patch("security.s3_guard.validate_s3_key")
    @patch("security.s3_guard.enforce_ownership")
    @patch("security.runtime_guard.check_download_rate")
    @patch("security.runtime_guard.check_signed_url_rate")
    def test_download_success(self, mock_signed, mock_dl, mock_own, mock_key, mock_url, mock_exists, client):
        resp = client.get(
            "/api/v1/cv/download",
            params={"key": "user_test-user-123/original/abcdef01.pdf"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "https://s3.example.com/signed-url"

    @patch("security.runtime_guard.check_download_rate")
    @patch("security.runtime_guard.check_signed_url_rate")
    @patch("security.s3_guard.validate_s3_key")
    @patch("security.s3_guard.enforce_ownership", side_effect=PermissionError("Not your file"))
    def test_download_forbidden(self, mock_own, mock_key, mock_signed, mock_dl, client):
        resp = client.get(
            "/api/v1/cv/download",
            params={"key": "user_other-user/original/abcdef01.pdf"},
        )
        assert resp.status_code == 403


class TestDeleteCV:
    @patch("services.storage_service.delete_cv")
    @patch("security.s3_guard.validate_s3_key")
    @patch("security.s3_guard.enforce_ownership")
    def test_delete_success(self, mock_own, mock_key, mock_del, client):
        resp = client.request(
            "DELETE",
            "/api/v1/cv/file",
            params={"key": "user_test-user-123/original/abcdef01.pdf"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "deleted" in data

    @patch("security.s3_guard.validate_s3_key", side_effect=ValueError("bad key"))
    def test_delete_invalid_key(self, mock_key, client):
        resp = client.request(
            "DELETE",
            "/api/v1/cv/file",
            params={"key": "user_test-user-123/original/abcdef01.pdf"},
        )
        assert resp.status_code == 403
