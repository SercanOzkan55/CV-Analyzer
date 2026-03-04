import pytest
import subprocess
import shutil


def test_dependency_audit():
    """Run pip-audit if available."""
    if not shutil.which("pip-audit"):
        pytest.skip("pip-audit not installed")
    result = subprocess.run(["pip-audit"], capture_output=True, timeout=120)
    assert result.returncode == 0 or b"No known vulnerabilities" in result.stdout or b"No dependencies found" in result.stdout
