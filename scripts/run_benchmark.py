"""Batch Benchmark Evaluation Script for CV Analyzer.

Runs all CV+JD pairs in the benchmark dataset through the scoring pipeline
and produces evaluation metrics (MAE, MSE, pass/fail rates, keyword coverage
distributions).

Usage:
    python scripts/run_benchmark.py
    python scripts/run_benchmark.py --verbose
    python scripts/run_benchmark.py --output results.json
"""

import argparse
import json
import math
import os
import sys
import io
import time

# Fix Windows console encoding for Unicode output
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from pathlib import Path
from typing import Any

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.keyword_service import keyword_match_score, compare
from services.ats_service import analyze_cv, compute_final_score


# ── Metric Helpers ────────────────────────────────────────────────


def _mae(errors: list[float]) -> float:
    """Mean Absolute Error."""
    if not errors:
        return 0.0
    return sum(abs(e) for e in errors) / len(errors)


def _mse(errors: list[float]) -> float:
    """Mean Squared Error."""
    if not errors:
        return 0.0
    return sum(e**2 for e in errors) / len(errors)


def _rmse(errors: list[float]) -> float:
    """Root Mean Squared Error."""
    return math.sqrt(_mse(errors))


def _in_range(value: float, expected: dict) -> bool:
    """Check if value falls within the expected [min, max] range."""
    return expected["min"] <= value <= expected["max"]


def _range_error(value: float, expected: dict) -> float:
    """Distance from nearest edge of the expected range (0 if inside)."""
    if value < expected["min"]:
        return expected["min"] - value
    if value > expected["max"]:
        return value - expected["max"]
    return 0.0


# ── Pipeline Runner ───────────────────────────────────────────────


def run_single_entry(entry: dict) -> dict:
    """Run a single benchmark entry through the scoring pipeline.

    Returns a dict with actual scores and comparison against expected ranges.
    """
    cv_text = entry["cv_text"]
    job_text = entry.get("job_description", "")

    # 1. Keyword match score
    t0 = time.perf_counter()
    kw_score = keyword_match_score(cv_text, job_text)
    kw_time = time.perf_counter() - t0

    # 2. Keyword gap/compare (v2)
    t0 = time.perf_counter()
    kw_compare = compare(cv_text, job_text)
    compare_time = time.perf_counter() - t0

    # 3. Full ATS analysis
    t0 = time.perf_counter()
    ats_result = analyze_cv(cv_text, job_text=job_text, lang="en")
    ats_time = time.perf_counter() - t0

    ats_overall = ats_result.get("overall_score", 0.0)
    content_score = ats_result.get("content", {}).get("content_score", 0.0)

    # 4. Compute final score using section-level scores from analyze_cv
    #    Extract section scores to feed compute_final_score properly
    section_scores_list = ats_result.get("section_scores", [])
    section_map = {s["name"]: s.get("score", 0) for s in section_scores_list}

    t0 = time.perf_counter()
    final = compute_final_score(
        keyword=kw_score,
        section=ats_result.get("layout", {}).get("section_presence_score", 0.0),
        exp=section_map.get("experience", 60.0),
        skills=section_map.get("skills", 60.0),
        layout=ats_result.get("layout", {}).get("layout_score", 0.0),
        contact=ats_result.get("layout", {}).get("contact_score", 0.0),
        ml_score=0.0,
        ml_confidence=0.0,  # Force rule-based override
    )
    final_time = time.perf_counter() - t0

    expected = entry.get("expected", {})

    # Compare against expected ranges
    checks = {}
    errors = {}
    for metric_name, actual_val in [
        ("keyword_score", kw_score),
        ("ats_score", ats_overall),
        ("final_score", final),
    ]:
        exp_range = expected.get(metric_name)
        if exp_range:
            checks[metric_name] = {
                "actual": round(actual_val, 2),
                "expected_min": exp_range["min"],
                "expected_max": exp_range["max"],
                "in_range": _in_range(actual_val, exp_range),
                "range_error": round(_range_error(actual_val, exp_range), 2),
            }
            errors[metric_name] = _range_error(actual_val, exp_range)

    return {
        "id": entry["id"],
        "name": entry["name"],
        "category": entry.get("category", "unknown"),
        "scores": {
            "keyword_score": round(kw_score, 2),
            "ats_overall": round(ats_overall, 2),
            "final_score": round(final, 2),
            "content_score": round(content_score, 2),
            "keyword_coverage_pct": kw_compare.get("keyword_coverage_pct", 0.0),
            "missing_keywords_count": len(kw_compare.get("missing_keywords", [])),
            "strong_keywords_count": len(kw_compare.get("strong_keywords", [])),
            "weak_keywords_count": len(kw_compare.get("weak_keywords", [])),
        },
        "timing_ms": {
            "keyword": round(kw_time * 1000, 1),
            "compare": round(compare_time * 1000, 1),
            "ats": round(ats_time * 1000, 1),
            "final": round(final_time * 1000, 1),
            "total": round((kw_time + compare_time + ats_time + final_time) * 1000, 1),
        },
        "checks": checks,
        "errors": errors,
    }


