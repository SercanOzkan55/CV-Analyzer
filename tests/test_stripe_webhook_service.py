import hashlib
import hmac
import json

import pytest

from services import stripe_webhook_service


def _signature_header(payload: bytes, secret: str, timestamp: int) -> str:
    signed_payload = str(timestamp).encode("utf-8") + b"." + payload
    sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


def test_verify_stripe_signature_accepts_valid_signed_payload():
    payload = json.dumps({"type": "checkout.session.completed"}).encode("utf-8")
    header = _signature_header(payload, "whsec_test", 1_700_000_000)

    stripe_webhook_service.verify_stripe_signature(
        payload=payload,
        sig_header=header,
        secret="whsec_test",
        tolerance_seconds=300,
        now=1_700_000_010,
    )


def test_verify_stripe_signature_rejects_tampered_payload():
    payload = json.dumps({"type": "checkout.session.completed"}).encode("utf-8")
    header = _signature_header(payload, "whsec_test", 1_700_000_000)

    with pytest.raises(stripe_webhook_service.StripeSignatureVerificationError) as exc:
        stripe_webhook_service.verify_stripe_signature(
            payload=b'{"type":"customer.subscription.deleted"}',
            sig_header=header,
            secret="whsec_test",
            tolerance_seconds=300,
            now=1_700_000_010,
        )

    assert exc.value.status_code == 401
    assert str(exc.value) == "Invalid signature"


def test_verify_stripe_signature_rejects_expired_timestamp():
    payload = json.dumps({"type": "checkout.session.completed"}).encode("utf-8")
    header = _signature_header(payload, "whsec_test", 1_700_000_000)

    with pytest.raises(stripe_webhook_service.StripeSignatureVerificationError) as exc:
        stripe_webhook_service.verify_stripe_signature(
            payload=payload,
            sig_header=header,
            secret="whsec_test",
            tolerance_seconds=300,
            now=1_700_001_000,
        )

    assert exc.value.status_code == 401
    assert str(exc.value) == "Signature timestamp expired"


def test_load_event_requires_json_object():
    assert stripe_webhook_service.load_event(b'{"type":"ping"}') == {"type": "ping"}

    with pytest.raises(ValueError, match="event must be an object"):
        stripe_webhook_service.load_event(b'["not", "an", "object"]')
