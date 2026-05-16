import io
import json
import logging

from logging_config import JSONFormatter, RedactingFilter
from security.redaction import redact_for_log, redact_sensitive_text


def test_redact_sensitive_text_masks_common_pii_and_secrets():
    bearer_header = "Authorization:" + " Bearer " + "eyJhbGciOiJIUzI1NiJ9.abcdefghijklmnop.qrstuvwxyz123456"
    secret_key_name = "OPENAI_" + "API_KEY"
    secret_value = "sk-" + "abcdefghijklmnopqrstuvwxyz" + "123456"
    raw = (
        "email=person@example.com phone=+90 555 123 45 67 "
        f"{bearer_header} "
        f"{secret_key_name}={secret_value}"
    )

    redacted = redact_sensitive_text(raw)

    assert "person@example.com" not in redacted
    assert "+90 555 123 45 67" not in redacted
    assert "eyJhbGci" not in redacted
    assert secret_value not in redacted
    assert "[redacted-email:" in redacted
    assert "[redacted-phone:" in redacted
    assert "[redacted-token]" in redacted
    assert "[redacted-secret]" in redacted


def test_redact_for_log_summarizes_cv_payloads():
    value = redact_for_log("Very long CV text with person@example.com", key="cv_text")

    assert value["redacted"] is True
    assert value["length"] == len("Very long CV text with person@example.com")
    assert "sha256" in value


def test_logging_filter_redacts_args_before_formatting():
    logger = logging.getLogger("test.redaction")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info("send to=%s token=%s", "person@example.com", "sk-abcdefghijklmnopqrstuvwxyz123456")

    output = stream.getvalue()
    assert "person@example.com" not in output
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in output
    assert "[redacted-email:" in output
    assert "[redacted-secret]" in output


def test_json_formatter_redacts_exception_message():
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="failed for person@example.com",
        args=(),
        exc_info=None,
    )
    formatted = JSONFormatter().format(record)
    payload = json.loads(formatted)

    assert "person@example.com" not in payload["message"]
    assert "[redacted-email:" in payload["message"]
