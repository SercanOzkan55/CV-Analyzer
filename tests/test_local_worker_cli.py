import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_WORKER_DIR = PROJECT_ROOT / "local_worker"
if str(LOCAL_WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(LOCAL_WORKER_DIR))

from worker import LocalWorker  # noqa: E402
from workspace import WorkspaceStore  # noqa: E402


def test_local_folder_mode_writes_ranked_outputs(tmp_path):
    cv_dir = tmp_path / "cvs"
    output_dir = tmp_path / "out"
    cv_dir.mkdir()
    (cv_dir / "alice.txt").write_text(
        "Alice Candidate\nPython React SQL backend APIs data pipelines and teamwork.",
        encoding="utf-8",
    )
    (cv_dir / "bob.txt").write_text(
        "Bob Candidate\nRetail operations and customer service.",
        encoding="utf-8",
    )

    config = {
        "title": "Backend Engineer",
        "description": "Backend engineer with Python, React, SQL, APIs.",
        "required_skills": ["Python", "SQL"],
        "nice_to_have_skills": ["React"],
        "hard_reject_criteria": ["no work authorization"],
        "accept_threshold": 70,
        "review_threshold": 45,
    }

    worker = LocalWorker(api_key="", processing_mode="local_folder", ai_mode="none", device_name="test")
    worker.run(1, local_folder=str(cv_dir), local_config=config, output_folder=str(output_dir))

    results = json.loads((output_dir / "local_worker_results.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "sync_manifest.json").read_text(encoding="utf-8"))

    assert (output_dir / "local_worker_results.csv").exists()
    assert (output_dir / "local_worker_workspace.sqlite3").exists()
    assert len(results) == 2
    assert results[0]["score"] >= results[1]["score"]
    assert results[0]["rank"] == 1
    assert manifest["mode"] == "local_folder"
    assert manifest["sync_status"] == "offline_ready"

    store = WorkspaceStore(output_dir / "local_worker_workspace.sqlite3")
    runs = store.list_runs()
    assert len(runs) == 1
    saved_rows = store.get_run_results(runs[0]["id"])
    assert len(saved_rows) == 2
