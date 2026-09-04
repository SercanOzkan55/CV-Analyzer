import json
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_WORKER_DIR = PROJECT_ROOT / "local_worker"
if str(LOCAL_WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(LOCAL_WORKER_DIR))

import worker as worker_module  # noqa: E402
from worker import (  # noqa: E402
    LocalWorker,
    LocalWorkerError,
    _should_verify_ssl,
    _validate_api_base_url,
    _validate_download_url,
    clamp_scoring_weight,
    csv_safe,
    iter_supported_local_files,
    maybe_apply_ai_review,
    score_cv,
)
from workspace import WorkspaceStore  # noqa: E402


def _synced_local_worker(quota_remaining=100):
    worker = LocalWorker(api_key="test-worker-key", processing_mode="local_folder", ai_mode="none", device_name="test")
    worker.access_token = "test-access-token"
    worker.quota_remaining = quota_remaining
    return worker


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

    worker = _synced_local_worker()
    worker.run(1, local_folder=str(cv_dir), local_config=config, output_folder=str(output_dir))

    results = json.loads((output_dir / "local_worker_results.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "sync_manifest.json").read_text(encoding="utf-8"))

    assert (output_dir / "local_worker_results.csv").exists()
    assert (output_dir / "local_worker_results.html").exists()
    assert (output_dir / "local_worker_workspace.sqlite3").exists()
    assert len(results) == 2
    assert results[0]["score"] >= results[1]["score"]
    assert results[0]["rank"] == 1
    assert manifest["mode"] == "local_folder"
    assert manifest["sync_status"] == "offline_ready"
    assert manifest["ai_review_limit"] == 25

    store = WorkspaceStore(output_dir / "local_worker_workspace.sqlite3")
    runs = store.list_runs()
    assert len(runs) == 1
    saved_rows = store.get_run_results(runs[0]["id"])
    assert len(saved_rows) == 2
    assert all(row["candidate_status"] in {"accepted", "rejected", "needs_manual_review"} for row in saved_rows)
    audit_logs = store.list_audit_logs(runs[0]["id"])
    assert len(audit_logs) == 2
    notifications = store.list_notifications()
    assert len(notifications) == 2
    assert all(notification["channel"] == "in_app" for notification in notifications)
    pending_rows = store.list_pending_sync_results()
    assert len(pending_rows) == 2
    assert all(row["sync_status"] == "pending" for row in pending_rows)
    store.update_result_sync_status(pending_rows[0]["local_result_id"], "failed", "network unavailable")
    pending_rows = store.list_pending_sync_results()
    assert any(row["sync_error"] == "network unavailable" for row in pending_rows)


def test_local_folder_mode_marks_duplicates_and_failed_files(tmp_path):
    cv_dir = tmp_path / "cvs"
    output_dir = tmp_path / "out"
    cv_dir.mkdir()
    duplicate_text = "Candidate\nPython SQL React APIs backend delivery." * 8
    (cv_dir / "one.txt").write_text(duplicate_text, encoding="utf-8")
    (cv_dir / "two.txt").write_text(duplicate_text, encoding="utf-8")
    (cv_dir / "broken.pdf").write_bytes(b"%PDF-1.4\nnot a real parseable pdf")

    config = {
        "title": "Backend Engineer",
        "description": "Backend engineer",
        "required_skills": ["Python", "SQL"],
        "nice_to_have_skills": ["React"],
        "hard_reject_criteria": [],
        "accept_threshold": 70,
        "review_threshold": 45,
    }

    worker = _synced_local_worker()
    worker.run(1, local_folder=str(cv_dir), local_config=config, output_folder=str(output_dir))

    results = json.loads((output_dir / "local_worker_results.json").read_text(encoding="utf-8"))
    failed = (output_dir / "failed_files.txt").read_text(encoding="utf-8")

    assert any(row["is_duplicate"] for row in results)
    assert any(
        "broken.pdf" in row["file"]
        and "extraction_failed" in row["risk_flags"]
        and row["candidate_status"] == "needs_manual_review"
        for row in results
    )
    assert "broken.pdf" in failed

    store = WorkspaceStore(output_dir / "local_worker_workspace.sqlite3")
    notifications = store.list_notifications()
    assert any(notification["type"] == "candidate_needs_manual_review" for notification in notifications)


def test_local_folder_mode_requires_synced_worker(tmp_path):
    cv_dir = tmp_path / "cvs"
    output_dir = tmp_path / "out"
    cv_dir.mkdir()
    (cv_dir / "alice.txt").write_text("Alice\nPython SQL.", encoding="utf-8")
    config = {
        "title": "Backend Engineer",
        "description": "Backend engineer",
        "required_skills": ["Python"],
        "nice_to_have_skills": [],
        "hard_reject_criteria": [],
        "accept_threshold": 70,
        "review_threshold": 45,
    }

    worker = LocalWorker(api_key="", processing_mode="local_folder", ai_mode="none", device_name="test")
    with pytest.raises(Exception, match="Missing API key"):
        worker.run(1, local_folder=str(cv_dir), local_config=config, output_folder=str(output_dir))


def test_local_folder_mode_blocks_when_quota_is_too_low(tmp_path):
    cv_dir = tmp_path / "cvs"
    output_dir = tmp_path / "out"
    cv_dir.mkdir()
    (cv_dir / "alice.txt").write_text("Alice\nPython SQL.", encoding="utf-8")
    (cv_dir / "bob.txt").write_text("Bob\nPython SQL.", encoding="utf-8")
    config = {
        "title": "Backend Engineer",
        "description": "Backend engineer",
        "required_skills": ["Python"],
        "nice_to_have_skills": [],
        "hard_reject_criteria": [],
        "accept_threshold": 70,
        "review_threshold": 45,
    }

    worker = _synced_local_worker(quota_remaining=1)
    with pytest.raises(Exception, match="has 1 scan"):
        worker.run(1, local_folder=str(cv_dir), local_config=config, output_folder=str(output_dir))


def test_score_cv_honors_custom_scoring_weights():
    text = "Candidate with Python and SQL production experience."
    default_score = score_cv(
        text,
        {
            "required_skills": ["Python", "SQL"],
            "nice_to_have_skills": ["React"],
            "accept_threshold": 75,
            "review_threshold": 50,
        },
    )
    weighted_score = score_cv(
        text,
        {
            "required_skills": ["Python", "SQL"],
            "nice_to_have_skills": ["React"],
            "accept_threshold": 75,
            "review_threshold": 50,
            "scoring_weights": {
                "required_skills": 90,
                "nice_to_have_skills": 5,
                "content_quality": 5,
            },
        },
    )

    assert weighted_score["score"] > default_score["score"]
    assert weighted_score["score_breakdown"]["required_skills"] == 90


# ── Phase 2: expanded scoring criteria ──────────────────────────────
# LIVE_CRITERIA_KEYS mirrors the 9 criteria that have a working scorer today
# (the 3 pre-existing ones plus the 6 ported in Phase 2). education/language/
# recruiter_score are excluded on purpose — they're reserved, weight-0
# placeholders until a later phase ports a CV structural parser.
LIVE_CRITERIA_KEYS = (
    "required_skills",
    "nice_to_have_skills",
    "skills_coverage",
    "experience_match",
    "role_title_match",
    "keyword_match",
    "ats_format",
    "content_quality",
    "soft_skills",
)


def _weights_isolating(key: str) -> dict:
    """scoring_weights that put all 100 points on a single criterion, so a
    test can check that criterion's contribution in isolation."""
    return {k: (100.0 if k == key else 0.0) for k in LIVE_CRITERIA_KEYS}


def test_score_cv_skills_coverage_criterion_responds_to_taxonomy_matches():
    job_description = "We need a DevOps engineer skilled in Docker, Kubernetes, AWS, and Terraform."
    good_cv = "Experience with Docker, Kubernetes, AWS, and Terraform for infrastructure automation."
    bad_cv = "Retail assistant managing inventory and customer service in a supermarket."
    config = {
        "required_skills": [],
        "description": job_description,
        "accept_threshold": 75,
        "review_threshold": 50,
        "scoring_weights": _weights_isolating("skills_coverage"),
    }

    good_score = score_cv(good_cv, config)
    bad_score = score_cv(bad_cv, config)

    assert good_score["score_breakdown"]["skills_coverage"] > bad_score["score_breakdown"]["skills_coverage"]
    assert good_score["score"] > bad_score["score"]


def test_score_cv_experience_match_criterion_responds_to_years():
    job_description = "Looking for a candidate with 5+ years of experience in software engineering."
    good_cv = "Software Engineer, 2015 - 2023, building backend systems for eight years."
    bad_cv = "Software Engineering intern for a few months in 2023."
    config = {
        "required_skills": [],
        "description": job_description,
        "accept_threshold": 75,
        "review_threshold": 50,
        "scoring_weights": _weights_isolating("experience_match"),
    }

    good_score = score_cv(good_cv, config)
    bad_score = score_cv(bad_cv, config)

    assert good_score["score_breakdown"]["experience_match"] > bad_score["score_breakdown"]["experience_match"]
    assert good_score["score"] > bad_score["score"]


def test_score_cv_role_title_match_criterion_responds_to_title_and_seniority():
    job_description = "We are hiring a Senior Backend Engineer to join our platform team."
    good_cv = "Senior Backend Engineer with proven leadership managing backend platform systems."
    bad_cv = "Marketing Coordinator specializing in social media campaigns and event planning."
    config = {
        "required_skills": [],
        "description": job_description,
        "accept_threshold": 75,
        "review_threshold": 50,
        "scoring_weights": _weights_isolating("role_title_match"),
    }

    good_score = score_cv(good_cv, config)
    bad_score = score_cv(bad_cv, config)

    assert good_score["score_breakdown"]["role_title_match"] > bad_score["score_breakdown"]["role_title_match"]
    assert good_score["score"] > bad_score["score"]


def test_score_cv_keyword_match_criterion_responds_to_jd_overlap():
    job_description = (
        "We need an engineer experienced with GraphQL, microservices, and distributed systems "
        "to design resilient event-driven architectures."
    )
    good_cv = "Designed GraphQL microservices and distributed systems with event-driven architectures."
    bad_cv = "Baked artisan bread and managed a small neighborhood cafe kitchen for five years."
    config = {
        "required_skills": [],
        "description": job_description,
        "accept_threshold": 75,
        "review_threshold": 50,
        "scoring_weights": _weights_isolating("keyword_match"),
    }

    good_score = score_cv(good_cv, config)
    bad_score = score_cv(bad_cv, config)

    assert good_score["score_breakdown"]["keyword_match"] > bad_score["score_breakdown"]["keyword_match"]
    assert good_score["score"] > bad_score["score"]


def test_score_cv_ats_format_criterion_responds_to_structure():
    good_cv = (
        "Jane Doe | jane@example.com | +1 555 123 4567\n\n"
        "EXPERIENCE\n"
        "- Built scalable APIs using Python and SQL\n"
        "- Led a team of five engineers\n\n"
        "EDUCATION\n"
        "- BSc Computer Science, MIT\n\n"
        "SKILLS\n"
        "- Python, SQL, Docker\n"
    )
    bad_cv = "words " * 5 + "with no sections bullets or contact information whatsoever just one wall of text"
    config = {
        "required_skills": [],
        "description": "",
        "accept_threshold": 75,
        "review_threshold": 50,
        "scoring_weights": _weights_isolating("ats_format"),
    }

    good_score = score_cv(good_cv, config)
    bad_score = score_cv(bad_cv, config)

    assert good_score["score_breakdown"]["ats_format"] > bad_score["score_breakdown"]["ats_format"]
    assert good_score["score"] > bad_score["score"]


def test_score_cv_soft_skills_criterion_responds_to_soft_skill_terms():
    good_cv = "Strong leadership, teamwork, communication, and problem solving skills, with a track record of mentoring."
    bad_cv = "Python, Docker, Kubernetes, SQL, REST APIs."
    config = {
        "required_skills": [],
        "description": "",
        "accept_threshold": 75,
        "review_threshold": 50,
        "scoring_weights": _weights_isolating("soft_skills"),
    }

    good_score = score_cv(good_cv, config)
    bad_score = score_cv(bad_cv, config)

    assert good_score["score_breakdown"]["soft_skills"] > bad_score["score_breakdown"]["soft_skills"]
    assert good_score["score"] > bad_score["score"]


def test_score_breakdown_has_all_live_criteria_even_with_empty_scoring_weights():
    result = score_cv(
        "Candidate with Python and SQL production experience.",
        {
            "required_skills": ["Python", "SQL"],
            "nice_to_have_skills": [],
            "description": "Backend role requiring Python and SQL.",
            "accept_threshold": 75,
            "review_threshold": 50,
            "scoring_weights": {},
        },
    )

    for key in LIVE_CRITERIA_KEYS:
        assert key in result["score_breakdown"], f"missing {key} in score_breakdown"
    assert "risk_penalty" in result["score_breakdown"]


def test_stuffing_guard_flags_jd_overlap_without_affecting_decision():
    job_description = (
        "We are hiring a Senior Backend Engineer with 5+ years of Python and SQL experience to build "
        "scalable REST APIs using FastAPI and PostgreSQL on AWS. The ideal candidate has strong "
        "leadership skills and has worked in agile cross functional teams delivering high quality "
        "software on tight deadlines consistently."
    )
    # Copy-pastes almost the entire JD verbatim into the CV — classic keyword stuffing.
    stuffed_cv = "Jane Doe\njane@example.com\n" + job_description
    config = {
        "required_skills": ["Python", "SQL"],
        "nice_to_have_skills": [],
        "hard_reject_criteria": [],
        "description": job_description,
        "accept_threshold": 75,
        "review_threshold": 50,
    }

    stuffed_result = score_cv(stuffed_cv, config)
    assert any("JD overlap" in flag for flag in stuffed_result["risk_flags"])
    # The flag must NOT auto-reject or zero the score by itself.
    assert stuffed_result["decision"] != "recommended_reject"
    assert stuffed_result["score"] > 50

    normal_cv = (
        "Jane Doe\njane@example.com\nEXPERIENCE\nSenior Python Developer at Acme (2018-2024)\n"
        "- Built scalable APIs using Python and SQL\nEDUCATION\nBSc Computer Science, MIT\n"
        "SKILLS\nPython, SQL"
    )
    normal_result = score_cv(normal_cv, config)
    assert not any("JD overlap" in flag for flag in normal_result["risk_flags"])


def test_write_csv_includes_score_breakdown_columns(tmp_path):
    pytest.importorskip("PySide6")
    import os as _os

    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication

    import qml_gui  # noqa: E402  (deferred: needs PySide6, guarded above)
    from scoring import criteria as scoring_criteria  # noqa: E402

    QCoreApplication.instance() or QCoreApplication([])

    worker = qml_gui.AnalysisWorker(tmp_path, tmp_path, {}, "none", "Test Job")
    score_breakdown = {
        key: (42.0 if meta.get("scorer") is not None else 0.0) for key, meta in scoring_criteria.CRITERIA.items()
    }
    rows = [
        {
            "rank": 1,
            "file": "cv1.pdf",
            "score": 88.5,
            "decision": "recommended_accept",
            "confidence": "high",
            "is_duplicate": False,
            "duplicate_of": "",
            "summary": "ok",
            "matched_skills": ["Python"],
            "missing_skills": [],
            "risk_flags": [],
            "explanation": "ok",
            "analyzed_at": "2026-01-01T00:00:00Z",
            "score_breakdown": score_breakdown,
        }
    ]
    csv_path = tmp_path / "out.csv"
    worker._write_csv(csv_path, rows)
    content = csv_path.read_text(encoding="utf-8-sig")

    for key, meta in scoring_criteria.CRITERIA.items():
        if meta.get("scorer") is not None:
            assert f"score_{key}" in content
    assert "42.0" in content or "42" in content


def test_clamp_scoring_weight_keeps_total_at_or_below_100():
    # Normal in-range value is returned unchanged.
    assert clamp_scoring_weight(70, other_total=30) == 70
    # A value that would push the total over 100 gets clamped down.
    assert clamp_scoring_weight(90, other_total=30) == 70
    # Negative input clamps to 0.
    assert clamp_scoring_weight(-5, other_total=30) == 0


def test_worker_api_url_policy_allows_http_only_for_localhost():
    assert _validate_api_base_url("http://localhost:8001/api/worker") == "http://localhost:8001/api/worker"
    assert _validate_api_base_url("http://127.0.0.1:8001/api/worker") == "http://127.0.0.1:8001/api/worker"
    assert _validate_api_base_url("https://worker.example.com/api/worker") == "https://worker.example.com/api/worker"
    assert _should_verify_ssl("http://localhost:8001/api/worker") is False
    assert _should_verify_ssl("https://worker.example.com/api/worker") is True

    with pytest.raises(ValueError, match="https://"):
        _validate_api_base_url("http://worker.example.com/api/worker")
    with pytest.raises(ValueError, match="absolute"):
        _validate_api_base_url("/api/worker")


def test_worker_download_url_must_match_api_origin(monkeypatch):
    worker = LocalWorker(
        api_key="test-worker-key",
        processing_mode="server_files",
        ai_mode="none",
        device_name="test",
        api_base_url="https://worker.example.com/api/worker",
    )

    class Response:
        status_code = 200
        content = b"cv bytes"
        text = "OK"

    captured = {}

    def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["kwargs"] = kwargs
        return Response()

    monkeypatch.setattr(worker, "_request", fake_request)

    assert _validate_download_url("/api/worker/download/1", worker.api_base_url) == (
        "https://worker.example.com/api/worker/download/1"
    )
    assert worker._download_item({"download_url": "/api/worker/download/1"}) == b"cv bytes"
    assert captured["method"] == "GET"
    assert captured["url"] == "https://worker.example.com/api/worker/download/1"
    assert captured["kwargs"]["absolute"] is True

    with pytest.raises(LocalWorkerError, match="origin"):
        worker._download_item({"download_url": "https://worker.example.com:8443/api/worker/download/1"})
    with pytest.raises(LocalWorkerError, match="https://"):
        worker._download_item({"download_url": "http://worker.example.com/api/worker/download/1"})


def test_csv_safe_blocks_formula_prefixes_and_handles_lists():
    assert csv_safe("=cmd") == "'=cmd"
    assert csv_safe("+SUM(A1:A2)") == "'+SUM(A1:A2)"
    assert csv_safe("|calc") == "'|calc"
    assert csv_safe("!danger") == "'!danger"
    assert csv_safe(["Python", "SQL"]) == "Python, SQL"
    assert csv_safe(42) == 42


def test_supported_file_iterator_excludes_only_real_output_dir(tmp_path):
    cv_dir = tmp_path / "cvs"
    output_dir = cv_dir / "out"
    sibling_output_prefix = cv_dir / "output2"
    output_dir.mkdir(parents=True)
    sibling_output_prefix.mkdir()
    (cv_dir / "root.txt").write_text("Root candidate", encoding="utf-8")
    (output_dir / "old-result.txt").write_text("Should be ignored", encoding="utf-8")
    (sibling_output_prefix / "candidate.txt").write_text("Should be processed", encoding="utf-8")
    (cv_dir / "notes.md").write_text("Unsupported", encoding="utf-8")

    files = {path.relative_to(cv_dir).as_posix() for path in iter_supported_local_files(cv_dir, output_dir)}

    assert files == {"root.txt", "output2/candidate.txt"}


def test_extract_text_enforces_size_limit(monkeypatch):
    monkeypatch.setattr(worker_module, "MAX_FILE_BYTES", 4)

    with pytest.raises(LocalWorkerError, match="File exceeds max size"):
        worker_module.extract_text(b"12345", "txt")


def test_openai_review_keeps_tls_verification_enabled(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": '{"decision":"recommended_review"}'}}]}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setenv("CV_WORKER_OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setattr(worker_module.requests, "post", fake_post)
    monkeypatch.setattr(worker_module, "VERIFY_SSL", False)

    result = maybe_apply_ai_review(
        "Candidate with Python and SQL experience.",
        {"accept_threshold": 75, "review_threshold": 50, "required_skills": ["Python"]},
        {"score": 52, "decision": "recommended_review", "confidence": "medium"},
        "customer_openai_key",
    )

    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["verify"] is True
    assert result["ai_review_status"] == "completed"


def test_workspace_store_purges_legacy_cv_text_payloads(tmp_path):
    db_path = tmp_path / "workspace.sqlite3"
    store = WorkspaceStore(db_path)
    run_id = store.create_run(None, "Legacy run", str(tmp_path), str(tmp_path / "out"), 1)
    legacy_payload = {
        "file": "candidate.txt",
        "score": 90,
        "decision": "recommended_accept",
        "confidence": "high",
        "cv_text": "raw private CV text",
        "nested": {"cv_text": "nested private text", "keep": "ok"},
    }
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO analysis_results
                (run_id, file_path, file_hash, duplicate_of, sync_status, sync_error,
                 candidate_status, score, decision, confidence, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "candidate.txt",
                "",
                "",
                "pending",
                "",
                "accepted",
                90,
                "recommended_accept",
                "high",
                json.dumps(legacy_payload, ensure_ascii=False),
                "2026-01-01T00:00:00Z",
            ),
        )

    migrated = WorkspaceStore(db_path)
    result = migrated.get_run_results(run_id)[0]

    assert "cv_text" not in json.dumps(result, ensure_ascii=False)
    assert result["nested"]["keep"] == "ok"


def test_local_worker_unicode_and_i18n():
    from worker import _normalize, _token_set, _derive_keywords, STOPWORDS

    # 1. Test clean lowercasing & Unicode normalization
    assert _normalize("İSTANBUL") == "istanbul"
    assert _normalize("ılık") == "ılık"
    assert _normalize("geliştirici") == "geliştirici"
    assert _normalize("entwickler") == "entwickler"
    assert _normalize("c++ developer") == "c++ developer"
    assert _normalize("c# backend") == "c# backend"
    assert _normalize("ci/cd pipeline") == "ci/cd pipeline"
    assert _normalize("node.js") == "node.js"
    assert _normalize("python_django") == "python django"

    # 2. Test token extraction
    tokens = _token_set("geliştirici c++ c# .net")
    assert "geliştirici" in tokens
    assert "c++" in tokens
    assert "c#" in tokens

    # 3. Test multilingual stopwords filtering
    assert "ve" in STOPWORDS
    assert "und" in STOPWORDS
    assert "para" in STOPWORDS
    assert "avec" in STOPWORDS

    # 4. Test keyword derivation with Unicode letters
    jd = "Aradığımız aday gelişmiş Python ve Django bilgisine sahip, tecrübeli bir geliştirici olmalıdır."
    derived = _derive_keywords(jd)
    assert "ve" not in derived
    assert "bir" not in derived
    derived_lower = [w.lower() for w in derived]
    assert "geliştirici" in derived_lower
    assert "python" in derived_lower
