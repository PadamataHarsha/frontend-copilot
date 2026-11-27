"""UC1 Requirement-to-Wireframe evaluator.

Uses only Python's standard library. It calls the FastAPI endpoint, validates
its public response contract, measures latency/reliability, and scores expected
section/component coverage plus forbidden-feature occurrences.
"""
from __future__ import annotations


import argparse
import csv
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.request import ProxyHandler, Request, build_opener

CANONICAL_KEYS = {"screen_name", "sections"}
SECTION_KEYS = {"title", "components"}
LOCAL_OPENER = build_opener(ProxyHandler({}))


def load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("Evaluation cases must be a non-empty JSON array.")
    return data


def post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, Any, float, str | None]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with LOCAL_OPENER.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            latency = time.perf_counter() - started
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            return response.status, parsed, latency, None
    except HTTPError as error:
        latency = time.perf_counter() - started
        raw = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        detail = parsed.get("detail") if isinstance(parsed, dict) else raw[:300]
        return error.code, parsed, latency, str(detail)
    except (URLError, TimeoutError) as error:
        return 0, None, time.perf_counter() - started, str(error)


def validate_wireframe(data: Any) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return False, ["Response is not an object"]
    missing = CANONICAL_KEYS - set(data)
    if missing:
        errors.append(f"Missing keys: {sorted(missing)}")
    screen = data.get("screen_name")
    if not isinstance(screen, str) or not screen.strip():
        errors.append("screen_name must be a non-empty string")
    sections = data.get("sections")
    if not isinstance(sections, list) or not 1 <= len(sections) <= 8:
        errors.append("sections must contain 1 to 8 items")
        return not errors, errors
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            errors.append(f"sections[{index}] is not an object")
            continue
        if not SECTION_KEYS.issubset(section):
            errors.append(f"sections[{index}] is missing title/components")
        title = section.get("title")
        components = section.get("components")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"sections[{index}].title is invalid")
        if not isinstance(components, list) or not 1 <= len(components) <= 10:
            errors.append(f"sections[{index}].components must contain 1 to 10 items")
        elif any(not isinstance(item, str) or not item.strip() for item in components):
            errors.append(f"sections[{index}].components contains an invalid item")
    return not errors, errors


def normalized_text(data: dict[str, Any]) -> str:
    parts = [str(data.get("screen_name", ""))]
    for section in data.get("sections", []):
        parts.append(str(section.get("title", "")))
        parts.extend(str(item) for item in section.get("components", []))
    return " ".join(parts).casefold()


def section_coverage(data: dict[str, Any], groups: list[list[str]]) -> tuple[int, int, float, list[list[str]]]:
    section_titles = " ".join(str(s.get("title", "")) for s in data.get("sections", [])).casefold()
    matched = [group for group in groups if any(term.casefold() in section_titles for term in group)]
    missing = [group for group in groups if group not in matched]
    total = len(groups)
    return len(matched), total, (len(matched) / total if total else 1.0), missing


def component_coverage(data: dict[str, Any], expected: list[str]) -> tuple[int, int, float, list[str]]:
    actual = {
        component.casefold()
        for section in data.get("sections", [])
        for component in section.get("components", [])
        if isinstance(component, str)
    }
    matched = [item for item in expected if item.casefold() in actual]
    missing = [item for item in expected if item.casefold() not in actual]
    total = len(expected)
    return len(matched), total, (len(matched) / total if total else 1.0), missing


