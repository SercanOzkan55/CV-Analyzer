"""Tests for services/storage_service.py — high-level CV storage."""

import pytest
from unittest.mock import patch, MagicMock
from services.storage_service import build_key


class TestBuildKey:
    def test_original_pdf(self):
        key = build_key("user123", "original", "pdf")
        assert key.startswith("user_user123/original/")
        assert key.endswith(".pdf")

    def test_optimized_docx(self):
        key = build_key("user456", "optimized", "docx")
        assert key.startswith("user_user456/optimized/")
        assert key.endswith(".docx")

    def test_unknown_extension_defaults_pdf(self):
        key = build_key("user789", "original", "txt")
        assert key.endswith(".pdf")

    def test_unique_keys(self):
        key1 = build_key("user1", "original")
        key2 = build_key("user1", "original")
        assert key1 != key2  # UUID makes each unique


class TestUploadOriginalCvMocked:
    @patch("services.storage_service.s3_service")
    @patch("services.storage_service.validate_file_upload", return_value="application/pdf")
    @patch("services.storage_service.is_configured", return_value=True)
    @patch("services.storage_service.validate_user_id", side_effect=lambda x: x)
    def test_upload_returns_key(self, mock_uid, mock_cfg, mock_validate, mock_s3):
        from services.storage_service import upload_original_cv

        key = upload_original_cv(b"pdf bytes", "user123")
        assert key.startswith("user_user123/original/")
        mock_s3.upload.assert_called_once()

    @patch("services.storage_service.is_configured", return_value=False)
    def test_upload_raises_when_not_configured(self, mock_cfg):
        from services.storage_service import upload_original_cv

        with pytest.raises(RuntimeError, match="not configured"):
            upload_original_cv(b"pdf", "user123")


class TestGetDownloadUrlMocked:
    @patch("services.storage_service.s3_service")
    @patch("services.storage_service.enforce_ownership")
    def test_returns_presigned_url(self, mock_ownership, mock_s3):
        from services.storage_service import get_download_url

        mock_s3.get_presigned_url.return_value = "https://s3.example.com/cv.pdf"
        url = get_download_url("user_user123/original/abc.pdf", "user123")
        assert "https" in url
        mock_ownership.assert_called_once()
