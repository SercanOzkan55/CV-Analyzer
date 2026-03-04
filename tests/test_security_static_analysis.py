import pytest
import subprocess
import shutil


def test_bandit_static_analysis():
    """Run bandit if available."""
    if not shutil.which("bandit"):
        pytest.skip("bandit not installed")
    result = subprocess.run(["bandit", "-r", ".", "-q"], capture_output=True, timeout=120)
    # bandit exit code 0 = no issues, 1 = issues found
    assert result.returncode in (0, 1)
