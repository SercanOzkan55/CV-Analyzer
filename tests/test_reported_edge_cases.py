from routes.analysis import _normalize_imported_jobs
from services.ats_service import _find_section_position


def test_import_jobs_accepts_wrapped_and_direct_lists():
    jobs = [{"title": "Engineer", "description": "Build systems"}]

    assert _normalize_imported_jobs({"jobs": jobs}) == jobs
    assert _normalize_imported_jobs(jobs) == jobs


def test_import_jobs_ignores_malformed_payloads_and_items():
    valid = {"title": "Engineer"}

    assert _normalize_imported_jobs({"jobs": "invalid"}) == []
    assert _normalize_imported_jobs("invalid") == []
    assert _normalize_imported_jobs([None, "invalid", valid]) == [valid]


def test_contact_fallback_returns_actual_detail_position():
    text = "summary\nexperienced engineer\nreferences\nperson@example.com"

    assert _find_section_position("contact", text) == text.index("person@example.com")


def test_contact_fallback_uses_earliest_detail():
    text = "summary\n+1 555 123 4567\nreferences\nperson@example.com"

    assert _find_section_position("contact", text) == text.index("+1 555 123 4567")
