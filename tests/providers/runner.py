"""Providers E2E runner: verifies provider endpoints against a live backend.

Follows the same declarative YAML methodology as ``tests.e2e.runner`` (real
endpoints, no mocks), reusing its step helpers. Only ``request`` steps are
used by the provider scenarios; ``chat`` steps are supported the same way
as in the e2e runner.

Scenario YAML schema::

    scenario: unique-name
    description: What this scenario verifies.
    cleanup: true
    steps:
      - action: request                # direct API call
        method: GET                    # GET (default) | POST | PUT | DELETE
        path: /api/config/providers
        body: {}                       # optional JSON body
        expect:
          http_status: 200
          json_status: success         # contract ``status`` field
          json_path_exists: [providers]

Run with ``python -m tests.providers.runner``. A JSON report is written under
``tests/providers/reports/``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from tests.e2e.runner import (
    DEFAULT_BASE_URL,
    evaluate_chat_expectations,
    load_scenarios,
    run_chat_step,
    run_request_step,
)

SESSION_PREFIX = "providers-"


def run_scenario(base_url: str, scenario: dict[str, Any]) -> dict[str, Any]:
    """Run one provider scenario end to end.

    Args:
        base_url: Backend base URL.
        scenario: Parsed scenario dict.

    Returns:
        Result dict: ``{"scenario", "file", "passed", "failures", "steps"}``.
    """
    sessions: dict[str, str] = {}
    variables: dict[str, str] = {}
    step_results: list[dict[str, Any]] = []
    all_failures: list[str] = []

    for index, step in enumerate(scenario.get("steps", []) or [], start=1):
        action = step.get("action")
        entry: dict[str, Any] = {"step": index, "action": action, "failures": []}

        if action == "chat":
            obs = run_chat_step(base_url, step, sessions)
            entry["failures"] = evaluate_chat_expectations(step.get("expect", {}) or {}, obs)
        elif action == "request":
            _, failures = run_request_step(base_url, step, variables)
            entry["failures"] = failures
        else:
            entry["failures"] = [f"unknown action '{action}'"]

        step_results.append(entry)
        all_failures.extend(entry["failures"])

    # Cleanup: delete sessions created by this scenario.
    if scenario.get("cleanup", True):
        for session_id in sessions.values():
            try:
                requests.delete(f"{base_url}/api/sessions/{session_id}", timeout=30)
            except requests.RequestException:
                pass  # cleanup is best-effort; never affects the verdict

    return {
        "scenario": scenario["scenario"],
        "file": scenario.get("_file", ""),
        "passed": not all_failures,
        "failures": all_failures,
        "steps": step_results,
    }


def main() -> int:
    """Parse arguments, run every scenario and print the report.

    Returns:
        Process exit code: 0 when all scenarios pass, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description="synapseForge providers E2E runner")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend base URL")
    parser.add_argument("--only", default=None, help="Run a single scenario by name")
    args = parser.parse_args()

    scenarios_dir = Path(__file__).parent / "scenarios"
    scenarios = load_scenarios(scenarios_dir)
    if args.only:
        scenarios = [s for s in scenarios if args.only in s["scenario"]]
        if not scenarios:
            print(f"No scenario named '{args.only}'.")
            return 1

    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(exist_ok=True)

    results = []
    for scenario in scenarios:
        print(f"\n=== {scenario['scenario']} ({scenario.get('_file', '')}) ===")
        started = time.time()
        result = run_scenario(args.base_url, scenario)
        result["duration_s"] = round(time.time() - started, 1)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{status}] {result['scenario']} ({result['duration_s']}s)")
        for failure in result["failures"]:
            print(f"  - {failure}")

    passed = sum(1 for r in results if r["passed"])
    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "base_url": args.base_url,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    report_path = reports_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nTotal: {passed}/{len(results)} escenario(s) en verde.")
    print(f"Reporte: {report_path}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
