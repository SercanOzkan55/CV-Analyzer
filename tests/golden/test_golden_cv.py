# -*- coding: utf-8 -*-
"""Golden test runner — runs pipeline on real CVs and validates output.

Usage:
    python -m pytest tests/golden/test_golden_cv.py -v
    python tests/golden/test_golden_cv.py  (standalone)
"""
import json
import os
import sys
import re
import unicodedata

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from tests.golden.expectations import GOLDEN_EXPECTATIONS


def _load_cases():
    path = os.path.join(os.path.dirname(__file__), "raw_cv_texts.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _run_pipeline(cv_text: str) -> dict:
    """Run the extract + normalize pipeline on raw text."""
    from agents.extract_agent import extract_structured
    from agents.normalize_agent import normalize
    structured = extract_structured(cv_text)
    normalized = normalize(structured)
    return normalized


def _validate_against_expectations(
    case_id: str,
    extracted: dict,
    expect: dict,
) -> list:
    """Check extracted data against golden expectations. Returns list of failures."""
    failures = []

    # Name
    name = str(extracted.get("full_name", "")).strip()
    name_expect = expect.get("name_contains", "")
    if name_expect and name_expect.lower() not in name.lower():
        failures.append(f"NAME: expected '{name_expect}' in '{name}'")

    # Email
    email = str(extracted.get("email", "")).strip()
    email_expect = expect.get("email", "")
    if email_expect and email_expect.lower() != email.lower():
        failures.append(f"EMAIL: expected '{email_expect}', got '{email}'")

    # Phone
    phone = str(extracted.get("phone", "")).strip()
    phone_expect = expect.get("phone_contains", "")
    if phone_expect and phone_expect not in phone:
        failures.append(f"PHONE: expected '{phone_expect}' in '{phone}'")

    # Skills MUST have
    skills_flat = [str(s).strip() for s in (extracted.get("skills") or [])]
    skills_cat = extracted.get("skills_categorized", {})
    all_skills_lower = set(s.lower() for s in skills_flat)
    # Include categorized skills and their category names (which are often the actual skills like 'Python')
    if isinstance(skills_cat, dict):
        for cat_name, items in skills_cat.items():
            all_skills_lower.add(cat_name.lower().strip())
            if isinstance(items, list):
                all_skills_lower.update(s.lower().strip() for s in items)
    for must_skill in expect.get("must_have_skills", []):
        if must_skill.lower() not in all_skills_lower:
            # Check partial match
            found = any(must_skill.lower() in s for s in all_skills_lower)
            if not found:
                failures.append(f"SKILL_MISSING: '{must_skill}'")

    # Skills MUST NOT have (garbage)
    for bad_skill in expect.get("must_not_have_skills", []):
        if bad_skill.lower() in all_skills_lower:
            failures.append(f"GARBAGE_SKILL: '{bad_skill}' in skills")

    # Experience count
    exp_count = len(extracted.get("experiences", []))
    min_exp = expect.get("min_experience_entries", 0)
    if exp_count < min_exp:
        failures.append(f"EXPERIENCE_COUNT: expected >= {min_exp}, got {exp_count}")

    # Education count
    edu_count = len(extracted.get("education", []))
    min_edu = expect.get("min_education_entries", 0)
    if edu_count < min_edu:
        failures.append(f"EDUCATION_COUNT: expected >= {min_edu}, got {edu_count}")

    # Project count
    proj_count = len(extracted.get("projects", []))
    min_proj = expect.get("min_project_entries", 0)
    if proj_count < min_proj:
        failures.append(f"PROJECT_COUNT: expected >= {min_proj}, got {proj_count}")

    # Languages MUST contain
    langs = [str(l).strip() for l in (extracted.get("languages") or [])]
    langs_lower = [l.lower() for l in langs]
    for must_lang in expect.get("languages_must_contain", []):
        found = any(must_lang.lower() in l for l in langs_lower)
        if not found:
            failures.append(f"LANGUAGE_MISSING: '{must_lang}', have: {langs}")

    # Languages MUST NOT contain (broken tokens)
    for bad_lang in expect.get("languages_must_not_contain", []):
        # Exact match only (not substring)
        if bad_lang.lower() in [l.lower().strip() for l in langs]:
            failures.append(f"BROKEN_LANGUAGE: '{bad_lang}' in languages")

    # Education content check
    edu_all_text = " ".join(
        f"{e.get('degree', '')} {e.get('school', '')} {e.get('field', '')}"
        for e in (extracted.get("education") or [])
    ).lower()
    for must_edu in expect.get("education_must_contain", []):
        if must_edu.lower() not in edu_all_text:
            failures.append(f"EDUCATION_CONTENT: '{must_edu}' not found")

    # Experience content check
    exp_all_text = " ".join(
        f"{e.get('title', '')} {e.get('company', '')}"
        for e in (extracted.get("experiences") or [])
    ).lower()
    for must_exp in expect.get("experience_must_contain", []):
        if must_exp.lower() not in exp_all_text:
            failures.append(f"EXPERIENCE_CONTENT: '{must_exp}' not found")

    # Summary contamination check
    summary = str(extracted.get("summary", "")).lower()
    for bad in expect.get("summary_must_not_contain", []):
        if bad.lower() in summary:
            failures.append(f"SUMMARY_CONTAMINATED: '{bad}' found in summary")

    # Projects content check
    proj_all_text = " ".join(
        str(p.get("name", "") or p.get("title", ""))
        for p in (extracted.get("projects") or [])
    ).lower()
    for must_proj in expect.get("projects_must_contain", []):
        if must_proj.lower() not in proj_all_text:
            failures.append(f"PROJECT_CONTENT: '{must_proj}' not found")

    return failures


def run_golden_tests(verbose: bool = True) -> dict:
    """Run all golden tests and return results."""
    cases = _load_cases()
    results = {}

    for case in cases:
        case_id = unicodedata.normalize("NFC", case["id"])
        # NFC-normalize keys in expectations for consistent matching
        expect = None
        for ek, ev in GOLDEN_EXPECTATIONS.items():
            if unicodedata.normalize("NFC", ek) == case_id:
                expect = ev
                break
        if not expect:
            if verbose:
                print(f"  SKIP {case_id} (no expectations)")
            continue

        if verbose:
            print(f"\n{'='*60}")
            print(f"  Testing: {case_id}")
            print(f"{'='*60}")

        # Run pipeline
        try:
            extracted = _run_pipeline(case["original_text"])
        except Exception as e:
            results[case_id] = {
                "status": "ERROR",
                "error": str(e),
                "failures": [f"PIPELINE_ERROR: {e}"],
            }
            if verbose:
                print(f"  ❌ PIPELINE ERROR: {e}")
            continue

        # Validate against expectations
        failures = _validate_against_expectations(case_id, extracted, expect)

        # Run quality validator
        from services.extraction_validator import validate_extraction
        quality = validate_extraction(case["original_text"], extracted)

        results[case_id] = {
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "quality_score": quality["quality_score"],
            "hard_fails": quality["hard_fails"],
            "needs_llm_fallback": quality["needs_llm_fallback"],
            "garbage_skills": quality.get("garbage_skills", []),
            "broken_languages": quality.get("broken_languages", []),
            # Extracted summary for debugging
            "extracted_name": extracted.get("full_name", ""),
            "extracted_email": extracted.get("email", ""),
            "extracted_skills_count": len(extracted.get("skills") or []),
            "extracted_exp_count": len(extracted.get("experiences") or []),
            "extracted_edu_count": len(extracted.get("education") or []),
        }

        if verbose:
            status = "✅ PASS" if not failures else f"❌ FAIL ({len(failures)} issues)"
            print(f"  {status}")
            print(f"  Quality Score: {quality['quality_score']}/100")
            print(f"  Needs LLM: {quality['needs_llm_fallback']}")
            if failures:
                for f in failures[:10]:
                    print(f"    ⚠ {f}")
            if quality["hard_fails"]:
                for hf in quality["hard_fails"][:5]:
                    print(f"    🔴 HARD-FAIL: {hf}")

    # Summary
    if verbose:
        print(f"\n{'='*60}")
        total = len(results)
        passed = sum(1 for r in results.values() if r["status"] == "PASS")
        print(f"  SUMMARY: {passed}/{total} passed")
        for cid, r in results.items():
            emoji = "✅" if r["status"] == "PASS" else "❌"
            print(f"    {emoji} {cid}: score={r['quality_score']}, "
                  f"failures={len(r['failures'])}, "
                  f"hard_fails={len(r['hard_fails'])}")
        print(f"{'='*60}")

    return results


if __name__ == "__main__":
    run_golden_tests(verbose=True)
