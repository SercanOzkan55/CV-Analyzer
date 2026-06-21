"""Tests for services/s3_service.py — S3 operations with mocked boto3."""

import pytest
from unittest.mock import patch, MagicMock

from services.s3_service import validate_key, _s3_error


class TestValidateKey:
    def test_valid_key(self):
        # Should not raise
        validate_key("user_abc123/original/aabbccdd11223344.pdf")

    def test_invalid_key_raises(self):
        with pytest.raises(Exception):
            validate_key("../../../etc/passwd")


class TestS3Error:
    def test_s3_error_does_not_crash(self):
        """_s3_error should handle import gracefully."""
        _s3_error()  # Should not raise even if metrics unavailable


class TestUploadMocked:
    @patch("services.s3_service._get_client")
    @patch("services.s3_service.validate_key")
    def test_upload_calls_put_object(self, mock_validate, mock_get_client):
        from services.s3_service import upload

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = upload(b"pdf content", "user_123/original/aabb0011.pdf")
        assert result == "user_123/original/aabb0011.pdf"
        mock_client.put_object.assert_called_once()

    @patch("services.s3_service._get_client")
    @patch("services.s3_service.validate_key")
    def test_upload_retries_on_transient_error(self, mock_validate, mock_get_client):
        from botocore.exceptions import BotoCoreError
        from services.s3_service import upload

        mock_client = MagicMock()
        mock_client.put_object.side_effect = [BotoCoreError(), None]
        mock_get_client.return_value = mock_client

        result = upload(b"data", "user_123/original/aabb0022.pdf", _retries=2)
        assert result == "user_123/original/aabb0022.pdf"
        assert mock_client.put_object.call_count == 2


class TestGetPresignedUrlMocked:
    @patch("services.s3_service._get_client")
    @patch("services.s3_service.validate_key")
    def test_returns_url(self, mock_validate, mock_get_client):
        from services.s3_service import get_presigned_url

        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/test"
        mock_get_client.return_value = mock_client

        url = get_presigned_url("user_123/original/aabb0033.pdf", expires=60)
        assert "https" in url


class TestDeleteMocked:
    @patch("services.s3_service._get_client")
    @patch("services.s3_service.validate_key")
    def test_delete_calls_delete_object(self, mock_validate, mock_get_client):
        from services.s3_service import delete

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        delete("user_123/original/aabb0044.pdf")
        mock_client.delete_object.assert_called_once()
