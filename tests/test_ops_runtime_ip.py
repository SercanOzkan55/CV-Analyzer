from types import SimpleNamespace

from core.ops_runtime import _extract_client_ip


def _request(peer: str, xff: str | None = None):
    headers = {}
    if xff:
        headers["X-Forwarded-For"] = xff
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=peer))


def test_extract_client_ip_ignores_xff_from_untrusted_peer(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.0/8")

    ip = _extract_client_ip(_request("203.0.113.10", "198.51.100.25"))

    assert ip == "203.0.113.10"


def test_extract_client_ip_uses_xff_from_trusted_proxy(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "10.0.0.0/8")

    ip = _extract_client_ip(_request("10.2.3.4", "198.51.100.25"))

    assert ip == "198.51.100.25"


def test_extract_client_ip_allows_loopback_proxy_without_allowlist(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")
    monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)

    ip = _extract_client_ip(_request("127.0.0.1", "198.51.100.25"))

    assert ip == "198.51.100.25"
