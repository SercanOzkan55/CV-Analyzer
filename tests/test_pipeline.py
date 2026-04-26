import importlib
import sys



def test_run_pipeline_happy_path(sample_texts):
    main = importlib.import_module("main")
    cv, job = sample_texts
    res = main.run_pipeline(cv, job)
    assert "final_score" in res


def test_run_pipeline_embedding_none(monkeypatch, sample_texts):
    # Simulate embedding service returning None
    import importlib

    # ensure the submodule is importable so monkeypatch.resolve can find it
    importlib.import_module("services.embedding_service")
    monkeypatch.setattr("services.embedding_service.get_embedding", lambda text: None)
    # If `main` was already imported (session fixture), ensure its local reference
    # to `get_embedding` is also patched so `run_pipeline` uses the mocked behavior.
    if "main" in sys.modules:
        monkeypatch.setattr("main.get_embedding", lambda text: None)
    main = importlib.import_module("main")

    # Clear in-memory analysis cache so we don't get a cached result from
    # a previous test that ran with real embeddings.
    if hasattr(main, "_analysis_mem_cache"):
        main._analysis_mem_cache.clear()

    cv, job = sample_texts
    # With embedding failures we expect the pipeline to handle gracefully
    res = main.run_pipeline(cv, job)
    assert isinstance(res, dict)
    assert "final_score" in res
    # embedding fallback should cap the final score to prevent manipulation
    assert res["final_score"] <= 40.0