# ── Aggregate Report ─────────────────────────────────────────────


def generate_report(results: list[dict]) -> dict:
    """Generate aggregate evaluation metrics from individual results."""
    total = len(results)
    if total == 0:
        return {"error": "No results to evaluate"}

    # Per-metric aggregation
    metrics = {}
    for metric_name in ["keyword_score", "ats_score", "final_score"]:
        range_errors = [r["errors"].get(metric_name, 0.0) for r in results if metric_name in r.get("errors", {})]
        in_range_count = sum(1 for r in results if r.get("checks", {}).get(metric_name, {}).get("in_range", False))
        total_with_check = sum(1 for r in results if metric_name in r.get("checks", {}))

        metrics[metric_name] = {
            "mae": round(_mae(range_errors), 2),
            "mse": round(_mse(range_errors), 2),
            "rmse": round(_rmse(range_errors), 2),
            "in_range_count": in_range_count,
            "total_checked": total_with_check,
            "in_range_pct": round((in_range_count / max(1, total_with_check)) * 100, 1),
        }

    # Category breakdown
    categories: dict[str, list] = {}
    for r in results:
        cat = r.get("category", "unknown")
        categories.setdefault(cat, []).append(r)

    category_summary = {}
    for cat, entries in categories.items():
        pass_count = sum(1 for e in entries if all(c.get("in_range", False) for c in e.get("checks", {}).values()))
        category_summary[cat] = {
            "total": len(entries),
            "all_in_range": pass_count,
            "pass_rate_pct": round((pass_count / len(entries)) * 100, 1),
        }

    # Keyword coverage distribution
    coverages = [
        r["scores"].get("keyword_coverage_pct", 0.0)
        for r in results
        if r["scores"].get("keyword_coverage_pct", 0.0) > 0
    ]
    coverage_dist = {
        "mean": round(sum(coverages) / max(1, len(coverages)), 2),
        "min": round(min(coverages, default=0.0), 2),
        "max": round(max(coverages, default=0.0), 2),
        "count": len(coverages),
    }

    # Timing summary
    total_times = [r["timing_ms"]["total"] for r in results]
    timing_summary = {
        "avg_ms": round(sum(total_times) / max(1, len(total_times)), 1),
        "max_ms": round(max(total_times, default=0), 1),
        "min_ms": round(min(total_times, default=0), 1),
    }

    # Failed entries (out of range)
    failures = []
    for r in results:
        for metric_name, check in r.get("checks", {}).items():
            if not check.get("in_range", True):
                failures.append(
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "metric": metric_name,
                        "actual": check["actual"],
                        "expected_range": f"[{check['expected_min']}, {check['expected_max']}]",
                        "deviation": check["range_error"],
                    }
                )

    return {
        "summary": {
            "total_entries": total,
            "all_metrics_in_range": sum(
                1 for r in results if all(c.get("in_range", False) for c in r.get("checks", {}).values())
            ),
            "overall_pass_rate_pct": round(
                sum(1 for r in results if all(c.get("in_range", False) for c in r.get("checks", {}).values()))
                / total
                * 100,
                1,
            ),
        },
        "metrics": metrics,
        "category_breakdown": category_summary,
        "keyword_coverage_distribution": coverage_dist,
        "timing": timing_summary,
        "failures": failures,
    }


# ── Console Printer ──────────────────────────────────────────────


