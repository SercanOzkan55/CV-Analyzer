import shutil
import subprocess

import pytest


def test_dependency_audit():
    """Run pip-audit if available."""
    if not shutil.which("pip-audit"):
        pytest.skip("pip-audit not installed")
    # Ignore ecdsa CVE-2024-23342 — no fix available (transitive via python-jose)
    result = subprocess.run(
        ["pip-audit", "--ignore-vuln", "CVE-2024-23342"],
        capture_output=True,
        timeout=120,
    )
    assert (
        result.returncode == 0
        or b"No known vulnerabilities" in result.stdout
        or b"No dependencies found" in result.stdout
    )
