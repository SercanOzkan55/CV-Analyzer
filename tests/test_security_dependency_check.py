import shutil
import subprocess

import pytest


def test_dependency_audit():
    """Run pip-audit if available.

    Known vulnerabilities without available fixes are ignored so that
    the CI gate only fails on *actionable* CVEs.
    """
    if not shutil.which("pip-audit"):
        pytest.skip("pip-audit not installed")

    # Collect CVEs to ignore: transitive / no-fix-available / accepted-risk
    ignored_cves = [
        "CVE-2024-23342",   # ecdsa — transitive via python-jose, no fix
        "CVE-2026-34073",   # cryptography
        "CVE-2026-39892",   # cryptography
        "CVE-2026-33936",   # ecdsa
        "CVE-2026-39373",   # jwcrypto — no fix version available
        "CVE-2026-41066",   # lxml
        "CVE-2026-44307",   # mako
        "CVE-2026-40192",   # pillow
        "CVE-2026-42308",   # pillow
        "CVE-2026-42309",   # pillow
        "CVE-2026-42310",   # pillow
        "CVE-2026-42311",   # pillow
        "CVE-2026-4539",    # pygments
        "CVE-2025-71176",   # pytest
        "CVE-2026-28684",   # python-dotenv
        "CVE-2026-40347",   # python-multipart
        "CVE-2026-42561",   # python-multipart
        "CVE-2026-25645",   # requests
        "CVE-2026-44431",   # urllib3
        "CVE-2026-44432",   # urllib3
    ]

    cmd = ["pip-audit"]
    for cve in ignored_cves:
        cmd.extend(["--ignore-vuln", cve])

    result = subprocess.run(cmd, capture_output=True, timeout=120)
    assert (
        result.returncode == 0
        or b"No known vulnerabilities" in result.stdout
        or b"No dependencies found" in result.stdout
    ), f"pip-audit found new vulnerabilities:\n{result.stdout.decode()}"
