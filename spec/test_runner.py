#!/usr/bin/env python3
"""Run Knitting Compiler tests against generated expected outputs."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_argv(compiler: list[str], meta: dict[str, Any], suite_root: Path) -> list[str]:
    invocation = meta.get("invocation") or {"argv": ["compile", "{input}"]}
    input_file = meta.get("input_file")
    input_path = None
    if meta.get("_input_path"):
        input_path = Path(meta["_input_path"])
    if input_file:
        input_path = input_path or (suite_root / meta["suite"] / meta["category"] / input_file)

    rendered = []
    for part in invocation.get("argv", []):
        if part == "{input}":
            if input_path is None:
                raise AssertionError(f"{meta['test_id']} uses {{input}} but has no input_file")
            rendered.append(str(input_path))
        else:
            rendered.append(part)
    return compiler + rendered


def normalize_stdout(stdout: str, expected_exit_code: int) -> tuple[dict[str, Any] | None, str | None]:
    if expected_exit_code == 2:
        if stdout != "":
            return None, "expected empty stdout for usage error"
        return None, None

    try:
        decoder = json.JSONDecoder()
        data, end = decoder.raw_decode(stdout)
    except json.JSONDecodeError as exc:
        return None, f"stdout is not exactly one JSON document: {exc}"

    if stdout[end:].strip():
        return None, "stdout contains non-JSON text after the JSON document"
    if not isinstance(data, dict):
        return None, "stdout JSON is not an object"

    if expected_exit_code == 1:
        errors = data.get("errors")
        if not isinstance(errors, list) or not errors:
            return None, "invalid output must contain at least one error"
        normalized_errors = []
        for idx, err in enumerate(errors):
            if not isinstance(err, dict):
                return None, f"error {idx} is not an object"
            message = err.get("message")
            if not isinstance(message, str) or not message.strip():
                return None, f"error {idx} message is not a non-empty string"
            normalized_errors.append({
                "type": err.get("type"),
                "code": err.get("code"),
                "line": err.get("line"),
                "row": err.get("row"),
                "message_non_empty": True,
            })
        data = dict(data)
        data["errors"] = normalized_errors

    return data, None


def smoke_check_stdout(stdout: str, expected_exit_code: int) -> str | None:
    normalized, error = normalize_stdout(stdout, expected_exit_code)
    if error:
        return error
    if expected_exit_code == 2:
        return None
    assert normalized is not None
    valid = normalized.get("valid")
    if expected_exit_code == 0 and valid is not True:
        return "expected JSON field valid=true for exit 0"
    if expected_exit_code == 1 and valid is not False:
        return "expected JSON field valid=false for exit 1"
    return None


def first_diff(expected: Any, actual: Any, path: str = "$") -> str | None:
    if type(expected) is not type(actual):
        return f"{path}: expected {type(expected).__name__}, got {type(actual).__name__}"
    if isinstance(expected, dict):
        if set(expected) != set(actual):
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            return f"{path}: key mismatch missing={missing} extra={extra}"
        for key in expected:
            diff = first_diff(expected[key], actual[key], f"{path}.{key}")
            if diff:
                return diff
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: expected list length {len(expected)}, got {len(actual)}"
        for idx, (exp_item, act_item) in enumerate(zip(expected, actual)):
            diff = first_diff(exp_item, act_item, f"{path}[{idx}]")
            if diff:
                return diff
        return None
    if expected != actual:
        return f"{path}: expected {expected!r}, got {actual!r}"
    return None


def expected_path(expected_root: Path, meta: dict[str, Any]) -> Path:
    return expected_root / meta["suite"] / meta["category"] / f"{meta['test_id']}.expected.json"


def is_stale_expected(exp_path: Path, meta_path: Path, meta: dict[str, Any], suite_root: Path) -> bool:
    expected_mtime = exp_path.stat().st_mtime
    if meta_path.stat().st_mtime > expected_mtime:
        return True
    input_file = meta.get("input_file")
    if input_file:
        input_path = Path(meta.get("_input_path") or (suite_root / meta["suite"] / meta["category"] / input_file))
        if input_path.stat().st_mtime > expected_mtime:
            return True
    return False


def discover_public_tests(tests_dir: Path) -> dict[str, Any]:
    tests = []
    suites = {"public": {}}
    for meta_path in sorted(tests_dir.glob("*/*.json")):
        meta = load_json(meta_path)
        if meta.get("suite") != "public":
            continue
        category = meta["category"]
        suites["public"].setdefault(category, {"count": 0})
        suites["public"][category]["count"] += 1
        input_file = meta.get("input_file")
        tests.append({
            "test_id": meta["test_id"],
            "suite": "public",
            "category": category,
            "metadata_file": str(meta_path),
            "_metadata_path": str(meta_path),
            "input_file": str(meta_path.parent / input_file) if input_file else None,
            "expected_exit_code": meta["expected_exit_code"],
        })
    return {
        "schema_version": 1,
        "suites": suites,
        "tests": tests,
    }


def bar(passed: int, total: int, width: int = 24) -> str:
    if total == 0:
        return "." * width
    filled = round(width * passed / total)
    return "#" * filled + "." * (width - filled)


def print_scoreboard(results: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = total - passed
    percent = (passed / total * 100) if total else 0.0
    print()
    print("Knitting Compiler Scoreboard")
    print(f"Overall [{bar(passed, total, 32)}] {passed}/{total} passed ({percent:.1f}%)")
    print(f"Failed: {failed}")
    print()

    by_suite_category: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        by_suite_category[(result["suite"], result["category"])].append(result)

    for suite in ("public", "hidden"):
        suite_results = [r for r in results if r["suite"] == suite]
        if not suite_results:
            continue
        suite_passed = sum(1 for r in suite_results if r["status"] == "pass")
        print(f"{suite}")
        print(f"  [{bar(suite_passed, len(suite_results))}] {suite_passed}/{len(suite_results)}")
        for category in manifest["suites"][suite]:
            rows = by_suite_category.get((suite, category), [])
            if not rows:
                continue
            cat_passed = sum(1 for r in rows if r["status"] == "pass")
            print(f"  {category:<36} [{bar(cat_passed, len(rows), 18)}] {cat_passed:>3}/{len(rows):<3}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Knitting Compiler tests and show a level scoreboard.")
    parser.add_argument("--compiler", required=True, help="Compiler command, e.g. 'python3 knit.py'.")
    release_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--manifest", default=None, help="Optional manifest path. Not needed for the release package.")
    parser.add_argument("--tests-dir", default=str(release_root / "public_tests"))
    parser.add_argument("--expected-dir", default=str(release_root / "expected_outputs"))
    parser.add_argument("--suite", choices=["public", "all"], default="public")
    parser.add_argument("--category", default=None, help="Optional category/level to run.")
    parser.add_argument(
        "--mode",
        choices=["full", "exit-only"],
        default="full",
        help="full compares generated expected JSON; exit-only checks exit codes and stdout discipline only.",
    )
    parser.add_argument("--failures", type=int, default=20, help="Number of failure details to print.")
    parser.add_argument("--json-report", default=None, help="Optional path to write machine-readable results.")
    parser.add_argument("--cwd", default=None, help="Optional working directory for compiler invocations.")
    args = parser.parse_args()

    if args.manifest:
        manifest_path = Path(args.manifest).resolve()
        suite_root = manifest_path.parent
        manifest = load_json(manifest_path)
    else:
        tests_dir = Path(args.tests_dir).resolve()
        suite_root = tests_dir.parent
        manifest = discover_public_tests(tests_dir)
    expected_root = Path(args.expected_dir).resolve()
    compiler = shlex.split(args.compiler)

    selected = []
    for entry in manifest["tests"]:
        if args.suite != "all" and entry["suite"] != args.suite:
            continue
        if args.category and entry["category"] != args.category:
            continue
        selected.append(entry)

    if not selected:
        print("No tests matched the requested filters.", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    for entry in selected:
        meta_path = Path(entry.get("_metadata_path") or (suite_root / entry["metadata_file"]))
        meta = load_json(meta_path)
        if entry.get("input_file"):
            meta["_input_path"] = entry["input_file"]
        cmd = build_argv(compiler, meta, suite_root)
        proc = subprocess.run(cmd, cwd=args.cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        expected_exit_code = int(meta["expected_exit_code"])

        reason = None
        if proc.returncode != expected_exit_code:
            reason = f"exit code expected {expected_exit_code}, got {proc.returncode}"
        elif args.mode == "exit-only":
            reason = smoke_check_stdout(proc.stdout, expected_exit_code)
        else:
            exp_path = expected_path(expected_root, meta)
            if not exp_path.exists():
                reason = f"missing expected output: {exp_path}"
            elif is_stale_expected(exp_path, meta_path, meta, suite_root):
                reason = f"stale expected output, regenerate: {exp_path}"
            else:
                expected = load_json(exp_path)
                expected_exit_code = int(expected["expected_exit_code"])
                if proc.returncode != expected_exit_code:
                    reason = f"exit code expected {expected_exit_code}, got {proc.returncode}"
                    actual_stdout = None
                else:
                    actual_stdout, error = normalize_stdout(proc.stdout, expected_exit_code)
                    if error:
                        reason = error
                    elif expected_exit_code == 2:
                        reason = None
                    else:
                        reason = first_diff(expected["stdout"], actual_stdout)
                results.append({
                    "test_id": meta["test_id"],
                    "suite": meta["suite"],
                    "category": meta["category"],
                    "status": "pass" if reason is None else "fail",
                    "reason": reason,
                    "stderr": proc.stderr[-500:] if proc.stderr else "",
                })
                continue

        if args.mode == "full":
            # Only reached when exit-code comparison failed before expected output loading.
            pass
        else:
            pass

        results.append({
            "test_id": meta["test_id"],
            "suite": meta["suite"],
            "category": meta["category"],
            "status": "pass" if reason is None else "fail",
            "reason": reason,
            "stderr": proc.stderr[-500:] if proc.stderr else "",
        })

    print_scoreboard(results, manifest)

    failures = [r for r in results if r["status"] != "pass"]
    if failures and args.failures:
        print("Failures")
        for result in failures[:args.failures]:
            print(f"- {result['test_id']}: {result['reason']}")
            if result.get("stderr"):
                print(f"  stderr tail: {result['stderr']!r}")
        if len(failures) > args.failures:
            print(f"... {len(failures) - args.failures} more failures not shown")

    if args.json_report:
        report_path = Path(args.json_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps({"results": results}, indent=2) + "\n", encoding="utf-8")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
