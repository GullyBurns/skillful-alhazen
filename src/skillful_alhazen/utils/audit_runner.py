"""
Generic data quality audit runner for Alhazen skills.

Reads a skill's quality-checks.yaml, executes TypeQL queries against TypeDB,
and produces structured JSON output with findings and summary statistics.

Usage:
    uv run python src/skillful_alhazen/utils/audit_runner.py run \
        --checks local_skills/jobhunt/quality-checks.yaml \
        [--file-issues] [--repo REPO_OVERRIDE]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone

import yaml


def _connect_typedb():
    """Connect to TypeDB using standard env vars. Returns (driver, database)."""
    from typedb.driver import Credentials, DriverOptions, TypeDB

    host = os.environ.get("TYPEDB_HOST", "localhost")
    port = os.environ.get("TYPEDB_PORT", "1729")
    db = os.environ.get("TYPEDB_DATABASE", "alhazen_notebook")
    user = os.environ.get("TYPEDB_USERNAME", "admin")
    pwd = os.environ.get("TYPEDB_PASSWORD", "password")

    driver = TypeDB.driver(
        f"{host}:{port}",
        Credentials(user, pwd),
        DriverOptions(is_tls_enabled=False),
    )
    return driver, db


def _run_query(driver, database, query: str) -> list[dict]:
    """Execute a TypeQL fetch query and return results as list of dicts."""
    from typedb.driver import TransactionType

    with driver.transaction(database, TransactionType.READ) as tx:
        results = list(tx.query(query.strip()).resolve())
    return results


def _extract_ids(results: list[dict]) -> list[str]:
    """Extract id values from fetch results. Handles nested dicts."""
    ids = []
    for row in results:
        val = row.get("id")
        if val is not None:
            ids.append(str(val))
    return ids


def run_checks(checks_path: str) -> dict:
    """Run all checks from a quality-checks.yaml file. Returns structured report."""
    with open(checks_path) as f:
        spec = yaml.safe_load(f)

    skill = spec.get("skill", "unknown")
    repo = spec.get("repo", "")
    checks = spec.get("checks", [])

    driver, database = _connect_typedb()
    findings = []

    for check in checks:
        name = check.get("name", "unnamed")
        print(f"  Running: {name} ...", file=sys.stderr, end=" ")

        finding = {
            "name": name,
            "category": check.get("category", ""),
            "severity": check.get("severity", "medium"),
            "description": check.get("description", ""),
            "affected_count": 0,
            "total_count": None,
            "affected_ids": [],
            "fix_type": check.get("fix_type", ""),
            "fix_description": check.get("fix_description", ""),
            "root_cause": check.get("root_cause"),
        }

        # Run find_violations query
        violations_query = check.get("find_violations")
        if not violations_query:
            print("SKIP (no query)", file=sys.stderr)
            continue

        try:
            violation_results = _run_query(driver, database, violations_query)
            finding["affected_count"] = len(violation_results)
            finding["affected_ids"] = _extract_ids(violation_results)
            # Also store full violation rows for richer output
            finding["violations"] = violation_results
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            finding["error"] = str(e)
            findings.append(finding)
            continue

        # Run count_total query if present
        count_query = check.get("count_total")
        if count_query:
            try:
                total_results = _run_query(driver, database, count_query)
                finding["total_count"] = len(total_results)
            except Exception as e:
                print(f"(count error: {e})", file=sys.stderr, end=" ")

        status = "PASS" if finding["affected_count"] == 0 else "FAIL"
        count_str = f"{finding['affected_count']}"
        if finding["total_count"] is not None:
            pct = (
                (finding["affected_count"] / finding["total_count"] * 100)
                if finding["total_count"] > 0
                else 0
            )
            count_str += f"/{finding['total_count']} ({pct:.0f}%)"
        print(f"{status} [{count_str}]", file=sys.stderr)

        findings.append(finding)

    driver.close()

    # Build summary
    sev_counts = Counter(f["severity"] for f in findings if f["affected_count"] > 0)
    cat_counts = Counter(f["category"] for f in findings if f["affected_count"] > 0)

    report = {
        "skill": skill,
        "repo": repo,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "checks_file": checks_path,
        "findings": findings,
        "summary": {
            "total_checks": len(findings),
            "checks_failing": sum(1 for f in findings if f["affected_count"] > 0),
            "checks_passing": sum(1 for f in findings if f["affected_count"] == 0),
            "checks_errored": sum(1 for f in findings if "error" in f),
            "by_severity": dict(sev_counts),
            "by_category": dict(cat_counts),
        },
    }

    # Human-readable summary to stderr
    s = report["summary"]
    print(f"\n{'=' * 50}", file=sys.stderr)
    print(
        f"Audit: {skill} | "
        f"{s['checks_passing']} pass, {s['checks_failing']} fail, "
        f"{s['checks_errored']} error",
        file=sys.stderr,
    )
    if sev_counts:
        parts = [f"{v} {k}" for k, v in sorted(sev_counts.items())]
        print(f"  Failing by severity: {', '.join(parts)}", file=sys.stderr)
    print(f"{'=' * 50}\n", file=sys.stderr)

    return report


def _build_issue_body(finding: dict) -> str:
    """Build a GitHub issue body from a finding."""
    lines = []
    lines.append("## Finding")
    lines.append(f"**Check:** {finding['name']}")
    lines.append(f"**Category:** {finding['category']}")
    lines.append(f"**Severity:** {finding['severity']}")
    lines.append(f"**Description:** {finding['description']}")
    lines.append(f"**Affected count:** {finding['affected_count']}")
    if finding["total_count"] is not None:
        pct = (
            (finding["affected_count"] / finding["total_count"] * 100)
            if finding["total_count"] > 0
            else 0
        )
        lines.append(f"**Total count:** {finding['total_count']} ({pct:.0f}% affected)")
    if finding["affected_ids"]:
        ids_display = finding["affected_ids"][:20]
        lines.append(f"\n**Sample affected IDs:** {', '.join(ids_display)}")
        if len(finding["affected_ids"]) > 20:
            lines.append(f"  ... and {len(finding['affected_ids']) - 20} more")

    lines.append("")
    lines.append("## Data Fix")
    lines.append(f"**Type:** {finding['fix_type']}")
    lines.append(f"**Description:** {finding['fix_description']}")

    rc = finding.get("root_cause")
    if rc:
        lines.append("")
        lines.append("## Root Cause")
        if rc.get("component"):
            lines.append(f"**Component:** {rc['component']}")
        if rc.get("file"):
            lines.append(f"**File:** {rc['file']}")
        if rc.get("function"):
            lines.append(f"**Function:** {rc['function']}")
        if rc.get("description"):
            lines.append(f"**Description:** {rc['description']}")

        lines.append("")
        lines.append("## Prevention Fix")
        lines.append(rc.get("prevention", "N/A"))

        lines.append("")
        lines.append("## Verification Test")
        lines.append(rc.get("test", "N/A"))

    return "\n".join(lines)


def file_issues(report: dict, repo_override: str | None = None):
    """Create GitHub issues for each failing check."""
    repo = repo_override or report.get("repo", "")
    if not repo:
        print("ERROR: No repo specified (use --repo or set in YAML)", file=sys.stderr)
        return

    has_gh = shutil.which("gh") is not None
    if not has_gh:
        print(
            "WARNING: gh CLI not found. Printing issue bodies to stdout instead.",
            file=sys.stderr,
        )

    for finding in report["findings"]:
        if finding["affected_count"] == 0:
            continue
        if "error" in finding:
            continue

        title = f"Audit [{finding['severity']}][{finding['category']}]: {finding['name']} - {finding['description'][:80]}"
        body = _build_issue_body(finding)

        if not has_gh:
            print(json.dumps({"title": title, "body": body, "repo": repo}))
            continue

        try:
            result = subprocess.run(
                [
                    "gh", "issue", "create",
                    "--repo", repo,
                    "--title", title,
                    "--body", body,
                    "--label", "audit:open",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                print(f"  Created: {result.stdout.strip()}", file=sys.stderr)
            else:
                print(
                    f"  Failed to create issue for {finding['name']}: {result.stderr.strip()}",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"  Error creating issue for {finding['name']}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Generic data quality audit runner for Alhazen skills"
    )
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run quality checks from a YAML file")
    run_parser.add_argument(
        "--checks", required=True, help="Path to quality-checks.yaml"
    )
    run_parser.add_argument(
        "--file-issues",
        action="store_true",
        help="Create GitHub issues for failing checks",
    )
    run_parser.add_argument(
        "--repo", default=None, help="Override the repo from the YAML file"
    )

    args = parser.parse_args()

    if args.command == "run":
        report = run_checks(args.checks)
        # Output JSON to stdout
        json.dump(report, sys.stdout, indent=2)
        print(file=sys.stdout)

        if args.file_issues:
            file_issues(report, repo_override=args.repo)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