def forbidden_hits(data: dict[str, Any], forbidden: list[str]) -> list[str]:
    haystack = normalized_text(data)
    return [item for item in forbidden if item.casefold() in haystack]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * p)))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate UC1 Requirement-to-Wireframe")
    parser.add_argument("--url", default="http://127.0.0.1:8000/wireframe/generate")
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("uc1_cases.json"))
    parser.add_argument("--runs", type=int, default=1, help="Runs per case")
    parser.add_argument("--timeout", type=float, default=70.0)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).with_name("results"))
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    cases = load_cases(args.cases)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    detailed: list[dict[str, Any]] = []

    print(f"Evaluating {len(cases)} cases x {args.runs} run(s) against {args.url}")
    for case in cases:
        for run in range(1, args.runs + 1):
            status, body, latency, error = post_json(args.url, {"requirement": case["requirement"]}, args.timeout)
            schema_valid, schema_errors = validate_wireframe(body) if status == 200 else (False, [])
            if status == 200 and schema_valid:
                sm, st, sc, missing_sections = section_coverage(body, case.get("expected_section_groups", []))
                cm, ct, cc, missing_components = component_coverage(body, case.get("expected_components", []))
                forbidden = forbidden_hits(body, case.get("forbidden_features", []))
            else:
                sm = cm = 0
                st = len(case.get("expected_section_groups", []))
                ct = len(case.get("expected_components", []))
                sc = cc = 0.0
                missing_sections = case.get("expected_section_groups", [])
                missing_components = case.get("expected_components", [])
                forbidden = []
            row = {
                "case_id": case["id"], "case_name": case["name"], "run": run,
                "http_status": status, "latency_seconds": round(latency, 4),
                "success": status == 200, "schema_valid": schema_valid,
                "schema_errors": schema_errors, "section_matches": sm, "section_total": st,
                "section_coverage": round(sc, 4), "missing_section_groups": missing_sections,
                "component_matches": cm, "component_total": ct,
                "component_coverage": round(cc, 4), "missing_components": missing_components,
                "forbidden_hits": forbidden, "hallucination_free": not forbidden,
                "error": error, "response": body,
            }
            detailed.append(row)
            result = "PASS" if status == 200 and schema_valid else "FAIL"
            print(f"[{result}] {case['id']} run {run}: HTTP {status}, {latency:.2f}s, sections {sc:.0%}, components {cc:.0%}, forbidden {len(forbidden)}")
            if args.delay and not (case is cases[-1] and run == args.runs):
                time.sleep(args.delay)

    total = len(detailed)
    success_rows = [row for row in detailed if row["success"]]
    valid_rows = [row for row in detailed if row["schema_valid"]]
    latencies = [row["latency_seconds"] for row in detailed]
    valid_section_scores = [row["section_coverage"] for row in valid_rows]
    valid_component_scores = [row["component_coverage"] for row in valid_rows]
    summary = {
        "timestamp_utc": timestamp,
        "endpoint": args.url,
        "cases": len(cases), "runs_per_case": args.runs, "total_requests": total,
        "http_success_count": len(success_rows),
        "http_success_rate": round(len(success_rows) / total, 4),
        "schema_valid_count": len(valid_rows),
        "schema_validity_rate": round(len(valid_rows) / total, 4),
        "average_section_coverage_on_valid": round(statistics.mean(valid_section_scores), 4) if valid_section_scores else 0.0,
        "average_component_coverage_on_valid": round(statistics.mean(valid_component_scores), 4) if valid_component_scores else 0.0,
        "hallucination_free_count": sum(1 for row in valid_rows if row["hallucination_free"]),
        "hallucination_free_rate_on_valid": round(sum(1 for row in valid_rows if row["hallucination_free"]) / len(valid_rows), 4) if valid_rows else 0.0,
        "latency_seconds": {
            "minimum": min(latencies) if latencies else 0.0,
            "median": statistics.median(latencies) if latencies else 0.0,
            "average": statistics.mean(latencies) if latencies else 0.0,
            "p95": percentile(latencies, 0.95),
            "maximum": max(latencies) if latencies else 0.0,
        },
        "status_counts": {str(code): sum(1 for row in detailed if row["http_status"] == code) for code in sorted({row["http_status"] for row in detailed})},
    }

    json_path = args.output_dir / f"uc1_evaluation_{timestamp}.json"
    csv_path = args.output_dir / f"uc1_evaluation_{timestamp}.csv"
    json_path.write_text(json.dumps({"summary": summary, "results": detailed}, indent=2), encoding="utf-8")
    csv_fields = [
        "case_id", "case_name", "run", "http_status", "latency_seconds", "success", "schema_valid",
        "section_coverage", "component_coverage", "hallucination_free", "error",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows({field: row.get(field) for field in csv_fields} for row in detailed)

    print("\nSummary")
    print(json.dumps(summary, indent=2))
    print(f"\nDetailed JSON: {json_path}")
    print(f"CSV summary:   {csv_path}")

    # Reliability/schema are hard gates; coverage is reported for human review.
    return 0 if summary["http_success_rate"] >= 0.9 and summary["schema_validity_rate"] >= 0.9 else 1


if __name__ == "__main__":
    sys.exit(main())
