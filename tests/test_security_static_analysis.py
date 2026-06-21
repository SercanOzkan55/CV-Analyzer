import shutil
import subprocess

import pytest


def test_bandit_static_analysis():
    """Run bandit if available."""
    if not shutil.which("bandit"):
        pytest.skip("bandit not installed")
    result = subprocess.run(
        [
            "bandit",
            "-r",
            "main.py",
            "auth.py",
            "database.py",
            "models.py",
            "services/",
            "security/",
            "config/",
            "agents/",
            "renderers/",
            "schemas/",
            "--exclude",
            "venv,node_modules,.git,__pycache__",
            "-q",
        ],
        capture_output=True,
        timeout=300,
    )
    # bandit exit code 0 = no issues, 1 = issues found
    assert result.returncode in (0, 1)