def print_report(results: list[dict], report: dict, verbose: bool = False) -> None:
    """Print a human-readable report to console."""
    print("\n" + "=" * 70)
    print("  CV ANALYZER — BENCHMARK EVALUATION REPORT")
    print("=" * 70)

    summary = report["summary"]
    print(
        f"\n[SUMMARY] Overall: {summary['all_metrics_in_range']}/{summary['total_entries']}"
        f" entries passed all checks ({summary['overall_pass_rate_pct']}%)\n"
    )

    # Per-metric table
    print("┌─────────────────┬────────┬────────┬────────┬─────────────┐")
    print("│ Metric          │  MAE   │  MSE   │  RMSE  │ In-Range %  │")
    print("├─────────────────┼────────┼────────┼────────┼─────────────┤")
    for name, m in report["metrics"].items():
        print(
            f"│ {name:<15} │ {m['mae']:>6.2f} │ {m['mse']:>6.2f} │ "
            f"{m['rmse']:>6.2f} │ {m['in_range_pct']:>6.1f}%"
            f" ({m['in_range_count']}/{m['total_checked']}) │"
        )
    print("└─────────────────┴────────┴────────┴────────┴─────────────┘")

    # Category breakdown
    print("\n[CATEGORIES] Category Breakdown:")
    for cat, info in report["category_breakdown"].items():
        mark = "PASS" if info["pass_rate_pct"] == 100 else "WARN" if info["pass_rate_pct"] >= 50 else "FAIL"
        print(f"   [{mark}] {cat:<20}: {info['all_in_range']}/{info['total']} passed ({info['pass_rate_pct']}%)")

    # Keyword coverage
    cov = report["keyword_coverage_distribution"]
    print(
        f"\n[KEYWORDS] Keyword Coverage (entries with JD): mean={cov['mean']}%, "
        f"range=[{cov['min']}% - {cov['max']}%], n={cov['count']}"
    )

    # Timing
    t = report["timing"]
    print(f"\n[TIMING] avg={t['avg_ms']}ms, min={t['min_ms']}ms, max={t['max_ms']}ms")

    # Failures
    if report["failures"]:
        print(f"\n[FAIL] Failures ({len(report['failures'])}):")
        for f in report["failures"]:
            print(
                f"   [{f['id']}] {f['name']}: {f['metric']}"
                f" = {f['actual']} (expected {f['expected_range']}, off by {f['deviation']})"
            )
    else:
        print("\n[OK] All entries within expected ranges!")

    # Verbose: per-entry details
    if verbose:
        print("\n" + "-" * 70)
        print("  DETAILED RESULTS")
        print("-" * 70)
        for r in results:
            status = "[PASS]" if all(c.get("in_range", False) for c in r.get("checks", {}).values()) else "[FAIL]"
            print(f"\n{status} [{r['id']}] {r['name']} ({r['category']})")
            print(
                f"   Scores: kw={r['scores']['keyword_score']}, "
                f"ats={r['scores']['ats_overall']}, final={r['scores']['final_score']}"
            )
            print(
                f"   Coverage: {r['scores']['keyword_coverage_pct']}%, "
                f"missing={r['scores']['missing_keywords_count']}, "
                f"strong={r['scores']['strong_keywords_count']}, "
                f"weak={r['scores']['weak_keywords_count']}"
            )
            print(f"   Time: {r['timing_ms']['total']}ms")
            for metric, check in r.get("checks", {}).items():
                icon = "[OK]" if check["in_range"] else "[X]"
                range_err = check["range_error"]
                status_msg = "OK" if check["in_range"] else f"off by {range_err}"
                print(
                    f"   {icon} {metric}: {check['actual']} "
                    f"[{check['expected_min']}-{check['expected_max']}]"
                    f" {status_msg}"
                )

    print("\n" + "=" * 70 + "\n")


# ── Main ─────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Run CV Analyzer benchmark evaluation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-entry details")
    parser.add_argument("--output", "-o", type=str, help="Save results to JSON file")
    parser.add_argument(
        "--dataset",
        "-d",
        type=str,
        help="Path to benchmark dataset JSON",
        default=str(PROJECT_ROOT / "tests" / "benchmark" / "benchmark_dataset.json"),
    )
    args = parser.parse_args()

    # Load dataset
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"[ERROR] Dataset not found: {dataset_path}")
        sys.exit(1)

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    entries = dataset.get("entries", [])
    print(f"\n>>> Running benchmark with {len(entries)} entries...")

    # Run evaluation
    results = []
    for i, entry in enumerate(entries, 1):
        print(f"   [{i}/{len(entries)}] {entry['id']}: {entry['name']}...", end="", flush=True)
        try:
            result = run_single_entry(entry)
            results.append(result)
            status = "PASS" if all(c.get("in_range", False) for c in result.get("checks", {}).values()) else "FAIL"
            print(f" [{status}] ({result['timing_ms']['total']}ms)")
        except Exception as e:
            print(f" [ERROR] {e}")
            results.append(
                {
                    "id": entry["id"],
                    "name": entry["name"],
                    "category": entry.get("category"),
                    "error": str(e),
                    "checks": {},
                    "errors": {},
                    "scores": {},
                    "timing_ms": {"total": 0},
                }
            )

    # Generate report
    report = generate_report(results)

    # Print console report
    print_report(results, report, verbose=args.verbose)

    # Save to file
    if args.output:
        output_path = Path(args.output)
        output_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "dataset_version": dataset.get("version", "unknown"),
            "results": results,
            "report": report,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"[SAVED] Results saved to {output_path}")

    # Exit code: non-zero if any failures
    if report["failures"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
